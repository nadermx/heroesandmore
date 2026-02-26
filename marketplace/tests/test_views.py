"""
Tests for marketplace views, focusing on seller setup and Stripe Connect.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class SellerSetupViewTests(TestCase):
    """Tests for seller_setup view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.url = reverse('marketplace:seller_setup')

    def test_seller_setup_requires_login(self):
        """Unauthenticated users should be redirected to signup."""
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/auth/signup/', response.url)

    def test_seller_setup_shows_country_picker(self):
        """GET with no Stripe account should show country selection."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketplace/seller_setup_country.html')

    @patch('marketplace.services.connect_service.stripe.Account.create')
    def test_seller_setup_creates_account_on_post(self, mock_create):
        """Should create Stripe account when country is submitted via POST."""
        mock_account = MagicMock()
        mock_account.id = 'acct_test123'
        mock_create.return_value = mock_account

        response = self.client.post(self.url, {'country': 'US'})

        mock_create.assert_called_once()
        # Should render embedded onboarding
        self.assertIn(response.status_code, [200, 302])

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_seller_setup_redirects_if_complete(self, mock_retrieve):
        """Should redirect to dashboard if account is already complete."""
        self.user.profile.stripe_account_id = 'acct_test123'
        self.user.profile.stripe_account_complete = True
        self.user.profile.save()

        mock_account = MagicMock()
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = True
        mock_account.requirements.currently_due = []
        mock_retrieve.return_value = mock_account

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/seller/', response.url)

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_seller_setup_renders_embedded_onboarding(self, mock_retrieve):
        """Should render embedded onboarding template for incomplete accounts."""
        self.user.profile.stripe_account_id = 'acct_test123'
        self.user.profile.stripe_account_complete = False
        self.user.profile.save()

        mock_account = MagicMock()
        mock_account.charges_enabled = False
        mock_account.payouts_enabled = False
        mock_account.requirements.currently_due = ['business_profile']
        mock_retrieve.return_value = mock_account

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'marketplace/seller_setup.html')
        self.assertIn('stripe_public_key', response.context)


class SellerSetupSessionViewTests(TestCase):
    """Tests for seller_setup_session API endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.url = reverse('marketplace:seller_setup_session')

    def test_session_requires_login(self):
        """Unauthenticated users should get 302."""
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)

    def test_session_requires_stripe_account(self):
        """Should return 400 if user has no Stripe account."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    @patch('stripe.AccountSession.create')
    def test_session_returns_client_secret(self, mock_create):
        """Should return client_secret for valid request."""
        self.user.profile.stripe_account_id = 'acct_test123'
        self.user.profile.save()

        mock_create.return_value = MagicMock(client_secret='seti_secret_123')

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('client_secret', response.json())
        mock_create.assert_called_once()

    @patch('stripe.AccountSession.create')
    def test_session_handles_stripe_error(self, mock_create):
        """Should return 500 on Stripe API errors."""
        self.user.profile.stripe_account_id = 'acct_test123'
        self.user.profile.save()

        import stripe
        mock_create.side_effect = stripe.error.StripeError('API error')

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 500)
        self.assertIn('error', response.json())


class SellerSetupReturnViewTests(TestCase):
    """Tests for seller_setup_return view."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(username='testuser', password='testpass123')
        self.url = reverse('marketplace:seller_setup_return')

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_return_updates_account_status(self, mock_retrieve):
        """Should update account status when returning from Stripe."""
        self.user.profile.stripe_account_id = 'acct_test123'
        self.user.profile.save()

        mock_account = MagicMock()
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = True
        mock_account.requirements.currently_due = []
        mock_retrieve.return_value = mock_account

        response = self.client.get(self.url)

        mock_retrieve.assert_called_once()
        self.assertEqual(response.status_code, 302)

    @patch('marketplace.services.connect_service.stripe.Account.retrieve')
    def test_return_shows_success_if_complete(self, mock_retrieve):
        """Should show success message if account is now complete."""
        self.user.profile.stripe_account_id = 'acct_test123'
        self.user.profile.stripe_account_complete = True
        self.user.profile.save()

        mock_account = MagicMock()
        mock_account.charges_enabled = True
        mock_account.payouts_enabled = True
        mock_account.requirements.currently_due = []
        mock_retrieve.return_value = mock_account

        response = self.client.get(self.url, follow=True)

        messages = list(response.context['messages'])
        self.assertTrue(any('complete' in str(m).lower() for m in messages))
