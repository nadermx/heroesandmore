import json
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


def _site_url():
    return getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')


@register.simple_tag
def absolute_url(path):
    """Convert a relative path to an absolute URL using SITE_URL."""
    if path and path.startswith(('http://', 'https://')):
        return path
    return f"{_site_url()}{path}"


@register.simple_tag
def absolute_static(path):
    """Build absolute URL for a static file."""
    return f"{_site_url()}{settings.STATIC_URL}{path}"


@register.simple_tag
def absolute_media(path):
    """Build absolute URL for a media file."""
    if path and str(path).startswith(('http://', 'https://')):
        return str(path)
    return f"{_site_url()}{settings.MEDIA_URL}{path}"


@register.filter
def json_ld_escape(value):
    """Escape a string for safe use inside JSON-LD script blocks."""
    if value is None:
        return ''
    return mark_safe(json.dumps(str(value))[1:-1])
