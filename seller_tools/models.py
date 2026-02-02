from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class SellerSubscription(models.Model):
    """
    Seller subscription tiers with varying commission rates and limits.
    Billing is handled internally using PaymentIntents (not Stripe Billing).
    """
    TIERS = [
        ('starter', 'Starter'),
        ('basic', 'Basic'),
        ('featured', 'Featured'),
        ('premium', 'Premium'),
    ]

    TIER_DETAILS = {
        'starter': {
            'name': 'Starter',
            'price': Decimal('0'),
            'max_listings': 50,
            'commission_rate': Decimal('12.95'),
            'featured_slots': 0,
            'description': 'Free tier - 50 listings, 12.95% commission'
        },
        'basic': {
            'name': 'Basic',
            'price': Decimal('9.99'),
            'max_listings': 200,
            'commission_rate': Decimal('9.95'),
            'featured_slots': 2,
            'description': '$9.99/mo - 200 listings, 9.95% commission, 2 featured slots'
        },
        'featured': {
            'name': 'Featured',
            'price': Decimal('29.99'),
            'max_listings': 1000,
            'commission_rate': Decimal('7.95'),
            'featured_slots': 10,
            'description': '$29.99/mo - 1000 listings, 7.95% commission, 10 featured slots'
        },
        'premium': {
            'name': 'Premium',
            'price': Decimal('99.99'),
            'max_listings': 9999,
            'commission_rate': Decimal('5.95'),
            'featured_slots': 50,
            'description': '$99.99/mo - Unlimited listings, 5.95% commission, 50 featured slots'
        },
    }

    STATUS_CHOICES = [
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
        ('suspended', 'Suspended'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_subscription')
    tier = models.CharField(max_length=20, choices=TIERS, default='starter')

    # Limits (can be customized per user)
    max_active_listings = models.IntegerField(default=50)
    commission_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('12.95'))
    featured_slots = models.IntegerField(default=0)

    # Internal Billing (uses Profile.stripe_customer_id for payment)
    default_payment_method = models.ForeignKey(
        'marketplace.PaymentMethod',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='subscriptions'
    )
    subscription_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='inactive')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    # Billing tracking
    last_billed_at = models.DateTimeField(null=True, blank=True)
    last_payment_intent_id = models.CharField(max_length=100, blank=True)
    failed_payment_attempts = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    grace_period_end = models.DateTimeField(null=True, blank=True)

    # Deprecated - kept for migration, use Profile.stripe_customer_id
    stripe_customer_id = models.CharField(max_length=100, blank=True)

    is_active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Seller Subscription'
        verbose_name_plural = 'Seller Subscriptions'

    def __str__(self):
        return f"{self.user.username} - {self.get_tier_display()}"

    def get_tier_info(self):
        return self.TIER_DETAILS.get(self.tier, self.TIER_DETAILS['starter'])

    def can_create_listing(self):
        """Check if user can create more listings"""
        active_count = self.user.listings.filter(status='active').count()
        return active_count < self.max_active_listings

    def get_remaining_listings(self):
        active_count = self.user.listings.filter(status='active').count()
        return max(0, self.max_active_listings - active_count)

    def is_in_grace_period(self):
        """Check if subscription is in grace period after failed payment"""
        from django.utils import timezone
        if not self.grace_period_end:
            return False
        return timezone.now() < self.grace_period_end

    def needs_renewal(self):
        """Check if subscription needs to be renewed"""
        from django.utils import timezone
        if self.tier == 'starter':
            return False
        if not self.current_period_end:
            return False
        return timezone.now() >= self.current_period_end


class SubscriptionBillingHistory(models.Model):
    """
    Audit trail for all subscription billing events.
    Records charges, refunds, prorations, and failures.
    """
    TRANSACTION_TYPES = [
        ('charge', 'Charge'),
        ('refund', 'Refund'),
        ('proration_credit', 'Proration Credit'),
        ('proration_charge', 'Proration Charge'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('succeeded', 'Succeeded'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    subscription = models.ForeignKey(
        SellerSubscription,
        on_delete=models.CASCADE,
        related_name='billing_history'
    )
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tier = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    failure_reason = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Subscription Billing History'
        verbose_name_plural = 'Subscription Billing History'

    def __str__(self):
        return f"{self.subscription.user.username} - {self.transaction_type} ${self.amount} ({self.status})"


class BulkImport(models.Model):
    """
    Track bulk listing imports from CSV/Excel files
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partial', 'Partial Success'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bulk_imports')
    file = models.FileField(upload_to='bulk_imports/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20)  # csv, xlsx

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)

    # Store validation/processing errors
    errors = models.JSONField(default=list)  # [{row: 5, field: 'price', error: "Invalid price"}]

    # Import options
    auto_publish = models.BooleanField(default=False)  # Publish listings immediately
    default_category = models.ForeignKey(
        'items.Category', null=True, blank=True, on_delete=models.SET_NULL
    )

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Bulk Import'
        verbose_name_plural = 'Bulk Imports'

    def __str__(self):
        return f"Import {self.pk} - {self.file_name} ({self.status})"

    def get_progress_percent(self):
        if self.total_rows == 0:
            return 0
        return int((self.processed_rows / self.total_rows) * 100)


class BulkImportRow(models.Model):
    """
    Individual rows from bulk import for tracking
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('error', 'Error'),
        ('skipped', 'Skipped'),
    ]

    bulk_import = models.ForeignKey(BulkImport, on_delete=models.CASCADE, related_name='rows')
    row_number = models.IntegerField()
    data = models.JSONField()  # Original row data

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)

    # Link to created listing if successful
    listing = models.ForeignKey(
        'marketplace.Listing',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='import_source'
    )

    class Meta:
        ordering = ['row_number']

    def __str__(self):
        return f"Row {self.row_number} - {self.status}"


class InventoryItem(models.Model):
    """
    Seller inventory management - track items before listing
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='inventory')

    # Item info
    title = models.CharField(max_length=200)
    category = models.ForeignKey('items.Category', on_delete=models.SET_NULL, null=True)
    condition = models.CharField(max_length=20, blank=True)

    # Grading
    grading_company = models.CharField(max_length=10, blank=True)
    grade = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    cert_number = models.CharField(max_length=50, blank=True)

    # Costing
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    purchase_source = models.CharField(max_length=100, blank=True)

    # Pricing targets
    target_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    minimum_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Images stored before listing
    image1 = models.ImageField(upload_to='inventory/', blank=True)
    image2 = models.ImageField(upload_to='inventory/', blank=True)
    image3 = models.ImageField(upload_to='inventory/', blank=True)

    # Link to price guide for valuation
    price_guide_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )

    # Status
    is_listed = models.BooleanField(default=False)
    listing = models.ForeignKey(
        'marketplace.Listing',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='inventory_item'
    )

    notes = models.TextField(blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Inventory Item'
        verbose_name_plural = 'Inventory Items'

    def __str__(self):
        return self.title

    def get_estimated_profit(self):
        """Calculate estimated profit based on target price and purchase price"""
        if self.target_price and self.purchase_price:
            return self.target_price - self.purchase_price
        return None
