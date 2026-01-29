# HeroesAndMore Competitor Analysis & Feature Implementation Plan

## Executive Summary

After analyzing **Goldin** (premium auction house) and **HipComic** (comic marketplace with collection tools), HipComic is the closer model to HeroesAndMore. This document outlines every feature they have that we're missing and a detailed implementation plan.

---

## Competitor Feature Comparison

### HipComic Features (Primary Model)

| Feature | HipComic Has | HeroesAndMore Has | Priority |
|---------|--------------|-------------------|----------|
| **Image Recognition Scanner** | YES - AI identifies comics from photos | NO | HIGH |
| **Real-time Price Guide** | YES - From actual sales data | NO | HIGH |
| **Collection Value Charts** | YES - Track value over time | NO | HIGH |
| **Live Bidding Rooms** | YES - Real-time auction rooms | NO | HIGH |
| **Auction Events** | YES - Scheduled auction events | Partial (basic auctions) | HIGH |
| **$0.99 No Reserve Auctions** | YES | NO | MEDIUM |
| **Mobile App (iOS/Android)** | YES - Full-featured | NO | HIGH |
| **eBay Sync** | YES - Auto-sync listings | NO | MEDIUM |
| **Bulk Lister with CSV Import** | YES | NO | MEDIUM |
| **HipValue Price Suggestions** | YES - Auto-suggest prices | NO | HIGH |
| **Watch List** | YES | Partial (wishlists) | LOW |
| **Free Shipping Over $75** | YES | NO | LOW |
| **Seller Subscription Tiers** | YES (Starter/Basic/Featured/Premium) | NO | MEDIUM |
| **PayPal Seller Protection** | YES - Up to $2,500 | NO | MEDIUM |
| **Graded Comic Support (CGC/CBCS)** | YES - Full integration | Partial | LOW |
| **Forums/Community** | YES | YES | DONE |

### Goldin Features (Premium Model)

| Feature | Goldin Has | HeroesAndMore Has | Priority |
|---------|------------|-------------------|----------|
| **Weekly Auction Schedule** | YES - Tue 8PM to Thu 10PM ET | NO | HIGH |
| **Elite/Themed Auctions** | YES - Goldin 100, Game Used, etc. | NO | MEDIUM |
| **Extended Bidding (15 min)** | YES - Prevents sniping | NO | HIGH |
| **The Vault (Storage)** | YES - Secure storage service | NO | LOW |
| **Consignment Advances** | YES - Interest-free loans | NO | LOW |
| **PSA Vault Integration** | YES | NO | LOW |
| **Push Notifications** | YES - Bid alerts, auction alerts | NO | HIGH |
| **SMS Notifications** | YES | NO | MEDIUM |
| **Buyer's Premium** | YES - 20% | We have 3% seller fee | KEEP OURS |
| **Professional Authentication** | YES - In-house verification | NO | MEDIUM |
| **Real-time Bid Updates** | YES | NO | HIGH |
| **Counteroffer System** | YES | NO | MEDIUM |
| **Mobile App** | YES - Full bidding support | NO | HIGH |

---

## Phase 1: Core Features We MUST Add (Weeks 1-4)

### 1.1 Image Recognition & Auto-Identification
**What HipComic Does:** Users snap a photo, AI identifies the item (volume, issue, variant, grade if slabbed)

**Implementation:**
```
- Integrate with Google Cloud Vision or custom ML model
- Train on sports cards (PSA/BGS labels), comics (CGC/CBCS), Funko boxes
- Extract: Title, Year, Set, Card Number, Grade, Cert Number
- Auto-populate listing form from scan
```

**Files to Create:**
- `marketplace/services/image_recognition.py`
- `marketplace/views/scan_listing.py`
- `templates/marketplace/scan_listing.html`
- `static/js/camera-capture.js`

### 1.2 Real-Time Price Guide
**What HipComic Does:** Tracks actual sales across marketplaces, shows price history charts

**Implementation:**
```
- Create PriceHistory model to track sales
- Scrape/import historical data from eBay sold listings
- Calculate fair market value by grade
- Show price charts with Chart.js or ApexCharts
- Update prices when items sell on our platform
```

**Models to Add:**
```python
class PriceGuide(models.Model):
    item_name = models.CharField(max_length=500)
    category = models.ForeignKey(Category)
    year = models.IntegerField()
    variant = models.CharField(blank=True)

class PricePoint(models.Model):
    price_guide = models.ForeignKey(PriceGuide)
    grade = models.CharField()  # Raw, PSA 10, CGC 9.8, etc.
    avg_price = models.DecimalField()
    low_price = models.DecimalField()
    high_price = models.DecimalField()
    num_sales = models.IntegerField()
    last_updated = models.DateTimeField()

class SaleRecord(models.Model):
    price_guide = models.ForeignKey(PriceGuide)
    sale_price = models.DecimalField()
    grade = models.CharField()
    sale_date = models.DateTimeField()
    source = models.CharField()  # 'heroesandmore', 'ebay', etc.
    listing = models.ForeignKey(Listing, null=True)
```

