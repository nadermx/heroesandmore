import secrets
import string
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


def generate_referral_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))


class Affiliate(models.Model):
    COMMISSION_RATE = Decimal('0.02')
    MINIMUM_PAYOUT = Decimal('25.00')

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='affiliate')
    referral_code = models.CharField(max_length=20, unique=True, default=generate_referral_code)
    paypal_email = models.EmailField(blank=True)
    total_referrals = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    pending_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    paid_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.referral_code})"

    def get_referral_url(self):
        return f"https://heroesandmore.com/?ref={self.referral_code}"


class Referral(models.Model):
    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='referrals')
    referred_user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    landing_url = models.URLField(max_length=500, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.referred_user.username} -> {self.affiliate.user.username}"


class AffiliatePayout(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    paypal_email = models.EmailField()
    paypal_payout_batch_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    period_start = models.DateField()
    period_end = models.DateField()
    error_message = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payout ${self.amount} to {self.affiliate.user.username}"


class AffiliateCommission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('reversed', 'Reversed'),
    ]

    affiliate = models.ForeignKey(Affiliate, on_delete=models.CASCADE, related_name='commissions')
    order = models.OneToOneField('marketplace.Order', on_delete=models.CASCADE, related_name='affiliate_commission')
    referral = models.ForeignKey(Referral, on_delete=models.CASCADE, related_name='commissions')
    order_item_price = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Affiliate.COMMISSION_RATE)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payout = models.ForeignKey(AffiliatePayout, on_delete=models.SET_NULL, null=True, blank=True, related_name='commissions')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"${self.commission_amount} on order #{self.order_id}"
