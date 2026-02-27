import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q

logger = logging.getLogger('alerts')


def _should_email(user, category):
    """Check if user has opted in to a specific email category."""
    profile = user.profile
    if not profile.email_notifications:
        return False
    return getattr(profile, f'email_{category}', True)


@shared_task
def check_wishlist_matches():
    """Check for new listings matching wishlist items"""
    from .models import WishlistItem, Alert

    # Get wishlist items with email notifications enabled
    items = WishlistItem.objects.filter(notify_email=True).select_related('wishlist__user')

    for item in items:
        # Find new listings since last check (within 24 hours)
        matches = item.get_matching_listings().filter(
            created__gte=timezone.now() - timedelta(hours=24)
        )

        if matches.exists():
            user = item.wishlist.user
            for listing in matches[:5]:  # Limit to 5 per item
                # Check if alert already exists
                existing = Alert.objects.filter(
                    user=user,
                    listing=listing,
                    alert_type='wishlist_match'
                ).exists()

                if not existing:
                    Alert.objects.create(
                        user=user,
                        alert_type='wishlist_match',
                        title=f'New match: {listing.title}',
                        message=f'A new listing matching your wishlist "{item.search_query}" is available for ${listing.price}',
                        link=listing.get_absolute_url(),
                        listing=listing,
                    )


@shared_task
def check_saved_searches():
    """Check saved searches for new matches"""
    from .models import SavedSearch, Alert
    from marketplace.models import Listing
    from django.db.models import Q

    searches = SavedSearch.objects.filter(notify_email=True).select_related('user', 'category')

    for search in searches:
        # Build query
        listings = Listing.objects.filter(status='active', created__gt=search.last_checked)

        if search.query:
            listings = listings.filter(
                Q(title__icontains=search.query) | Q(description__icontains=search.query)
            )

        if search.category:
            listings = listings.filter(category=search.category)

        if search.min_price:
            listings = listings.filter(price__gte=search.min_price)

        if search.max_price:
            listings = listings.filter(price__lte=search.max_price)

        if search.condition:
            listings = listings.filter(condition=search.condition)

        if search.listing_type:
            listings = listings.filter(listing_type=search.listing_type)

        # Create alerts for matches
        for listing in listings[:10]:
            Alert.objects.create(
                user=search.user,
                alert_type='new_listing',
                title=f'New listing: {listing.title}',
                message=f'A new listing matching your search "{search.name}" is available',
                link=listing.get_absolute_url(),
                listing=listing,
            )

        # Update last checked
        search.last_checked = timezone.now()
        search.save(update_fields=['last_checked'])


@shared_task
def check_ending_auctions():
    """Notify bidders about auctions ending soon"""
    from .models import Alert
    from marketplace.models import Listing, Bid

    # Find auctions ending in the next hour
    ending_soon = Listing.objects.filter(
        status='active',
        listing_type='auction',
        auction_end__gt=timezone.now(),
        auction_end__lte=timezone.now() + timedelta(hours=1)
    )

    for listing in ending_soon:
        # Get unique bidders
        bidders = Bid.objects.filter(listing=listing).values_list('bidder', flat=True).distinct()

        for bidder_id in bidders:
            # Check if we already sent this alert
            existing = Alert.objects.filter(
                user_id=bidder_id,
                listing=listing,
                alert_type='auction_ending',
                created__gte=timezone.now() - timedelta(hours=2)
            ).exists()

            if not existing:
                Alert.objects.create(
                    user_id=bidder_id,
                    alert_type='auction_ending',
                    title=f'Auction ending: {listing.title}',
                    message=f'The auction you bid on is ending soon! Current price: ${listing.get_current_price()}',
                    link=listing.get_absolute_url(),
                    listing=listing,
                )


@shared_task
def send_alert_emails():
    """Send email for unread alerts"""
    from .models import Alert

    # Get alerts that haven't been emailed
    alerts = Alert.objects.filter(emailed=False).select_related('user')

    # Group by user
    user_alerts = {}
    for alert in alerts:
        if _should_email(alert.user, 'notifications'):
            if alert.user_id not in user_alerts:
                user_alerts[alert.user_id] = []
            user_alerts[alert.user_id].append(alert)

    # Send digest emails
    for user_id, user_alert_list in user_alerts.items():
        user = user_alert_list[0].user

        subject = f"You have {len(user_alert_list)} new notification(s) on HeroesAndMore"

        message_parts = []
        for alert in user_alert_list[:10]:  # Limit to 10 per email
            message_parts.append(f"- {alert.title}\n  {alert.message}")

        message = f"Hi {user.username},\n\nYou have new notifications:\n\n"
        message += "\n\n".join(message_parts)
        message += "\n\nVisit https://heroesandmore.com/alerts/ to view all notifications."

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        except Exception:
            pass

        # Mark as emailed
        Alert.objects.filter(id__in=[a.id for a in user_alert_list]).update(emailed=True)


