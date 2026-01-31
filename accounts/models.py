from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse


class Profile(models.Model):
    SELLER_TIERS = [
        ('starter', 'Starter'),
        ('basic', 'Basic'),
        ('featured', 'Featured'),
        ('premium', 'Premium'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)

    # Seller info
    is_seller_verified = models.BooleanField(default=False)

    # Stripe Connect (seller)
    stripe_account_id = models.CharField(max_length=100, blank=True)
    stripe_account_type = models.CharField(max_length=20, default='express')  # express, standard, custom
    stripe_account_complete = models.BooleanField(default=False)
    stripe_payouts_enabled = models.BooleanField(default=False)
    stripe_charges_enabled = models.BooleanField(default=False)

    # Stripe Customer (buyer)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    default_payment_method_id = models.CharField(max_length=100, blank=True)

    # Seller subscription tier
    seller_tier = models.CharField(max_length=20, choices=SELLER_TIERS, default='starter')
    subscription_expires = models.DateTimeField(null=True, blank=True)

    # Seller verification
    id_verified = models.BooleanField(default=False)
    address_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    # Stats
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    total_sales_count = models.IntegerField(default=0)
    total_sales_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Settings
    is_public = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_absolute_url(self):
        return reverse('accounts:profile', kwargs={'username': self.user.username})

    def update_rating(self):
        from marketplace.models import Review
        reviews = Review.objects.filter(seller=self.user)
        if reviews.exists():
            self.rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
            self.rating_count = reviews.count()
            self.save(update_fields=['rating', 'rating_count'])


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


class RecentlyViewed(models.Model):
    """
    Track recently viewed items with timestamp
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recently_viewed')
    listing = models.ForeignKey('marketplace.Listing', on_delete=models.CASCADE, related_name='viewed_by')
    viewed_at = models.DateTimeField(auto_now=True)
    view_count = models.IntegerField(default=1)

    class Meta:
        unique_together = ['user', 'listing']
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user.username} viewed {self.listing.title}"

    @classmethod
    def record_view(cls, user, listing):
        """Record a listing view for a user"""
        if not user.is_authenticated:
            return None

        obj, created = cls.objects.get_or_create(
            user=user,
            listing=listing,
            defaults={'view_count': 1}
        )
        if not created:
            obj.view_count += 1
            obj.save(update_fields=['view_count', 'viewed_at'])

        # Keep only last 50 viewed items
        old_views = cls.objects.filter(user=user).order_by('-viewed_at')[50:]
        cls.objects.filter(pk__in=[v.pk for v in old_views]).delete()

        return obj


class DeviceToken(models.Model):
    """
    Store device tokens for push notifications (FCM).
    """
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated']

    def __str__(self):
        return f"{self.user.username} - {self.platform} device"
