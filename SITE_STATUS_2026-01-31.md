# HeroesAndMore Site Status Report
**Date: January 31, 2026**

## Admin Accounts Created ✅

| Username | Email | Password | Access |
|----------|-------|----------|--------|
| john | john@heroesandmore.com → john@nader.mx | Pass4Ham! | Superuser |
| jim | jim@heroesandmore.com → jim@sickboys.com | Pass4Ham! | Superuser |
| tony | tony@heroesandmore.com → tmgormond@gmail.com | Pass4Ham! | Superuser |

**Admin URL:** https://www.heroesandmore.com/admin/

---

## URL Status

### Public Pages (Working ✅)
| URL | Status |
|-----|--------|
| `/` | 200 ✅ |
| `/auth/login/` | 200 ✅ |
| `/auth/signup/` | 200 ✅ |
| `/items/` | 200 ✅ |
| `/marketplace/` | 200 ✅ |
| `/marketplace/1/` | 200 ✅ |
| `/collections/` | 200 ✅ |
| `/social/forums/` | 200 ✅ |
| `/price-guide/` | 200 ✅ |
| `/about/` | 200 ✅ |
| `/help/` | 200 ✅ |
| `/contact/` | 200 ✅ |
| `/terms/` | 200 ✅ |
| `/privacy/` | 200 ✅ |

### Protected Pages (Redirect to Login - Expected ✅)
| URL | Status |
|-----|--------|
| `/marketplace/1/checkout/` | 302 → Login |
| `/marketplace/payment-methods/` | 302 → Login |
| `/marketplace/seller-setup/` | 302 → Login |
| `/seller/` | 302 → Login |
| `/seller/subscription/` | 302 → Login |
| `/scanner/` | 302 → Login |
| `/admin/` | 302 → Login |

### API (Not Deployed ❌)
| URL | Status |
|-----|--------|
| `/api/v1/` | 404 |
| `/api/docs/` | 404 |

---

## Database Summary

| Model | Count | Notes |
|-------|-------|-------|
| Users | 9 | Including 3 new admins |
| Categories | 50 | Full hierarchy |
| Listings | 16 | Active marketplace items |
| Orders | 0 | No purchases yet |
| Collections | 0 | No user collections |
| Price Guide Items | 10 | Sample data |
| Sale Records | 200 | Historical price data |
| Forum Categories | 0 | **Needs setup** |
| Forum Threads | 0 | **Needs content** |
| Wishlists | 0 | User-created |
| Seller Subscriptions | 1 | Test subscription |

---

## Stripe Integration Status ✅

### Configuration
- **Mode:** TEST (pk_test_*, sk_test_*)
- **Public Key:** Configured
- **Secret Key:** Configured
- **Main Webhook Secret:** Configured
- **Connect Webhook Secret:** Configured

### Products Created
| Tier | Price | Price ID |
|------|-------|----------|
| Basic | $9.99/mo | price_1SviaC3wuO9hq6j69VRNCjfX |
| Featured | $29.99/mo | price_1SviaC3wuO9hq6j6tVD6UYwI |
| Premium | $99.99/mo | price_1SviaC3wuO9hq6j6U9rGhx6k |

### Webhook Endpoints
- Main: https://www.heroesandmore.com/marketplace/webhooks/stripe/
- Connect: https://www.heroesandmore.com/marketplace/webhooks/stripe-connect/

---

## Email Forwarding ✅

| Address | Forwards To |
|---------|-------------|
| support@ | john@nader.mx, tmgormond@gmail.com, jim@sickboys.com |
| auctions@ | john@nader.mx, tmgormond@gmail.com, jim@sickboys.com |
| sales@ | john@nader.mx, tmgormond@gmail.com, jim@sickboys.com |
| john@ | john@nader.mx |
| jim@ | jim@sickboys.com |
| tony@ | tmgormond@gmail.com |

---

## Immediate Action Items

### P0 - Critical (Do Now)
1. **Test Full Purchase Flow**
   - Login as buyer
   - Go to a listing
   - Complete checkout with test card 4242 4242 4242 4242
   - Verify order created and webhook processed

2. **Create Forum Categories**
   - Login to /admin/
   - Go to Social > Forum Categories
   - Create initial structure (General, Trading Cards, Comics, etc.)

### P1 - Important (This Week)
3. **Test Seller Subscription**
   - Login as seller
   - Go to /seller/subscription/
   - Upgrade to Basic tier
   - Verify subscription active in Stripe dashboard

4. **Test Stripe Connect**
   - Go to /marketplace/seller-setup/
   - Complete Express onboarding
   - Verify account in Stripe Connect dashboard

### P2 - Soon (Next Week)
5. **Deploy REST API**
   - Push api/ app to git
   - Deploy to server
   - Add to INSTALLED_APPS
   - Test endpoints

6. **Set Up Scanner**
   - Create Google Cloud Vision credentials
   - Add to server config
   - Test image recognition

---

## Test Cards (Stripe Test Mode)

| Card Number | Description |
|-------------|-------------|
| 4242 4242 4242 4242 | Success |
| 4000 0025 0000 3155 | Requires 3D Secure |
| 4000 0000 0000 9995 | Declined |
| 4000 0000 0000 0077 | Declined (Expired) |

Use any future expiry date and any 3-digit CVC.

---

## Quick Admin Commands

```bash
# SSH to server
ssh heroesandmore@174.138.33.140

# Check logs
sudo tail -100 /var/log/supervisor/heroesandmore_web-stdout*

# Restart app
sudo supervisorctl restart heroesandmore:*

# Django shell
cd /home/www/heroesandmore && sudo -u www venv/bin/python manage.py shell

# Check mail queue
sudo mailq
```