### 1.3 Collection Value Tracking with Charts
**What HipComic Does:** Users see their collection value over time with interactive charts

**Implementation:**
```
- Add CollectionSnapshot model (daily/weekly snapshots)
- Calculate total value from price guide data
- Show gain/loss percentages
- Interactive charts showing value trends
- "My Portfolio" dashboard
```

**New Views:**
- `collections/portfolio.py` - Portfolio dashboard
- `templates/collections/portfolio.html` - Charts and stats

### 1.4 Live Bidding Rooms
**What HipComic Does:** One hour before auction ends, users join a live room with real-time updates

**Implementation:**
```
- WebSocket connection via Django Channels
- Real-time bid updates without page refresh
- Live bidding room UI with:
  - Current high bid
  - Time remaining (countdown)
  - Bid history
  - Quick bid buttons ($+1, $+5, $+10, Max bid)
  - "Watching" indicator
- Push notifications for outbid
```

**Technical Stack:**
- Django Channels for WebSockets
- Redis for real-time pub/sub
- JavaScript WebSocket client

**Files to Create:**
- `marketplace/consumers.py` - WebSocket consumers
- `marketplace/routing.py` - WebSocket routing
- `templates/marketplace/live_bidding_room.html`
- `static/js/live-bidding.js`

### 1.5 Extended Bidding (Anti-Sniping)
**What Goldin Does:** If bid placed in last 15 minutes, auction extends 15 more minutes

**Implementation:**
```python
# In Listing model
def place_bid(self, user, amount):
    # ... existing bid logic ...

    # Extended bidding
    time_remaining = self.auction_end - timezone.now()
    if time_remaining < timedelta(minutes=15):
        self.auction_end = timezone.now() + timedelta(minutes=15)
        self.save()
        # Notify all watchers of extension
```

---

## Phase 2: Auction System Overhaul (Weeks 5-6)

### 2.1 Scheduled Auction Events
**What They Do:** Weekly auctions with set start/end times, themed events

**Implementation:**
```python
class AuctionEvent(models.Model):
    name = models.CharField(max_length=200)  # "Weekly Auction #47"
    slug = models.SlugField()
    description = models.TextField()
    event_type = models.CharField(choices=[
        ('weekly', 'Weekly Auction'),
        ('themed', 'Themed Event'),
        ('elite', 'Elite Auction'),
    ])
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    preview_start = models.DateTimeField()  # When items visible
    is_featured = models.BooleanField(default=False)
    cover_image = models.ImageField()

class AuctionEventListing(models.Model):
    event = models.ForeignKey(AuctionEvent)
    listing = models.ForeignKey(Listing)
    lot_number = models.IntegerField()
    starting_bid = models.DecimalField()
    reserve_price = models.DecimalField(null=True)
```

**Features:**
- Auction calendar view
- Event landing pages
- Lot ordering within events
- Preview periods
- Bulk add items to events

### 2.2 $0.99 No Reserve Auctions
```python
# Add to Listing model
no_reserve = models.BooleanField(default=False)
minimum_bid = models.DecimalField(default=0.99)
```

### 2.3 Make Offer / Counteroffer System
```python
class Offer(models.Model):
    listing = models.ForeignKey(Listing)
    buyer = models.ForeignKey(User)
    amount = models.DecimalField()
    message = models.TextField(blank=True)
    status = models.CharField(choices=[
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('countered', 'Countered'),
        ('expired', 'Expired'),
    ])
    counter_amount = models.DecimalField(null=True)
    counter_message = models.TextField(blank=True)
    expires_at = models.DateTimeField()
    created = models.DateTimeField(auto_now_add=True)
```

---

## Phase 3: Mobile App (Weeks 7-10)

### 3.1 React Native or Flutter App
**Core Features:**
- Camera scanning for listings
- Browse & search
- Real-time bidding
- Collection management
- Push notifications
- Offline collection viewing

**Screens:**
1. Home - Featured auctions, ending soon
2. Browse - Categories, filters, search
3. Item Detail - Images, bid/buy, seller info
4. Live Auction Room - Real-time bidding
5. My Collection - Portfolio, value charts
6. Scan - Camera to identify/list items
7. Sell - Create listings
8. Profile - Orders, settings, notifications
9. Messages - Buyer/seller communication

### 3.2 Push Notifications (Firebase)
```
Notification Types:
- Outbid on item
- Auction ending soon (1hr, 15min, 5min)
- Watched item price drop
- New listing matching saved search
- Order shipped
- New message
- Offer received/countered
```

