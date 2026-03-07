from django.contrib import admin
from affiliates.models import Affiliate, Referral, AffiliateCommission, AffiliatePayout


@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = ['user', 'referral_code', 'total_referrals', 'total_earnings', 'pending_balance', 'paid_balance', 'is_active', 'created']
    list_filter = ['is_active', 'created']
    search_fields = ['user__username', 'user__email', 'referral_code', 'paypal_email']
    raw_id_fields = ['user']
    readonly_fields = ['referral_code', 'total_referrals', 'total_earnings', 'pending_balance', 'paid_balance', 'created']


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ['referred_user', 'affiliate', 'ip_address', 'created']
    list_filter = ['created']
    search_fields = ['referred_user__username', 'referred_user__email', 'affiliate__user__username']
    raw_id_fields = ['affiliate', 'referred_user']


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display = ['affiliate', 'order', 'commission_type', 'order_item_price', 'commission_amount', 'status', 'created']
    list_filter = ['status', 'commission_type', 'created']
    search_fields = ['affiliate__user__username', 'affiliate__user__email']
    raw_id_fields = ['affiliate', 'order', 'referral', 'payout']


@admin.register(AffiliatePayout)
class AffiliatePayoutAdmin(admin.ModelAdmin):
    list_display = ['affiliate', 'amount', 'paypal_email', 'status', 'period_start', 'period_end', 'created']
    list_filter = ['status', 'created']
    search_fields = ['affiliate__user__username', 'paypal_email', 'paypal_payout_batch_id']
    raw_id_fields = ['affiliate']
