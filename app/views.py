import json
import secrets
import time
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Count, Q, Sum
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import timedelta

from items.models import Category
from items.views import _get_site_stats

logger = logging.getLogger('frontend')
app_logger = logging.getLogger('app')


# ── Category sell page configuration ──────────────────────────────────────────

CATEGORY_LANDING_CONFIG = {
    'mtg': {
        'slug': 'mtg',
        'name': 'Magic: The Gathering',
        'short_name': 'MTG',
        'template': 'pages/sell/mtg.html',
        'meta_title': 'Sell Magic: The Gathering Cards | Lower Fees Than TCGplayer - HeroesAndMore',
        'meta_description': 'Sell MTG cards with fees from 5.95% — less than half of TCGplayer. List Reserve List staples, Commander decks, and sealed product. Fast Stripe payouts.',
        'db_category_slug': 'mtg',
        'grading_services': ['psa', 'bgs', 'cgc'],
        'competitor': 'TCGplayer',
    },
    'pokemon': {
        'slug': 'pokemon',
        'name': 'Pokemon',
        'short_name': 'Pokemon',
        'template': 'pages/sell/pokemon.html',
        'meta_title': 'Sell Pokemon Cards | Lower Fees Than eBay - HeroesAndMore',
        'meta_description': 'Sell Pokemon cards with fees from 5.95%. WOTC vintage, Japanese exclusives, modern chase cards. Secure payments, fast payouts, built for collectors.',
        'db_category_slug': 'pokemon',
        'grading_services': ['psa', 'bgs', 'cgc'],
        'competitor': 'eBay',
    },
    'yugioh': {
        'slug': 'yugioh',
        'name': 'Yu-Gi-Oh!',
        'short_name': 'Yu-Gi-Oh',
        'template': 'pages/sell/yugioh.html',
        'meta_title': 'Sell Yu-Gi-Oh! Cards | Lower Fees Than TCGplayer - HeroesAndMore',
        'meta_description': 'Sell Yu-Gi-Oh! cards with fees from 5.95%. Ghost Rares, Starlight Rares, 1st Edition classics. Lower fees than TCGplayer with fast payouts.',
        'db_category_slug': 'yugioh',
        'grading_services': ['psa', 'bgs', 'cgc'],
        'competitor': 'TCGplayer',
    },
    'comics': {
        'slug': 'comics',
        'name': 'Comics',
        'short_name': 'Comics',
        'template': 'pages/sell/comics.html',
        'meta_title': 'Sell Comic Books | Lower Fees Than eBay - HeroesAndMore',
        'meta_description': 'Sell comic books with fees from 5.95%. Key issues, first appearances, CGC slabs. Keep more profit than eBay or auction houses. Fast Stripe payouts.',
        'db_category_slug': 'comics',
        'grading_services': ['cgc'],
        'competitor': 'eBay',
    },
    'vintage-baseball-cards': {
        'slug': 'vintage-baseball-cards',
        'name': 'Vintage Baseball Cards',
        'short_name': 'Vintage Baseball',
        'template': 'pages/sell/vintage_baseball.html',
        'meta_title': 'Sell Vintage Baseball Cards | Lower Fees Than COMC - HeroesAndMore',
        'meta_description': 'Sell vintage baseball cards with fees from 5.95%. T206, Topps, Bowman pre-war cards. Lower fees than COMC or eBay with secure Stripe payouts.',
        'db_category_slug': 'sports-cards',
        'grading_services': ['psa', 'sgc', 'bgs'],
        'competitor': 'COMC',
    },
}


def robots_txt(request):
    """Serve robots.txt with sitemap reference."""
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if not site_url:
        site_url = f"{request.scheme}://{request.get_host()}"

    content = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /api/",
        f"Sitemap: {site_url}/sitemap.xml",
    ])
    return HttpResponse(content, content_type='text/plain; charset=utf-8')


