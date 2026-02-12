import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('alerts')


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
        if alert.user.profile.email_notifications:
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
        message += "\n\nVisit https://herosandmore.com/alerts/ to view all notifications."

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
        Alert.objects.create(
            user=previous_bid.bidder,
            alert_type='outbid',
            title=f'Outbid on: {listing.title}',
            message=f'Someone placed a higher bid of ${new_bid_amount}. Current price: ${listing.get_current_price()}',
            link=listing.get_absolute_url(),
            listing=listing,
        )


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
        if order.buyer.email:
            html_content = render_to_string('marketplace/emails/order_confirmed.html', context)
            try:
                send_mail(
                    subject=f'Order Confirmed - #{order.id}',
                    message=f'Your order #{order.id} for {order.listing.title} has been confirmed.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.buyer.email],
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

        # Create in-app alerts
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
        if order.buyer.email:
            html_content = render_to_string('marketplace/emails/order_shipped.html', context)
            try:
                send_mail(
                    subject=f'Your order has shipped - #{order.id}',
                    message=f'Your order #{order.id} has been shipped via {order.tracking_carrier}. Tracking: {order.tracking_number}',
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
    if order.buyer.email:
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
    if order.seller.email:
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
    if order.buyer.email:
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
    if seller.email:
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
    if buyer.email:
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
    if seller.email:
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
    if seller.email:
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
        if seller.email:
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
