from django.conf import settings


def alerts(request):
    """Provide unread alert count for notification badge in navbar."""
    if request.user.is_authenticated:
        from alerts.models import Alert
        return {'unread_alerts_count': Alert.objects.filter(user=request.user, read=False).count()}
    return {'unread_alerts_count': 0}


def seo(request):
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    return {
        'site_url': site_url,
        'default_og_image': f"{site_url}/static/images/og-default.png",
    }


def auction_banner(request):
    """Provide open auction event for trusted seller banner."""
    if not request.user.is_authenticated:
        return {}
    try:
        if not request.user.profile.is_trusted_seller:
            return {}
    except Exception:
        return {}

    from marketplace.models import AuctionEvent
    event = AuctionEvent.objects.filter(
        is_platform_event=True,
        accepting_submissions=True,
    ).order_by('submission_deadline').first()

    if event:
        return {'banner_auction_event': event}
    return {}