def sitemap_xml(request):
    """Lightweight XML sitemap for indexable public pages."""
    from marketplace.models import Listing
    from items.models import Category, Item
    from pricing.models import PriceGuideItem
    from social.models import ForumThread

    site_url = getattr(settings, 'SITE_URL', '').rstrip('/')
    if not site_url:
        site_url = f"{request.scheme}://{request.get_host()}"

    today = timezone.now().date().isoformat()
    urls = [
        (f"{site_url}/", today, "daily", "1.0"),
        (f"{site_url}/marketplace/", today, "hourly", "0.9"),
        (f"{site_url}/items/", today, "daily", "0.8"),
        (f"{site_url}/price-guide/", today, "daily", "0.9"),
        (f"{site_url}/social/forums/", today, "daily", "0.7"),
        (f"{site_url}/sell/", today, "weekly", "0.7"),
        (f"{site_url}/sell/mtg/", today, "weekly", "0.7"),
        (f"{site_url}/sell/pokemon/", today, "weekly", "0.7"),
        (f"{site_url}/sell/yugioh/", today, "weekly", "0.7"),
        (f"{site_url}/sell/comics/", today, "weekly", "0.7"),
        (f"{site_url}/sell/vintage-baseball-cards/", today, "weekly", "0.7"),
        (f"{site_url}/bid/", today, "daily", "0.7"),
    ]

    for category in Category.objects.filter(is_active=True).only('slug', 'updated')[:5000]:
        urls.append((f"{site_url}{category.get_absolute_url()}", category.updated.date().isoformat(), "daily", "0.7"))

    for listing in Listing.objects.filter(status='active').only('id', 'updated').order_by('-updated')[:10000]:
        urls.append((f"{site_url}{listing.get_absolute_url()}", listing.updated.date().isoformat(), "hourly", "0.8"))

    for item in Item.objects.select_related('category').only('slug', 'category__slug', 'updated')[:10000]:
        urls.append((f"{site_url}{item.get_absolute_url()}", item.updated.date().isoformat(), "weekly", "0.6"))

    for price_item in PriceGuideItem.objects.only('slug', 'updated').order_by('-updated')[:20000]:
        urls.append((f"{site_url}{price_item.get_absolute_url()}", price_item.updated.date().isoformat(), "daily", "0.9"))

    for thread in ForumThread.objects.only('id', 'updated').order_by('-updated')[:5000]:
        urls.append((f"{site_url}{thread.get_absolute_url()}", thread.updated.date().isoformat(), "weekly", "0.5"))

    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod, changefreq, priority in urls:
        xml_parts.extend([
            "  <url>",
            f"    <loc>{loc}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            f"    <changefreq>{changefreq}</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ])
    xml_parts.append("</urlset>")

    return HttpResponse("\n".join(xml_parts), content_type='application/xml; charset=utf-8')


def sell_landing(request):
    """Sell index hub — links to all category sell pages."""
    from marketplace.models import Listing, Order
    from accounts.models import Profile

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    one_hour_ago = now - timedelta(hours=1)

    categories = Category.objects.filter(parent=None, is_active=True).order_by('order')[:8]

    # Recent completed sales (last 30 days) for social proof
    recent_sales = (
        Order.objects.filter(
            status__in=['paid', 'shipped', 'delivered', 'completed'],
            paid_at__gte=thirty_days_ago,
        )
        .select_related('listing')
        .order_by('-paid_at')[:6]
    )

    # 30-day sales aggregates
    sales_agg = Order.objects.filter(
        status__in=['paid', 'shipped', 'delivered', 'completed'],
        paid_at__gte=thirty_days_ago,
    ).aggregate(
        count=Count('id'),
        total_value=Sum('item_price'),
        total_payouts=Sum('seller_payout'),
    )

    # Lifetime seller payouts
    lifetime_payouts = Order.objects.filter(
        status__in=['paid', 'shipped', 'delivered', 'completed'],
    ).aggregate(total=Sum('seller_payout'))['total'] or 0

    # Active auctions with bids
    active_auctions = (
        Listing.objects.filter(
            status='active',
            listing_type='auction',
            auction_end__gt=now,
        )
        .select_related('seller', 'seller__profile', 'category')
        .annotate(
            save_count=Count('saves'),
            bid_count_total=Count('bids'),
            recent_bids=Count('bids', filter=Q(bids__created__gte=one_hour_ago)),
        )
        .filter(bid_count_total__gt=0)
        .order_by('-bid_count_total')[:4]
    )

    # Top sellers (by sales value)
    top_sellers = (
        Profile.objects.filter(
            total_sales_count__gte=5,
            rating__gte=4.0,
        )
        .select_related('user')
        .order_by('-total_sales_value')[:3]
    )

    context = {
        'categories': categories,
        'recent_sales': recent_sales,
        'sales_count_30d': sales_agg['count'] or 0,
        'sales_value_30d': sales_agg['total_value'] or 0,
        'sales_payouts_30d': sales_agg['total_payouts'] or 0,
        'lifetime_payouts': lifetime_payouts,
        'active_auctions': active_auctions,
        'top_sellers': top_sellers,
        'sell_categories': CATEGORY_LANDING_CONFIG,
        **_get_site_stats(),
    }
    return render(request, 'pages/sell/index.html', context)


