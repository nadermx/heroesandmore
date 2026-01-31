import stripe
import logging
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class ConnectService:
    """Stripe Connect operations for sellers"""

    @staticmethod
    def create_express_account(user):
        """Create Express connected account for seller"""
        profile = user.profile

        account = stripe.Account.create(
            type='express',
            country='US',
            email=user.email,
            capabilities={
                'card_payments': {'requested': True},
                'transfers': {'requested': True},
            },
            business_type='individual',
            metadata={'user_id': user.id}
        )

        profile.stripe_account_id = account.id
        profile.stripe_account_type = 'express'
        profile.save(update_fields=['stripe_account_id', 'stripe_account_type'])

        return account

    @staticmethod
    def create_account_link(account_id, return_url, refresh_url):
        """Create onboarding link for Express account"""
        return stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type='account_onboarding',
        )

    @staticmethod
    def create_login_link(account_id):
        """Create login link to Stripe Express dashboard"""
        return stripe.Account.create_login_link(account_id)

    @staticmethod
    def retrieve_account(account_id):
        """Get account status and details"""
        return stripe.Account.retrieve(account_id)

    @staticmethod
    def update_account_status(user):
        """Sync account status from Stripe"""
        profile = user.profile
        if not profile.stripe_account_id:
            return None

        try:
            account = stripe.Account.retrieve(profile.stripe_account_id)

            profile.stripe_charges_enabled = account.charges_enabled
            profile.stripe_payouts_enabled = account.payouts_enabled
            profile.stripe_account_complete = (
                account.charges_enabled and
                account.payouts_enabled and
                not account.requirements.currently_due
            )
            profile.save(update_fields=[
                'stripe_charges_enabled',
                'stripe_payouts_enabled',
                'stripe_account_complete'
            ])

            return account
        except stripe.error.InvalidRequestError as e:
            logger.error(f"Error retrieving Stripe account {profile.stripe_account_id}: {e}")
            return None

    @staticmethod
    def create_transfer(order):
        """Create transfer to seller (for non-destination charge flows)"""
        seller_profile = order.seller.profile
        if not seller_profile.stripe_account_id:
            raise ValueError("Seller has no connected account")

        # Calculate seller payout (item price minus platform fee)
        payout_amount = order.seller_payout

        transfer = stripe.Transfer.create(
            amount=int(payout_amount * 100),
            currency='usd',
            destination=seller_profile.stripe_account_id,
            transfer_group=f"order_{order.id}",
            metadata={'order_id': order.id}
        )

        order.stripe_transfer_id = transfer.id
        order.stripe_transfer_status = 'pending'
        order.save(update_fields=['stripe_transfer_id', 'stripe_transfer_status'])

        return transfer

    @staticmethod
    def get_balance(account_id=None):
        """Get balance for platform or connected account"""
        if account_id:
            return stripe.Balance.retrieve(stripe_account=account_id)
        return stripe.Balance.retrieve()

    @staticmethod
    def list_transfers(account_id=None, limit=100):
        """List transfers to a connected account"""
        params = {'limit': limit}
        if account_id:
            params['destination'] = account_id
        return stripe.Transfer.list(**params)

    @staticmethod
    def list_payouts(account_id, limit=20):
        """List payouts for a connected account"""
        return stripe.Payout.list(
            limit=limit,
            stripe_account=account_id
        )

    @staticmethod
    def get_account_balance_transactions(account_id, limit=20):
        """Get balance transactions for a connected account"""
        return stripe.BalanceTransaction.list(
            limit=limit,
            stripe_account=account_id
        )
