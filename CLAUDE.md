# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
HeroesAndMore — collectibles marketplace built with Django. Listings (fixed price + auctions), collections, price guide, scanner, seller tools, social features.

## Tech Stack
- **Backend**: Django 5.x, Python 3.12 (server) / 3.13 (local), PostgreSQL (SQLite local), Redis, Celery
- **Frontend**: Bootstrap 5, HTMX (global in base.html with auto CSRF)
- **Payments**: Stripe Connect, PayPal | **Shipping**: USPS/EasyPost | **Deploy**: Ansible, Nginx, Supervisor, DigitalOcean
- **Analytics**: TikTok Events API (server-side), Clicky

## Project Structure
```
app/              # Django settings        marketplace/      # Listings, orders, payments, auctions
accounts/         # Auth, profiles          social/           # Forums, messaging, follows
user_collections/ # Collections (URL ns: 'collections')  alerts/  # Wishlists, notifications
items/            # Item DB & categories    pricing/          # Price guide, market data
scanner/          # Image recognition       seller_tools/     # Bulk import, inventory, subscriptions
shipping/         # USPS/EasyPost shipping   affiliates/       # Affiliate referral program
templates/        # HTML templates
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

**Payments:** `marketplace.Review` (seller ratings) | `marketplace.PaymentMethod` | `marketplace.StripeEvent` (webhook dedup) | `marketplace.Refund`

**Other:** `user_collections.Collection` (value tracking) | `pricing.PriceGuideItem` / `GradePrice` / `SaleRecord` | `seller_tools.SellerSubscription` / `BulkImport` / `BulkImportRow` / `InventoryItem` | `alerts.Wishlist` / `SavedSearch` / `PriceAlert` / `NewsletterSubscriber` | `social.Follow` / `ForumThread` / `ForumCategory` / `ForumPost` / `Comment` / `Activity` | `accounts.RecentlyViewed` (last 50 viewed, auto-cleanup via `record_view()`)

### Important Listing Methods
- `get_current_price()` — auction: highest bid or starting price; fixed: `self.price`
- `get_images()` / `get_videos()` — non-empty image/video fields
- `has_video` — True if any video upload or `video_url`
- `get_video_url_embed()` — embeddable YouTube/Vimeo URL
- `is_auction_ended()` / `time_remaining` / `time_remaining_parts`
- `quantity_available` — `quantity - quantity_sold`
- `record_sale(qty)` / `reverse_sale(qty)` — atomic stock management via `select_for_update()` + `F()`
- `previous_price` — set automatically when seller lowers price (triggers `send_price_drop_notifications`)
- `bid_count` is NOT a model property — use `listing.bids.count` or annotate `Count('bids')`

### Image Optimization
On listing create/edit, images are processed async via Celery (`process_listing_images_task`):
- **Display version**: Max 1200px, WebP quality=82 (replaces field value)
- **Thumbnail**: 400px wide, WebP quality=75 (saved with `_thumb` suffix)
- **Full-res original**: Preserved with `_original` suffix (for zoom viewing)
- Service: `marketplace/services/image_service.py` | Template tags: `{% load image_tags %}` → `{% thumbnail image %}`, `{% original_image image %}`
- Backfill existing: `python manage.py optimize_images` (supports `--batch=N`, `--listing=ID`)
- Already-WebP images are skipped (won't double-process)

### CDN
Media served via `cdn.heroesandmore.com` (nginx vhost serving local filesystem with long cache headers).
- Config: `ansible/files/cdn.heroesandmore.nginx.conf` | Cert: Let's Encrypt auto-renew
- Django setting: `CDN_DOMAIN` in config.py → `MEDIA_URL = https://cdn.heroesandmore.com/media/`
- Works independently of `USE_SPACES` — currently local filesystem, swap to DO Spaces later by changing nginx `alias` to `proxy_pass`
- Benefits: cookie-free domain, parallel browser connections, immutable cache headers

### Checkout Urgency (No Stock Reservation)
Stock is NOT reserved when entering checkout — only at payment confirmation. This allows multiple buyers to checkout simultaneously. Instead, an urgency indicator shows: "X people have this in checkout right now"
- `Order.stock_reserved` (BooleanField) tracks whether `record_sale()` was called
- `Listing.active_checkout_count` property counts pending orders
- `record_sale()` called at: `process_payment`, PayPal capture, Stripe/PayPal webhooks, `checkout_complete` fallback
- Offer acceptance still reserves stock immediately (seller commitment)
- `expire_unpaid_orders` only calls `reverse_sale()` if `stock_reserved=True`

