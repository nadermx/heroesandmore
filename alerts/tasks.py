from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


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
