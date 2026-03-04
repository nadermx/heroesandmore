# CLAUDE.md

## Project Overview
HeroesAndMore — collectibles marketplace built with Django. Listings (fixed price + auctions), collections, price guide, scanner, seller tools, social features.

## Tech Stack
- **Backend**: Django 5.x, Python 3.12, PostgreSQL (SQLite local), Redis, Celery
- **Frontend**: Bootstrap 5, HTMX (global in base.html with auto CSRF)
- **Payments**: Stripe Connect | **Shipping**: EasyPost | **Deploy**: Ansible, Nginx, Supervisor, DigitalOcean

## Project Structure
```
app/              # Django settings        marketplace/      # Listings, orders, payments, auctions
accounts/         # Auth, profiles          social/           # Forums, messaging, follows
user_collections/ # Collections (URL ns: 'collections')  alerts/  # Wishlists, notifications
items/            # Item DB & categories    pricing/          # Price guide, market data
scanner/          # Image recognition       seller_tools/     # Bulk import, inventory, subscriptions
shipping/         # EasyPost integration    templates/        # HTML templates
static/           # CSS, JS, images         ansible/          # Deployment
config.py         # Local config (gitignored)
```

## Local Development
```bash
source venv/bin/activate
python manage.py runserver
celery -A app worker -l info          # Background tasks
celery -A app beat -l info            # Scheduled tasks
python manage.py seed_categories      # Initial categories
python manage.py import_market_data   # Price data (--source ebay|heritage|gocollect)
```

### Running Tests
```bash
python manage.py test                              # All tests
python manage.py test marketplace                  # Single app
python manage.py test marketplace.tests.test_listings.BiddingTests.test_bid_on_auction  # Single test
python manage.py test --keepdb                     # Reuse test DB
```
Each app has `tests/` with `test_models.py`, `test_views.py`. API tests in `api/tests/`.

## Key Models

**Core:** `accounts.Profile` (profiles, seller verification, subscriptions, founding member) | `items.Category` (hierarchical) | `items.Item` (base DB) | `marketplace.Listing` (fixed + auction, `collector_notes`) | `marketplace.Bid` (`related_name='bids'`, `created`) | `marketplace.SavedListing` (`related_name='saves'`) | `marketplace.AuctionEvent` | `marketplace.Order` (auth + guest) | `marketplace.Offer` (offer/counteroffer) | `marketplace.AutoBid` (proxy bidding) | `marketplace.GuestListingSubmission` (guest sell page submissions)

**Shipping:** `shipping.Address` (EasyPost verified) | `shipping.ShippingProfile` (pre-seeded packages) | `shipping.ShippingLabel` (tracking, void) | `shipping.ShippingRate` (30-min cache)

**Other:** `user_collections.Collection` (value tracking) | `pricing.PriceGuideItem` / `GradePrice` / `SaleRecord` | `seller_tools.SellerSubscription` / `BulkImport` / `BulkImportRow` / `InventoryItem` | `alerts.Wishlist` / `SavedSearch` / `PriceAlert` | `social.Follow` / `ForumThread`

### Important Listing Methods
- `get_current_price()` — auction: highest bid or starting price; fixed: `self.price`
- `get_images()` / `get_videos()` — non-empty image/video fields
- `has_video` — True if any video upload or `video_url`
- `get_video_url_embed()` — embeddable YouTube/Vimeo URL
- `is_auction_ended()` / `time_remaining` / `time_remaining_parts`
- `quantity_available` — `quantity - quantity_sold`
- `record_sale(qty)` / `reverse_sale(qty)` — atomic stock management via `select_for_update()` + `F()`
- `bid_count` is NOT a model property — use `listing.bids.count` or annotate `Count('bids')`

### Video Upload
Tier-gated: Starter 1/250MB, Basic 1/500MB, Featured 2/1GB, Premium 3/2GB. Formats: MP4, WebM, MOV. YouTube/Vimeo URLs always allowed. Nginx `client_max_body_size=2G`, 600s timeouts.