def sell_category_landing(request, category_key):
    """Category-specific sell landing page with guest or auth listing form."""
    from marketplace.models import Listing, Order, GuestListingSubmission
    from marketplace.forms import GuestListingForm, ListingForm

    config = CATEGORY_LANDING_CONFIG.get(category_key)
    if not config:
        from django.http import Http404
        raise Http404

    # Resolve the DB category
    db_category = get_object_or_404(Category, slug=config['db_category_slug'])

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    one_hour_ago = now - timedelta(hours=1)

    if request.method == 'POST':
        if request.user.is_authenticated:
            # Auth user: create draft Listing directly
            form = ListingForm(request.POST, request.FILES, user=request.user)
            if form.is_valid():
                listing = form.save(commit=False)
                listing.seller = request.user
                listing.category = db_category
                listing.status = 'draft'
                listing.save()
                messages.success(request, 'Your listing draft has been created! Review and publish it below.')
                return redirect('marketplace:listing_edit', pk=listing.pk)
        else:
            # Guest: honeypot + create GuestListingSubmission
            # Honeypot check
            if request.POST.get('website', ''):
                app_logger.warning(f"Sell form spam blocked (honeypot): {request.POST.get('guest_email', '')}")
                messages.success(request, 'Your listing has been submitted! Check your email to finish setting up.')
                return redirect('sell_category', category_key=category_key)

            form_ts = request.POST.get('_ts', '')
            if form_ts:
                try:
                    elapsed = time.time() - float(form_ts)
                    if elapsed < 3:
                        app_logger.warning(f"Sell form spam blocked (too fast: {elapsed:.1f}s): {request.POST.get('guest_email', '')}")
                        messages.success(request, 'Your listing has been submitted! Check your email to finish setting up.')
                        return redirect('sell_category', category_key=category_key)
                except (ValueError, TypeError):
                    pass

            form = GuestListingForm(request.POST, request.FILES)
            if form.is_valid():
                submission = form.save(commit=False)
                submission.category = db_category
                submission.source_category_key = category_key
                submission.guest_token = secrets.token_urlsafe(48)
                # Capture UTM params
                submission.utm_source = request.GET.get('utm_source', '')[:200]
                submission.utm_medium = request.GET.get('utm_medium', '')[:200]
                submission.utm_campaign = request.GET.get('utm_campaign', '')[:200]
                submission.save()

                # Send claim email
                _send_claim_email(request, submission)

                messages.success(request, 'Your listing has been submitted! Check your email to finish setting up your account.')
                return redirect('sell_claim', token=submission.guest_token)
    else:
        if request.user.is_authenticated:
            form = ListingForm(user=request.user, initial={'category': db_category})
        else:
            form = GuestListingForm()

    # Category-specific recent sales
    recent_sales = (
        Order.objects.filter(
            status__in=['paid', 'shipped', 'delivered', 'completed'],
            paid_at__gte=thirty_days_ago,
            listing__category=db_category,
        )
        .select_related('listing')
        .order_by('-paid_at')[:6]
    )

    # Active listings in this category
    active_listings = (
        Listing.objects.filter(
            status='active',
            category=db_category,
        )
        .select_related('seller', 'seller__profile', 'category')
        .annotate(
            save_count=Count('saves'),
            bid_count_total=Count('bids'),
            recent_bids=Count('bids', filter=Q(bids__created__gte=one_hour_ago)),
        )
        .order_by('-created')[:8]
    )

    # Sales stats for this category
    sales_agg = Order.objects.filter(
        status__in=['paid', 'shipped', 'delivered', 'completed'],
        paid_at__gte=thirty_days_ago,
        listing__category=db_category,
    ).aggregate(
        count=Count('id'),
        total_value=Sum('item_price'),
    )

    context = {
        'config': config,
        'category_key': category_key,
        'db_category': db_category,
        'form': form,
        'recent_sales': recent_sales,
        'active_listings': active_listings,
        'sales_count_30d': sales_agg['count'] or 0,
        'sales_value_30d': sales_agg['total_value'] or 0,
        'is_guest': not request.user.is_authenticated,
        **_get_site_stats(),
    }
    return render(request, config['template'], context)


