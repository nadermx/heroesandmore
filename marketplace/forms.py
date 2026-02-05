from django import forms
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
            'title', 'description', 'category', 'condition',
            'grading_service', 'grade', 'cert_number',
            'price', 'listing_type', 'reserve_price', 'allow_offers',
            'image1', 'image2', 'image3', 'image4', 'image5',
            'shipping_price', 'ships_from',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
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
            'shipping_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'ships_from': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City, State'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Require an image for manual listings, but allow programmatic imports to omit
        if 'image1' in self.fields:
            self.fields['image1'].required = True

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
        else:
            cleaned_data['auction_end'] = None

        cleaned_data['is_graded'] = bool(grading_service or grade)

        return cleaned_data

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
