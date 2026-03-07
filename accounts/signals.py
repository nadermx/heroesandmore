import logging
from django.db import models
from allauth.account.signals import user_signed_up
from django.dispatch import receiver

logger = logging.getLogger('accounts')


@receiver(user_signed_up)
def on_user_signed_up(request, user, **kwargs):
    """Send welcome email with live auctions when a new user signs up."""
    try:
        from alerts.tasks import send_welcome_email
        send_welcome_email.delay(user.id)
    except Exception:
        logger.error(f"Failed to queue welcome email for user {user.id}", exc_info=True)

    # Affiliate referral attribution
    try:
        ref_code = None
        if request:
            ref_code = request.COOKIES.get('ham_ref') or request.session.get('ham_ref')
        if ref_code:
            from affiliates.models import Affiliate, Referral
            affiliate = Affiliate.objects.filter(referral_code=ref_code, is_active=True).first()
            if affiliate and affiliate.user != user:
                if not Referral.objects.filter(referred_user=user).exists():
                    Referral.objects.create(
                        affiliate=affiliate,
                        referred_user=user,
                        ip_address=request.META.get('REMOTE_ADDR') if request else None,
                        user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
                        landing_url=request.build_absolute_uri() if request else '',
                    )
                    Affiliate.objects.filter(pk=affiliate.pk).update(
                        total_referrals=models.F('total_referrals') + 1
                    )
                    logger.info(f"Affiliate referral created: {user.username} referred by {affiliate.user.username}")
    except Exception:
        logger.error(f"Failed to create affiliate referral for user {user.id}", exc_info=True)

    # TikTok server-side CompleteRegistration event
    try:
        from marketplace.services.tiktok_events import send_event
        send_event(
            'CompleteRegistration',
            email=user.email,
            ip=request.META.get('REMOTE_ADDR') if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT') if request else None,
            page_url=request.build_absolute_uri() if request else None,
        )
    except Exception:
        logger.warning("Failed to send TikTok registration event for user %s", user.id)
