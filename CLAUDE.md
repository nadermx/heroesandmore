# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HeroesAndMore is a collectibles marketplace and community platform built with Django. Features include listings (fixed price and auctions), collections, price guide, image scanner, seller tools, and social features.

## Tech Stack
- **Backend**: Django 5.x, Python 3.12
- **Database**: PostgreSQL (SQLite for local dev)
- **Cache/Queue**: Redis, Celery
- **Frontend**: Bootstrap 5, HTMX (loaded globally in base.html with auto CSRF)
- **Payments**: Stripe Connect
- **Deployment**: Ansible, Nginx, Supervisor, DigitalOcean

## Project Structure
```
heroesandmore/
├── app/                    # Django project settings
├── accounts/               # User auth, profiles
├── user_collections/       # Collection management (URL namespace: 'collections')
├── items/                  # Item database & categories
├── marketplace/            # Listings, orders, payments, auction events
├── social/                 # Forums, messaging, follows
├── alerts/                 # Wishlists, notifications, price alerts
├── pricing/                # Price guide, valuation, market data
├── scanner/                # Image recognition for collectibles
├── seller_tools/           # Bulk import, inventory, subscriptions
├── shipping/               # EasyPost shipping: addresses, labels, rates, tracking
├── templates/              # HTML templates
├── static/                 # CSS, JS, images
├── ansible/                # Deployment automation
└── config.py               # Local config (gitignored)
```

**Note:** The `user_collections` app is named this way to avoid conflicts with Python's built-in `collections` module. URL namespace is still 'collections'.

## Local Development

