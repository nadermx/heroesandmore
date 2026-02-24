import json
import time
import logging
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from datetime import timedelta

from items.models import Category
from items.views import _get_site_stats

logger = logging.getLogger('frontend')
app_logger = logging.getLogger('app')


def sell_landing(request):
    if request.user.is_authenticated:
        return redirect('marketplace:listing_create')
    categories = Category.objects.filter(parent=None, is_active=True).order_by('order')[:8]
    context = {
        'categories': categories,
        **_get_site_stats(),
    }
    return render(request, 'pages/sell.html', context)


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
