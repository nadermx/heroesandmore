def get_shipping_service():
    """Return the configured shipping service class (USPSService or EasyPostService)."""
    from django.conf import settings
    provider = getattr(settings, 'SHIPPING_PROVIDER', 'usps')
    if provider == 'usps':
        from .usps_service import USPSService
        return USPSService
    from .easypost_service import EasyPostService
    return EasyPostService
