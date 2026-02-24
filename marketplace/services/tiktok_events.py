"""
TikTok Events API — server-side event tracking.
Sends conversion events directly to TikTok for better attribution.
"""
import hashlib
import logging
import time
import requests
from django.conf import settings

logger = logging.getLogger('marketplace')

TIKTOK_PIXEL_ID = 'D6F1PMJC77U56TVASA00'
TIKTOK_API_URL = 'https://business-api.tiktok.com/open_api/v1.2/pixel/track/'
TIKTOK_TEST_EVENT_CODE = getattr(settings, 'TIKTOK_TEST_EVENT_CODE', None)


def _hash_value(value):
    """SHA256 hash for PII fields per TikTok requirements."""
    if not value:
        return None
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def send_event(event_name, email=None, ip=None, user_agent=None,
               content_id=None, content_name=None, value=None, currency='USD',
               content_type='product'):
    """
    Send a server-side event to TikTok Events API.

    Args:
        event_name: TikTok event name (CompletePayment, CompleteRegistration, etc.)
        email: User email (will be hashed)
        ip: User IP address
        user_agent: User-Agent header
        content_id: Product/listing ID
        content_name: Product/listing title
        value: Monetary value
        currency: Currency code (default USD)
        content_type: Content type (default product)
    """
    access_token = getattr(settings, 'TIKTOK_ACCESS_TOKEN', None)
    if not access_token:
        return

    properties = {}
    if content_id:
        properties['contents'] = [{
            'content_id': str(content_id),
            'content_type': content_type,
            'content_name': content_name or '',
        }]
    if value is not None:
        properties['value'] = float(value)
        properties['currency'] = currency

    user_data = {}
    if email:
        user_data['email'] = _hash_value(email)
    if ip:
        user_data['ip'] = ip
    if user_agent:
        user_data['user_agent'] = user_agent

    event = {
        'pixel_code': TIKTOK_PIXEL_ID,
        'event': event_name,
        'timestamp': int(time.time()),
        'context': {
            'user': user_data,
        },
        'properties': properties,
    }

    if TIKTOK_TEST_EVENT_CODE:
        event['test_event_code'] = TIKTOK_TEST_EVENT_CODE

    payload = {
        'pixel_code': TIKTOK_PIXEL_ID,
        'data': [event],
    }

    try:
        resp = requests.post(
            TIKTOK_API_URL,
            json=payload,
            headers={
                'Access-Token': access_token,
                'Content-Type': 'application/json',
            },
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('code') == 0:
                logger.info("TikTok event '%s' sent successfully", event_name)
            else:
                logger.warning("TikTok event '%s' error: %s", event_name, data.get('message'))
        else:
            logger.warning("TikTok event '%s' HTTP %s: %s", event_name, resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("TikTok event '%s' failed: %s", event_name, e)