def _send_claim_email(request, submission):
    """Send the claim/account creation email for a guest submission."""
    site_url = getattr(settings, 'SITE_URL', '').rstrip('/') or f"{request.scheme}://{request.get_host()}"
    claim_url = f"{site_url}/sell/claim/{submission.guest_token}/"

    try:
        send_mail(
            subject='Finish setting up your listing on HeroesAndMore',
            message=(
                f"Hi {submission.guest_name},\n\n"
                f"Your listing \"{submission.title}\" has been submitted! "
                f"Create your free account to publish it:\n\n"
                f"{claim_url}\n\n"
                f"This link expires in 7 days.\n\n"
                f"— The HeroesAndMore Team"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[submission.guest_email],
            fail_silently=False,
        )
    except Exception:
        app_logger.error(f'Failed to send claim email to {submission.guest_email}', exc_info=True)


def sell_claim_submission(request, token):
    """Claim a guest listing submission by creating an account or logging in."""
    from marketplace.models import GuestListingSubmission, Listing

    submission = get_object_or_404(GuestListingSubmission, guest_token=token, status='pending')

    # Already logged in — convert immediately
    if request.user.is_authenticated:
        listing = _convert_submission_to_listing(submission, request.user)
        messages.success(request, f'Your listing "{listing.title}" is ready! Review and publish it below.')
        return redirect('marketplace:listing_edit', pk=listing.pk)

    context = {
        'submission': submission,
        'token': token,
        'email_matches_existing': User.objects.filter(email=submission.guest_email).exists(),
    }
    return render(request, 'pages/sell/claim.html', context)


def _convert_submission_to_listing(submission, user):
    """Convert a GuestListingSubmission into a draft Listing."""
    from marketplace.models import Listing

    listing = Listing(
        seller=user,
        category=submission.category,
        title=submission.title,
        description=submission.description,
        collector_notes=submission.collector_notes,
        condition=submission.condition,
        grading_service=submission.grading_service,
        grade=submission.grade,
        cert_number=submission.cert_number,
        is_graded=bool(submission.grading_service or submission.grade),
        price=submission.price,
        listing_type=submission.listing_type,
        quantity=submission.quantity,
        reserve_price=submission.reserve_price,
        allow_offers=submission.allow_offers,
        shipping_mode=submission.shipping_mode,
        shipping_price=submission.shipping_price,
        ships_from=submission.ships_from,
        status='draft',
    )
    # Copy images
    for i in range(1, 6):
        src = getattr(submission, f'image{i}')
        if src and src.name:
            setattr(listing, f'image{i}', src)

    listing.save()

    # Mark submission as converted
    submission.status = 'converted'
    submission.converted_listing = listing
    submission.converted_user = user
    submission.save()

    return listing


def trusted_seller_landing(request):
    """Marketing page for the Trusted Seller program."""
    is_trusted = (
        request.user.is_authenticated
        and hasattr(request.user, 'profile')
        and request.user.profile.is_trusted_seller
    )
    context = {
        'is_trusted': is_trusted,
        **_get_site_stats(),
    }
    return render(request, 'pages/trusted_seller.html', context)


def bid_landing(request):
    """Ad landing page — shows live auction inventory for conversion."""
    from marketplace.models import Listing, Bid, SavedListing
    from accounts.models import Profile

    now = timezone.now()
    one_hour_ago = now - timedelta(hours=1)

    # Featured auctions ending soonest
    featured_auctions = (
        Listing.objects.filter(
            status='active', listing_type='auction',
            auction_end__gt=now,
        )
        .select_related('seller', 'seller__profile', 'category')
        .annotate(
            save_count=Count('saves'),
            bid_count_total=Count('bids'),
            recent_bids=Count('bids', filter=Q(bids__created__gte=one_hour_ago)),
        )
        .order_by('auction_end')[:12]
    )

    # Most watched auctions
    most_watched = (
        Listing.objects.filter(
            status='active', listing_type='auction',
            auction_end__gt=now,
        )
        .select_related('seller', 'seller__profile', 'category')
        .annotate(save_count=Count('saves'))
        .order_by('-save_count')[:6]
    )

    # Recent bids feed (last 6 hours)
    six_hours_ago = now - timedelta(hours=6)
    recent_bid_feed = (
        Bid.objects.filter(created__gte=six_hours_ago)
        .select_related('listing', 'bidder')
        .order_by('-created')[:15]
    )

    # Founding member progress
    total_members = User.objects.count()
    founding_target = 1000
    founding_progress = min(int((total_members / founding_target) * 100), 100)

    context = {
        'featured_auctions': featured_auctions,
        'most_watched': most_watched,
        'recent_bid_feed': recent_bid_feed,
        'total_members': total_members,
        'founding_target': founding_target,
        'founding_progress': founding_progress,
        **_get_site_stats(),
    }
    return render(request, 'pages/bid_landing.html', context)


def contact(request):
    """Contact form page - sends email to support on submission."""
    if request.method == 'POST':
        # Honeypot check — bots fill hidden fields
        if request.POST.get('website', ''):
            app_logger.warning(f"Contact form spam blocked (honeypot): {request.POST.get('email', '')}")
            messages.success(request, 'Your message has been sent! We\'ll get back to you within 24 hours.')
            return redirect('contact')

        # Timestamp check — form submitted too fast (< 3 seconds = bot)
        form_ts = request.POST.get('_ts', '')
        if form_ts:
            try:
                elapsed = time.time() - float(form_ts)
                if elapsed < 3:
                    app_logger.warning(f"Contact form spam blocked (too fast: {elapsed:.1f}s): {request.POST.get('email', '')}")
                    messages.success(request, 'Your message has been sent! We\'ll get back to you within 24 hours.')
                    return redirect('contact')
            except (ValueError, TypeError):
                pass

        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', 'general')
        message_text = request.POST.get('message', '').strip()

        if not all([name, email, message_text]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'pages/contact.html')

        subject_labels = {
            'general': 'General Inquiry',
            'buying': 'Buying Help',
            'selling': 'Selling Help',
            'account': 'Account Issues',
            'report': 'Report a Problem',
            'other': 'Other',
        }
        subject_label = subject_labels.get(subject, 'General Inquiry')

        try:
            send_mail(
                subject=f'[Contact Form] {subject_label} — from {name}',
                message=f'From: {name} <{email}>\nSubject: {subject_label}\n\n{message_text}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['support@heroesandmore.com'],
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent! We\'ll get back to you within 24 hours.')
            return redirect('contact')
        except Exception:
            app_logger.error('Contact form email failed', exc_info=True)
            messages.error(request, 'Sorry, there was a problem sending your message. Please email us directly at support@heroesandmore.com.')

    return render(request, 'pages/contact.html')


@csrf_exempt
@require_POST
def log_frontend_error(request):
    """
    Endpoint for logging frontend JavaScript errors.
    POST /api/log-error/

    Expected payload:
    {
        "message": "Error message",
        "source": "script URL",
        "lineno": 123,
        "colno": 45,
        "error": "Error stack trace",
        "url": "Page URL where error occurred",
        "userAgent": "Browser user agent"
    }
    """
    try:
        data = json.loads(request.body)

        error_info = {
            'message': data.get('message', 'Unknown error'),
            'source': data.get('source', 'unknown'),
            'line': data.get('lineno', 0),
            'column': data.get('colno', 0),
            'stack': data.get('error', ''),
            'url': data.get('url', ''),
            'user_agent': data.get('userAgent', ''),
            'user_id': request.user.id if request.user.is_authenticated else None,
        }

        logger.error(
            f"Frontend error: {error_info['message']} | "
            f"Source: {error_info['source']}:{error_info['line']}:{error_info['column']} | "
            f"URL: {error_info['url']} | "
            f"User: {error_info['user_id']} | "
            f"Stack: {error_info['stack']}"
        )

        return JsonResponse({'status': 'logged'})
    except Exception as e:
        logger.error(f"Failed to log frontend error: {e}")
        return JsonResponse({'status': 'error'}, status=400)
