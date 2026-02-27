import logging
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

import requests

logger = logging.getLogger('marketplace.services')

# USPS mail class codes and display names
USPS_MAIL_CLASSES = [
    ('GROUND_ADVANTAGE', 'USPS Ground Advantage'),
    ('PRIORITY_MAIL', 'Priority Mail'),
    ('PRIORITY_MAIL_EXPRESS', 'Priority Mail Express'),
]

# USPS tracking status → order status mapping
USPS_STATUS_MAP = {
    'In Transit': 'shipped',
    'In Transit, Arriving Late': 'shipped',
    'In Transit, Arriving On Time': 'shipped',
    'Out for Delivery': 'shipped',
    'Delivered': 'delivered',
    'Delivered, To Agent': 'delivered',
    'Delivered, Front Door/Porch': 'delivered',
    'Delivered, In/At Mailbox': 'delivered',
    'Delivered, Left with Individual': 'delivered',
    'Delivered, PO Box': 'delivered',
}


class USPSService:
    """USPS REST API v3 shipping operations — same interface as EasyPostService."""

    TOKEN_CACHE_KEY = 'usps_oauth_token'

    @staticmethod
    def _get_token():
        """Get OAuth 2.0 access token, cached until expiry."""
        token = cache.get(USPSService.TOKEN_CACHE_KEY)
        if token:
            return token

        client_id = getattr(settings, 'USPS_CLIENT_ID', '')
        client_secret = getattr(settings, 'USPS_CLIENT_SECRET', '')
        base_url = getattr(settings, 'USPS_BASE_URL', 'https://apis.usps.com')

        if not client_id or not client_secret:
            raise ValueError("USPS_CLIENT_ID and USPS_CLIENT_SECRET must be configured")

        resp = requests.post(
            f'{base_url}/oauth2/v3/token',
            json={
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'client_credentials',
            },
            headers={'Content-Type': 'application/json'},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data['access_token']
        # Cache for slightly less than the token lifetime (default 1 hour)
        expires_in = data.get('expires_in', 3600)
        cache.set(USPSService.TOKEN_CACHE_KEY, token, timeout=max(expires_in - 60, 60))
        return token

    @staticmethod
    def _make_request(method, path, **kwargs):
        """Authenticated HTTP request with auto-retry on 401."""
        base_url = getattr(settings, 'USPS_BASE_URL', 'https://apis.usps.com')
        url = f'{base_url}{path}'
        kwargs.setdefault('timeout', 30)

        for attempt in range(2):
            token = USPSService._get_token()
            kwargs.setdefault('headers', {})
            kwargs['headers']['Authorization'] = f'Bearer {token}'

            resp = requests.request(method, url, **kwargs)

            if resp.status_code == 401 and attempt == 0:
                # Token expired — clear cache and retry
                cache.delete(USPSService.TOKEN_CACHE_KEY)
                kwargs['headers'].pop('Authorization', None)
                continue

            resp.raise_for_status()
            return resp

        raise RuntimeError("USPS API authentication failed after retry")

    @staticmethod
    def verify_address(address_dict):
        """Verify and correct an address via USPS Address API v3.

        Args:
            address_dict: dict with keys: name, street1, street2, city, state, zip, country, phone

        Returns:
            dict with: verified (bool), address (corrected dict), easypost_id, errors (list)
        """
        try:
            params = {
                'streetAddress': address_dict.get('street1', ''),
                'city': address_dict.get('city', ''),
                'state': address_dict.get('state', ''),
                'ZIPCode': address_dict.get('zip', ''),
            }
            secondary = address_dict.get('street2', '')
            if secondary:
                params['secondaryAddress'] = secondary

            resp = USPSService._make_request('GET', '/addresses/v3/address', params=params)
            data = resp.json()
            addr = data.get('address', {})

            return {
                'verified': True,
                'easypost_id': f"usps_addr_{uuid.uuid4().hex[:12]}",
                'address': {
                    'name': address_dict.get('name', ''),
                    'company': address_dict.get('company', ''),
                    'street1': addr.get('streetAddress', address_dict.get('street1', '')),
                    'street2': addr.get('secondaryAddress', ''),
                    'city': addr.get('city', address_dict.get('city', '')),
                    'state': addr.get('state', address_dict.get('state', '')),
                    'zip': addr.get('ZIPCode', address_dict.get('zip', '')),
                    'country': 'US',
                    'phone': address_dict.get('phone', ''),
                },
                'errors': [],
            }
        except Exception as e:
            logger.warning(f"USPS address verification failed: {e}")
            return {
                'verified': False,
                'easypost_id': '',
                'address': address_dict,
                'errors': [str(e)],
            }

    @staticmethod
    def get_rates(from_address, to_address, parcel, customs_info=None):
        """Get shipping rates from USPS Prices API v3.

        Queries Ground Advantage, Priority Mail, and Priority Mail Express.

        Args:
            from_address: dict with zip key
            to_address: dict with zip key
            parcel: dict with weight (oz), length, width, height
            customs_info: dict (optional, for international)

        Returns:
            list of dicts: [{carrier, service, rate, days, rate_id, shipment_id}]
        """
        origin_zip = from_address.get('zip', '').replace('-', '')[:5]
        dest_zip = to_address.get('zip', '').replace('-', '')[:5]
        weight_oz = parcel.get('weight', 2)
        # Convert ounces to pounds (USPS API expects pounds)
        weight_lbs = round(weight_oz / 16, 2)
        if weight_lbs < 0.01:
            weight_lbs = 0.01

        length = parcel.get('length', 9.5)
        width = parcel.get('width', 6.5)
        height = parcel.get('height', 0.25)

        # Generate a shipment ID to group these rates
        shipment_id = f"usps_shp_{uuid.uuid4().hex[:12]}"

        rates = []
        est_days = {
            'GROUND_ADVANTAGE': 5,
            'PRIORITY_MAIL': 3,
            'PRIORITY_MAIL_EXPRESS': 2,
        }

        for mail_class, display_name in USPS_MAIL_CLASSES:
            try:
                payload = {
                    'originZIPCode': origin_zip,
                    'destinationZIPCode': dest_zip,
                    'weight': weight_lbs,
                    'length': length,
                    'width': width,
                    'height': height,
                    'mailClass': mail_class,
                    'processingCategory': 'MACHINABLE',
                    'rateIndicator': 'DR',  # Dimensional Rectangular
                    'priceType': 'RETAIL',
                }

                resp = USPSService._make_request(
                    'POST', '/prices/v3/base-rates/search',
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                )
                data = resp.json()

                # Extract the total price
                total_price = data.get('totalBasePrice')
                if total_price is None:
                    # Try alternate response formats
                    prices = data.get('rates', data.get('prices', []))
                    if prices and isinstance(prices, list):
                        total_price = prices[0].get('price', prices[0].get('totalBasePrice'))

                if total_price is not None:
                    rate_id = f"usps_{mail_class.lower()}_{uuid.uuid4().hex[:8]}"
                    rates.append({
                        'carrier': 'USPS',
                        'service': display_name,
                        'rate': Decimal(str(total_price)),
                        'days': est_days.get(mail_class, 5),
                        'rate_id': rate_id,
                        'shipment_id': shipment_id,
                        # Store request params for later label purchase
                        '_mail_class': mail_class,
                    })

            except requests.exceptions.HTTPError as e:
                # Some mail classes may not be available for certain routes/weights
                logger.debug(f"USPS rate not available for {mail_class}: {e}")
                continue
            except Exception as e:
                logger.warning(f"USPS rate query failed for {mail_class}: {e}")
                continue

        if not rates:
            raise RuntimeError("No USPS shipping rates available for this route")

        rates.sort(key=lambda r: r['rate'])
        return rates

    @staticmethod
    def buy_label(shipment_id, rate_id, label_format='PDF'):
        """Purchase a shipping label via USPS Labels API v3.

        Requires EPS account number configured in settings.

        Returns:
            dict: {tracking_number, label_url, carrier, service, rate}
        """
        from shipping.models import ShippingRate

        # Look up the cached rate to reconstruct the request
        cached_rate = ShippingRate.objects.filter(
            easypost_rate_id=rate_id,
            easypost_shipment_id=shipment_id,
        ).first()

        if not cached_rate:
            raise ValueError("Rate quote expired or not found. Please get new rates.")

        eps_account = getattr(settings, 'USPS_EPS_ACCOUNT_NUMBER', '')
        if not eps_account:
            raise ValueError("USPS EPS account not configured — label purchase unavailable")

        # Build label request from cached rate data
        order = cached_rate.listing  # We need the listing for address details
        payload = {
            'imageInfo': {
                'imageType': label_format,
                'labelType': 'LABEL',
            },
            'toAddress': {
                'streetAddress': cached_rate.to_address.street1,
                'secondaryAddress': cached_rate.to_address.street2 or '',
                'city': cached_rate.to_address.city,
                'state': cached_rate.to_address.state,
                'ZIPCode': cached_rate.to_address.zip_code,
                'firstName': cached_rate.to_address.name.split()[0] if cached_rate.to_address.name else '',
                'lastName': ' '.join(cached_rate.to_address.name.split()[1:]) if cached_rate.to_address.name else '',
            },
            'fromAddress': {},  # Will be populated from seller's ship-from
            'packageDescription': {
                'weight': round(float(cached_rate.listing.weight_oz or 2) / 16, 2),
                'length': float(cached_rate.listing.length_in or 9.5),
                'width': float(cached_rate.listing.width_in or 6.5),
                'height': float(cached_rate.listing.height_in or 0.25),
                'mailClass': cached_rate.service.upper().replace(' ', '_'),
                'processingCategory': 'MACHINABLE',
                'rateIndicator': 'DR',
            },
            'paymentInfo': {
                'paymentMethod': 'EPS',
                'accountNumber': eps_account,
            },
        }

        try:
            resp = USPSService._make_request(
                'POST', '/labels/v3/label',
                json=payload,
                headers={'Content-Type': 'application/json'},
            )
            data = resp.json()

            return {
                'tracking_number': data.get('trackingNumber', ''),
                'label_url': data.get('labelImage', ''),
                'carrier': 'USPS',
                'service': cached_rate.service,
                'rate': cached_rate.rate,
            }
        except Exception as e:
            logger.error(f"USPS label purchase failed: {e}", exc_info=True)
            raise

    @staticmethod
    def refund_label(shipment_id):
        """USPS label refunds are manual — log a warning."""
        logger.warning(
            f"USPS label refund requested for {shipment_id}. "
            "USPS refunds must be processed manually at usps.com."
        )
        return {'status': 'manual_refund_required'}

    @staticmethod
    def get_tracking(tracking_number, carrier='USPS'):
        """Get tracking events from USPS Tracking API v3."""
        try:
            resp = USPSService._make_request(
                'GET',
                f'/tracking/v3/tracking/{tracking_number}',
                params={'expand': 'DETAIL'},
            )
            data = resp.json()

            events = []
            tracking_events = data.get('trackingEvents', [])
            for evt in tracking_events:
                events.append({
                    'status': evt.get('eventType', ''),
                    'message': evt.get('eventDescription', ''),
                    'datetime': evt.get('eventTimestamp', ''),
                    'city': evt.get('eventCity', ''),
                    'state': evt.get('eventState', ''),
                })

            # Map USPS status description to our status
            status_desc = data.get('statusCategory', '')
            mapped_status = 'unknown'
            for usps_status, our_status in USPS_STATUS_MAP.items():
                if usps_status.lower() in status_desc.lower():
                    mapped_status = our_status
                    break

            return {
                'status': mapped_status,
                'est_delivery_date': data.get('expectedDeliveryDate', None),
                'events': events,
            }
        except Exception as e:
            logger.error(f"USPS tracking failed for {tracking_number}: {e}", exc_info=True)
            raise

    @staticmethod
    def build_parcel(listing):
        """Build parcel dict from listing fields or its shipping profile.

        Identical to EasyPostService — provider-agnostic.
        """
        weight = listing.weight_oz
        length = listing.length_in
        width = listing.width_in
        height = listing.height_in

        profile = listing.shipping_profile
        if profile:
            weight = weight or profile.weight_oz
            length = length or profile.length_in
            width = width or profile.width_in
            height = height or profile.height_in

        parcel = {
            'weight': float(weight or 2),
            'length': float(length or 9.5),
            'width': float(width or 6.5),
            'height': float(height or 0.25),
        }

        if profile and profile.predefined_package:
            parcel['predefined_package'] = profile.predefined_package

        return parcel

    @staticmethod
    def build_customs_info(listing, value):
        """Build customs info dict for international shipments.

        Identical to EasyPostService — provider-agnostic.
        """
        description = listing.customs_description
        hs_tariff = listing.hs_tariff_number

        profile = listing.shipping_profile
        if profile:
            description = description or profile.customs_description
            hs_tariff = hs_tariff or profile.hs_tariff_number

        return {
            'customs_certify': True,
            'customs_signer': listing.seller.get_full_name() or listing.seller.username,
            'contents_type': 'merchandise',
            'restriction_type': 'none',
            'customs_items': [{
                'description': description or listing.title[:50],
                'quantity': 1,
                'value': float(value),
                'weight': float(listing.weight_oz or 2),
                'origin_country': 'US',
                'hs_tariff_number': hs_tariff or '',
            }],
        }

    @staticmethod
    def process_tracking_webhook(payload):
        """USPS does not support webhooks — use poll_usps_tracking task instead."""
        raise NotImplementedError("USPS does not support webhooks. Use poll_usps_tracking Celery task.")
