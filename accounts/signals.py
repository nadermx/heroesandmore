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
