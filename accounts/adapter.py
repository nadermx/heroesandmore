import logging
from allauth.account.adapter import DefaultAccountAdapter

logger = logging.getLogger('accounts')


class AccountAdapter(DefaultAccountAdapter):
    """Custom allauth adapter that handles email failures gracefully."""

    def send_mail(self, template_prefix, email, context):
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as e:
            logger.error(
                "Failed to send email to %s (template: %s): %s",
                email, template_prefix, e
            )
