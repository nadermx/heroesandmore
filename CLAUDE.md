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
python manage.py import_market_data       # Import price data (--source ebay|heritage|gocollect --verbose)
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
- `/collections/` - Browse collections
- `/social/forums/` - Forums
- `/price-guide/` - Price guide and market data
- `/scanner/` - Item scanner (image recognition)
- `/seller/` - Seller dashboard and tools
- `/sell/` - Sell landing page (redirects to listing create if authenticated)
- `/admin/` - Django admin
- `/api/v1/` - REST API root
- `/api/docs/` - Swagger UI

## Key Models

### Core Models
- `accounts.Profile` - User profiles, seller verification, subscription tiers
- `accounts.RecentlyViewed` - Track recently viewed listings
- `items.Category` - Hierarchical categories
- `items.Item` - Base item database
- `marketplace.Listing` - For sale items (fixed price and auctions)
- `marketplace.AuctionEvent` - Scheduled auction events
- `marketplace.Order` - Purchases
- `marketplace.Offer` - Make offer/counteroffer system
- `user_collections.Collection` - User collections with value tracking
- `user_collections.CollectionValueSnapshot` - Daily value snapshots for charts

### Price Guide (pricing app)
- `pricing.PriceGuideItem` - Master catalog of items with pricing data
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

Available loggers: `accounts`, `marketplace`, `pricing`, `alerts`, `scanner`, `api`, `seller_tools`, `frontend`

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

## Market Data Architecture

Price guide data is imported via `pricing/services/market_data.py`:
- `EbayMarketData`, `HeritageAuctionsData`, `GoCollectData` - scraper classes
- `MarketDataImporter` - coordinates imports, matches to price guide items
- Celery task `import_all_market_data` runs at 6 AM and 6 PM daily
- External sources require proxy service (eBay, Heritage block direct requests)

## REST API (Added 2026-01)

Full REST API for Android/iOS app support using Django REST Framework.

### API Base URL
- `/api/v1/` - API root

### Authentication
- JWT tokens via `/api/v1/auth/token/` (POST username, password)
- Refresh tokens via `/api/v1/auth/token/refresh/`
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
- Uses `StripeConnect.init()` with `account-onboarding` component

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

## Email (Self-Hosted)

Email is self-hosted on the server using Postfix with OpenDKIM and PostSRSd.

### Domain Setup
- **mail.heroesandmore.com** - SENDING domain (outbound emails, e.g., noreply@mail.heroesandmore.com)
- **heroesandmore.com** - RECEIVING domain (inbound, forwards to team members)

### Firewall
Port 25 (SMTP) **must** be open for inbound mail delivery. This is configured in `ansible/security.yml`. If the firewall is ever reset, verify port 25 is allowed: `ufw allow 25/tcp`

### DNS Records (managed via DigitalOcean API)
- SPF: `v=spf1 ip4:174.138.33.140 a ~all`
- DKIM: `mail._domainkey.mail.heroesandmore.com`
- DMARC: `v=DMARC1; p=none; rua=mailto:postmaster@heroesandmore.com; fo=1`
- PTR: `174.138.33.140` → `mail.heroesandmore.com` (set via DigitalOcean droplet name)

### Email Forwarding with SRS
PostSRSd (Sender Rewriting Scheme) is configured to prevent SPF failures when forwarding external emails. Config: `/etc/default/postsrsd`

### Credentials
API keys are stored in `~/.credentials/`:
- `digitalocean_api_key` - DNS management
- Other keys: aws, github, linode, vultr, etc.

### Email Aliases
Config file: `/etc/postfix/virtual` - forwards addresses to team members.

```bash
# Add new alias
ssh heroesandmore@174.138.33.140
sudo nano /etc/postfix/virtual
# Add: newemail@heroesandmore.com    recipient@example.com
sudo postmap /etc/postfix/virtual && sudo systemctl reload postfix
```

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

## Shared Utilities

### Site Stats Pattern
`items.views._get_site_stats()` returns dynamic platform stats (active listings, collectors count, total sold, avg rating). Used by the homepage, about page, and `/sell/` landing page. Import it when any view needs real-time platform numbers.

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

## Notes
- The `collections` app uses `item_collections` as the related_name to avoid conflicts with Python's built-in collections module
- All listing images are stored in `media/listings/`
- User avatars are stored in `media/avatars/`
- Commission is tier-based per `SellerSubscription.commission_rate` (not the flat `PLATFORM_FEE_PERCENT` in settings, which is a base fallback)
- Image scanner requires Google Cloud Vision API (configure credentials)
- Error pages (`404.html`, `403.html`, `500.html`) are standalone HTML — they don't extend `base.html` for reliability
- Django template syntax: `{% with %}` blocks cannot contain `{% else %}` — only `{% if %}` blocks can
- Avoid `-webkit-appearance: none` on `.form-control` — it breaks native iOS keyboard behavior
