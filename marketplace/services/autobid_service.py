"""
Proxy bidding (auto-bid / max bid) engine.

Every bid is a max bid (eBay model). The user enters their maximum willingness
to pay. The system places the minimum necessary bid and automatically
counter-bids when someone else bids — up to the user's max.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from marketplace.models import Listing, Bid, AutoBid

logger = logging.getLogger('marketplace')

BID_INCREMENT = Decimal('1.00')


@dataclass
class BidResult:
    success: bool
    message: str
    current_price: Decimal = Decimal('0')
    is_winning: bool = False
    was_auto_outbid: bool = False
    bid: Optional[Bid] = None


class AutoBidService:

    @staticmethod
    @transaction.atomic
    def place_bid(listing, user, max_amount):
        """
        Place a proxy bid on an auction listing.

        Args:
            listing: The Listing to bid on (will be locked with select_for_update)
            user: The User placing the bid
            max_amount: Decimal maximum the user is willing to pay

        Returns:
            BidResult with outcome details
        """
        # Lock the listing row to prevent race conditions
        listing = Listing.objects.select_for_update().get(pk=listing.pk)

        # --- Validation ---
        if listing.listing_type != 'auction':
            return BidResult(success=False, message='This is not an auction listing.')

        if listing.status != 'active':
            return BidResult(success=False, message='This listing is not active.')

        if listing.is_auction_ended():
            return BidResult(success=False, message='This auction has ended.')

        if user == listing.seller:
            return BidResult(success=False, message='You cannot bid on your own listing.')

        current_price = listing.get_current_price()
        highest_bid = listing.bids.order_by('-amount', '-pk').first()
        min_bid = (current_price + BID_INCREMENT) if highest_bid else listing.starting_bid

        if max_amount < min_bid:
            return BidResult(
                success=False,
                message=f'Your max bid must be at least ${min_bid:.2f}',
                current_price=current_price,
            )

        # --- Check if user is already the high bidder ---
        if highest_bid and highest_bid.bidder == user:
            # User is already winning — just raise their max
            autobid, _ = AutoBid.objects.update_or_create(
                user=user,
                listing=listing,
                defaults={'max_amount': max_amount, 'is_active': True},
            )
            return BidResult(
                success=True,
                message=f'Your maximum bid has been updated to ${max_amount:.2f}. You\'re still the high bidder at ${current_price:.2f}.',
                current_price=current_price,
                is_winning=True,
                bid=highest_bid,
            )

        # --- Find competing auto-bid ---
        competing_autobid = AutoBid.objects.filter(
            listing=listing,
            is_active=True,
        ).exclude(user=user).order_by('-max_amount').first()

        # Create/update this user's AutoBid record
        user_autobid, _ = AutoBid.objects.update_or_create(
            user=user,
            listing=listing,
            defaults={'max_amount': max_amount, 'is_active': True},
        )

        if not competing_autobid:
            # No competing auto-bid — place bid at min_bid
            bid_amount = min_bid
            bid = _create_bid(listing, user, bid_amount, max_amount, is_auto=False)
            _handle_extended_bidding(listing, bid)
            _notify_outbid(listing, bid_amount, user, highest_bid)

            return BidResult(
                success=True,
                message=f'You\'re the high bidder! Your bid: ${bid_amount:.2f} (max: ${max_amount:.2f})',
                current_price=bid_amount,
                is_winning=True,
                bid=bid,
            )

        # --- Competing auto-bid exists — resolve ---
        competing_user = competing_autobid.user
        competing_max = competing_autobid.max_amount

        if max_amount > competing_max:
            # New bidder wins: loser bids their max, winner counters at loser's max + increment
            loser_bid = _create_bid(listing, competing_user, competing_max, competing_max, is_auto=True)
            _handle_extended_bidding(listing, loser_bid)

            winner_amount = min(competing_max + BID_INCREMENT, max_amount)
            winner_bid = _create_bid(listing, user, winner_amount, max_amount, is_auto=False)
            _handle_extended_bidding(listing, winner_bid)

            # Deactivate loser's auto-bid
            competing_autobid.deactivate()

            # Notify the outbid user
            _notify_outbid(listing, winner_amount, user, loser_bid)

            return BidResult(
                success=True,
                message=f'You\'re the high bidder at ${winner_amount:.2f}! Another bidder had a max of ${competing_max:.2f}.',
                current_price=winner_amount,
                is_winning=True,
                bid=winner_bid,
            )

        else:
            # Existing auto-bidder wins (or tie — first bidder wins ties)
            # New bidder bids their max
            new_bid = _create_bid(listing, user, max_amount, max_amount, is_auto=False)
            _handle_extended_bidding(listing, new_bid)

            # Existing auto-bidder counters at new bidder's max + increment (capped at their max)
            counter_amount = min(max_amount + BID_INCREMENT, competing_max)
            counter_bid = _create_bid(listing, competing_user, counter_amount, competing_max, is_auto=True)
            _handle_extended_bidding(listing, counter_bid)

            # Deactivate new bidder's auto-bid (they lost)
            user_autobid.deactivate()

            # Notify the new bidder they were outbid
            _notify_outbid(listing, counter_amount, competing_user, new_bid)

            return BidResult(
                success=True,
                message=f'You were outbid! Another bidder has a higher maximum. Current price: ${counter_amount:.2f}',
                current_price=counter_amount,
                is_winning=False,
                was_auto_outbid=True,
                bid=new_bid,
            )

    @staticmethod
    def deactivate_listing_autobids(listing):
        """Deactivate all auto-bids for a listing (called when auction ends)."""
        AutoBid.objects.filter(listing=listing, is_active=True).update(
            is_active=False,
            updated=timezone.now(),
        )


def _create_bid(listing, user, amount, max_amount, is_auto):
    """Create a Bid record."""
    return Bid.objects.create(
        listing=listing,
        bidder=user,
        amount=amount,
        max_bid_amount=max_amount,
        is_auto_bid=is_auto,
    )


def _handle_extended_bidding(listing, bid):
    """Extend auction if bid is within the anti-sniping window."""
    if listing.use_extended_bidding and listing.auction_end:
        time_left = listing.auction_end - timezone.now()
        if time_left.total_seconds() < listing.extended_bidding_minutes * 60:
            listing.auction_end = timezone.now() + timedelta(
                minutes=listing.extended_bidding_minutes
            )
            listing.times_extended += 1
            listing.save(update_fields=['auction_end', 'times_extended'])
            bid.triggered_extension = True
            bid.save(update_fields=['triggered_extension'])


def _notify_outbid(listing, new_bid_amount, new_bidder, previous_bid):
    """Send outbid notification to the previous high bidder."""
    if previous_bid and previous_bid.bidder != new_bidder:
        try:
            from alerts.tasks import notify_outbid
            notify_outbid.delay(listing.id, float(new_bid_amount), new_bidder.id)
        except Exception:
            pass