### Setup
```bash
cd /home/john/heroesandmore
source venv/bin/activate
cp config.py.example config.py  # Edit with your local settings
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Run Celery (for background tasks)
```bash
celery -A app worker -l info
celery -A app beat -l info
```

### Management Commands
```bash
python manage.py seed_categories          # Populate initial categories
python manage.py import_market_data       # Import price data (--source ebay|heritage|gocollect --verbose --skip-images)
```

### Running Tests
```bash
python manage.py test                                           # Run all tests
python manage.py test marketplace                               # Run single app tests
python manage.py test marketplace.tests.test_listings           # Run specific test module
python manage.py test marketplace.tests.test_listings.BiddingTests  # Run specific test class
python manage.py test marketplace.tests.test_listings.BiddingTests.test_bid_on_auction  # Single test
python manage.py test --keepdb                                  # Reuse test DB (faster)
python manage.py test --verbosity=2                             # Verbose output
```

**Test Structure**: Each app has `tests/` directory with test files:
- `test_models.py` - Model and basic view tests
- `test_views.py` - View-specific tests
- API tests are in `api/tests/` covering all endpoints

## Key URLs
- `/` - Homepage
- `/items/` - Browse categories
- `/marketplace/` - All listings
- `/bid/` - Ad landing page (conversion-focused, shows live auctions, no login required)
- `/collections/` - Browse collections
- `/social/forums/` - Forums
- `/price-guide/` - Price guide and market data
- `/scanner/` - Item scanner (image recognition)
- `/seller/` - Seller dashboard and tools
- `/sell/` - Sell landing page (redirects to listing create if authenticated)
- `/marketplace/order/track/` - Guest order lookup (email + order number)
- `/marketplace/order/track/<token>/` - Guest order detail by token
- `/admin/` - Django admin
- `/api/v1/` - REST API root
- `/api/docs/` - Swagger UI

## Key Models

### Core Models
- `accounts.Profile` - User profiles, seller verification, subscription tiers, founding member status
- `accounts.RecentlyViewed` - Track recently viewed listings
- `items.Category` - Hierarchical categories
- `items.Item` - Base item database
- `marketplace.Listing` - For sale items (fixed price and auctions), has `collector_notes` field
- `marketplace.Bid` - Auction bids (FK to listing via `related_name='bids'`, has `created` timestamp)
- `marketplace.SavedListing` - User saves/watchlist (FK to listing via `related_name='saves'`)
- `marketplace.AuctionEvent` - Scheduled auction events
- `marketplace.Order` - Purchases (supports both authenticated buyers and guest checkout)
- `marketplace.Offer` - Make offer/counteroffer system
- `marketplace.AutoBid` - Proxy bidding (eBay-style auto-bid up to max amount)
- `shipping.Address` - Structured shipping addresses with EasyPost verification
- `shipping.ShippingProfile` - Pre-seeded package profiles for collectibles
- `shipping.ShippingLabel` - Purchased shipping labels with tracking
- `shipping.ShippingRate` - Cached rate quotes (30-min expiry)
- `user_collections.Collection` - User collections with value tracking
- `user_collections.CollectionValueSnapshot` - Daily value snapshots for charts

### Important Listing Model Methods
Templates and views depend heavily on these — know them before modifying listing display code:
- `get_current_price()` — For auctions: highest bid amount or starting price. For fixed: `self.price`
- `get_images()` — Returns list of non-empty image fields (image1–image5)
- `get_videos()` — Returns list of non-empty video FileFields (video1–video3)
- `has_video` — Property: True if any video upload or `video_url` exists
- `get_video_url_embed()` — Returns embeddable URL for YouTube/Vimeo (nocookie/dnt), or None
- `is_auction_ended()` — Checks `auction_end` against `timezone.now()`
- `time_remaining` — Returns `timedelta` or `None`
- `time_remaining_parts` — Returns dict `{days, hours, minutes, seconds}` for template display
- `quantity_available` — Property: `quantity - quantity_sold`
- `bid_count` is NOT a model property — use `listing.bids.count` or annotate with `Count('bids')`

### Video Upload Support
Listings support video uploads (`video1`, `video2`, `video3` FileFields) and external video URLs (`video_url` URLField for YouTube/Vimeo). Video capacity is tier-gated via `VIDEO_TIER_LIMITS` in settings.py:
- Starter: 1 video, 250MB max
- Basic: 1 video, 500MB max
- Featured: 2 videos, 1GB max
- Premium: 3 videos, 2GB max

Accepted formats: MP4, WebM, MOV. YouTube/Vimeo URLs are always allowed (no storage cost).
Nginx `client_max_body_size` set to `2G` with 600s proxy timeouts for large uploads.

### Extended Bidding (Anti-Sniping)
- `Listing.use_extended_bidding` (default `True`) + `extended_bidding_minutes` (default `15`)
- Bids placed within the last N minutes of auction end extend the deadline
- `times_extended` tracks how many extensions have occurred
- Logic lives in the API bid view (`marketplace/api/views.py`)

### Price Guide (pricing app)
- `pricing.PriceGuideItem` - Master catalog of items with pricing data (has `image`, `image_source_url`, `image_source` for auto-imported images)
- `pricing.GradePrice` - Price data for each grade (PSA 10, BGS 9.5, etc.)
- `pricing.SaleRecord` - Individual sale records for price tracking

### Scanner (scanner app)
- `scanner.ScanResult` - Image recognition results
- `scanner.ScanSession` - Bulk scanning sessions

### Seller Tools (seller_tools app)
- `seller_tools.SellerSubscription` - Seller tiers (starter, basic, featured, premium)
- `seller_tools.BulkImport` - Bulk listing imports from Excel (.xlsx) or CSV, with post-import photo capture flow
- `seller_tools.BulkImportRow` - Individual rows with JSON data, status, linked listing FK
- `seller_tools.InventoryItem` - Pre-listing inventory management

### Alerts (alerts app)
- `alerts.Wishlist` - Want lists
- `alerts.SavedSearch` - Saved searches with notifications
- `alerts.PriceAlert` - Price drop alerts

### Social
- `social.Follow` - User follows
- `social.ForumThread` - Forum discussions

## Homepage Architecture (`items/views.py` → `home()`, `templates/home.html`)

The homepage is designed as a "high-stakes auction floor" with urgency-driven sections:

**Section order:** Hero → Stats Bar → Ending Soon (FOMO grid, 8 items) → Featured Lots (recent) → Bid Wars (conditional) → Browse Categories → Curated for Serious Collectors (conditional) → Official Auctions (conditional) → Why Heroes & More → WHERE LEGENDS LIVE CTA

**Key queries in the view:**
- `ending_soon` — annotated with `save_count`, `bid_count_total`, `recent_bids` (last hour) for HOT LOT badge
- `bid_wars` — auctions with bids in last hour, ordered by `recent_bids` count (shows "+X bids" overlay)
- `curated_listings` — graded items (`is_graded=True`), sorted by price descending

**Listing card annotation requirements** (`components/listing_card.html`): When including this component, the queryset must be annotated with `save_count=Count('saves')`, `bid_count_total=Count('bids')`, and `recent_bids=Count('bids', filter=Q(...))`. HOT LOT badge shows when `listing.recent_bids >= 5` or `listing.save_count >= 10`. The card also accesses `listing.bid_count` (not `bid_count_total`) for bid count display — this is a known inconsistency.

**Listing detail auction features** (`marketplace/listing_detail.html`):
- Social proof stack: watcher count, recent bid count (last minute), bid war active badge
- Comps range from `recent_sales` prices
- Quick bid buttons (+$10/+$25/+$50) synced with sticky bid bar
- Sticky bid bar: appears via `IntersectionObserver` when main bid form scrolls off-screen
- Live countdown: JS ticker with urgency classes (`urgency-warning` < 60s, `urgency-critical` < 10s)

## CSS Architecture

All styles live inline in `templates/base.html` `<style>` block — there are no separate CSS files. Page-specific styles go in `{% block extra_css %}`. This is intentional for faster initial load (no extra HTTP request for critical CSS).

Key CSS custom properties are defined in `:root` — use `var(--brand-primary)`, `var(--brand-navy)`, `var(--brand-cyan)`, `var(--brand-gold)` etc. for consistency.

## Deployment

### Ansible Setup
Ansible playbooks are in the `ansible/` directory:
- `servers` - Inventory file with server IPs
- `group_vars/all` - Public configuration variables
- `group_vars/vault.yml` - Secret variables (gitignored)
- `templates/config.py.j2` - Config file template

**Important**: Copy `group_vars/vault.yml.example` to `group_vars/vault.yml` and add your secrets.

**Ansible binary location**: `/home/john/heroesandmore/venv/bin/ansible-playbook` (installed in project venv, not system-wide).

### Quick Deploy (Code Only)
For simple code updates without config changes:
```bash
cd /home/john/heroesandmore/ansible
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers gitpull.yml
```

### Full Deploy (With Config)
For deployments that update config.py:
```bash
cd /home/john/heroesandmore/ansible
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers deploy.yml
```

### Backup Database
```bash
cd /home/john/heroesandmore/ansible
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers backup.yml
```

### Check Logs & Debug
Use the debug script for easy log access:
```bash
cd ansible
./debug.sh help           # Show all commands
./debug.sh errors         # Check error log
./debug.sh stripe         # Check Stripe/payment issues
./debug.sh all            # Quick overview of all logs
./debug.sh tail errors    # Live tail error log
./debug.sh grep "pattern" # Search all logs
./debug.sh status         # Check service status
```

Or manually:
```bash
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell -a "tail -100 /var/log/heroesandmore/heroesandmore.log" --become
```

### Restart Services
```bash
/home/john/heroesandmore/venv/bin/ansible -i servers all -m shell -a "supervisorctl restart heroesandmore:*" --become
# Or use: ./debug.sh restart
```

### SSH to Server
```bash
ssh heroesandmore@174.138.33.140
cd /home/www/heroesandmore
```

## Logging & Debugging

### Log Files
Application logs in `/home/www/heroesandmore/logs/`:

| File | Purpose | When to Check |
|------|---------|---------------|
| `errors.log` | All ERROR level logs | First place to look for issues |
| `stripe.log` | Stripe API calls, payments, Connect | Payment failures, webhook issues |
| `frontend.log` | JavaScript errors from browsers | Client-side bugs, mobile issues |
| `app.log` | General application activity | Flow debugging |
| `security.log` | Auth failures, permission issues | Login problems, suspicious activity |
| `celery_tasks.log` | Background task execution | Scheduled jobs failing |
| `api.log` | REST API requests | Mobile app issues |
| `db.log` | Database warnings | Performance issues |

System logs in `/var/log/heroesandmore/`:

| File | Purpose |
|------|---------|
| `heroesandmore.out.log` | Gunicorn web server stdout |
| `heroesandmore.err.log` | Gunicorn web server stderr (errors) |
| `celery.out.log` | Celery worker stdout |
| `celery.err.log` | Celery worker stderr (errors) |
| `celerybeat.out.log` | Celery beat stdout |
| `celerybeat.err.log` | Celery beat stderr (errors) |

### Adding Logging in Code
```python
import logging
logger = logging.getLogger('marketplace')  # Use app name