### Video Upload
Tier-gated: Starter 1/250MB, Basic 1/500MB, Featured 2/1GB, Premium 3/2GB. Formats: MP4, WebM, MOV. YouTube/Vimeo URLs always allowed. Nginx `client_max_body_size=2G`, 600s timeouts.

### Extended Bidding (Anti-Sniping)
`use_extended_bidding` (default True) + `extended_bidding_minutes` (default 15). Bids in last N minutes extend deadline. `times_extended` tracks count. Logic in `marketplace/api/views.py`.

## Homepage (`items/views.py` → `home()`)
Sections: Hero → Stats → Official Auctions (conditional) → Ending Soon (8) → Featured Lots → Bid Wars (conditional) → Categories → Curated (conditional) → CTA

**Listing card annotations required** (`components/listing_card.html`): `save_count=Count('saves')`, `bid_count_total=Count('bids')`, `recent_bids=Count('bids', filter=Q(...))`. HOT LOT: `recent_bids >= 5` or `save_count >= 10`. Known inconsistency: card uses `listing.bid_count` not `bid_count_total`.

## CSS Architecture
All styles inline in `templates/base.html` `<style>` block (no separate CSS files). Page-specific in `{% block extra_css %}`. Use `var(--brand-primary)`, `var(--brand-navy)`, `var(--brand-cyan)`, `var(--brand-gold)`.

## Deployment
```bash
cd /home/john/heroesandmore/ansible
ansible-playbook gitpull.yml    # Quick deploy (most common)
ansible-playbook deploy.yml     # Full deploy (config changes)
ansible-playbook backup.yml     # Backup DB
```
SSH key auth (`~/.ssh/id_ed25519`) is deployed to the server. `ansible.cfg` sets inventory and host key checking. `group_vars/web.yml` (gitignored) has the become password. No extra flags needed — just `ansible-playbook <playbook>.yml` from the ansible dir.
Debug: `cd ansible && ./debug.sh help` (errors, stripe, all, tail, grep, status, restart)

**CAUTION**: fail2ban is active — failed SSH attempts will ban your IP for ~10 min. If banned, wait or unban via DO console (droplet ID: `547914037`).

### Log Files
**App logs** (`/home/www/heroesandmore/logs/`): `errors.log`, `stripe.log`, `frontend.log`, `app.log`, `security.log`, `celery_tasks.log`, `api.log`, `db.log`
**System logs** (`/var/log/heroesandmore/`): `heroesandmore.{out,err}.log`, `celery.{out,err}.log`, `celerybeat.{out,err}.log`
**Loggers**: `accounts`, `marketplace`, `pricing`, `alerts`, `scanner`, `api`, `seller_tools`, `frontend`, `shipping`, `affiliates`

## Config
See `config.py.example`. Required: `SECRET_KEY`, `DATABASE_PASSWORD`, Stripe keys. Optional: `CDN_DOMAIN`, `USE_SPACES`, `DO_SPACES_KEY/SECRET`, `EASYPOST_API_KEY`, Stripe price IDs, PayPal keys, `TIKTOK_ACCESS_TOKEN`, `USPS_CLIENT_ID/SECRET/EPS_ACCOUNT_NUMBER`. For deploys: `ansible/group_vars/vault.yml`.

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
- **Every 15 min**: `alerts.tasks.send_alert_emails`
- **Every 30 min**: `alerts.tasks.send_watched_auction_final_24h`, `check_ending_auctions`
- **Hourly**: `pricing.tasks.check_price_alerts`, `seller_tools.tasks.retry_failed_payments` (:30)
- **Every 2 hours**: `shipping.tasks.poll_usps_tracking`
- **Daily**: `shipping.tasks.cleanup_expired_rates` (1AM), `process_subscription_renewals` (2AM), `cleanup_expired_guest_submissions` (2:30AM), `expire_grace_periods` (3:30AM), `update_trusted_seller_status` (4AM), `approve_pending_commissions` (5AM), `import_all_market_data` (6AM/6PM), `check_wishlist_matches` (8AM), `send_review_followup_reminders` (9AM), `send_seller_delivery_followup` (9:30AM), `send_renewal_reminders` (10AM), `send_post_purchase_followup` (10:30AM), `send_relist_reminders` (11AM)
- **Weekly**: `send_new_listings_digest` (Wed 10AM), `send_weekly_auction_digest` (Fri 10AM), `send_weekly_results_recap` (Mon 10AM)
- **Monthly**: `affiliates.tasks.process_affiliate_payouts` (1st at 5:30AM)
- **Signal-triggered**: `send_welcome_email` (allauth `user_signed_up` via `accounts/signals.py`)
- **On-demand**: `pricing.tasks.update_price_guide_stats`, `record_sale_from_order`, `user_collections.tasks.update_collection_values`, `create_daily_snapshots`, `affiliates.tasks.create_affiliate_commission`, `reverse_affiliate_commission`, `alerts.tasks.send_price_drop_notifications` (triggered on listing price decrease)

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
Services: `stripe_service.py`, `connect_service.py`, `subscription_service.py`, `tiktok_events.py` (server-side event tracking)
Seller onboarding: embedded Connect at `/marketplace/seller-setup/` — international supported
Local: `stripe listen --forward-to localhost:8000/marketplace/webhooks/stripe/`

