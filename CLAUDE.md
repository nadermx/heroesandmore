# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HeroesAndMore is a collectibles marketplace and community platform built with Django. Features include listings (fixed price and auctions), collections, price guide, image scanner, seller tools, and social features.

## Tech Stack
- **Backend**: Django 5.x, Python 3.12
- **Database**: PostgreSQL (SQLite for local dev)
- **Cache/Queue**: Redis, Celery
- **Frontend**: Bootstrap 5, HTMX
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

## Key URLs
- `/` - Homepage
- `/items/` - Browse categories
- `/marketplace/` - All listings
- `/collections/` - Browse collections
- `/social/forums/` - Forums
- `/price-guide/` - Price guide and market data
- `/scanner/` - Item scanner (image recognition)
- `/seller/` - Seller dashboard and tools
- `/admin/` - Django admin

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
- `seller_tools.BulkImport` - Bulk listing imports from CSV
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

### Quick Deploy (Code Only)
For simple code updates without config changes:
```bash
cd ansible
ansible-playbook -i servers gitpull.yml
```

### Full Deploy (With Config)
For deployments that update config.py:
```bash
cd ansible
ansible-playbook -i servers deploy.yml
```

### Backup Database
```bash
cd ansible
ansible-playbook -i servers backup.yml
```

### Check Logs
```bash
ansible -i servers all -m shell -a "tail -100 /var/log/heroesandmore/heroesandmore.log" --become
```

### Restart Services
```bash
ansible -i servers all -m shell -a "supervisorctl restart heroesandmore:*" --become
```

### SSH to Server
```bash
ssh heroesandmore@174.138.33.140
cd /home/www/heroesandmore
```

## Config Values Needed (config.py)
Copy `config.py.example` to `config.py` and set:
- `SECRET_KEY` - Django secret key
- `DATABASE_PASSWORD` - PostgreSQL password
- `STRIPE_PUBLIC_KEY` - Stripe publishable key
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing
- `DO_SPACES_KEY` - DigitalOcean Spaces access key
- `DO_SPACES_SECRET` - DigitalOcean Spaces secret

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

### API Structure
```
api/v1/
├── auth/
│   ├── token/                  # Get JWT tokens
│   └── token/refresh/          # Refresh access token
├── accounts/
│   ├── register/               # Create account
│   ├── me/                     # Current user profile
│   ├── me/avatar/              # Upload avatar
│   ├── me/password/            # Change password
│   ├── me/recently-viewed/     # Recently viewed listings
│   ├── me/device/              # Register device for push notifications
│   └── profiles/<username>/    # Public profiles
├── marketplace/
│   ├── listings/               # CRUD listings, bid, offer, save
│   ├── saved/                  # Saved listings
│   ├── offers/                 # Offers (accept/decline/counter)
│   ├── orders/                 # Orders (ship/received/review)
│   └── auctions/               # Auction events
├── collections/
│   ├── mine/                   # User's collections
│   ├── <id>/items/             # Collection items
│   ├── <id>/value/             # Value summary
│   └── public/                 # Public collections
├── pricing/
│   ├── items/                  # Price guide items
│   ├── items/<id>/grades/      # Prices by grade
│   ├── items/<id>/sales/       # Recent sales
│   ├── items/<id>/history/     # Price history (charts)
│   └── trending/               # Trending items
├── alerts/
│   ├── notifications/          # User notifications
│   ├── wishlists/              # Wishlists with items
│   ├── saved-searches/         # Saved searches
│   └── price-alerts/           # Price alerts
├── social/
│   ├── feed/                   # Activity feed
│   ├── following/              # Users following
│   ├── followers/              # User's followers
│   ├── follow/<user_id>/       # Follow/unfollow
│   ├── messages/               # Conversations
│   └── forums/                 # Forum categories/threads
├── scanner/
│   ├── scan/                   # Upload for scanning
│   ├── scans/                  # Scan history
│   └── sessions/               # Bulk scan sessions
├── seller/
│   ├── dashboard/              # Seller stats
│   ├── analytics/              # Sales analytics
│   ├── subscription/           # Current subscription
│   ├── inventory/              # Inventory management
│   ├── imports/                # Bulk imports
│   ├── orders/                 # Orders to fulfill
│   └── sales/                  # Sales history
└── items/
    ├── categories/             # Category tree
    ├── search/                 # Global search
    └── autocomplete/           # Search autocomplete
```

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

Email is self-hosted on the server using Postfix with OpenDKIM.

### Domain Setup
- **mail.heroesandmore.com** - SENDING domain (outbound emails, e.g., noreply@mail.heroesandmore.com)
- **heroesandmore.com** - RECEIVING domain (inbound, forwards to team members)

### DNS Records (managed via DigitalOcean API)
- SPF: `v=spf1 ip4:174.138.33.140 a ~all`
- DKIM: `mail._domainkey.mail.heroesandmore.com`
- DMARC: `v=DMARC1; p=none; rua=mailto:postmaster@mail.heroesandmore.com; fo=1`

### Credentials
API keys are stored in `~/.credentials/`:
- `digitalocean_api_key` - DNS management
- Other keys: aws, github, linode, vultr, etc.

### Email Aliases (Forwarding)
Config file: `/etc/postfix/virtual`

```
# Group forwards (to all team members)
hello@heroesandmore.com     john@nader.mx, tmgormond@gmail.com, jim@sickboys.com
support@heroesandmore.com   john@nader.mx, tmgormond@gmail.com, jim@sickboys.com
auctions@heroesandmore.com  john@nader.mx, tmgormond@gmail.com, jim@sickboys.com
sales@heroesandmore.com     john@nader.mx, tmgormond@gmail.com, jim@sickboys.com

# Individual forwards
john@heroesandmore.com      john@nader.mx
jim@heroesandmore.com       jim@sickboys.com
tony@heroesandmore.com      tmgormond@gmail.com

# System addresses
info@heroesandmore.com      john@nader.mx
postmaster@heroesandmore.com john@nader.mx
```

### Adding New Email Alias
```bash
ssh heroesandmore@174.138.33.140
sudo nano /etc/postfix/virtual
# Add: newemail@heroesandmore.com    recipient@example.com
sudo postmap /etc/postfix/virtual
sudo systemctl reload postfix
```

### Sending Test Email
```bash
ssh heroesandmore@174.138.33.140
echo "Test message" | mail -s "Subject" -a "From: HeroesAndMore <noreply@mail.heroesandmore.com>" recipient@example.com
```

## GitHub Repositories

Project is split across three repositories:

| Repo | URL | Description |
|------|-----|-------------|
| Web | https://github.com/nadermx/heroesandmore | Django web app (this repo) |
| Android | https://github.com/nadermx/heroesandmore-android | Native Android app (Kotlin) |
| iOS | https://github.com/nadermx/heroesandmore-ios | Native iOS app (Swift/SwiftUI) |

## Team

| Name | Email | Role |
|------|-------|------|
| John | john@nader.mx | Owner |
| Tony | tmgormond@gmail.com | Collaborator |
| Jim | jim@sickboys.com | Collaborator |

## Notes
- The `collections` app uses `item_collections` as the related_name to avoid conflicts with Django's built-in collections module
- All listing images are stored in `media/listings/`
- User avatars are stored in `media/avatars/`
- Platform fee is tier-based (see commission rates above)
- Image scanner requires Google Cloud Vision API (configure credentials)
