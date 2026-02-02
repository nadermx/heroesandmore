"""Template tags and filters for seller_tools app."""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key."""
    if dictionary is None:
        return None
    if isinstance(dictionary, dict):
        item = dictionary.get(key)
        if item and isinstance(item, dict):
            return item.get('price', item)
        return item
    return None
