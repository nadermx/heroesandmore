import logging
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('marketplace.services')


class EasyPostService:
    """EasyPost shipping operations — follows StripeService static method pattern."""

    @staticmethod
    def get_client():
        """Returns configured easypost.Client instance."""
        import easypost
        api_key = getattr(settings, 'EASYPOST_API_KEY', None)
        if not api_key:
            raise ValueError("EASYPOST_API_KEY is not configured")
        return easypost.EasyPostClient(api_key)

    @staticmethod
    def verify_address(address_dict):
        """Verify and correct an address via EasyPost.

        Args:
            address_dict: dict with keys: name, street1, street2, city, state, zip, country, phone

        Returns:
            dict with: verified (bool), address (corrected dict), easypost_id, errors (list)
        """
        client = EasyPostService.get_client()
        try:
            address = client.address.create(**address_dict)
            verified = client.address.verify(address.id)

            return {
                'verified': True,
                'easypost_id': verified.id,
                'address': {
                    'name': verified.name or address_dict.get('name', ''),
                    'company': verified.company or '',
                    'street1': verified.street1,
                    'street2': verified.street2 or '',
                    'city': verified.city,
                    'state': verified.state,
                    'zip': verified.zip,
                    'country': verified.country,
                    'phone': verified.phone or '',
                },
                'errors': [],
            }
        except Exception as e:
            logger.warning(f"Address verification failed: {e}")
            return {
                'verified': False,
                'easypost_id': '',
                'address': address_dict,
                'errors': [str(e)],
            }

    @staticmethod
    def get_rates(from_address, to_address, parcel, customs_info=None):
        """Get shipping rates for a shipment.

        Args:
            from_address: dict (easypost address format)
            to_address: dict (easypost address format)
            parcel: dict with weight, length, width, height
            customs_info: dict (optional, for international)

        Returns:
            list of dicts: [{carrier, service, rate, days, rate_id, shipment_id}]
        """
        client = EasyPostService.get_client()
        try:
            shipment_params = {
                'from_address': from_address,
                'to_address': to_address,
                'parcel': parcel,
            }
            if customs_info:
                shipment_params['customs_info'] = customs_info

            shipment = client.shipment.create(**shipment_params)

            rates = []
            for rate in shipment.rates:
                rates.append({
                    'carrier': rate.carrier,
                    'service': rate.service,
                    'rate': Decimal(rate.rate),
                    'days': rate.est_delivery_days,
                    'rate_id': rate.id,
                    'shipment_id': shipment.id,
                })

            # Sort by price
            rates.sort(key=lambda r: r['rate'])
            return rates

        except Exception as e:
            logger.error(f"Failed to get shipping rates: {e}", exc_info=True)
            raise

    @staticmethod
    def buy_label(shipment_id, rate_id, label_format='PDF'):
        """Purchase a shipping label.

        Returns:
            dict: {tracking_number, label_url, carrier, service, rate}
        """
        client = EasyPostService.get_client()
        try:
            shipment = client.shipment.buy(shipment_id, rate={'id': rate_id})

            result = {
                'tracking_number': shipment.tracking_code or '',
                'label_url': '',
                'carrier': shipment.selected_rate.carrier if shipment.selected_rate else '',
                'service': shipment.selected_rate.service if shipment.selected_rate else '',
                'rate': Decimal(shipment.selected_rate.rate) if shipment.selected_rate else Decimal('0'),
            }

            if shipment.postage_label:
                result['label_url'] = shipment.postage_label.label_url or ''

            logger.info(f"Label purchased: {result['tracking_number']} via {result['carrier']} {result['service']}")
            return result

        except Exception as e:
            logger.error(f"Failed to buy label for shipment {shipment_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def refund_label(shipment_id):
        """Void/refund a shipping label."""
        client = EasyPostService.get_client()
        try:
            shipment = client.shipment.refund(shipment_id)
            logger.info(f"Label refunded for shipment {shipment_id}")
            return {'status': shipment.refund_status}
        except Exception as e:
            logger.error(f"Failed to refund label for shipment {shipment_id}: {e}", exc_info=True)
            raise

    @staticmethod
    def get_tracking(tracking_number, carrier):
        """Get tracking events for a shipment."""
        client = EasyPostService.get_client()
        try:
            tracker = client.tracker.create(
                tracking_code=tracking_number,
                carrier=carrier,
            )
            events = []
            if tracker.tracking_details:
                for detail in tracker.tracking_details:
                    events.append({
                        'status': detail.status,
                        'message': detail.message,
                        'datetime': detail.datetime,
                        'city': getattr(detail.tracking_location, 'city', '') if detail.tracking_location else '',
                        'state': getattr(detail.tracking_location, 'state', '') if detail.tracking_location else '',
                    })
            return {
                'status': tracker.status,
                'est_delivery_date': tracker.est_delivery_date,
                'events': events,
            }
        except Exception as e:
            logger.error(f"Failed to get tracking for {tracking_number}: {e}", exc_info=True)
            raise

    @staticmethod
    def build_parcel(listing):
        """Build parcel dict from listing fields or its shipping profile.

        Priority: listing override fields > shipping profile > defaults
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

        # Fallback defaults (standard card envelope)
        parcel = {
            'weight': float(weight or 2),
            'length': float(length or 9.5),
            'width': float(width or 6.5),
            'height': float(height or 0.25),
        }

        # Use predefined package if profile has one
        if profile and profile.predefined_package:
            parcel['predefined_package'] = profile.predefined_package

        return parcel

    @staticmethod
    def build_customs_info(listing, value):
        """Build customs info dict for international shipments."""
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
        """Process EasyPost tracker.updated webhook event.

        Maps EasyPost statuses to order statuses:
        - in_transit -> shipped
        - delivered -> delivered
        """
        from marketplace.models import Order
        from shipping.models import ShippingLabel

        result = payload.get('result', {})
        tracking_code = result.get('tracking_code', '')
        status = result.get('status', '')

        if not tracking_code or not status:
            logger.warning("Tracking webhook missing tracking_code or status")
            return

        # Find order by tracking number
        order = None
        label = ShippingLabel.objects.filter(tracking_number=tracking_code).first()
        if label:
            order = label.order
        else:
            order = Order.objects.filter(tracking_number=tracking_code).first()

        if not order:
            logger.warning(f"No order found for tracking {tracking_code}")
            return

        status_map = {
            'in_transit': 'shipped',
            'out_for_delivery': 'shipped',
            'delivered': 'delivered',
        }

        new_status = status_map.get(status)
        if not new_status:
            return

        # Only advance status, never go backwards
        status_order = ['pending', 'payment_failed', 'paid', 'shipped', 'delivered', 'completed']
        try:
            current_idx = status_order.index(order.status)
            new_idx = status_order.index(new_status)
        except ValueError:
            return

        if new_idx <= current_idx:
            return

        order.status = new_status
        update_fields = ['status', 'updated']

        if new_status == 'shipped' and not order.shipped_at:
            order.shipped_at = timezone.now()
            update_fields.append('shipped_at')
        elif new_status == 'delivered' and not order.delivered_at:
            order.delivered_at = timezone.now()
            update_fields.append('delivered_at')

        order.save(update_fields=update_fields)
        logger.info(f"Order #{order.id} status updated to {new_status} via tracking webhook")

        # Send push notification on delivery
        if new_status == 'delivered' and order.buyer:
            try:
                from alerts.tasks import send_order_notifications
                send_order_notifications.delay(order.id, 'delivered')
            except Exception:
                pass
