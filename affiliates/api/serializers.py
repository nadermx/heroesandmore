from rest_framework import serializers
from affiliates.models import Affiliate, Referral, AffiliateCommission, AffiliatePayout


class AffiliateSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    referral_url = serializers.CharField(source='get_referral_url', read_only=True)

    class Meta:
        model = Affiliate
        fields = [
            'id', 'username', 'referral_code', 'referral_url', 'paypal_email',
            'total_referrals', 'total_earnings', 'pending_balance', 'paid_balance',
            'is_active', 'created',
        ]
        read_only_fields = [
            'id', 'username', 'referral_code', 'referral_url',
            'total_referrals', 'total_earnings', 'pending_balance', 'paid_balance',
            'is_active', 'created',
        ]


class ReferralSerializer(serializers.ModelSerializer):
    referred_username = serializers.CharField(source='referred_user.username', read_only=True)

    class Meta:
        model = Referral
        fields = ['id', 'referred_username', 'created']


class AffiliateCommissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffiliateCommission
        fields = [
            'id', 'order_id', 'commission_type', 'order_item_price',
            'commission_rate', 'commission_amount', 'status', 'created',
        ]


class AffiliatePayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffiliatePayout
        fields = [
            'id', 'amount', 'paypal_email', 'status',
            'period_start', 'period_end', 'created',
        ]
