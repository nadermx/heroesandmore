from django import template
from marketplace.services.image_service import get_thumbnail_url, get_original_url

register = template.Library()


@register.simple_tag
def thumbnail(image_field):
    """Return thumbnail URL for an image field, falling back to original URL."""
    url = get_thumbnail_url(image_field)
    if url:
        return url
    if image_field and image_field.name:
        try:
            return image_field.url
        except Exception:
            pass
    return ''


@register.simple_tag
def original_image(image_field):
    """Return full-resolution original URL for an image field."""
    url = get_original_url(image_field)
    if url:
        return url
    if image_field and image_field.name:
        try:
            return image_field.url
        except Exception:
            pass
    return ''
