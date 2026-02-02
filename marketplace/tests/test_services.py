"""
Tests for marketplace services, focusing on Stripe Connect.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User
from marketplace.services.connect_service import ConnectService


class ConnectServiceTests(TestCase):
    """Tests for ConnectService."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    @patch('marketplace.services.connect_service.stripe.Account.create')
    def test_create_express_account_success(self, mock_create):
        """Should create Stripe account and save to profile."""
        mock_account = MagicMock()
        mock_account.id = 'acct_new123'
        mock_create.return_value = mock_account

        result = ConnectService.create_express_account(self.user)

        self.assertEqual(result.id, 'acct_new123')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.stripe_account_id, 'acct_new123')
        self.assertEqual(self.user.profile.stripe_account_type, 'express')
        
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs['type'], 'express')
        self.assertEqual(call_kwargs['email'], 'test@example.com')

    @patch('marketplace.services.connect_service.stripe.Account.create')
    def test_create_express_account_stripe_error(self, mock_create):
        """Should raise and log on Stripe errors."""
        import stripe
        mock_create.side_effect = stripe.error.StripeError('API error')

        with self.assertRaises(stripe.error.StripeError):
            ConnectService.create_express_account(self.user)

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_update_account_status_success(self, mock_retrieve):
        """Should update profile with account status."""
        self.user.profile.stripe_account_id = 'acct_test123'
        self.user.profile.save()

        mock_account = MagicMock()
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = True
        mock_account.requirements.currently_due = []
        mock_retrieve.return_value = mock_account

        result = ConnectService.update_account_status(self.user)

        self.assertIsNotNone(result)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.stripe_charges_enabled)
        self.assertTrue(self.user.profile.stripe_payouts_enabled)
        self.assertTrue(self.user.profile.stripe_account_complete)

    def test_update_account_status_no_account(self):
        """Should return None if user has no Stripe account."""
        result = ConnectService.update_account_status(self.user)
        self.assertIsNone(result)

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_update_account_status_clears_invalid_account(self, mock_retrieve):
        """Should clear account ID when Stripe returns PermissionError."""
        import stripe
        self.user.profile.stripe_account_id = 'acct_invalid123'
        self.user.profile.save()

        mock_retrieve.side_effect = stripe.error.PermissionError('No access')

        result = ConnectService.update_account_status(self.user)

        self.assertIsNone(result)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.stripe_account_id, '')
        self.assertFalse(self.user.profile.stripe_account_complete)

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_update_account_status_clears_on_invalid_request(self, mock_retrieve):
        """Should clear account ID on InvalidRequestError."""
        import stripe
        self.user.profile.stripe_account_id = 'acct_deleted123'
        self.user.profile.save()

        mock_retrieve.side_effect = stripe.error.InvalidRequestError(
            'No such account', 'account'
        )

        result = ConnectService.update_account_status(self.user)

        self.assertIsNone(result)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.stripe_account_id, '')

    @patch('marketplace.services.connect_service.stripe.AccountLink.create')
    def test_create_account_link(self, mock_create):
        """Should create account link with correct params."""
        mock_link = MagicMock()
        mock_link.url = 'https://connect.stripe.com/setup/...'
        mock_create.return_value = mock_link

        result = ConnectService.create_account_link(
            'acct_test123',
            return_url='https://example.com/return',
            refresh_url='https://example.com/refresh'
        )

        self.assertEqual(result.url, mock_link.url)
        mock_create.assert_called_once_with(
            account='acct_test123',
            refresh_url='https://example.com/refresh',
            return_url='https://example.com/return',
            type='account_onboarding',
        )

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_retrieve_account(self, mock_retrieve):
        """Should retrieve account from Stripe."""
        mock_account = MagicMock()
        mock_account.id = 'acct_test123'
        mock_retrieve.return_value = mock_account

        result = ConnectService.retrieve_account('acct_test123')

        self.assertEqual(result.id, 'acct_test123')
        mock_retrieve.assert_called_once_with('acct_test123')


class ConnectServiceTransferTests(TestCase):
    """Tests for ConnectService transfer functionality."""

    def setUp(self):
        self.seller = User.objects.create_user(
            username='seller',
            email='seller@example.com',
            password='testpass123'
        )
        self.seller.profile.stripe_account_id = 'acct_seller123'
        self.seller.profile.save()

    @patch('marketplace.services.connect_service.stripe.Transfer.create')
    def test_create_transfer_success(self, mock_create):
        """Should create transfer to seller account."""
        from decimal import Decimal
        
        # Create a mock order
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.seller = self.seller
        mock_order.seller_payout = Decimal('95.00')
        mock_order.save = MagicMock()

        mock_transfer = MagicMock()
        mock_transfer.id = 'tr_test123'
        mock_create.return_value = mock_transfer

        result = ConnectService.create_transfer(mock_order)

        self.assertEqual(result.id, 'tr_test123')
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        self.assertEqual(call_kwargs['amount'], 9500)  # Cents
        self.assertEqual(call_kwargs['destination'], 'acct_seller123')