### Extended Bidding (Anti-Sniping)
`use_extended_bidding` (default True) + `extended_bidding_minutes` (default 15). Bids in last N minutes extend deadline. `times_extended` tracks count. Logic in `marketplace/api/views.py`.

## Homepage (`items/views.py` → `home()`)
Sections: Hero → Stats → Ending Soon (8) → Featured Lots → Bid Wars (conditional) → Categories → Curated (conditional) → Official Auctions (conditional) → CTA

**Listing card annotations required** (`components/listing_card.html`): `save_count=Count('saves')`, `bid_count_total=Count('bids')`, `recent_bids=Count('bids', filter=Q(...))`. HOT LOT: `recent_bids >= 5` or `save_count >= 10`. Known inconsistency: card uses `listing.bid_count` not `bid_count_total`.

## CSS Architecture
All styles inline in `templates/base.html` `<style>` block (no separate CSS files). Page-specific in `{% block extra_css %}`. Use `var(--brand-primary)`, `var(--brand-navy)`, `var(--brand-cyan)`, `var(--brand-gold)`.

## Deployment
```bash
cd /home/john/heroesandmore/ansible
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers gitpull.yml    # Quick deploy
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers deploy.yml     # Full deploy (config)
/home/john/heroesandmore/venv/bin/ansible-playbook -i servers backup.yml     # Backup DB
```
Debug: `cd ansible && ./debug.sh help` (errors, stripe, all, tail, grep, status, restart)
SSH: `ssh heroesandmore@174.138.33.140` → `/home/www/heroesandmore`

### Log Files
**App logs** (`/home/www/heroesandmore/logs/`): `errors.log`, `stripe.log`, `frontend.log`, `app.log`, `security.log`, `celery_tasks.log`, `api.log`, `db.log`
**System logs** (`/var/log/heroesandmore/`): `heroesandmore.{out,err}.log`, `celery.{out,err}.log`, `celerybeat.{out,err}.log`
**Loggers**: `accounts`, `marketplace`, `pricing`, `alerts`, `scanner`, `api`, `seller_tools`, `frontend`, `shipping`

## Config
See `config.py.example`. Required: `SECRET_KEY`, `DATABASE_PASSWORD`, Stripe keys, `DO_SPACES_KEY/SECRET`. Optional: `EASYPOST_API_KEY`, Stripe price IDs. For deploys: `ansible/group_vars/vault.yml`.

## Seller Subscription Tiers
Starter (Free): 50 listings, 12.95% | Basic ($9.99): 200, 9.95% | Featured ($29.99): 1000, 7.95% | Premium ($99.99): unlimited, 5.95%. Trusted Sellers get 2% discount (floor 3.95%).

## Trusted Seller Program
Auto-checked daily 4 AM: 20+ sales, 4.5+ rating (10+ reviews), Featured/Premium tier. Fields: `Profile.is_trusted_seller`, `Profile.qualifies_as_trusted_seller`. Benefits: gold badge, 2% commission discount, platform auction submission. Marketing: `/trusted-seller/`.

## Platform Auction Events
`AuctionEvent` (is_platform_event, cadence, status: draft/preview/live/ended) + `AuctionLotSubmission` (pending/approved/rejected/withdrawn).

**Workflow:** Staff creates event → trusted sellers submit → staff approves (auto-assigns lot_number, links listing) → at `preview_start`: lots visible → at `bidding_start`: `activate_platform_events` task converts to auctions, sets live.

URLs: `/marketplace/auctions/`, `/<slug>/`, `/<slug>/submit/`
API: `GET .../platform/`, `POST .../platform/<slug>/submit/`, `GET .../submissions/`