Subscription settings: grace 7 days, max 4 retries at [1,3,5,7] day intervals.

## PayPal Integration
**Buyers**: PayPal checkout alongside Stripe cards. PayPal JS SDK buttons on checkout page.
**Sellers**: Can set `paypal_email` on Profile for receiving payouts. `preferred_payout_method` field (stripe/paypal).

**Buyer Flow**: PayPal JS SDK → `POST /marketplace/paypal/create-order/<pk>/` → buyer approves → `POST /marketplace/paypal/capture-order/<pk>/` → order marked paid
**Seller Payouts**: `send_paypal_payout` Celery task sends PayPal Payouts API to seller's PayPal email after capture

Service: `marketplace/services/paypal_service.py` (REST API v2, `requests`-based, OAuth2 token caching)
Webhook: `/marketplace/webhooks/paypal/` (CAPTURE.COMPLETED, CAPTURE.REFUNDED, CAPTURE.DENIED)
Config: `PAYPAL_CLIENT_ID`, `PAYPAL_SECRET`, `PAYPAL_WEBHOOK_ID`, `PAYPAL_SANDBOX` (bool)
Order fields: `payment_method` (stripe/paypal), `paypal_order_id`, `paypal_capture_id`, `paypal_payout_batch_id`
Profile fields: `paypal_email`, `preferred_payout_method`
Payout settings: `/seller/payout-settings/` — sellers can set PayPal email and choose preferred payout method

## Shipping (USPS / EasyPost)
Provider: `SHIPPING_PROVIDER` setting (`usps` default, or `easypost`). Modes: `flat` (default), `calculated` (real-time rates), `free`.
Services: `marketplace/services/easypost_service.py`, `marketplace/services/usps_service.py` (REST API v3), `marketplace/services/shipping_factory.py` (provider selection). USPS config: `USPS_CLIENT_ID`, `USPS_CLIENT_SECRET`, `USPS_EPS_ACCOUNT_NUMBER`
Profiles: `standard-card` (2oz), `graded-slab` (8oz), `multiple-cards` (16oz), `figure-toy` (32oz), `custom`
Fee: $0.29 (Stripe) + $0.05 (label) + commission%. Webhook: `/shipping/webhooks/easypost/` (HMAC verified)
Checkout: address validated → rates fetched → rate selected → payment. Seller: "Buy Label" on order detail.

## Email (Self-Hosted)
Postfix + OpenDKIM + PostSRSd. Send from `mail.heroesandmore.com`, receive on `heroesandmore.com`.
**Critical**: `SRS_EXCLUDE_DOMAINS=mail.heroesandmore.com,heroesandmore.com` in `/etc/default/postsrsd`

## Email Preferences
Master `email_notifications` + per-category: `email_bidding`, `email_offers`, `email_marketing`, `email_reminders`, `email_listings`, `email_price_drops`, `email_post_purchase`. All default True. Settings page: `/settings/`.

Use `_should_email(user, category)` from `alerts/tasks.py` for optional emails. Transactional emails (orders, payments, welcome, subscription failures) always send.