@shared_task
def notify_outbid(listing_id, new_bid_amount, new_bidder_id):
    """Notify previous high bidder they've been outbid"""
    from django.template.loader import render_to_string
    from .models import Alert
    from marketplace.models import Listing, Bid

    listing = Listing.objects.get(id=listing_id)

    # Get the previous high bidder (excluding the new bidder)
    previous_bid = Bid.objects.filter(
        listing=listing
    ).exclude(
        bidder_id=new_bidder_id
    ).order_by('-amount').first()

    if previous_bid:
        current_price = listing.get_current_price()

        # In-app alert
        Alert.objects.create(
            user=previous_bid.bidder,
            alert_type='outbid',
            title=f'Outbid on: {listing.title}',
            message=f'You\'ve been outbid! Current price: ${current_price}. Place a higher maximum bid to win.',
            link=listing.get_absolute_url(),
            listing=listing,
        )

        # Email notification
        if previous_bid.bidder.email and _should_email(previous_bid.bidder, 'bidding'):
            site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
            context = {
                'listing': listing,
                'user': previous_bid.bidder,
                'current_price': current_price,
                'site_url': site_url,
            }
            try:
                html_content = render_to_string('marketplace/emails/outbid.html', context)
                send_mail(
                    subject=f'You\'ve been outbid on: {listing.title}',
                    message=f'You\'ve been outbid on {listing.title}. Current price: ${current_price}. Place a higher maximum bid to win.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[previous_bid.bidder.email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass


@shared_task
def send_order_notifications(order_id, event_type):
    """
    Send email notifications for order events.

    event_type can be:
    - 'paid': Order confirmed (buyer) + New sale (seller)
    - 'shipped': Order shipped (buyer)
    - 'delivered': Order delivered (seller)
    - 'payment_failed': Payment failed (buyer)
    """
    from django.template.loader import render_to_string
    from marketplace.models import Order
    from .models import Alert

    try:
        order = Order.objects.select_related(
            'buyer', 'seller', 'listing', 'buyer__profile', 'seller__profile'
        ).get(id=order_id)
    except Order.DoesNotExist:
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'order': order, 'site_url': site_url}

    if event_type == 'paid':
        # Email to buyer: Order confirmed
        buyer_email = order.buyer_email
        if buyer_email:
            html_content = render_to_string('marketplace/emails/order_confirmed.html', context)
            try:
                send_mail(
                    subject=f'Order Confirmed - #{order.id}',
                    message=f'Your order #{order.id} for {order.listing.title} has been confirmed.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[buyer_email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass

        # Email to seller: New sale
        if order.seller.email:
            html_content = render_to_string('marketplace/emails/new_sale.html', context)
            try:
                send_mail(
                    subject=f'You made a sale! - Order #{order.id}',
                    message=f'Your item {order.listing.title} has sold for ${order.item_price}.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.seller.email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass

        # Create in-app alerts (skip buyer alert for guest orders)
        if order.buyer:
            Alert.objects.create(
                user=order.buyer,
                alert_type='order_update',
                title=f'Order #{order.id} Confirmed',
                message=f'Your order for {order.listing.title} has been confirmed.',
                link=f'/marketplace/order/{order.id}/',
            )
        Alert.objects.create(
            user=order.seller,
            alert_type='order_update',
            title=f'New Sale! Order #{order.id}',
            message=f'Your item {order.listing.title} has sold for ${order.item_price}.',
            link=f'/marketplace/order/{order.id}/',
        )

    elif event_type == 'shipped':
        # Email to buyer: Order shipped
        buyer_email = order.buyer_email
        if buyer_email:
            html_content = render_to_string('marketplace/emails/order_shipped.html', context)
            try:
                send_mail(
                    subject=f'Your order has shipped - #{order.id}',
                    message=f'Your order #{order.id} has been shipped via {order.tracking_carrier}. Tracking: {order.tracking_number}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[buyer_email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass

        # In-app alert (skip for guest orders)
        if order.buyer:
            Alert.objects.create(
                user=order.buyer,
                alert_type='order_update',
                title=f'Order #{order.id} Shipped',
                message=f'Your order has been shipped! Tracking: {order.tracking_number}',
                link=f'/marketplace/order/{order.id}/',
            )

    elif event_type == 'delivered':
        # Email to seller: Delivery confirmed
        if order.seller.email:
            html_content = render_to_string('marketplace/emails/order_delivered.html', context)
            try:
                send_mail(
                    subject=f'Delivery Confirmed - Order #{order.id}',
                    message=f'The buyer has confirmed receipt of order #{order.id}. Your payout: ${order.seller_payout}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.seller.email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass

        # In-app alert
        Alert.objects.create(
            user=order.seller,
            alert_type='order_update',
            title=f'Order #{order.id} Delivered',
            message=f'The buyer confirmed receipt. Your payout: ${order.seller_payout}',
            link=f'/marketplace/order/{order.id}/',
        )

    elif event_type == 'payment_failed':
        # Email to buyer: Payment failed
        if order.buyer.email:
            html_content = render_to_string('marketplace/emails/payment_failed.html', context)
            try:
                send_mail(
                    subject=f'Payment Issue - Order #{order.id}',
                    message=f'We were unable to process your payment for order #{order.id}. Please try again.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.buyer.email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass

        # In-app alert
        Alert.objects.create(
            user=order.buyer,
            alert_type='order_update',
            title=f'Payment Failed - Order #{order.id}',
            message=f'We were unable to process your payment. Please try again.',
            link=f'/marketplace/{order.listing.id}/checkout/',
        )


@shared_task
def send_auction_won_notification(order_id):
    """
    Notify auction winner that they won and need to complete payment.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Order
    from .models import Alert

    try:
        order = Order.objects.select_related(
            'buyer', 'seller', 'listing', 'buyer__profile', 'seller__profile'
        ).get(id=order_id)
    except Order.DoesNotExist:
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'order': order, 'site_url': site_url}

    # Email to winner
    if order.buyer.email and _should_email(order.buyer, 'bidding'):
        html_content = render_to_string('marketplace/emails/auction_won.html', context)
        try:
            send_mail(
                subject=f'You won the auction! - {order.listing.title}',
                message=f'Congratulations! You won the auction for {order.listing.title} with a bid of ${order.item_price}. Complete your purchase now.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.buyer.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # Email to seller
    if order.seller.email and _should_email(order.seller, 'bidding'):
        html_content = render_to_string('marketplace/emails/auction_ended_seller.html', context)
        try:
            send_mail(
                subject=f'Your auction has ended - {order.listing.title}',
                message=f'Your auction for {order.listing.title} has ended. Winning bid: ${order.item_price}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.seller.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alerts
    Alert.objects.create(
        user=order.buyer,
        alert_type='auction_won',
        title=f'You won: {order.listing.title}',
        message=f'Congratulations! Your winning bid: ${order.item_price}. Complete your purchase now.',
        link=f'/marketplace/{order.listing.id}/checkout/',
    )
    Alert.objects.create(
        user=order.seller,
        alert_type='auction_ended',
        title=f'Auction ended: {order.listing.title}',
        message=f'Your auction has ended with a winning bid of ${order.item_price}.',
        link=f'/marketplace/order/{order.id}/',
    )


@shared_task
def send_offer_accepted_notification(order_id):
    """
    Notify buyer that their offer was accepted and they can complete payment.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Order
    from .models import Alert

    try:
        order = Order.objects.select_related(
            'buyer', 'seller', 'listing', 'buyer__profile', 'seller__profile'
        ).get(id=order_id)
    except Order.DoesNotExist:
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'order': order, 'site_url': site_url}

    # Email to buyer
    if order.buyer.email and _should_email(order.buyer, 'offers'):
        html_content = render_to_string('marketplace/emails/offer_accepted.html', context)
        try:
            send_mail(
                subject=f'Your offer was accepted! - {order.listing.title}',
                message=f'Great news! Your offer of ${order.item_price} for {order.listing.title} was accepted. Complete your purchase now.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.buyer.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alert
    Alert.objects.create(
        user=order.buyer,
        alert_type='offer_accepted',
        title=f'Offer accepted: {order.listing.title}',
        message=f'Your offer of ${order.item_price} was accepted! Complete your purchase now.',
        link=f'/marketplace/{order.listing.id}/checkout/',
    )


@shared_task
def send_refund_notification(order_id, refund_amount):
    """
    Notify buyer that a refund has been issued.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Order
    from .models import Alert

    try:
        order = Order.objects.select_related(
            'buyer', 'seller', 'listing'
        ).get(id=order_id)
    except Order.DoesNotExist:
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'order': order, 'site_url': site_url, 'refund_amount': refund_amount}

    # Email to buyer
    if order.buyer.email:
        html_content = render_to_string('marketplace/emails/refund_issued.html', context)
        try:
            send_mail(
                subject=f'Refund Issued - Order #{order.id}',
                message=f'A refund of ${refund_amount} has been issued for order #{order.id}. It may take 5-10 business days to appear on your statement.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.buyer.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alert
    Alert.objects.create(
        user=order.buyer,
        alert_type='order_update',
        title=f'Refund Issued - Order #{order.id}',
        message=f'A refund of ${refund_amount} has been issued.',
        link=f'/marketplace/order/{order.id}/',
    )


@shared_task
def send_new_offer_notification(offer_id):
    """
    Notify seller that they received a new offer on their listing.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Offer
    from .models import Alert

    try:
        offer = Offer.objects.select_related(
            'listing', 'listing__seller', 'buyer'
        ).get(id=offer_id)
    except Offer.DoesNotExist:
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'offer': offer, 'site_url': site_url}

    seller = offer.listing.seller

    # Email to seller
    if seller.email and _should_email(seller, 'offers'):
        html_content = render_to_string('marketplace/emails/new_offer.html', context)
        try:
            send_mail(
                subject=f'New Offer on {offer.listing.title}',
                message=f'{offer.buyer.username} made an offer of ${offer.amount} on your listing "{offer.listing.title}".',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[seller.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alert
    Alert.objects.create(
        user=seller,
        alert_type='new_offer',
        title=f'New Offer: ${offer.amount}',
        message=f'{offer.buyer.username} made an offer of ${offer.amount} on "{offer.listing.title}".',
        link=f'/accounts/seller/',
        listing=offer.listing,
    )


@shared_task
def send_counter_offer_notification(offer_id):
    """
    Notify buyer that seller made a counter-offer.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Offer
    from .models import Alert

    try:
        offer = Offer.objects.select_related(
            'listing', 'listing__seller', 'buyer'
        ).get(id=offer_id)
    except Offer.DoesNotExist:
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'offer': offer, 'site_url': site_url}

    buyer = offer.buyer

    # Email to buyer
    if buyer.email and _should_email(buyer, 'offers'):
        html_content = render_to_string('marketplace/emails/counter_offer.html', context)
        try:
            send_mail(
                subject=f'Counter Offer on {offer.listing.title}',
                message=f'The seller has countered your offer with ${offer.counter_amount} for "{offer.listing.title}".',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[buyer.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alert
    Alert.objects.create(
        user=buyer,
        alert_type='counter_offer',
        title=f'Counter Offer: ${offer.counter_amount}',
        message=f'The seller countered with ${offer.counter_amount} on "{offer.listing.title}". Respond within 48 hours.',
        link=f'/marketplace/{offer.listing.id}/',
        listing=offer.listing,
    )


@shared_task
def send_counter_offer_accepted_notification(offer_id, order_id):
    """
    Notify seller that buyer accepted their counter-offer.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Offer, Order
    from .models import Alert

    try:
        offer = Offer.objects.select_related(
            'listing', 'listing__seller', 'buyer'
        ).get(id=offer_id)
        order = Order.objects.get(id=order_id)
    except (Offer.DoesNotExist, Order.DoesNotExist):
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'offer': offer, 'order': order, 'site_url': site_url}

    seller = offer.listing.seller

    # Email to seller
    if seller.email and _should_email(seller, 'offers'):
        html_content = render_to_string('marketplace/emails/counter_offer_accepted.html', context)
        try:
            send_mail(
                subject=f'Counter Offer Accepted - {offer.listing.title}',
                message=f'{offer.buyer.username} accepted your counter-offer of ${offer.counter_amount} for "{offer.listing.title}".',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[seller.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alert
    Alert.objects.create(
        user=seller,
        alert_type='offer_accepted',
        title=f'Counter Offer Accepted!',
        message=f'{offer.buyer.username} accepted your counter-offer of ${offer.counter_amount}.',
        link=f'/marketplace/order/{order.id}/',
    )


@shared_task
def send_cancellation_notification(order_id, cancelled_by):
    """
    Notify both parties that an order was cancelled.
    cancelled_by: 'buyer' or 'seller'
    """
    from django.template.loader import render_to_string
    from marketplace.models import Order
    from .models import Alert

    try:
        order = Order.objects.select_related(
            'buyer', 'seller', 'listing'
        ).get(id=order_id)
    except Order.DoesNotExist:
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'order': order, 'site_url': site_url, 'cancelled_by': cancelled_by}

    # Determine who to notify
    if cancelled_by == 'buyer':
        notify_user = order.seller
        other_party = 'The buyer'
    else:
        notify_user = order.buyer
        other_party = 'The seller'

    # Email notification
    if notify_user.email:
        html_content = render_to_string('marketplace/emails/order_cancelled.html', context)
        try:
            send_mail(
                subject=f'Order Cancelled - #{order.id}',
                message=f'{other_party} has cancelled order #{order.id} for {order.listing.title if order.listing else "item"}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notify_user.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alert
    Alert.objects.create(
        user=notify_user,
        alert_type='order_update',
        title=f'Order #{order.id} Cancelled',
        message=f'{other_party} has cancelled this order.',
        link=f'/marketplace/order/{order.id}/',
    )


@shared_task
def send_listing_expired_notification(listing_id):
    """
    Notify seller that their auction ended with no bids.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Listing
    from .models import Alert

    try:
        listing = Listing.objects.select_related(
            'seller', 'seller__profile', 'category'
        ).get(id=listing_id)
    except Listing.DoesNotExist:
        return

    seller = listing.seller
    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'listing': listing, 'seller': seller, 'site_url': site_url}

    # Email to seller
    if seller.email and _should_email(seller, 'listings'):
        html_content = render_to_string('marketplace/emails/listing_expired.html', context)
        try:
            send_mail(
                subject=f'Your auction ended without bids - {listing.title}',
                message=f'Your auction for "{listing.title}" ended without any bids. You can relist it from your My Listings page.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[seller.email],
                html_message=html_content,
                fail_silently=True,
            )
        except Exception:
            pass

    # In-app alert
    Alert.objects.create(
        user=seller,
        alert_type='listing_expired',
        title=f'Auction expired: {listing.title}',
        message=f'Your auction ended without any bids. You can relist it or adjust the price.',
        link=f'/marketplace/my-listings/?status=expired',
        listing=listing,
    )


@shared_task
def notify_trusted_sellers_new_event(event_id):
    """
    Notify all trusted sellers when a platform event opens for submissions.
    Triggered from AuctionEventAdmin.save_model().
    """
    from django.template.loader import render_to_string
    from marketplace.models import AuctionEvent
    from accounts.models import Profile
    from .models import Alert

    try:
        event = AuctionEvent.objects.get(id=event_id)
    except AuctionEvent.DoesNotExist:
        logger.error(f"notify_trusted_sellers_new_event: event {event_id} not found")
        return

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'event': event, 'site_url': site_url}

    trusted_profiles = Profile.objects.filter(
        is_trusted_seller=True
    ).select_related('user')

    sent = 0
    for profile in trusted_profiles:
        user = profile.user
        if not user.is_active:
            continue

        # Create in-app alert
        Alert.objects.create(
            user=user,
            alert_type='auction_event',
            title=f'Official Auction: {event.name}',
            message=f'A new platform auction is accepting submissions! Deadline: {event.submission_deadline.strftime("%b %d, %Y") if event.submission_deadline else "TBD"}. Submit your best lots now.',
            link=f'/marketplace/auctions/{event.slug}/submit/',
        )

        # Send email
        if user.email and _should_email(user, 'marketing'):
            html_content = render_to_string(
                'marketplace/emails/auction_event_submissions_open.html', context
            )
            try:
                send_mail(
                    subject=f'Submit Your Lots: {event.name} - HeroesAndMore',
                    message=f'A new official auction "{event.name}" is now accepting submissions from Trusted Sellers. Submit your lots at {site_url}/marketplace/auctions/{event.slug}/submit/',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send auction event email to {user.email}: {e}")

        sent += 1

    logger.info(f"Notified {sent} trusted sellers about event '{event.name}'")
    return sent


@shared_task
def send_relist_reminders():
    """
    Send reminders for listings that expired 3 days ago and haven't been relisted.
    Runs daily.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Listing
    from .models import Alert

    three_days_ago = timezone.now() - timedelta(days=3)
    # Find listings expired ~3 days ago (within a 24-hour window)
    expired_listings = Listing.objects.filter(
        status='expired',
        expired_at__date=three_days_ago.date(),
    ).select_related('seller', 'seller__profile', 'category')

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    sent = 0

    for listing in expired_listings:
        # Skip if we already sent a relist reminder for this listing
        already_reminded = Alert.objects.filter(
            user=listing.seller,
            listing=listing,
            alert_type='relist_reminder',
        ).exists()

        if already_reminded:
            continue

        seller = listing.seller
        context = {'listing': listing, 'seller': seller, 'site_url': site_url}

        # Email
        if seller.email and _should_email(seller, 'reminders'):
            html_content = render_to_string('marketplace/emails/relist_reminder.html', context)
            try:
                send_mail(
                    subject=f'Still want to sell? - {listing.title}',
                    message=f'Your listing "{listing.title}" expired 3 days ago. Relist it to give it another chance!',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[seller.email],
                    html_message=html_content,
                    fail_silently=True,
                )
            except Exception:
                pass

        # In-app alert
        Alert.objects.create(
            user=seller,
            alert_type='relist_reminder',
            title=f'Relist your item? {listing.title}',
            message=f'Your listing expired 3 days ago. Consider relisting with a lower starting price.',
            link=f'/marketplace/{listing.id}/relist/',
            listing=listing,
        )
        sent += 1

    if sent:
        logger.info(f"Sent {sent} relist reminders")

    return sent


@shared_task
def send_welcome_email(user_id):
    """
    Send welcome email with live auctions to new user.
    Triggered by allauth user_signed_up signal.
    """
    from django.template.loader import render_to_string
    from django.contrib.auth.models import User
    from marketplace.models import Listing

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return

    if not user.email:
        return

    now = timezone.now()
    featured_auctions = (
        Listing.objects.filter(
            status='active', listing_type='auction', auction_end__gt=now,
        )
        .select_related('category')
        .order_by('auction_end')[:6]
    )

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {
        'user': user,
        'featured_auctions': featured_auctions,
        'site_url': site_url,
    }

    html_content = render_to_string('marketplace/emails/welcome_auctions.html', context)
    try:
        send_mail(
            subject='Welcome to HeroesAndMore — Live Auctions Happening Now',
            message=f'Welcome {user.username}! Check out live auctions at {site_url}/marketplace/?type=auction',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content,
            fail_silently=True,
        )
        logger.info(f"Welcome email sent to {user.email}")
    except Exception:
        logger.error(f"Failed to send welcome email to {user.email}", exc_info=True)


@shared_task
def send_weekly_auction_digest():
    """
    Weekly auction digest — sent Friday 10 AM.
    Shows auctions ending this weekend, most watched, total bids this week.
    """
    from django.template.loader import render_to_string
    from django.contrib.auth.models import User
    from marketplace.models import Listing, Bid
    from accounts.models import Profile

    now = timezone.now()
    weekend_end = now + timedelta(days=3)

    # Auctions ending this weekend
    ending_weekend = (
        Listing.objects.filter(
            status='active', listing_type='auction',
            auction_end__gt=now, auction_end__lte=weekend_end,
        )
        .select_related('category')
        .annotate(save_count=Count('saves'))
        .order_by('-save_count')[:8]
    )

    # Most watched active auctions
    most_watched = (
        Listing.objects.filter(
            status='active', listing_type='auction', auction_end__gt=now,
        )
        .annotate(save_count=Count('saves'))
        .order_by('-save_count')[:6]
    )

    # Stats this week
    week_ago = now - timedelta(days=7)
    total_bids_week = Bid.objects.filter(created__gte=week_ago).count()

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')

    # Send to users with email notifications + marketing enabled
    users = User.objects.filter(
        profile__email_notifications=True,
        profile__email_marketing=True,
        is_active=True,
    ).exclude(email='')

    sent = 0
    for user in users.iterator():
        context = {
            'user': user,
            'ending_weekend': ending_weekend,
            'most_watched': most_watched,
            'total_bids_week': total_bids_week,
            'site_url': site_url,
        }
        html_content = render_to_string('marketplace/emails/weekly_auction_digest.html', context)
        try:
            send_mail(
                subject='This Week on HeroesAndMore — Auctions Ending Soon',
                message=f'Check out auctions ending this weekend at {site_url}/marketplace/?type=auction&sort=ending',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_content,
                fail_silently=True,
            )
            sent += 1
        except Exception:
            pass

    logger.info(f"Weekly auction digest sent to {sent} users")
    return sent


@shared_task
def send_watched_auction_final_24h():
    """
    Notify users when auctions they saved are ending in 24 hours.
    Runs every 30 minutes.
    """
    from django.template.loader import render_to_string
    from marketplace.models import Listing, SavedListing
    from .models import Alert

    now = timezone.now()
    twenty_four_hours = now + timedelta(hours=24)

    # Auctions ending in next 24 hours
    ending_soon = Listing.objects.filter(
        status='active', listing_type='auction',
        auction_end__gt=now, auction_end__lte=twenty_four_hours,
    )

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    sent = 0

    for listing in ending_soon:
        # Users who saved this listing
        saved_entries = SavedListing.objects.filter(
            listing=listing,
        ).select_related('user', 'user__profile')

        for saved in saved_entries:
            user = saved.user
            if not user.is_active or not user.email:
                continue
            if not _should_email(user, 'marketing'):
                continue

            # Dedup: skip if already alerted for this listing in last 24h
            already_sent = Alert.objects.filter(
                user=user,
                listing=listing,
                alert_type='auction_final_24h',
                created__gte=now - timedelta(hours=24),
            ).exists()
            if already_sent:
                continue

            context = {
                'user': user,
                'listing': listing,
                'site_url': site_url,
            }
            html_content = render_to_string('marketplace/emails/auction_final_24h.html', context)
            try:
                send_mail(
                    subject=f'Last chance: {listing.title} — ending soon!',
                    message=f'An auction you saved is ending in less than 24 hours: {listing.title}. Bid now at {site_url}{listing.get_absolute_url()}',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_content,
                    fail_silently=True,
                )
                sent += 1
            except Exception:
                pass

            # Create in-app alert for dedup tracking
            Alert.objects.create(
                user=user,
                alert_type='auction_final_24h',
                title=f'Ending soon: {listing.title}',
                message=f'An auction you saved is ending in less than 24 hours!',
                link=listing.get_absolute_url(),
                listing=listing,
            )

    if sent:
        logger.info(f"Sent {sent} final 24h auction alerts")
    return sent


@shared_task
def send_weekly_results_recap():
    """
    Weekly results recap — sent Monday 10 AM.
    Shows auctions that ended last week with bids, top results.
    """
    from django.template.loader import render_to_string
    from django.contrib.auth.models import User
    from marketplace.models import Listing, Order

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    # Top results from last week (auctions that sold)
    top_results = (
        Order.objects.filter(
            created__gte=week_ago,
            status__in=['paid', 'shipped', 'delivered', 'completed'],
            listing__listing_type='auction',
        )
        .select_related('listing', 'listing__category')
        .order_by('-item_price')[:10]
    )

    if not top_results:
        logger.info("No auction results last week, skipping recap")
        return 0

    total_sold = top_results.count()

    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')

    users = User.objects.filter(
        profile__email_notifications=True,
        profile__email_marketing=True,
        is_active=True,
    ).exclude(email='')

    sent = 0
    for user in users.iterator():
        context = {
            'user': user,
            'top_results': top_results,
            'total_sold': total_sold,
            'site_url': site_url,
        }
        html_content = render_to_string('marketplace/emails/weekly_recap.html', context)
        try:
            send_mail(
                subject='Last Week on HeroesAndMore — Top Auction Results',
                message=f'Check out last week\'s top auction results at {site_url}/marketplace/',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_content,
                fail_silently=True,
            )
            sent += 1
        except Exception:
            pass

    logger.info(f"Weekly recap sent to {sent} users")
    return sent