logger.debug('Detailed info for debugging')
logger.info('General information')
logger.warning('Something unexpected')
logger.error('Error occurred', exc_info=True)  # Include traceback
```

Available loggers: `accounts`, `marketplace`, `pricing`, `alerts`, `scanner`, `api`, `seller_tools`, `frontend`, `shipping`

## Config Values Needed (config.py)
Copy `config.py.example` to `config.py` and set:

**Required:**
- `SECRET_KEY` - Django secret key
- `DATABASE_PASSWORD` - PostgreSQL password
- `STRIPE_PUBLIC_KEY` - Stripe publishable key
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe main webhook signing
- `STRIPE_CONNECT_WEBHOOK_SECRET` - Stripe Connect webhook signing
- `DO_SPACES_KEY` - DigitalOcean Spaces access key
- `DO_SPACES_SECRET` - DigitalOcean Spaces secret

**Optional (for subscriptions):**
- `STRIPE_PRICE_BASIC`, `STRIPE_PRICE_FEATURED`, `STRIPE_PRICE_PREMIUM` - Stripe price IDs for seller tiers

**Optional (for shipping):**
- `EASYPOST_API_KEY` - EasyPost API key for shipping rates/labels
- `EASYPOST_WEBHOOK_SECRET` - EasyPost webhook HMAC secret

**Defaults usually fine:**
- `DATABASE_HOST`, `DATABASE_PORT` - Database connection (default: localhost:5432)
- `REDIS_URL` - Redis connection (default: redis://localhost:6379/0)
- `SITE_URL` - Base URL for callbacks (default: http://localhost:8000)
- `EMAIL_*` - Email settings (console backend used in development)

For Ansible deploys, these go in `ansible/group_vars/vault.yml`.

## Seller Subscription Tiers
- Starter (Free): 50 listings, 12.95% commission
- Basic ($9.99/mo): 200 listings, 9.95% commission
- Featured ($29.99/mo): 1000 listings, 7.95% commission
- Premium ($99.99/mo): unlimited listings, 5.95% commission

Trusted Sellers get an additional 2% discount (floor 3.95%). See Trusted Seller Program below.

## Trusted Seller Program

Automated program that rewards high-performing sellers with badges, lower commissions, and platform auction access.

### Qualification (automatic, checked daily at 4 AM)
- 20+ completed sales
- 4.5+ average rating with 10+ reviews
- Featured or Premium subscription tier
- Managed by `seller_tools.tasks.update_trusted_seller_status` Celery task

### Key Fields
- `Profile.is_trusted_seller` — Boolean, updated daily by Celery task
- `Profile.qualifies_as_trusted_seller` — computed property checking current metrics

### Benefits
1. **Gold badge** on listing cards, listing detail, seller profiles (web + mobile apps)
2. **2% commission discount** — applied in `StripeService.get_seller_commission_rate()` with 3.95% floor
3. **Platform auction lot submission** — trusted sellers can submit listings for curated events

### Marketing Page
- URL: `/trusted-seller/` → `app.views.trusted_seller_landing`
- Template: `templates/pages/trusted_seller.html`

## Platform Auction Events

Curated auction events run by the platform. Trusted sellers submit lots for staff review.

### Models
- `AuctionEvent` — with `is_platform_event`, `cadence` (monthly/quarterly/special), `accepting_submissions`, `submission_deadline`, `status` (draft/preview/live/ended)
- `AuctionLotSubmission` — links seller + listing to an event with status (pending/approved/rejected/withdrawn), staff review fields

### Workflow
1. Staff creates `AuctionEvent` with `is_platform_event=True`, `accepting_submissions=True`
2. Trusted sellers submit listings via `/marketplace/auctions/<slug>/submit/`
3. Staff reviews in admin — approve auto-assigns `lot_number` and links listing to event
4. Event goes live, lots displayed in grid on `/marketplace/auctions/<slug>/`

### URLs
- `/marketplace/auctions/` — browse platform events
- `/marketplace/auctions/<slug>/` — event detail with lots
- `/marketplace/auctions/<slug>/submit/` — submission form (trusted sellers only)

### API Endpoints
- `GET /api/v1/marketplace/auctions/platform/` — list platform events
- `POST /api/v1/marketplace/auctions/platform/<slug>/submit/` — submit lot (`{"listing_id": <id>}`)
- `GET /api/v1/marketplace/auctions/submissions/` — user's own submissions

## Celery Tasks

### Pricing Tasks
- `pricing.tasks.update_price_guide_stats` - Update cached price stats
- `pricing.tasks.record_sale_from_order` - Record sales in price guide
- `pricing.tasks.check_price_alerts` - Check and trigger price alerts (hourly)
- `pricing.tasks.import_all_market_data` - Import market data (6 AM and 6 PM)

### Collection Tasks
- `user_collections.tasks.update_collection_values` - Update collection valuations
- `user_collections.tasks.create_daily_snapshots` - Create daily value snapshots

### Subscription Billing Tasks (seller_tools.tasks)
- `process_subscription_renewals` - Process due renewals (daily 2 AM)
- `retry_failed_payments` - Retry past_due subscriptions (hourly :30)
- `expire_grace_periods` - Downgrade expired subscriptions (daily 3:30 AM)
- `send_renewal_reminders` - Email 3 days before renewal (daily 10 AM)

### Seller Status Tasks
- `seller_tools.tasks.update_trusted_seller_status` - Auto-promote/demote trusted sellers (daily 4 AM)

### Listing & Alert Tasks
- `marketplace.tasks.end_auctions` - End expired auctions, notify winners/sellers, expire no-bid listings (every 5 min)
- `marketplace.tasks.expire_unpaid_orders` - Cancel orders pending > 15min, restore listing stock (every 5 min)
- `alerts.tasks.send_listing_expired_notification` - Email + in-app alert when auction ends with no bids
- `alerts.tasks.send_relist_reminders` - Remind sellers about expired listings after 3 days (daily 11 AM)

### Email Marketing Tasks
- `alerts.tasks.send_welcome_email` - Welcome email with live auctions (triggered by allauth signal, not beat)
- `alerts.tasks.send_weekly_auction_digest` - Weekend auctions + most watched (Friday 10 AM)
- `alerts.tasks.send_watched_auction_final_24h` - Saved auctions ending in 24h (every 30 min)
- `alerts.tasks.send_weekly_results_recap` - Top auction results recap (Monday 10 AM)

## Market Data Architecture

Price guide data is imported via `pricing/services/market_data.py`:
- `EbayMarketData`, `HeritageAuctionsData`, `GoCollectData` - scraper classes
- `MarketDataImporter` - coordinates imports, matches to price guide items
- Celery task `import_all_market_data` runs at 6 AM and 6 PM daily
- All scrapers use `_make_proxied_request()` with free rotating proxies (eBay/Heritage block datacenter IPs)
- `download_image_for_item()` downloads images for PriceGuideItems during import
- eBay parser handles both legacy `.s-item` and new `.s-card` HTML layouts (2025+ redesign)

## REST API (Added 2026-01)

Full REST API for Android/iOS app support using Django REST Framework.

### API Base URL
- `/api/v1/` - API root

### Authentication
- JWT tokens via `/api/v1/auth/token/` (POST username, password)
- Refresh tokens via `/api/v1/auth/token/refresh/`
- Google OAuth: POST `/api/v1/auth/google/` with `{"id_token": "..."}`
- Apple Sign-In: POST `/api/v1/auth/apple/` with `{"id_token": "...", "first_name": "...", "last_name": "..."}`
- Password reset: POST `/api/v1/auth/password/reset/` and `/api/v1/auth/password/reset/confirm/`
- Bearer token in header: `Authorization: Bearer <token>`

### API Documentation
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI Schema: `/api/schema/`

### API Endpoints
Main resource endpoints under `/api/v1/`:
- `auth/` - JWT token auth
- `accounts/` - User profiles, registration, devices
- `marketplace/` - Listings, offers, orders, auctions
- `collections/` - User collections (`/mine/` for user's own, `/public/` for browsing)
- `pricing/` - Price guide items, grades, sales history
- `alerts/` - Notifications, wishlists, saved searches
- `social/` - Feed, follows, messages, forums
- `scanner/` - Image scanning
- `seller/` - Dashboard, analytics, inventory
- `items/` - Categories, search

### Nested Routes
Uses `drf-nested-routers` for nested resources:
- `/api/v1/collections/{id}/items/` - Items within a collection
- `/api/v1/pricing/items/{id}/grades/` - Grades for a price guide item
- `/api/v1/pricing/items/{id}/sales/` - Sales history for a price guide item

### Key API Files
```
api/                            # Central API app
├── urls.py                     # API routing
├── permissions.py              # Custom permissions (IsOwner, IsOwnerOrReadOnly, etc.)
└── pagination.py               # Custom pagination classes