---

## Phase 4: Seller Tools (Weeks 11-12)

### 4.1 Bulk Lister with CSV Import
```python
class BulkImport(models.Model):
    seller = models.ForeignKey(User)
    file = models.FileField()
    status = models.CharField()  # processing, complete, failed
    total_rows = models.IntegerField()
    processed_rows = models.IntegerField()
    errors = models.JSONField(default=list)
    created = models.DateTimeField(auto_now_add=True)
```

**CSV Format Support:**
- HipComic format
- eBay export format
- Custom template

### 4.2 eBay Sync
```python
class EbaySync(models.Model):
    user = models.ForeignKey(User)
    ebay_user_id = models.CharField()
    access_token = models.TextField()
    refresh_token = models.TextField()
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField()

class EbaySyncedListing(models.Model):
    sync = models.ForeignKey(EbaySync)
    listing = models.ForeignKey(Listing)
    ebay_item_id = models.CharField()
```

### 4.3 Seller Subscription Tiers
```python
class SellerSubscription(models.Model):
    user = models.ForeignKey(User)
    tier = models.CharField(choices=[
        ('starter', 'Starter - Free'),
        ('basic', 'Basic - $9.99/mo'),
        ('featured', 'Featured - $24.99/mo'),
        ('premium', 'Premium - $49.99/mo'),
    ])
    max_listings = models.IntegerField()
    commission_rate = models.DecimalField()  # 12.95%, 11.95%, 9.95%, 7.95%
    featured_listings = models.IntegerField()  # 0, 5, 15, unlimited
    is_active = models.BooleanField()
    expires_at = models.DateTimeField()
```

**Tier Benefits:**
| Tier | Monthly | Commission | Listings | Featured Spots |
|------|---------|------------|----------|----------------|
| Starter | Free | 12.95% | 50 | 0 |
| Basic | $9.99 | 11.95% | 250 | 5 |
| Featured | $24.99 | 9.95% | 1000 | 15 |
| Premium | $49.99 | 7.95% | Unlimited | Unlimited |

### 4.4 Price Suggestions When Listing
```python
def get_price_suggestion(item_name, category, grade):
    """
    Returns suggested price based on price guide data
    """
    price_guide = PriceGuide.objects.filter(
        item_name__icontains=item_name,
        category=category
    ).first()

    if price_guide:
        price_point = price_guide.pricepoint_set.filter(grade=grade).first()
        return {
            'suggested_price': price_point.avg_price,
            'low': price_point.low_price,
            'high': price_point.high_price,
            'recent_sales': price_point.num_sales,
        }
    return None
```

---

## Phase 5: Enhanced User Experience (Weeks 13-14)

### 5.1 Advanced Search & Filters
```
Filters to Add:
- Grading company (PSA, BGS, CGC, SGC, Raw)
- Grade range (slider: 1-10)
- Year range
- Seller rating
- Ships from location
- Auction vs Buy Now
- Ending within (1hr, 24hr, 7 days)
- Price range
- Free shipping only
- No reserve only
```

### 5.2 Saved Searches with Alerts
```python
class SavedSearch(models.Model):
    user = models.ForeignKey(User)
    name = models.CharField()
    query = models.CharField()
    filters = models.JSONField()  # All filter params
    notify_email = models.BooleanField(default=True)
    notify_push = models.BooleanField(default=True)
    notify_frequency = models.CharField(choices=[
        ('instant', 'Instant'),
        ('daily', 'Daily Digest'),
        ('weekly', 'Weekly Digest'),
    ])
```

### 5.3 Recently Viewed & Recommendations
```python
class RecentlyViewed(models.Model):
    user = models.ForeignKey(User)
    listing = models.ForeignKey(Listing)
    viewed_at = models.DateTimeField(auto_now=True)

# Recommendation engine based on:
# - Recently viewed categories
# - Purchase history
# - Collection items
# - Similar users' interests
```

### 5.4 Shipping Calculator
```python
class ShippingRate(models.Model):
    seller = models.ForeignKey(User)
    name = models.CharField()  # "Standard", "Priority", "Express"
    carrier = models.CharField()  # USPS, UPS, FedEx
    base_price = models.DecimalField()
    per_item_price = models.DecimalField()
    free_threshold = models.DecimalField(null=True)  # Free over $X
    estimated_days = models.CharField()  # "3-5 business days"
```

---

## Phase 6: Trust & Safety (Weeks 15-16)