## Celery Tasks
- **Every 5 min**: `marketplace.tasks.end_auctions`, `activate_platform_events`, `expire_unpaid_orders`
- **Every 30 min**: `alerts.tasks.send_watched_auction_final_24h`
- **Hourly**: `pricing.tasks.check_price_alerts`, `seller_tools.tasks.retry_failed_payments` (:30)
- **Daily**: `process_subscription_renewals` (2AM), `expire_grace_periods` (3:30AM), `update_trusted_seller_status` (4AM), `import_all_market_data` (6AM/6PM), `send_renewal_reminders` (10AM), `send_relist_reminders` (11AM), `shipping.tasks.cleanup_expired_rates` (1AM)
- **Weekly**: `send_weekly_auction_digest` (Fri 10AM), `send_weekly_results_recap` (Mon 10AM)
- **Signal-triggered**: `send_welcome_email` (allauth `user_signed_up` via `accounts/signals.py`)
- **On-demand**: `pricing.tasks.update_price_guide_stats`, `record_sale_from_order`, `user_collections.tasks.update_collection_values`, `create_daily_snapshots`

## Market Data
Scrapers in `pricing/services/market_data.py`: `EbayMarketData`, `HeritageAuctionsData`, `GoCollectData`. Uses `_make_proxied_request()` with rotating proxies. eBay handles both `.s-item` and `.s-card` layouts.

## REST API
Base: `/api/v1/` | Auth: JWT (`/auth/token/`), Google/Apple OAuth | Docs: `/api/docs/`

Endpoints: `auth/`, `accounts/`, `marketplace/`, `collections/` (mine/public), `pricing/`, `alerts/`, `social/`, `scanner/`, `seller/`, `items/`, `shipping/`

Nested: `collections/{id}/items/`, `pricing/items/{id}/grades/`, `pricing/items/{id}/sales/`

Rate limits: 100/hr anon, 1000/hr auth (disabled in tests). CORS: production heroesandmore.com only, dev all.

Push: `accounts.DeviceToken` (FCM), register via `POST /api/v1/accounts/me/device/`

API files: `api/` (central routing, permissions, pagination) + `{app}/api/` (serializers, views, urls)

## Stripe Integration
**Payments**: PaymentIntents + Stripe Connect (Express) for seller payouts
**Subscriptions**: Internal billing via PaymentIntents (not Stripe Billing) — `Profile.stripe_customer_id` unified

Webhooks: `/marketplace/webhooks/stripe/` (payment_intent, charge) | `/marketplace/webhooks/stripe-connect/` (account.updated)
Services: `stripe_service.py`, `connect_service.py`, `subscription_service.py`
Seller onboarding: embedded Connect at `/marketplace/seller-setup/` — international supported
Local: `stripe listen --forward-to localhost:8000/marketplace/webhooks/stripe/`

Subscription settings: grace 7 days, max 4 retries at [1,3,5,7] day intervals.

## EasyPost Shipping
Modes: `flat` (default), `calculated` (real-time rates), `free`
Service: `marketplace/services/easypost_service.py` — `verify_address()`, `get_rates()`, `buy_label()`, `refund_label()`
Profiles: `standard-card` (2oz), `graded-slab` (8oz), `multiple-cards` (16oz), `figure-toy` (32oz), `custom`
Fee: $0.29 (Stripe) + $0.05 (label) + commission%. Webhook: `/shipping/webhooks/easypost/` (HMAC verified)
Checkout: address validated → rates fetched → rate selected → payment. Seller: "Buy Label" on order detail.

## Email (Self-Hosted)
Postfix + OpenDKIM + PostSRSd. Send from `mail.heroesandmore.com`, receive on `heroesandmore.com`.
**Critical**: `SRS_EXCLUDE_DOMAINS=mail.heroesandmore.com,heroesandmore.com` in `/etc/default/postsrsd`

## Email Preferences
Master `email_notifications` + per-category: `email_bidding`, `email_offers`, `email_marketing`, `email_reminders`, `email_listings`. All default True. Settings page: `/settings/`.

Use `_should_email(user, category)` from `alerts/tasks.py` for optional emails. Transactional emails (orders, payments, welcome, subscription failures) always send.

## Authentication & Spam
allauth + Google/Apple OAuth. Credentials in DB via `SocialApp` only (NOT settings). `LOGIN_URL = '/auth/signup/'`.
Mobile API auth independent of allauth — direct token verification + JWT.