{app}/api/                      # Each app has an api/ subdirectory
├── __init__.py
├── serializers.py              # DRF serializers
├── views.py                    # API views/viewsets
└── urls.py                     # App-specific API routes
```

### API Rate Limiting
- Anonymous: 100 requests/hour
- Authenticated: 1000 requests/hour
- Automatically disabled during tests (`TESTING` flag)

### CORS
- Production: `heroesandmore.com` and `www.heroesandmore.com` only
- Development (`DEBUG=True`): all origins allowed
- Credentials allowed (`CORS_ALLOW_CREDENTIALS = True`)

### Push Notifications
- `accounts.DeviceToken` model stores FCM tokens (Firebase)
- Register device: POST `/api/v1/accounts/me/device/`
- Notification types: new_bid, outbid, offer, order_shipped, message, price_alert

## Stripe Payment Integration

### Overview
Full Stripe integration for marketplace payments:
- **Stripe Payments**: PaymentIntents for checkout with saved cards support
- **Stripe Connect**: Express accounts for seller payouts
- **Internal Subscription Billing**: PaymentIntents for seller tier subscriptions (not Stripe Billing)

### Webhook Endpoints
- Main: `/marketplace/webhooks/stripe/` - payment_intent.*, charge.*
- Connect: `/marketplace/webhooks/stripe-connect/` - account.updated

### Service Layer (`marketplace/services/`)
- `stripe_service.py` - Payment intents, payment methods, refunds
- `connect_service.py` - Seller account onboarding, transfers
- `subscription_service.py` - Internal subscription billing via PaymentIntents

### Seller Onboarding (Embedded)
Uses Stripe Connect embedded components so users stay on-site:
- Onboarding page: `/marketplace/seller-setup/`
- Account session API: `/marketplace/seller-setup/session/`
- Template: `templates/marketplace/seller_setup.html`
- Uses `StripeConnect.onLoad` callback with `account-onboarding` component
- First visit shows country picker (`seller_setup_country.html`), POST creates account, then shows embedded onboarding
- **International sellers supported** — `connect_service.py` does NOT restrict `country` parameter, allowing Stripe to handle supported countries automatically

### Local Testing
```bash
stripe listen --forward-to localhost:8000/marketplace/webhooks/stripe/
```

### Payment Flow (Marketplace)
1. Buyer clicks "Buy Now" -> creates pending Order
2. Checkout shows Stripe Elements, creates PaymentIntent with seller's Connect account as destination
3. Webhook updates Order status, listing marked sold
4. Funds transferred to seller minus commission

### Subscription Billing (Internal)
Subscription billing is handled internally using PaymentIntents instead of Stripe Billing:
- Uses unified `Profile.stripe_customer_id` for all payments
- Charges via PaymentIntent with `off_session=True` for renewals
- Celery tasks handle renewals, retries, and grace period expiry
- Benefits: Single customer record, no Stripe dashboard management, full local control

#### Key Models
- `SellerSubscription` - Subscription state, payment method FK, billing tracking
- `SubscriptionBillingHistory` - Audit trail for all billing events

#### Subscription Service Methods
- `subscribe(user, tier, payment_method_id)` - Initial subscription with immediate charge
- `charge_renewal(subscription)` - Charge renewal (called by Celery)
- `change_tier(user, new_tier)` - Upgrade/downgrade with proration
- `cancel(user, at_period_end=True)` - Cancel gracefully or immediately

#### Settings
```python
SUBSCRIPTION_GRACE_PERIOD_DAYS = 7      # Days before downgrading
SUBSCRIPTION_MAX_RETRY_ATTEMPTS = 4     # Max payment retries
SUBSCRIPTION_RETRY_INTERVALS = [1, 3, 5, 7]  # Days between retries
```

## EasyPost Shipping Integration

Full EasyPost integration for real-time carrier rates, label purchase, address validation, and automated tracking.

### Shipping Modes
- `flat` (default) — seller sets fixed price, existing behavior unchanged
- `calculated` — real-time carrier rates at checkout via EasyPost
- `free` — $0 shipping

### Shipping App (`shipping/`)
```
shipping/
├── models.py          # Address, ShippingProfile, ShippingLabel, ShippingRate
├── admin.py
├── apps.py
├── webhooks.py        # EasyPost webhook handler (HMAC verified)
├── tasks.py           # cleanup_expired_rates (daily 1 AM)
├── urls.py            # /shipping/webhooks/easypost/
├── api/               # DRF endpoints for mobile app
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
└── tests/
    ├── test_models.py, test_service.py, test_views.py, test_webhooks.py
