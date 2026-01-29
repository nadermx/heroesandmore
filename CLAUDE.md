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
cd /home/john/herosandmore
source venv/bin/activate
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

### Initial Server Setup
```bash
cd ansible
ansible-playbook -i servers setup.yml
```

### Deploy Updates
```bash
cd ansible
ansible-playbook -i servers gitpull.yml
```

### Check Logs
```bash
ansible -i servers all -m shell -a "tail -100 /var/log/herosandmore/herosandmore.log" --become
```

### Restart Services
```bash
ansible -i servers all -m shell -a "supervisorctl restart herosandmore:*" --become
```

## Config Values Needed (config.py)
- `SECRET_KEY` - Django secret key
- `DATABASE_PASSWORD` - PostgreSQL password
- `STRIPE_PUBLIC_KEY` - Stripe publishable key
- `STRIPE_SECRET_KEY` - Stripe secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing
- `DO_SPACES_KEY` - DigitalOcean Spaces access key
- `DO_SPACES_SECRET` - DigitalOcean Spaces secret

## Common Tasks

### Add New Category
Go to `/admin/items/category/` and add via Django admin.

### Check Pending Orders
```bash
ansible -i ansible/servers all -m shell -a "cd /home/www/herosandmore && venv/bin/python manage.py shell -c \"from marketplace.models import Order; print(Order.objects.filter(status='pending').count())\"" --become --become-user=www
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

## Notes
- The `collections` app uses `item_collections` as the related_name to avoid conflicts with Django's built-in collections module
- All listing images are stored in `media/listings/`
- User avatars are stored in `media/avatars/`
- Platform fee is 3% (configurable in settings.PLATFORM_FEE_PERCENT)
- Image scanner requires Google Cloud Vision API (configure credentials)
