from decimal import Decimal
from django.db import transaction
from django.test import TestCase
from django.contrib.auth.models import User
from affiliates.models import Affiliate, Referral, AffiliateCommission, AffiliatePayout, generate_referral_code
from marketplace.models import Order


class AffiliateModelTests(TestCase):
    def test_generate_referral_code_length(self):
        code = generate_referral_code()
        self.assertEqual(len(code), 8)

    def test_generate_referral_code_unique(self):
        codes = {generate_referral_code() for _ in range(100)}
        self.assertGreater(len(codes), 90)

    def test_affiliate_creation(self):
        user = User.objects.create_user('testuser', 'test@example.com', 'pass123')
        affiliate = Affiliate.objects.create(user=user)
        self.assertTrue(affiliate.is_active)
        self.assertEqual(affiliate.total_referrals, 0)
        self.assertEqual(affiliate.total_earnings, Decimal('0.00'))
        self.assertEqual(len(affiliate.referral_code), 8)

    def test_referral_one_per_user(self):
        aff_user = User.objects.create_user('affiliate', 'aff@example.com', 'pass123')
        affiliate = Affiliate.objects.create(user=aff_user)
        referred = User.objects.create_user('referred', 'ref@example.com', 'pass123')
        Referral.objects.create(affiliate=affiliate, referred_user=referred)

        aff_user2 = User.objects.create_user('affiliate2', 'aff2@example.com', 'pass123')
        affiliate2 = Affiliate.objects.create(user=aff_user2)
        with self.assertRaises(Exception):
            Referral.objects.create(affiliate=affiliate2, referred_user=referred)

    def test_get_referral_url(self):
        user = User.objects.create_user('testuser', 'test@example.com', 'pass123')
        affiliate = Affiliate.objects.create(user=user)
        self.assertIn(affiliate.referral_code, affiliate.get_referral_url())


class AffiliateCommissionTests(TestCase):
    def setUp(self):
        self.aff_user = User.objects.create_user('affiliate', 'aff@example.com', 'pass123')
        self.affiliate = Affiliate.objects.create(user=self.aff_user, paypal_email='aff@paypal.com')

        self.buyer = User.objects.create_user('buyer', 'buyer@example.com', 'pass123')
        self.referral = Referral.objects.create(affiliate=self.affiliate, referred_user=self.buyer)

        self.seller = User.objects.create_user('seller', 'seller@example.com', 'pass123')

    def _create_order(self, item_price=Decimal('100.00')):
        return Order.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            item_price=item_price,
            shipping_price=Decimal('5.00'),
            amount=item_price + Decimal('5.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=item_price - Decimal('10.00') + Decimal('5.00'),
            shipping_address='123 Test St',
            status='paid',
        )

    def test_commission_creation(self):
        order = self._create_order()
        commission = AffiliateCommission.objects.create(
            affiliate=self.affiliate,
            order=order,
            referral=self.referral,
            order_item_price=order.item_price,
            commission_rate=Affiliate.COMMISSION_RATE,
            commission_amount=order.item_price * Affiliate.COMMISSION_RATE,
        )
        self.assertEqual(commission.commission_amount, Decimal('2.00'))
        self.assertEqual(commission.status, 'pending')

    def test_one_commission_per_order_per_type(self):
        order = self._create_order()
        AffiliateCommission.objects.create(
            affiliate=self.affiliate,
            order=order,
            referral=self.referral,
            commission_type='buyer',
            order_item_price=order.item_price,
            commission_rate=Affiliate.COMMISSION_RATE,
            commission_amount=Decimal('2.00'),
        )
        # Same type should fail
        with self.assertRaises(Exception):
            with transaction.atomic():
                AffiliateCommission.objects.create(
                    affiliate=self.affiliate,
                    order=order,
                    referral=self.referral,
                    commission_type='buyer',
                    order_item_price=order.item_price,
                    commission_rate=Affiliate.COMMISSION_RATE,
                    commission_amount=Decimal('2.00'),
                )
        # Different type should succeed
        AffiliateCommission.objects.create(
            affiliate=self.affiliate,
            order=order,
            referral=self.referral,
            commission_type='seller',
            order_item_price=order.item_price,
            commission_rate=Affiliate.COMMISSION_RATE,
            commission_amount=Decimal('2.00'),
        )