```

### Key Models
- **Address** — Structured shipping address with EasyPost verification, `to_easypost_dict()`, `formatted` property, unique default per user
- **ShippingProfile** — Pre-seeded package profiles: `standard-card` (2oz), `graded-slab` (8oz), `multiple-cards` (16oz), `figure-toy` (32oz), `custom`
- **ShippingLabel** — Purchased labels with tracking, void support
- **ShippingRate** — Cached rate quotes (expire after 30 min)

### Service Layer (`marketplace/services/easypost_service.py`)
Static method pattern matching StripeService:
- `verify_address()` — Verify + return corrected address
- `get_rates()` — Get sorted carrier rate list
- `buy_label()` — Purchase label, return tracking/URL
- `refund_label()` — Void/refund label
- `build_parcel()` — Build from listing fields or profile
- `build_customs_info()` — For international shipments
- `process_tracking_webhook()` — Map EasyPost → order statuses

### Fee Structure
Platform fee = $0.29 (Stripe processing) + $0.05 (shipping label) + commission % per tier. See `StripeService.PLATFORM_FLAT_FEE`.

### Checkout Flow (Calculated Shipping)
1. Buyer enters structured address fields (replaces textarea for new orders)
2. Address verified via EasyPost AJAX (`/marketplace/shipping/validate-address/`)
3. Rates fetched (`/marketplace/<pk>/shipping-rates/`)
4. Buyer selects rate → total updated (`/marketplace/order/<pk>/select-rate/`)
5. Payment proceeds as normal

### Seller Label Purchase
Seller clicks "Buy Label" on order detail → selects rate → label purchased → tracking auto-populated.
URL: `/marketplace/order/<pk>/buy-label/`

### Webhook
`/shipping/webhooks/easypost/` — HMAC-verified, handles `tracker.updated` events, maps statuses: `in_transit`→`shipped`, `delivered`→`delivered`. Status never goes backwards.

### API Endpoints
```
GET/POST  /api/v1/shipping/addresses/              # CRUD
POST      /api/v1/shipping/addresses/validate/      # Verify address
POST      /api/v1/shipping/rates/                   # Get rates
POST      /api/v1/shipping/labels/<order_id>/buy/   # Buy label
POST      /api/v1/shipping/labels/<order_id>/void/  # Void label
GET       /api/v1/shipping/tracking/<order_id>/     # Tracking info
GET       /api/v1/shipping/profiles/                # List profiles
```

### Settings
```python
EASYPOST_API_KEY = getattr(config, 'EASYPOST_API_KEY', None)
EASYPOST_WEBHOOK_SECRET = getattr(config, 'EASYPOST_WEBHOOK_SECRET', '')
SHIPPING_RATE_CACHE_MINUTES = 30
SHIPPING_LABEL_FORMAT = 'PDF'
```

## Email (Self-Hosted)

Email is self-hosted on the server using Postfix with OpenDKIM and PostSRSd.

- **mail.heroesandmore.com** — SENDING domain (outbound, DKIM-signed, e.g., noreply@mail.heroesandmore.com)
- **heroesandmore.com** — RECEIVING domain (forwards to team via `/etc/postfix/virtual`)
- Port 25 must be open for inbound mail (configured in `ansible/security.yml`)
- DNS (SPF, DKIM, DMARC, PTR) managed via DigitalOcean API
- **Critical**: `SRS_EXCLUDE_DOMAINS=mail.heroesandmore.com,heroesandmore.com` must be in `/etc/default/postsrsd` — without this, SPF/DKIM alignment breaks and transactional emails get rejected by Gmail/Outlook

## GitHub Repositories

Project is split across three standalone repositories (each in its own directory):

| Repo | URL | Local Path |
|------|-----|------------|
| Web | https://github.com/nadermx/heroesandmore | `~/heroesandmore/` (this repo) |
| Android | https://github.com/nadermx/heroesandmore-android | `~/heroesandmore-android/` |
| iOS | https://github.com/nadermx/heroesandmore-ios | `~/heroesandmore-ios/` |

## Team

| Name | Email | Role |
|------|-------|------|
| John | john@nader.mx | Owner |
| Tony | tmgormond@gmail.com | Collaborator |
| Jim | jim@sickboys.com | Collaborator |

## Testing Notes
- Rate limiting is automatically disabled during tests (`TESTING` flag in settings.py)
- Stripe API calls should be mocked in tests - see `marketplace/tests/test_orders.py` for examples
- API tests use `rest_framework.test.APIClient` with JWT authentication
- Test database uses SQLite in-memory for speed
- **Allauth SocialApp required**: Tests rendering login/signup pages must create a Google `SocialApp` in setUp — use the `SocialAppMixin` from `accounts/tests/test_views.py`
- **Honeypot in signup tests**: POST to `/auth/signup/` must include `'_ts': str(int(time.time()) - 5)` or the honeypot middleware silently redirects (fakes success). See `accounts/tests/test_views.py` `_signup_data()` helper.

## Shared Utilities

### Site Stats Pattern
`items.views._get_site_stats()` returns dynamic platform stats. Used by homepage, about page, `/sell/`, and `/bid/` landing pages. Import it when any view needs real-time platform numbers.

**Variable names returned** (use these in templates):
- `stat_active_listings` — active listing count
- `stat_collectors` — active user count
- `stat_sold_total` — total sold dollar amount
- `stat_avg_rating` — average seller rating (rounded, or `None`)

### Custom Template Tags
- **`seo_tags`** (`items/templatetags/seo_tags.py`): `absolute_url`, `absolute_static`, `absolute_media`, `json_ld_escape` — used in meta tags and JSON-LD structured data across templates
- **`seller_tools_tags`** (`seller_tools/templatetags/seller_tools_tags.py`): `get_item` filter for template dictionary lookups

### Frontend Error Logging
`/api/log-error/` (POST) — JavaScript errors are sent here and logged to the `frontend` logger. Implemented in `app/views.py`.

### Context Processor
`app/context_processors.seo()` provides `site_url` and `default_og_image` to all templates.

## Multi-Quantity Listings

Fixed-price listings support multi-quantity (e.g., 20 of the same item). Auctions are always quantity=1.

- `Listing.quantity` / `Listing.quantity_sold` / `Listing.quantity_available` (property)
- `Listing.record_sale(qty)` — atomically decrements stock using `select_for_update()` + `F()`. Returns `True`/`False`.
- `Listing.reverse_sale(qty)` — atomically restores stock (for refunds/cancellations)
- **Never set `listing.status = 'sold'` directly** — always use `record_sale()` / `reverse_sale()`
- `Order.quantity` tracks units per order; `item_price = unit_price * quantity`, shipping is flat per order

## Dashboard Templates
- **`templates/accounts/dashboard.html`** — User dashboard (general stats: listings, sales, purchases). Route: `/dashboard/`
- **`seller_tools/templates/seller_tools/dashboard.html`** — Seller dashboard (subscription tier, commission, listing stats). Route: `/seller/`
- `templates/accounts/seller_dashboard.html` exists but is **unused dead code** — the seller dashboard view renders `seller_tools/dashboard.html`

## Bulk Import & Photo Capture Flow
- Excel template download with dropdown validation (openpyxl) — categories, conditions, grading services
- Supports both Excel (.xlsx) and CSV upload
- Image columns (`image1_url`–`image5_url`) accept web URLs or local filenames from uploaded images
- Post-import photo capture: mobile-first camera flow via HTMX at `/seller/import/<pk>/photos/`
- Photo slots use `<input type="file" accept="image/*" capture="environment">` for rear camera on mobile

## Authentication & Spam Protection

### Auth
- Django allauth with email + Google OAuth + Apple Sign-In
- **OAuth credentials stored in DB** via `SocialApp` model (not in settings) — allauth v65 raises `MultipleObjectsReturned` if both settings `APP` keys and DB records exist for the same provider
- `SOCIALACCOUNT_PROVIDERS` in settings.py contains only scope/params config, NOT client ID/secret
- allauth v65 uses HMAC email confirmation by default (`ACCOUNT_EMAIL_CONFIRMATION_HMAC = True`)
- `LOGIN_URL = '/auth/signup/'` — intentional: unauthenticated users are sent to signup, not login
- Mobile API social auth (`accounts/api/views.py`: `GoogleAuthView`, `AppleAuthView`) is independent of allauth — verifies tokens directly with Google/Apple APIs and issues JWT tokens

### Honeypot Spam Protection
Four-layer protection on signup and contact forms (`app/middleware.py` + `app/views.py`):
1. **Hidden `website` field** — positioned off-screen (`left: -9999px`), bots auto-fill it
2. **Timestamp `_ts` field** — set via JS `Date.now()/1000`, submissions under 3 seconds = bot
3. **Missing timestamp detection** — headless bots that don't execute JS won't have `_ts` at all
4. **Bot username detection** — flags random gibberish usernames (e.g., `hpPAeAxtNbBktCqnG`) via regex pattern matching on length, mixed case, and lack of common separators

Bots get silently redirected with a fake success message (no error shown). Spam attempts logged via `logger.warning()`.

When adding honeypot to new forms, add both hidden fields to the template and check them in the view or middleware. See `templates/account/signup.html` and `templates/pages/contact.html` for template examples.

## Listing Expiration & Relist Flow
- When `end_auctions` finds no-bid auctions past their end time, it sets `status='expired'` + `expired_at=now()`
- Seller gets email (`listing_expired.html`) + in-app alert immediately
- After 3 days, `send_relist_reminders` sends a follow-up email (`relist_reminder.html`)
- Relist view (`/marketplace/<pk>/relist/`): auctions reset to draft (bids cleared), fixed-price reactivated immediately
- Expired listings can also be edited directly (same as draft/active)

## Guest Checkout

Anonymous users can buy fixed-price items without creating an account. Auctions still require login.

### Order Model (Guest Support)
- `Order.buyer` is nullable (`null=True, blank=True`) — `None` for guest orders
- `Order.guest_email` / `Order.guest_name` — collected at checkout for guests
- `Order.guest_order_token` — auto-generated via `secrets.token_urlsafe(48)` on save when `buyer` is None
- `Order.buyer_email` property — returns `buyer.email` or `guest_email`
- `Order.buyer_display_name` property — returns buyer's name/username or guest_name/guest_email

### Checkout Flow
- `checkout` view creates Order with `buyer=None` for anonymous users, stores `guest_order_token` in session
- `_get_order_for_checkout()` helper does dual lookup: by `buyer=request.user` OR by session `guest_order_token`
- `StripeService.create_payment_intent()` creates ephemeral Stripe customer for guests (no saved cards)
- Guest order tracking: `/marketplace/order/track/` (lookup) and `/marketplace/order/track/<token>/` (detail)
- Guest confirmation page prompts "Create an account to track your order"

### Important Rules
- Only fixed-price listings allow guest checkout — auctions redirect to signup
- Offers require login
- In-app Alert creation is skipped for guest orders (no user to attach to)
- `alerts.tasks.send_order_notifications` uses `order.buyer_email` instead of `order.buyer.email`

## Founding Collector Program

Early adopter recognition for users who sign up before `FOUNDING_MEMBER_CUTOFF` (settings.py, default `2026-06-01`).

### Key Fields
- `Profile.is_founding_member` — Boolean, auto-set in `create_user_profile` signal
- `Profile.founding_member_since` — DateTimeField, set at signup if before cutoff

### Badge Display (Must Be Consistent)
When adding a new badge type, update ALL these locations:
- `templates/components/listing_card.html` — card overlay badges
- `templates/marketplace/listing_detail.html` — seller info section
- `templates/accounts/profile.html` — profile header
- `templates/accounts/dashboard.html` — dashboard header
- `seller_tools/templates/seller_tools/dashboard.html` — seller dashboard header
- `accounts/admin.py` — list_display and list_filter
- `marketplace/api/serializers.py` — `seller_is_*` fields on ListingListSerializer and ListingDetailSerializer
- `accounts/api/serializers.py` — ProfileSerializer and PublicProfileSerializer
- Android app: DTOs, domain models, repository mappings, UI composables
- iOS app: Model structs, SwiftUI views

## Email Marketing Flows

### Celery Tasks (alerts/tasks.py)
- `send_welcome_email(user_id)` — triggered by allauth `user_signed_up` signal (wired in `accounts/signals.py`)
- `send_weekly_auction_digest()` — Friday 10 AM, auctions ending this weekend
- `send_watched_auction_final_24h()` — every 30 min, alerts for saved auctions ending in 24h
- `send_weekly_results_recap()` — Monday 10 AM, top auction results from last week

### Signal Wiring
- `accounts/apps.py` has `AccountsConfig` with `ready()` that imports `accounts.signals`
- `accounts/signals.py` has `user_signed_up` signal handler from allauth
- `INSTALLED_APPS` uses `'accounts.apps.AccountsConfig'` (not bare `'accounts'`)

## Gotchas & Pitfalls
- **allauth v65 SocialApp**: OAuth credentials MUST be in DB only (via `SocialApp` admin model), NOT in settings `APP` keys — having both causes `MultipleObjectsReturned`
- `bid_count` is NOT a model property — use `listing.bids.count` or annotate with `Count('bids')`
- **Never set `listing.status = 'sold'` directly** — always use `record_sale()` / `reverse_sale()`
- Commission is tier-based per `SellerSubscription.commission_rate` (not the flat `PLATFORM_FEE_PERCENT` in settings, which is a base fallback)
- Django template syntax: `{% with %}` blocks cannot contain `{% else %}` — only `{% if %}` blocks can
- Avoid `-webkit-appearance: none` on `.form-control` — it breaks native iOS keyboard behavior
- Error pages (`404.html`, `403.html`, `500.html`) are standalone HTML — they don't extend `base.html` for reliability
- On server, `config.py` is owned by `www:www` — use `sudo -u www` when running scripts that need it
- **Celery Beat scheduler**: Uses default file-based scheduler — do NOT use `django_celery_beat.schedulers:DatabaseScheduler` (it's installed but not in INSTALLED_APPS, will crash)
- **Auth templates**: Custom templates exist for `login.html`, `signup.html`, `logout.html`, `password_reset.html`, `password_reset_done.html`, `password_reset_from_key.html`, `password_reset_from_key_done.html` — any missing allauth template will render unstyled
- **COOP header**: `SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'` is required for Stripe Connect embedded components — `same-origin` blocks their cross-origin popups
- **Three-repo consistency**: When adding new API fields or badges, update all three repos (web, Android, iOS) — see "Badge Display" checklist under Founding Collector Program
- **Order "completed" status filter**: When counting sold/completed orders, always use `status__in=['paid', 'shipped', 'delivered', 'completed']` — not just `status='paid'`, which misses orders that have progressed
- **Landing page views live in `app/views.py`**: `sell_landing`, `bid_landing`, `trusted_seller_landing`, `contact` — not in any app's views.py
