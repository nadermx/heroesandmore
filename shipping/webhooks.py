import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from marketplace.services.easypost_service import EasyPostService  # EasyPost webhooks always use EasyPost directly

logger = logging.getLogger('shipping')


@csrf_exempt
@require_POST
def easypost_webhook(request):
    """Handle EasyPost webhook events (tracking updates)."""
    payload = request.body
    signature = request.headers.get('X-Hmac-Signature', '')

    # Verify HMAC signature if webhook secret is configured
    webhook_secret = getattr(settings, 'EASYPOST_WEBHOOK_SECRET', '')
    if webhook_secret:
        expected = hmac.new(
            webhook_secret.encode('utf-8'),
            payload,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(f'hmac-sha256-hex={expected}', signature):
            logger.warning("EasyPost webhook signature verification failed")
            return HttpResponseBadRequest("Invalid signature")

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    event_type = data.get('description', '')
    logger.info(f"EasyPost webhook received: {event_type}")

    if event_type == 'tracker.updated':
        try:
            EasyPostService.process_tracking_webhook(data)
        except Exception as e:
            logger.error(f"Error processing tracking webhook: {e}", exc_info=True)

    return HttpResponse(status=200)
