import logging
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