**Honeypot** (signup + contact): hidden `website` field, `_ts` timestamp (>3s), missing-JS detection, gibberish username regex. Bots get fake success redirect.

## Guest Checkout
Fixed-price only (auctions redirect to signup). `Order.buyer` nullable, `guest_email`/`guest_name`/`guest_order_token`. Track: `/marketplace/order/track/` + `/track/<token>/`. Ephemeral Stripe customer, no saved cards.

## Category Sell Landing Pages
Media buy destinations at `/sell/<category>/` — MTG, Pokemon, Yu-Gi-Oh, Comics, Vintage Baseball. Guests can submit listings without an account via `GuestListingSubmission` model (honeypot-protected). Claim flow at `/sell/claim/<token>/` converts submission to draft Listing on signup/login. Auth users create draft Listings directly. Index hub at `/sell/`. Templates in `templates/pages/sell/`. Config dict `CATEGORY_LANDING_CONFIG` in `app/views.py`. Celery cleanup expires pending submissions after 7 days.

## Founding Collector Program
`Profile.is_founding_member` auto-set at signup before `FOUNDING_MEMBER_CUTOFF` (2026-06-01).

**Badge checklist** (update ALL when adding badges): `listing_card.html`, `listing_detail.html`, `profile.html`, `dashboard.html`, `seller_tools/dashboard.html`, `accounts/admin.py`, `marketplace/api/serializers.py`, `accounts/api/serializers.py`, Android DTOs/UI, iOS models/views.

## Multi-Quantity Listings
Fixed-price only. **Never set `listing.status = 'sold'` directly** — use `record_sale(qty)` / `reverse_sale(qty)`.

## Repos & Team
Web: `github.com/nadermx/heroesandmore` | Android: `heroesandmore-android` | iOS: `heroesandmore-ios`
John (john@nader.mx, owner) | Tony (tmgormond@gmail.com) | Jim (jim@sickboys.com)

## Shared Utilities
- `items.views._get_site_stats()` → `stat_active_listings`, `stat_collectors`, `stat_sold_total`, `stat_avg_rating`
- Template tags: `seo_tags` (absolute_url, json_ld_escape), `seller_tools_tags` (get_item filter)
- Context processor: `app/context_processors.seo()` → `site_url`, `default_og_image`
- Frontend errors: POST `/api/log-error/` → `frontend` logger
- Landing pages in `app/views.py`: `sell_landing`, `bid_landing`, `trusted_seller_landing`, `contact`
- Dashboard: `/dashboard/` (user) | `/seller/` (seller tools) | `accounts/seller_dashboard.html` is dead code

## Testing Notes
- Rate limiting disabled via `TESTING` flag. Mock Stripe calls. API uses `APIClient` + JWT.
- **SocialApp required**: Tests with login/signup pages need Google `SocialApp` in setUp — use `SocialAppMixin`
- **Honeypot**: POST `/auth/signup/` must include `'_ts': str(int(time.time()) - 5)`

## Gotchas
- allauth v65: OAuth creds in DB only (SocialApp), not settings — `MultipleObjectsReturned`
- `bid_count` NOT a model property — use `listing.bids.count` or `Count('bids')`
- **Never** `listing.status = 'sold'` — use `record_sale()` / `reverse_sale()`
- Commission is per `SellerSubscription.commission_rate`, not `PLATFORM_FEE_PERCENT`
- `{% with %}` cannot contain `{% else %}` — only `{% if %}` can
- `-webkit-appearance: none` on `.form-control` breaks iOS keyboard
- Error pages (404/403/500) are standalone HTML, don't extend base.html
- Server `config.py` owned by `www:www` — use `sudo -u www`
- Celery Beat: file-based scheduler only (django_celery_beat not in INSTALLED_APPS)
- `SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'` for Stripe Connect
- Order completed filter: `status__in=['paid', 'shipped', 'delivered', 'completed']`
- Three-repo consistency: update web + Android + iOS for new API fields/badges
