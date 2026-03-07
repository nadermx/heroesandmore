from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from affiliates.models import Affiliate, Referral, AffiliateCommission
from affiliates.tasks import create_affiliate_commission, reverse_affiliate_commission
from marketplace.models import Order


class CommissionTaskTests(TestCase):
    def setUp(self):
        self.aff_user = User.objects.create_user('affiliate', 'aff@example.com', 'pass123')
        self.affiliate = Affiliate.objects.create(user=self.aff_user, paypal_email='aff@paypal.com')
        self.buyer = User.objects.create_user('buyer', 'buyer@example.com', 'pass123')
        self.referral = Referral.objects.create(affiliate=self.affiliate, referred_user=self.buyer)
        self.seller = User.objects.create_user('seller', 'seller@example.com', 'pass123')

    def _create_order(self, buyer=None, seller=None, item_price=Decimal('100.00')):
        return Order.objects.create(
            buyer=buyer or self.buyer,
            seller=seller or self.seller,
            item_price=item_price,
            shipping_price=Decimal('5.00'),
            amount=item_price + Decimal('5.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=item_price - Decimal('10.00') + Decimal('5.00'),
            shipping_address='123 Test St',
            status='paid',
        )

    def test_create_commission(self):
        order = self._create_order()
        create_affiliate_commission(order.id)

        commission = AffiliateCommission.objects.get(order=order)
        self.assertEqual(commission.commission_amount, Decimal('2.00'))
        self.assertEqual(commission.status, 'pending')

        self.affiliate.refresh_from_db()
        self.assertEqual(self.affiliate.pending_balance, Decimal('2.00'))
        self.assertEqual(self.affiliate.total_earnings, Decimal('2.00'))

    def test_no_commission_for_guest(self):
        order = Order.objects.create(
            buyer=None,
            seller=self.seller,
            item_price=Decimal('100.00'),
            shipping_price=Decimal('5.00'),
            amount=Decimal('105.00'),
            platform_fee=Decimal('10.00'),
            seller_payout=Decimal('95.00'),
            shipping_address='123 Test St',
            guest_email='guest@example.com',
            guest_name='Guest',
            status='paid',
        )
        create_affiliate_commission(order.id)
        self.assertFalse(AffiliateCommission.objects.filter(order=order).exists())

    def test_no_commission_if_no_referral(self):
        unreferred = User.objects.create_user('unreferred', 'unref@example.com', 'pass123')
        order = self._create_order(buyer=unreferred)
        create_affiliate_commission(order.id)
        self.assertFalse(AffiliateCommission.objects.filter(order=order).exists())

    def test_no_self_dealing(self):
        order = self._create_order(seller=self.aff_user)
        create_affiliate_commission(order.id)
        self.assertFalse(AffiliateCommission.objects.filter(order=order).exists())

    def test_no_duplicate_commission(self):
        order = self._create_order()
        create_affiliate_commission(order.id)
        create_affiliate_commission(order.id)
        self.assertEqual(AffiliateCommission.objects.filter(order=order).count(), 1)

    def test_inactive_affiliate_no_commission(self):
        self.affiliate.is_active = False
        self.affiliate.save()
        order = self._create_order()
        create_affiliate_commission(order.id)
        self.assertFalse(AffiliateCommission.objects.filter(order=order).exists())

    def test_reverse_commission(self):
        order = self._create_order()
        create_affiliate_commission(order.id)

        reverse_affiliate_commission(order.id)

        commission = AffiliateCommission.objects.get(order=order)
        self.assertEqual(commission.status, 'reversed')

        self.affiliate.refresh_from_db()
        self.assertEqual(self.affiliate.pending_balance, Decimal('0.00'))
        self.assertEqual(self.affiliate.total_earnings, Decimal('0.00'))

    def test_reverse_nonexistent_commission(self):
        order = self._create_order()
        reverse_affiliate_commission(order.id)  # Should not raise