### 6.1 Authentication Badge System
```python
class AuthenticationRequest(models.Model):
    listing = models.ForeignKey(Listing)
    requested_by = models.ForeignKey(User)
    authenticator = models.ForeignKey(User, null=True)  # Staff
    status = models.CharField(choices=[
        ('pending', 'Pending Review'),
        ('approved', 'Authenticated'),
        ('rejected', 'Not Authentic'),
        ('inconclusive', 'Inconclusive'),
    ])
    notes = models.TextField()
    certificate_number = models.CharField(blank=True)
```

### 6.2 Buyer/Seller Protection
```
Protection Features:
- 3-day inspection period
- Photo verification on delivery
- Dispute resolution system
- Automatic refunds for not-as-described
- Seller verification requirements
```

### 6.3 Verified Seller Program
```python
class SellerVerification(models.Model):
    user = models.ForeignKey(User)
    id_verified = models.BooleanField()
    address_verified = models.BooleanField()
    bank_verified = models.BooleanField()
    sales_count = models.IntegerField()
    positive_feedback_percent = models.DecimalField()
    is_verified_seller = models.BooleanField()
    badge_earned_at = models.DateTimeField(null=True)
```

---

## Database Schema Additions Summary

### New Models Required:
1. `PriceGuide` - Item price tracking
2. `PricePoint` - Price by grade
3. `SaleRecord` - Historical sales
4. `CollectionSnapshot` - Portfolio value history
5. `AuctionEvent` - Scheduled auctions
6. `AuctionEventListing` - Items in events
7. `Offer` - Make offer system
8. `BulkImport` - CSV imports
9. `EbaySync` - eBay integration
10. `EbaySyncedListing` - Synced items
11. `SellerSubscription` - Seller tiers
12. `SavedSearch` - Search alerts
13. `RecentlyViewed` - User history
14. `ShippingRate` - Seller shipping options
15. `AuthenticationRequest` - Verification requests
16. `SellerVerification` - Verified sellers

### Model Modifications:
1. `Listing` - Add: `no_reserve`, `minimum_bid`, `extended_bidding`, `event`
2. `Bid` - Add: `is_auto_bid`, `max_bid_amount`
3. `Collection` - Add: `total_value`, `value_updated_at`
4. `Profile` - Add: `subscription`, `ebay_sync`, `is_verified_seller`

---

## Technical Requirements

### Infrastructure:
- **Redis** - Already have, need for WebSockets
- **Django Channels** - WebSocket support
- **Celery** - Already have, for background jobs
- **Firebase** - Push notifications
- **Google Cloud Vision** - Image recognition (or AWS Rekognition)

### External APIs:
- eBay API - Listing sync, sold prices
- PayPal/Stripe - Already have Stripe
- Firebase Cloud Messaging - Push notifications
- USPS/UPS/FedEx - Shipping rates

### Mobile:
- React Native or Flutter
- iOS App Store ($99/year)
- Google Play Store ($25 one-time)

---

## Implementation Timeline

| Phase | Description | Duration | Priority |
|-------|-------------|----------|----------|
| 1 | Core Features (Scanner, Price Guide, Live Bidding) | 4 weeks | CRITICAL |
| 2 | Auction System Overhaul | 2 weeks | HIGH |
| 3 | Mobile App | 4 weeks | HIGH |
| 4 | Seller Tools | 2 weeks | MEDIUM |
| 5 | Enhanced UX | 2 weeks | MEDIUM |
| 6 | Trust & Safety | 2 weeks | MEDIUM |

**Total: 16 weeks (4 months)**

---

## Quick Wins (Can Do This Week)

1. **Extended Bidding** - Simple code change, big impact
2. **Auction Events Page** - Basic event grouping
3. **Shipping Threshold** - Free shipping over $75
4. **Better Filters** - Add grading company, year range
5. **Outbid Notifications** - Email when outbid
6. **Recently Viewed** - Simple tracking

---

## Revenue Model Comparison

### HipComic:
- 9.95% - 12.95% commission (tier based)
- Subscription tiers ($0-$49.99/mo)
- No buyer fees

### Goldin:
- 20% buyer's premium
- Negotiable seller commission
- Vault storage fees

### HeroesAndMore (Current):
- 3% seller commission
- No buyer fees
- No subscriptions

### Recommendation:
Keep the low 3% commission as competitive advantage, but add:
- Optional seller subscriptions for power sellers
- Featured listing fees ($2.99 for 7-day boost)
- Promoted listings (PPC advertising)

---

## Conclusion

The biggest gaps between HeroesAndMore and competitors are:

1. **No image recognition/scanning** - This is table stakes now
2. **No real-time price guide** - Users need valuation help
3. **Basic auction system** - Need live bidding, events, extended bidding
4. **No mobile app** - Critical for younger collectors
5. **No bulk listing tools** - Deters serious sellers

Implementing Phase 1 (Core Features) should be the immediate priority as these features are what make HipComic successful and are expected by collectors in 2026.
