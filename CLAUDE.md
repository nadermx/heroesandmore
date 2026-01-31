# HeroesAndMore - Collectibles Marketplace

## Project Overview
A full-featured collectibles marketplace and community platform built with Django.

## Tech Stack
- **Backend**: Django 6.0, Python 3.12
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

### Create initial categories
```bash
python manage.py shell
# Then run the seed script or add via admin
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

## Common Tasks

### Add New Category
Go to `/admin/items/category/` and add via Django admin.

### Check Pending Orders
```bash
ansible -i ansible/servers all -m shell -a "cd /home/www/heroesandmore && venv/bin/python manage.py shell -c \"from marketplace.models import Order; print(Order.objects.filter(status='pending').count())\"" --become --become-user=www
```

### Database Backup
```bash
ansible -i ansible/servers all -m shell -a "sudo -u postgres pg_dump herosandmore > /tmp/herosandmore_backup.sql" --become
```

## New Features (Added 2026-01)

### Price Guide System
- Comprehensive price tracking for collectibles
- Prices by grade (PSA, BGS, CGC, SGC, Raw)
- Historical sales data and trends
- Price suggestions when creating listings
- Price alerts for target prices

### Image Scanner
- Upload photos to identify collectibles
- OCR for graded slabs (cert numbers, grades)
- Match to price guide for instant valuation
- Create listings or add to collection from scans

### Auction Events
- Scheduled auction events (weekly, themed, elite)
- Extended bidding (anti-sniping)
- Auto-bidding (proxy bidding)
- Live auction room (via WebSocket when implemented)

### Seller Tools
- Subscription tiers with varying commission rates:
  - Starter: Free, 50 listings, 12.95% commission
  - Basic: $9.99/mo, 200 listings, 9.95% commission
  - Featured: $29.99/mo, 1000 listings, 7.95% commission
  - Premium: $99.99/mo, unlimited listings, 5.95% commission
- Bulk import from CSV
- Inventory management (track items before listing)
- Sales analytics and reports

### Collection Value Tracking
- Automatic valuation from price guide
- Daily value snapshots for charts
- Portfolio gain/loss tracking

## Celery Tasks
- `pricing.tasks.update_price_guide_stats` - Update cached price stats
- `pricing.tasks.record_sale_from_order` - Record sales in price guide
- `pricing.tasks.check_price_alerts` - Check and trigger price alerts
- `user_collections.tasks.update_collection_values` - Update collection valuations
- `user_collections.tasks.create_daily_snapshots` - Create daily value snapshots

## Market Data Scraping (TODO)

The price guide needs real market data from external sources. Currently using sample data.

### Data Sources to Scrape

**1. eBay Sold Listings**
- URL: `https://www.ebay.com/sch/i.html?_nkw={query}&LH_Complete=1&LH_Sold=1`
- Data: title, sale price, sale date, condition
- Challenge: eBay blocks scrapers with CAPTCHA (returns 307 redirect to `/splashui/challenge`)
- Solutions:
  - eBay Browse API (free developer account): https://developer.ebay.com/
  - Proxy service like ScraperAPI, Bright Data (~$50/mo)
  - Third-party data: Terapeak, 130point.com

**2. Heritage Auctions**
- URL: `https://www.ha.com/{category}/search-results.s?type=surl-sold`
- Categories: sports-collectibles, comics-comic-art, trading-card-games
- Data: lot title, hammer price, auction date, grade info
- Challenge: Also blocks scrapers (403 Forbidden)
- Solutions: Proxy service or their official API (requires partnership)

**3. GoCollect (Comics)**
- URL: `https://www.gocollect.com/search?q={query}`
- Data: fair market value by grade, recent sales
- Challenge: Requires login for detailed data
- Best for: CGC/CBCS graded comics price history

**4. PSA/BGS Price Guides**
- PSA: https://www.psacard.com/auctionprices
- BGS: https://www.beckett.com/grading/bgs-graded-card-values
- Challenge: Both require subscriptions for full data

**5. TCGPlayer (Trading Cards)**
- URL: `https://www.tcgplayer.com/`
- API available for partners
- Good for: Pokemon, Magic, Yu-Gi-Oh current market prices

### Current Implementation

Located in: `pricing/services/market_data.py`

Classes:
- `EbayMarketData` - Scrapes eBay sold listings (blocked without proxy)
- `HeritageAuctionsData` - Scrapes Heritage completed auctions (blocked)
- `GoCollectData` - Scrapes GoCollect for comics
- `MarketDataImporter` - Coordinates imports, matches to price guide items

Celery tasks in `pricing/tasks.py`:
- `import_all_market_data` - Runs at 6 AM and 6 PM daily
- `import_ebay_market_data`
- `import_heritage_market_data`
- `import_gocollect_market_data`

Management command: `python manage.py import_market_data --source ebay --verbose`

### Recommended Next Steps

1. **Short term**: Use proxy service (ScraperAPI) for eBay scraping
2. **Medium term**: Apply for eBay Browse API access
3. **Long term**: Partner with data providers or build user-submitted sales

### Recent Sales Ticker

The listing detail page shows a "Recent Sales" ticker below the price when:
- The listing has a `price_guide_item` linked
- The price guide item has `SaleRecord` entries

Template: `templates/marketplace/listing_detail.html`
View: `marketplace/views.py:listing_detail()` passes `recent_sales` context

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

### Dependencies (requirements.txt)
```
djangorestframework>=3.15.0
djangorestframework-simplejwt>=5.3.0
django-cors-headers>=4.3.0
drf-spectacular>=0.27.0
django-filter>=24.0
firebase-admin>=6.4.0           # Push notifications
```

### Push Notifications
- `accounts.DeviceToken` model stores FCM tokens
- Register device: POST `/api/v1/accounts/me/device/`
- Notification types: new_bid, outbid, offer, order_shipped, message, price_alert

### Testing API
```bash
# Get token
curl -X POST https://heroesandmore.com/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test123"}'

# List listings
curl https://heroesandmore.com/api/v1/marketplace/listings/ \
  -H "Authorization: Bearer <token>"

# Create listing
curl -X POST https://heroesandmore.com/api/v1/marketplace/listings/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test Item","price":"99.99","category":1,"condition":"mint"}'
```

## Notes
- The `collections` app uses `item_collections` as the related_name to avoid conflicts with Django's built-in collections module
- All listing images are stored in `media/listings/`
- User avatars are stored in `media/avatars/`
- Platform fee is 3% (configurable in settings.PLATFORM_FEE_PERCENT)
- Image scanner requires Google Cloud Vision API (configure credentials)
