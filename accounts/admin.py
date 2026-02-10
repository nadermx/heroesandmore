from django.contrib import admin
from django.utils.html import format_html
from allauth.account.models import EmailAddress
from allauth.account.admin import EmailAddressAdmin as BaseEmailAddressAdmin
from allauth.socialaccount.models import SocialAccount
from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_seller_verified', 'rating', 'is_public', 'created']
    list_filter = ['is_seller_verified', 'is_public', 'created']
    search_fields = ['user__username', 'user__email', 'location']
    readonly_fields = ['rating', 'rating_count', 'created', 'updated']


# Override allauth's EmailAddress admin to show signup method
admin.site.unregister(EmailAddress)


@admin.register(EmailAddress)
class EmailAddressAdmin(BaseEmailAddressAdmin):
    list_display = ('email', 'user', 'primary', 'verified', 'signup_method')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Prefetch social accounts to avoid N+1 queries
        qs = qs.select_related('user')
        return qs

    @admin.display(description='Signup Method')
    def signup_method(self, obj):
        providers = SocialAccount.objects.filter(user=obj.user).values_list('provider', flat=True)
        if providers:
            labels = ', '.join(p.capitalize() for p in providers)
            return format_html('<span style="color: #1a73e8; font-weight: 500;">{}</span>', labels)
        return format_html('<span style="color: #666;">Email</span>')
