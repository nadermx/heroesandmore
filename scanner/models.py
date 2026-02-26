from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class ScanResult(models.Model):
    """
    Store image recognition results
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('no_match', 'No Match Found'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scan_results')
    image = models.ImageField(upload_to='scans/')

    # Recognition results
    identified_item = models.ForeignKey(
        'pricing.PriceGuideItem',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scan_matches'
    )
    confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Extracted data from image
    extracted_data = models.JSONField(default=dict)
    # Example structure:
    # {
    #   'type': 'graded_card',
    #   'title': 'Michael Jordan',
    #   'year': 1986,
    #   'set': 'Fleer',
    #   'card_number': '57',
    #   'grading_company': 'PSA',
    #   'grade': '10',
    #   'cert_number': '12345678'
    # }

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)

    # What user did with the result
    converted_to_listing = models.ForeignKey(
        'marketplace.Listing',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scan_source'
    )
    added_to_collection = models.ForeignKey(
        'user_collections.CollectionItem',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='scan_source'
    )

    created = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        if self.identified_item:
            return f"Scan: {self.identified_item.name} ({self.confidence}%)"
        return f"Scan {self.pk} - {self.status}"

    def get_suggested_title(self):
        """Generate a suggested listing title from extracted data"""
        data = self.extracted_data
        if not data:
            return ""

        parts = []
        if data.get('year'):
            parts.append(str(data['year']))
        if data.get('set'):
            parts.append(data['set'])
        if data.get('title') or data.get('name'):
            parts.append(data.get('title') or data.get('name'))
        if data.get('card_number'):
            parts.append(f"#{data['card_number']}")
        if data.get('grading_company') and data.get('grade'):
            parts.append(f"{data['grading_company']} {data['grade']}")

        return ' '.join(parts)

    def get_absolute_url(self):
        return reverse('scanner:result', kwargs={'pk': self.pk})


class ScanSession(models.Model):
    """
    Track bulk scanning sessions
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='scan_sessions')
    name = models.CharField(max_length=100, blank=True)

    total_scans = models.IntegerField(default=0)
    successful_scans = models.IntegerField(default=0)
    failed_scans = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Scan session {self.pk} - {self.user.username}"
