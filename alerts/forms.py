from django import forms
from .models import Wishlist, WishlistItem, SavedSearch


class WishlistForm(forms.ModelForm):
    class Meta:
        model = Wishlist
        fields = ['name', 'description', 'is_public']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class WishlistItemForm(forms.ModelForm):
    class Meta:
        model = WishlistItem
        fields = ['search_query', 'category', 'max_price', 'min_condition', 'notes', 'notify_email']
        widgets = {
            'search_query': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Michael Jordan rookie'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'max_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Max price'}),
            'min_condition': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', 'Any condition'),
                ('mint', 'Mint'),
                ('near_mint', 'Near Mint or better'),
                ('excellent', 'Excellent or better'),
                ('very_good', 'Very Good or better'),
                ('good', 'Good or better'),
            ]),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notify_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SavedSearchForm(forms.ModelForm):
    class Meta:
        model = SavedSearch
        fields = ['name', 'query', 'category', 'min_price', 'max_price', 'condition', 'listing_type', 'notify_email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'query': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'min_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'max_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'condition': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', 'Any'),
                ('mint', 'Mint'),
                ('near_mint', 'Near Mint'),
                ('excellent', 'Excellent'),
                ('very_good', 'Very Good'),
                ('good', 'Good'),
                ('fair', 'Fair'),
                ('poor', 'Poor'),
            ]),
            'listing_type': forms.Select(attrs={'class': 'form-select'}, choices=[
                ('', 'Any'),
                ('fixed', 'Fixed Price'),
                ('auction', 'Auction'),
            ]),
            'notify_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
