from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Address(models.Model):
    """Structured shipping address — replaces free-form textarea for new orders."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shipping_addresses',
                             null=True, blank=True)
    name = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    street1 = models.CharField(max_length=200)
    street2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default='US')
    phone = models.CharField(max_length=30, blank=True)

    # EasyPost verification
    easypost_id = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)

    is_default = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created']
        verbose_name_plural = 'addresses'

    def __str__(self):
        return f"{self.name}, {self.street1}, {self.city}, {self.state} {self.zip_code}"

    @property
    def formatted(self):
        lines = [self.name]
        if self.company:
            lines.append(self.company)
        lines.append(self.street1)
        if self.street2:
            lines.append(self.street2)
        lines.append(f"{self.city}, {self.state} {self.zip_code}")
        if self.country and self.country != 'US':
            lines.append(self.country)
        return '\n'.join(lines)

    def to_easypost_dict(self):
        return {
            'name': self.name,
            'company': self.company or None,
            'street1': self.street1,
            'street2': self.street2 or None,
            'city': self.city,
            'state': self.state,
            'zip': self.zip_code,
            'country': self.country,
            'phone': self.phone or None,
        }

    def save(self, *args, **kwargs):
        # Ensure only one default address per user
        if self.is_default and self.user:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class ShippingProfile(models.Model):
    """Pre-configured package profiles for collectibles."""
    PROFILE_TYPES = [
        ('standard_card', 'Standard Card (PWE)'),
        ('graded_slab', 'Graded Slab'),
        ('multiple_cards', 'Multiple Cards / Lot'),
        ('figure_toy', 'Figure / Toy'),
        ('custom', 'Custom'),
    ]

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    profile_type = models.CharField(max_length=20, choices=PROFILE_TYPES)

    weight_oz = models.DecimalField(max_digits=8, decimal_places=2)
    length_in = models.DecimalField(max_digits=6, decimal_places=2)
    width_in = models.DecimalField(max_digits=6, decimal_places=2)
    height_in = models.DecimalField(max_digits=6, decimal_places=2)

    predefined_package = models.CharField(max_length=50, blank=True,
                                          help_text="EasyPost predefined package name")
    customs_description = models.CharField(max_length=200, blank=True)
    hs_tariff_number = models.CharField(max_length=20, blank=True,
                                        help_text="Harmonized System tariff code")

    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


class ShippingLabel(models.Model):
    """Purchased shipping labels via EasyPost."""
    order = models.ForeignKey('marketplace.Order', on_delete=models.CASCADE, related_name='shipping_labels')

    easypost_shipment_id = models.CharField(max_length=100)
    easypost_label_id = models.CharField(max_length=100, blank=True)

    carrier = models.CharField(max_length=50)
    service = models.CharField(max_length=100)
    rate = models.DecimalField(max_digits=8, decimal_places=2)

    tracking_number = models.CharField(max_length=100, blank=True)
    label_url = models.URLField(max_length=500, blank=True)
    label_format = models.CharField(max_length=10, default='PDF')

    is_voided = models.BooleanField(default=False)
    voided_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Label {self.tracking_number or self.easypost_shipment_id} for Order #{self.order_id}"


class ShippingRate(models.Model):
    """Cached rate quotes from EasyPost."""
    listing = models.ForeignKey('marketplace.Listing', on_delete=models.CASCADE, related_name='shipping_rates')
    to_address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name='rate_quotes')

    easypost_shipment_id = models.CharField(max_length=100)
    easypost_rate_id = models.CharField(max_length=100)

    carrier = models.CharField(max_length=50)
    service = models.CharField(max_length=100)
    rate = models.DecimalField(max_digits=8, decimal_places=2)
    est_delivery_days = models.IntegerField(null=True, blank=True)

    expires_at = models.DateTimeField()
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['rate']

    def __str__(self):
        return f"{self.carrier} {self.service} ${self.rate}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
