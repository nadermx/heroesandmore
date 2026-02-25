"""
Tests for proxy bidding (auto-bid / max bid) system.
"""
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from items.models import Category
from marketplace.models import Listing, Bid, AutoBid
from marketplace.services.autobid_service import AutoBidService, BidResult


class AutoBidServiceTests(TestCase):
    """Tests for the proxy bidding engine."""

    def setUp(self):
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.bidder1 = User.objects.create_user('bidder1', 'bidder1@test.com', 'pass123')
        self.bidder2 = User.objects.create_user('bidder2', 'bidder2@test.com', 'pass123')
        self.bidder3 = User.objects.create_user('bidder3', 'bidder3@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.seller,
            title='Test Auction',
            description='Test',
            category=self.category,
            price=Decimal('10.00'),
            starting_bid=Decimal('10.00'),
            listing_type='auction',
            status='active',
            auction_end=timezone.now() + timedelta(days=3),
        )

    def test_first_bid_at_starting_price(self):
        """First bid should be placed at the starting bid price."""
        result = AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))

        self.assertTrue(result.success)
        self.assertTrue(result.is_winning)
        self.assertEqual(result.current_price, Decimal('10.00'))

        # Check actual bid record
        bid = Bid.objects.get(listing=self.listing)
        self.assertEqual(bid.amount, Decimal('10.00'))
        self.assertEqual(bid.bidder, self.bidder1)
        self.assertFalse(bid.is_auto_bid)

        # Check auto-bid record
        autobid = AutoBid.objects.get(user=self.bidder1, listing=self.listing)
        self.assertEqual(autobid.max_amount, Decimal('50.00'))
        self.assertTrue(autobid.is_active)

    def test_first_bid_at_minimum(self):
        """If max equals starting bid, bid should still succeed."""
        result = AutoBidService.place_bid(self.listing, self.bidder1, Decimal('10.00'))

        self.assertTrue(result.success)
        self.assertTrue(result.is_winning)
        bid = Bid.objects.get(listing=self.listing)
        self.assertEqual(bid.amount, Decimal('10.00'))

    def test_lower_max_loses(self):
        """A bidder with a lower max should be immediately outbid."""
        # First bidder sets max at 50
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))

        # Second bidder sets max at 30
        result = AutoBidService.place_bid(self.listing, self.bidder2, Decimal('30.00'))

        self.assertTrue(result.success)
        self.assertFalse(result.is_winning)
        self.assertTrue(result.was_auto_outbid)

        # bidder2's bid at 30, then bidder1 counters at 31
        bids = Bid.objects.filter(listing=self.listing).order_by('amount')
        self.assertEqual(bids.count(), 3)  # first bid + loser bid + counter bid

        highest = Bid.objects.filter(listing=self.listing).order_by('-amount').first()
        self.assertEqual(highest.bidder, self.bidder1)
        self.assertEqual(highest.amount, Decimal('31.00'))
        self.assertTrue(highest.is_auto_bid)

        # bidder2's autobid should be deactivated
        b2_autobid = AutoBid.objects.get(user=self.bidder2, listing=self.listing)
        self.assertFalse(b2_autobid.is_active)

    def test_higher_max_wins(self):
        """A bidder with a higher max should win and push the price up."""
        # First bidder sets max at 30
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('30.00'))

        # Second bidder sets max at 50
        result = AutoBidService.place_bid(self.listing, self.bidder2, Decimal('50.00'))

        self.assertTrue(result.success)
        self.assertTrue(result.is_winning)
        self.assertFalse(result.was_auto_outbid)

        # bidder1's max (30) then bidder2 counters at 31
        highest = Bid.objects.filter(listing=self.listing).order_by('-amount').first()
        self.assertEqual(highest.bidder, self.bidder2)
        self.assertEqual(highest.amount, Decimal('31.00'))

        # bidder1's autobid deactivated
        b1_autobid = AutoBid.objects.get(user=self.bidder1, listing=self.listing)
        self.assertFalse(b1_autobid.is_active)

    def test_equal_max_first_bidder_wins(self):
        """Ties go to the first bidder (eBay-style)."""
        # First bidder sets max at 50
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))

        # Second bidder also sets max at 50
        result = AutoBidService.place_bid(self.listing, self.bidder2, Decimal('50.00'))

        self.assertTrue(result.success)
        self.assertFalse(result.is_winning)
        self.assertTrue(result.was_auto_outbid)

        # bidder1 should still be winning (counter bid has higher pk, wins ties)
        highest = Bid.objects.filter(listing=self.listing).order_by('-amount', '-pk').first()
        self.assertEqual(highest.bidder, self.bidder1)

    def test_already_winning_user_raises_max(self):
        """If user is already the high bidder, just update max — no new bid."""
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))
        bid_count_before = Bid.objects.filter(listing=self.listing).count()

        result = AutoBidService.place_bid(self.listing, self.bidder1, Decimal('100.00'))

        self.assertTrue(result.success)
        self.assertTrue(result.is_winning)

        # No new bid created
        self.assertEqual(Bid.objects.filter(listing=self.listing).count(), bid_count_before)

        # AutoBid updated
        autobid = AutoBid.objects.get(user=self.bidder1, listing=self.listing)
        self.assertEqual(autobid.max_amount, Decimal('100.00'))

    def test_below_minimum_rejected(self):
        """Max bid below the minimum bid should be rejected."""
        result = AutoBidService.place_bid(self.listing, self.bidder1, Decimal('5.00'))

        self.assertFalse(result.success)
        self.assertIn('at least', result.message)
        self.assertEqual(Bid.objects.filter(listing=self.listing).count(), 0)

    def test_below_minimum_after_existing_bid(self):
        """Max bid below current price + increment after existing bids should be rejected."""
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('10.00'))

        result = AutoBidService.place_bid(self.listing, self.bidder2, Decimal('10.50'))

        self.assertFalse(result.success)
        self.assertIn('at least', result.message)

    def test_seller_cannot_bid(self):
        """Seller should not be able to bid on their own listing."""
        result = AutoBidService.place_bid(self.listing, self.seller, Decimal('50.00'))

        self.assertFalse(result.success)
        self.assertIn('own listing', result.message)

    def test_ended_auction_rejected(self):
        """Bids on ended auctions should be rejected."""
        self.listing.auction_end = timezone.now() - timedelta(hours=1)
        self.listing.save()

        result = AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))

        self.assertFalse(result.success)
        self.assertIn('ended', result.message)

    def test_three_way_bidding(self):
        """Three bidders competing should resolve correctly."""
        # bidder1: max 30
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('30.00'))

        # bidder2: max 50 (beats bidder1)
        AutoBidService.place_bid(self.listing, self.bidder2, Decimal('50.00'))

        # bidder3: max 40 (beats neither)
        result = AutoBidService.place_bid(self.listing, self.bidder3, Decimal('40.00'))

        self.assertFalse(result.is_winning)
        self.assertTrue(result.was_auto_outbid)

        # bidder2 should still be winning
        highest = Bid.objects.filter(listing=self.listing).order_by('-amount').first()
        self.assertEqual(highest.bidder, self.bidder2)

    def test_extended_bidding_triggers_on_counter_bid(self):
        """Extended bidding should trigger on auto-bids placed during the sniping window."""
        # Set auction to end in 5 minutes (within the 15-min extended bidding window)
        self.listing.auction_end = timezone.now() + timedelta(minutes=5)
        self.listing.save()

        # First bidder
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))

        original_end = self.listing.auction_end

        # Second bidder triggers proxy resolution within the window
        AutoBidService.place_bid(self.listing, self.bidder2, Decimal('30.00'))

        self.listing.refresh_from_db()
        # Auction should be extended
        self.assertGreater(self.listing.auction_end, original_end)
        self.assertGreater(self.listing.times_extended, 0)

    @patch('alerts.tasks.notify_outbid.delay')
    def test_outbid_notification_sent(self, mock_notify):
        """Outbid notification should be sent when a bidder is outbid."""
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('30.00'))
        AutoBidService.place_bid(self.listing, self.bidder2, Decimal('50.00'))

        # Should have been called — bidder1 was outbid
        self.assertTrue(mock_notify.called)

    def test_bid_records_created_correctly(self):
        """All bid records should have correct fields."""
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))
        AutoBidService.place_bid(self.listing, self.bidder2, Decimal('30.00'))

        # bidder2's direct bid
        b2_bid = Bid.objects.filter(listing=self.listing, bidder=self.bidder2).first()
        self.assertIsNotNone(b2_bid)
        self.assertEqual(b2_bid.amount, Decimal('30.00'))
        self.assertEqual(b2_bid.max_bid_amount, Decimal('30.00'))
        self.assertFalse(b2_bid.is_auto_bid)

        # bidder1's counter bid (auto)
        b1_counter = Bid.objects.filter(
            listing=self.listing, bidder=self.bidder1, is_auto_bid=True
        ).first()
        self.assertIsNotNone(b1_counter)
        self.assertEqual(b1_counter.amount, Decimal('31.00'))
        self.assertTrue(b1_counter.is_auto_bid)

    def test_deactivate_listing_autobids(self):
        """All auto-bids should be deactivated for a listing."""
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))
        AutoBidService.place_bid(self.listing, self.bidder2, Decimal('60.00'))

        # bidder2 should have active autobid
        self.assertTrue(
            AutoBid.objects.filter(user=self.bidder2, listing=self.listing, is_active=True).exists()
        )

        AutoBidService.deactivate_listing_autobids(self.listing)

        self.assertFalse(
            AutoBid.objects.filter(listing=self.listing, is_active=True).exists()
        )

    def test_winner_capped_at_own_max(self):
        """When winner's counter would exceed their max, it's capped."""
        # bidder1: max 32
        AutoBidService.place_bid(self.listing, self.bidder1, Decimal('32.00'))

        # bidder2: max 31 (loses, but bidder1's counter would be 32, not 32)
        AutoBidService.place_bid(self.listing, self.bidder2, Decimal('31.00'))

        highest = Bid.objects.filter(listing=self.listing).order_by('-amount').first()
        self.assertEqual(highest.bidder, self.bidder1)
        # Counter = min(31 + 1, 32) = 32
        self.assertEqual(highest.amount, Decimal('32.00'))

    def test_non_auction_rejected(self):
        """Fixed-price listings should reject bids."""
        fixed_listing = Listing.objects.create(
            seller=self.seller,
            title='Fixed Price Item',
            description='Test',
            category=self.category,
            price=Decimal('10.00'),
            listing_type='fixed',
            status='active',
        )
        result = AutoBidService.place_bid(fixed_listing, self.bidder1, Decimal('15.00'))
        self.assertFalse(result.success)
        self.assertIn('not an auction', result.message)

    def test_inactive_listing_rejected(self):
        """Bids on non-active listings should be rejected."""
        self.listing.status = 'draft'
        self.listing.save()

        result = AutoBidService.place_bid(self.listing, self.bidder1, Decimal('50.00'))
        self.assertFalse(result.success)
        self.assertIn('not active', result.message)


class CancelAutoBidViewTests(TestCase):
    """Tests for the cancel auto-bid web view."""

    def setUp(self):
        self.seller = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.bidder = User.objects.create_user('bidder', 'bidder@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')
        self.listing = Listing.objects.create(
            seller=self.seller,
            title='Test Auction',
            description='Test',
            category=self.category,
            price=Decimal('10.00'),
            starting_bid=Decimal('10.00'),
            listing_type='auction',
            status='active',
            auction_end=timezone.now() + timedelta(days=3),
        )

    def test_cancel_autobid(self):
        """Should deactivate user's auto-bid."""
        AutoBidService.place_bid(self.listing, self.bidder, Decimal('50.00'))

        self.client.login(username='bidder', password='pass123')
        response = self.client.post(f'/marketplace/{self.listing.pk}/cancel-autobid/')

        self.assertEqual(response.status_code, 302)
        autobid = AutoBid.objects.get(user=self.bidder, listing=self.listing)
        self.assertFalse(autobid.is_active)

    def test_cancel_autobid_requires_login(self):
        """Should redirect to login if not authenticated."""
        response = self.client.post(f'/marketplace/{self.listing.pk}/cancel-autobid/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('signup', response.url)
