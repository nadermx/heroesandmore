from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from accounts.models import Profile, RecentlyViewed


class UserSerializer(serializers.ModelSerializer):
    """Basic user info serializer"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class ProfileSerializer(serializers.ModelSerializer):
    """Full profile serializer for current user"""
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'username', 'email', 'avatar', 'avatar_url', 'bio',
            'location', 'website', 'is_seller_verified', 'is_trusted_seller',
            'is_founding_member', 'founding_member_since',
            'stripe_account_complete',
            'seller_tier', 'rating', 'rating_count', 'total_sales_count',
            'is_public', 'email_notifications', 'created'
        ]
        read_only_fields = [
            'rating', 'rating_count', 'is_seller_verified', 'is_trusted_seller',
            'is_founding_member', 'founding_member_since',
            'stripe_account_complete', 'total_sales_count', 'seller_tier'
        ]

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None


class PublicProfileSerializer(serializers.ModelSerializer):
    """Limited profile info for public viewing"""
    username = serializers.CharField(source='user.username')
    avatar_url = serializers.SerializerMethodField()
    listings_count = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'username', 'avatar_url', 'bio', 'location', 'website',
            'rating', 'rating_count', 'is_seller_verified', 'is_trusted_seller',
            'is_founding_member',
            'total_sales_count', 'listings_count', 'created'
        ]

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def get_listings_count(self, obj):
        return obj.user.listings.filter(status='active').count()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating profile"""
    class Meta:
        model = Profile
        fields = ['avatar', 'bio', 'location', 'website', 'is_public', 'email_notifications']


class RegisterSerializer(serializers.Serializer):
    """User registration serializer"""
    username = serializers.CharField(max_length=150, min_length=3)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already taken")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already registered")
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': "Passwords don't match"})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """Change password serializer"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': "Passwords don't match"})
        return data


class RecentlyViewedSerializer(serializers.ModelSerializer):
    """Serializer for recently viewed listings"""
    listing_id = serializers.IntegerField(source='listing.id')
    listing_title = serializers.CharField(source='listing.title')
    listing_price = serializers.DecimalField(
        source='listing.price', max_digits=10, decimal_places=2
    )
    listing_image = serializers.SerializerMethodField()

    class Meta:
        model = RecentlyViewed
        fields = ['listing_id', 'listing_title', 'listing_price', 'listing_image', 'viewed_at']

    def get_listing_image(self, obj):
        if obj.listing.image1:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.listing.image1.url)
            return obj.listing.image1.url
        return None


class DeviceTokenSerializer(serializers.Serializer):
    """Serializer for registering device tokens for push notifications"""
    token = serializers.CharField(max_length=255)
    platform = serializers.ChoiceField(choices=[('android', 'Android'), ('ios', 'iOS')])


class GoogleAuthSerializer(serializers.Serializer):
    """Serializer for Google OAuth authentication"""
    id_token = serializers.CharField()


class AppleAuthSerializer(serializers.Serializer):
    """Serializer for Apple Sign In authentication"""
    id_token = serializers.CharField()
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for requesting password reset"""
    email = serializers.EmailField()

    def validate_email(self, value):
        # Don't reveal if email exists or not
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming password reset"""
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({'new_password_confirm': "Passwords don't match"})
        return data


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for user notification settings"""
    class Meta:
        model = Profile
        fields = [
            'email_notifications',
            'push_new_bid',
            'push_outbid',
            'push_offer',
            'push_order_shipped',
            'push_message',
            'push_price_alert',
        ]
