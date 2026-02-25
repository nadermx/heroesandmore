from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from shipping.models import Address, ShippingProfile, ShippingLabel
from marketplace.models import Listing, Order
from marketplace.services.easypost_service import EasyPostService
from api.permissions import IsOwner

from .serializers import (
    AddressSerializer, ShippingProfileSerializer, ShippingLabelSerializer,
    ShippingRateSerializer, ValidateAddressSerializer, GetRatesSerializer,
    BuyLabelSerializer, TrackingSerializer,
)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ShippingProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ShippingProfile.objects.filter(is_active=True)
    serializer_class = ShippingProfileSerializer
    permission_classes = []


@api_view(['POST'])
@permission_classes([])
def validate_address(request):
    """Verify a shipping address via EasyPost."""
    serializer = ValidateAddressSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    result = EasyPostService.verify_address(serializer.validated_data)
    return Response(result)


@api_view(['POST'])
@permission_classes([])
def get_rates(request):
    """Get shipping rates for a listing + destination address."""
    serializer = GetRatesSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    try:
        listing = Listing.objects.get(pk=data['listing_id'], shipping_mode='calculated')
    except Listing.DoesNotExist:
        return Response({'error': 'Listing not found or does not use calculated shipping'},
                        status=status.HTTP_404_NOT_FOUND)

    seller_profile = listing.seller.profile
    if not seller_profile.default_ship_from:
        return Response({'error': 'Seller has not configured a ship-from address'},
                        status=status.HTTP_400_BAD_REQUEST)

    from_address = seller_profile.default_ship_from.to_easypost_dict()
    to_address = {k: v for k, v in data.items() if k != 'listing_id'}
    parcel = EasyPostService.build_parcel(listing)

    customs_info = None
    if to_address.get('country', 'US') != 'US':
        customs_info = EasyPostService.build_customs_info(listing, float(listing.get_current_price()))

    try:
        rates = EasyPostService.get_rates(from_address, to_address, parcel, customs_info)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    rate_serializer = ShippingRateSerializer(rates, many=True)
    return Response({'rates': rate_serializer.data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def buy_label(request, order_id):
    """Buy a shipping label for an order (seller only)."""
    try:
        order = Order.objects.get(pk=order_id, seller=request.user, status='paid')
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = BuyLabelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        label_data = EasyPostService.buy_label(
            serializer.validated_data['shipment_id'],
            serializer.validated_data['rate_id'],
        )

        label = ShippingLabel.objects.create(
            order=order,
            easypost_shipment_id=serializer.validated_data['shipment_id'],
            easypost_label_id=serializer.validated_data['rate_id'],
            carrier=label_data['carrier'],
            service=label_data['service'],
            rate=label_data['rate'],
            tracking_number=label_data['tracking_number'],
            label_url=label_data['label_url'],
        )

        from django.utils import timezone
        order.tracking_number = label_data['tracking_number']
        order.tracking_carrier = label_data['carrier']
        order.label_cost = label_data['rate']
        order.status = 'shipped'
        order.shipped_at = timezone.now()
        order.save(update_fields=[
            'tracking_number', 'tracking_carrier', 'label_cost',
            'status', 'shipped_at', 'updated'
        ])

        try:
            from alerts.tasks import send_order_notifications
            send_order_notifications.delay(order.id, 'shipped')
        except Exception:
            pass

        return Response(ShippingLabelSerializer(label).data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def label_detail(request, order_id):
    """Get label details for an order."""
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.user != order.seller and request.user != order.buyer:
        return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

    labels = ShippingLabel.objects.filter(order=order)
    return Response(ShippingLabelSerializer(labels, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def void_label(request, order_id):
    """Void a shipping label."""
    try:
        order = Order.objects.get(pk=order_id, seller=request.user)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    label = ShippingLabel.objects.filter(order=order, is_voided=False).first()
    if not label:
        return Response({'error': 'No active label found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        EasyPostService.refund_label(label.easypost_shipment_id)
        from django.utils import timezone
        label.is_voided = True
        label.voided_at = timezone.now()
        label.save(update_fields=['is_voided', 'voided_at'])
        return Response({'status': 'voided'})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracking_info(request, order_id):
    """Get tracking info for an order."""
    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.user != order.seller and request.user != order.buyer:
        return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)

    if not order.tracking_number or not order.tracking_carrier:
        return Response({'error': 'No tracking info'}, status=status.HTTP_404_NOT_FOUND)

    try:
        result = EasyPostService.get_tracking(order.tracking_number, order.tracking_carrier)
        serializer = TrackingSerializer(result)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