## Authentication & Spam
allauth + Google/Apple OAuth. Credentials in DB via `SocialApp` only (NOT settings). `LOGIN_URL = '/auth/signup/'`.
Mobile API auth independent of allauth — direct token verification + JWT.

**Honeypot** (signup + contact): hidden `website` field, `_ts` timestamp (>3s), missing-JS detection, gibberish username regex. Bots get fake success redirect.

## Guest Checkout
Fixed-price only (auctions redirect to signup). `Order.buyer` nullable, `guest_email`/`guest_name`/`guest_order_token`. Track: `/marketplace/order/track/` + `/track/<token>/`. Ephemeral Stripe customer, no saved cards.

## Category Sell Landing Pages
Media buy destinations at `/sell/<category>/` — MTG, Pokemon, Yu-Gi-Oh, Comics, Vintage Baseball. Guests can submit listings without an account via `GuestListingSubmission` model (honeypot-protected). Claim flow at `/sell/claim/<token>/` converts submission to draft Listing on signup/login. Auth users create draft Listings directly. Index hub at `/sell/`. Templates in `templates/pages/sell/`. Config dict `CATEGORY_LANDING_CONFIG` in `app/views.py`. Celery cleanup expires pending submissions after 7 days.

## Affiliate Program
Users join at `/affiliates/join/`, get a unique referral code. Referral link: `?ref=CODE` sets `ham_ref` cookie (30 days) via `AffiliateMiddleware`. On signup, `accounts/signals.py` creates `Referral` (lifetime attribution). On payment success, `create_affiliate_commission` task creates 2% commission on `item_price` for both buyer and seller referrals. An order can have up to 2 commissions (one per side). Commissions: pending (30 days) → approved → paid. Monthly PayPal payouts ($25 min) on 1st of month. The 2% comes from platform cut — seller payout unchanged.

Models: `Affiliate` (user, referral_code, balances), `Referral` (affiliate → referred_user, OneToOne), `AffiliateCommission` (order FK, commission_type buyer/seller, unique_together order+type), `AffiliatePayout` (PayPal batch). Commission hooks in `marketplace/webhooks.py` (Stripe + PayPal success/refund) and `marketplace/views.py` (PayPal capture + checkout fallback).

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
- Context processors: `app/context_processors.seo()` → `site_url`, `default_og_image`; `auction_banner()` → `banner_auction_event` for trusted sellers
- Frontend errors: POST `/api/log-error/` → `frontend` logger
- Landing pages in `app/views.py`: `sell_landing`, `bid_landing`, `trusted_seller_landing`, `contact`
- Dashboard: `/dashboard/` (user) | `/seller/` (seller tools)

## Testing Notes
- Rate limiting disabled via `TESTING` flag. Mock Stripe calls. API uses `APIClient` + JWT.
- **SocialApp required**: Tests with login/signup pages need Google `SocialApp` in setUp — use `SocialAppMixin`
- **Honeypot**: POST `/auth/signup/` must include `'_ts': str(int(time.time()) - 5)`

## Gotchas
- allauth v65: OAuth creds in DB only (SocialApp), not settings — `MultipleObjectsReturned`
- `bid_count` NOT a model property — use `listing.bids.count` or `Count('bids')`
- `Order.buyer` is nullable (guest checkout) — always guard with `{% if order.buyer %}` in templates before accessing `order.buyer.username`
- **Never** `listing.status = 'sold'` — use `record_sale()` / `reverse_sale()`
- Commission is per `SellerSubscription.commission_rate`, not `PLATFORM_FEE_PERCENT`
- `{% with %}` cannot contain `{% else %}` — only `{% if %}` can
- `-webkit-appearance: none` on `.form-control` breaks iOS keyboard
- No optional chaining (`?.`) in inline JS — old browsers from ad traffic don't support ES2020; use `var el = document.getElementById(id); if (el) ...` pattern instead
- Error pages (404/403/500) are standalone HTML, don't extend base.html
- Server `config.py` owned by `www:www` — use `sudo -u www`
- Celery Beat: file-based scheduler only (django_celery_beat not in INSTALLED_APPS)
- `SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'` for Stripe Connect
- Order completed filter: `status__in=['paid', 'shipped', 'delivered', 'completed']`
- Three-repo consistency: update web + Android + iOS for new API fields/badges
