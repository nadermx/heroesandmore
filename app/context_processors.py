from django.conf import settings


def seo(request):
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    return {
        'site_url': site_url,
        'default_og_image': f"{site_url}/static/images/og-default.png",
    }
