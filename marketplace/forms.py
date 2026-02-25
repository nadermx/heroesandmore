import os
import re

from django import forms
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Listing, Offer, Review


class ListingForm(forms.ModelForm):
    auction_duration = forms.ChoiceField(
        choices=[
            ('1', '1 day'),
            ('3', '3 days'),
            ('5', '5 days'),
            ('7', '7 days'),
            ('10', '10 days'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Listing
        fields = [
            'title', 'description', 'collector_notes', 'category', 'condition',
            'grading_service', 'grade', 'cert_number',
            'price', 'listing_type', 'quantity', 'reserve_price', 'allow_offers',
            'image1', 'image2', 'image3', 'image4', 'image5',
            'video1', 'video2', 'video3', 'video_url',
            'shipping_price', 'ships_from',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'collector_notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "e.g. 'Press candidate, strong eye appeal'"}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'grading_service': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 9.5, Gem Mint 10'}),
            'cert_number': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'listing_type': forms.Select(attrs={'class': 'form-select'}),
            'reserve_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'allow_offers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'image1': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'image2': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'image3': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'image4': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'image5': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'video1': forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/mp4,video/webm,video/quicktime'}),
            'video2': forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/mp4,video/webm,video/quicktime'}),
            'video3': forms.FileInput(attrs={'class': 'form-control', 'accept': 'video/mp4,video/webm,video/quicktime'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://youtube.com/watch?v=... or https://vimeo.com/...'}),
            'shipping_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'ships_from': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City, State'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user
        # Require an image for manual listings, but allow programmatic imports to omit
        if 'image1' in self.fields:
            self.fields['image1'].required = True

    def _get_video_limits(self):
        """Get video limits for the current user's subscription tier."""
        tier = 'starter'
        if self._user:
            sub = getattr(self._user, 'seller_subscription', None)
            if sub:
                tier = sub.tier
        return settings.VIDEO_TIER_LIMITS.get(tier, settings.VIDEO_TIER_LIMITS['starter'])

    def clean(self):
        cleaned_data = super().clean()
        listing_type = cleaned_data.get('listing_type')
        grading_service = cleaned_data.get('grading_service')
        grade = cleaned_data.get('grade')

        if listing_type == 'auction':
            duration = cleaned_data.get('auction_duration')
            if not duration:
                raise forms.ValidationError("Please select an auction duration")
            cleaned_data['auction_end'] = timezone.now() + timedelta(days=int(duration))
            cleaned_data['quantity'] = 1
        else:
            cleaned_data['auction_end'] = None

        cleaned_data['is_graded'] = bool(grading_service or grade)

        # Video validation — upload OR URL, not both
        has_upload = any(
            cleaned_data.get(f) and hasattr(cleaned_data.get(f), 'name')
            for f in ['video1', 'video2', 'video3']
        )
        has_existing_upload = self.instance and self.instance.pk and any(
            getattr(self.instance, f) and getattr(self.instance, f).name
            for f in ['video1', 'video2', 'video3']
        )
        has_url = bool((cleaned_data.get('video_url') or '').strip())

        if (has_upload or has_existing_upload) and has_url:
            raise forms.ValidationError(
                'Please choose either a video upload or a YouTube/Vimeo URL, not both.'
            )

        self._validate_videos(cleaned_data)
        self._validate_video_url(cleaned_data)

        return cleaned_data

    def _validate_videos(self, cleaned_data):
        limits = self._get_video_limits()
        allowed_ext = settings.VIDEO_ALLOWED_EXTENSIONS
        video_fields = ['video1', 'video2', 'video3']
        video_count = 0

        for field_name in video_fields:
            file = cleaned_data.get(field_name)
            if file and hasattr(file, 'name'):
                video_count += 1
                ext = os.path.splitext(file.name)[1].lower().lstrip('.')
                if ext not in allowed_ext:
                    raise forms.ValidationError(
                        f"Video format '.{ext}' is not supported. Accepted: MP4, WebM, MOV."
                    )
                if file.size > limits['max_size_mb'] * 1024 * 1024:
                    raise forms.ValidationError(
                        f"Video exceeds maximum size of {limits['max_size_mb']}MB for your plan."
                    )
            elif self.instance and self.instance.pk:
                existing = getattr(self.instance, field_name)
                if existing and existing.name:
                    video_count += 1

        if video_count > limits['max_count']:
            raise forms.ValidationError(
                f"Your plan allows {limits['max_count']} video(s). "
                f"Upgrade your seller subscription for more."
            )

    def _validate_video_url(self, cleaned_data):
        video_url = (cleaned_data.get('video_url') or '').strip()
        if not video_url:
            return
        youtube_pattern = r'^(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+'
        vimeo_pattern = r'^(?:https?://)?(?:www\.)?vimeo\.com/\d+'
        if not (re.match(youtube_pattern, video_url) or re.match(vimeo_pattern, video_url)):
            raise forms.ValidationError(
                {'video_url': 'Please enter a valid YouTube or Vimeo URL.'}
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_graded = self.cleaned_data.get('is_graded', False)
        if instance.listing_type == 'auction':
            instance.starting_bid = instance.price
        if commit:
            instance.save()
        return instance


class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ['amount', 'message']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '1'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional message to seller'}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'text']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, i) for i in range(1, 6)]),
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Share your experience (optional)'}),
        }


class ShippingForm(forms.Form):
    tracking_number = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tracking number'})
    )
    tracking_carrier = forms.ChoiceField(
        choices=[
            ('usps', 'USPS'),
            ('ups', 'UPS'),
            ('fedex', 'FedEx'),
            ('dhl', 'DHL'),
            ('other', 'Other'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
