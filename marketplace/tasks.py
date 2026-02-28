from datetime import timedelta
from decimal import Decimal
import logging
import stripe
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import Order, Listing, Bid

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@shared_task
def end_auctions():
    """
    Process ended auctions:
    - Find auctions that have ended with bids
    - Create orders for winning bidders
    - Notify winners and sellers
    - Update listing status
    """
    from .services.stripe_service import StripeService

    # Find auctions that ended but listing still active
    ended_auctions = Listing.objects.filter(
        listing_type='auction',
        status='active',
        auction_end__lte=timezone.now()
    ).select_related('seller', 'seller__profile')

    processed = 0

    for listing in ended_auctions:
        try:
            # Get the winning bid (highest)
            winning_bid = Bid.objects.filter(
                listing=listing
            ).order_by('-amount').first()

            if winning_bid:
                # Create order for the winner
                is_platform = hasattr(listing.seller, 'profile') and listing.seller.profile.is_platform_account
                platform_fee = StripeService.calculate_platform_fee(winning_bid.amount, listing.seller)
                seller_payout = Decimal('0') if is_platform else winning_bid.amount - platform_fee

                order = Order.objects.create(
                    buyer=winning_bid.bidder,
                    seller=listing.seller,
                    listing=listing,
                    item_price=winning_bid.amount,
                    shipping_price=listing.shipping_price,
                    amount=winning_bid.amount + listing.shipping_price,
                    platform_fee=platform_fee,
                    seller_payout=seller_payout,
                    status='pending',
                    shipping_address='',  # Buyer fills this at checkout
                )

                listing.record_sale(1)

                # Send notifications
                try:
                    from alerts.tasks import send_auction_won_notification
                    send_auction_won_notification.delay(order.id)
                except Exception as e:
                    logger.warning(f"Failed to send auction won notification: {e}")

                logger.info(f"Auction ended: Listing {listing.id} won by user {winning_bid.bidder.id} for ${winning_bid.amount}")
            else:
                # No bids - mark as expired/unsold
                listing.status = 'expired'
                listing.expired_at = timezone.now()
                listing.save(update_fields=['status', 'expired_at'])

                # Notify seller
                try:
                    from alerts.tasks import send_listing_expired_notification
                    send_listing_expired_notification.delay(listing.id)
                except Exception as e:
                    logger.warning(f"Failed to send listing expired notification: {e}")

                logger.info(f"Auction ended with no bids: Listing {listing.id}")

            # Deactivate all auto-bids for this listing
            from .services.autobid_service import AutoBidService
            AutoBidService.deactivate_listing_autobids(listing)

            processed += 1

        except Exception as e:
            logger.exception(f"Error processing ended auction {listing.id}: {e}")

    if processed:
        logger.info(f"Processed {processed} ended auctions")

    return processed


@shared_task
def activate_platform_events():
    """
    Auto-activate platform auction events when bidding_start is reached.
    Converts draft lots to active auctions and sets event status to live.
    Runs every 5 minutes.
    """
    from .models import AuctionEvent

    now = timezone.now()

    # Find events that should be live but aren't yet
    events = AuctionEvent.objects.filter(
        is_platform_event=True,
        status__in=['draft', 'preview'],
        bidding_start__lte=now,
    )

    activated = 0
    for event in events:
        lots = event.listings.filter(status='draft')
        count = lots.update(
            status='active',
            auction_end=event.bidding_end,
            listing_type='auction',
        )
        event.total_lots = event.listings.filter(status='active').count()
        event.status = 'live'
        event.save(update_fields=['total_lots', 'status'])
        activated += 1
        logger.info(
            f"Auto-activated platform event '{event.name}': {count} lots set live"
        )

    return activated


@shared_task
def expire_unpaid_orders():
    """Cancel unpaid orders that have been pending too long and release listings."""
    cutoff = timezone.now() - timedelta(minutes=settings.ORDER_PAYMENT_TIMEOUT_MINUTES)

    orders = Order.objects.filter(
        status__in=['pending', 'payment_failed'],
        created__lt=cutoff
    ).select_related('listing')

    expired_count = 0

    for order in orders:
        try:
            if order.stripe_payment_intent:
                try:
                    stripe.PaymentIntent.cancel(order.stripe_payment_intent)
                except Exception as e:
                    logger.warning(
                        "Failed to cancel PaymentIntent %s: %s",
                        order.stripe_payment_intent,
                        e
                    )

            order.status = 'cancelled'
            order.save(update_fields=['status', 'updated'])

            if order.listing:
                order.listing.reverse_sale(order.quantity)

            expired_count += 1
        except Exception as e:
            logger.exception("Error expiring order %s: %s", order.id, e)

    if expired_count:
        logger.info("Expired %s unpaid orders", expired_count)

    return expired_count
