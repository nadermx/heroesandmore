from celery import shared_task
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@shared_task
def update_price_guide_stats(item_id):
    """Update cached stats for a price guide item"""
    from .models import PriceGuideItem, SaleRecord

    try:
        item = PriceGuideItem.objects.get(id=item_id)
    except PriceGuideItem.DoesNotExist:
        return f"PriceGuideItem {item_id} not found"

    # Update overall stats
    sales = item.sales.all()
    item.total_sales = sales.count()

    if sales.exists():
        item.avg_sale_price = sales.aggregate(Avg('sale_price'))['sale_price__avg']
        item.last_sale_date = sales.order_by('-sale_date').first().sale_date

        # Calculate trend (compare last 30 days to previous 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        sixty_days_ago = timezone.now() - timedelta(days=60)

        recent_avg = sales.filter(sale_date__gte=thirty_days_ago).aggregate(
            Avg('sale_price'))['sale_price__avg']
        previous_avg = sales.filter(
            sale_date__gte=sixty_days_ago,
            sale_date__lt=thirty_days_ago
        ).aggregate(Avg('sale_price'))['sale_price__avg']

        if recent_avg and previous_avg:
            change = ((recent_avg - previous_avg) / previous_avg) * 100
            if change > 5:
                item.price_trend = 'up'
            elif change < -5:
                item.price_trend = 'down'
            else:
                item.price_trend = 'stable'

    item.save()

    # Update grade-specific prices
    for gp in item.grade_prices.all():
        grade_sales = sales.filter(
            grading_company=gp.grading_company,
            grade=gp.grade
        )

        if grade_sales.exists():
            prices = list(grade_sales.values_list('sale_price', flat=True))
            gp.num_sales = len(prices)
            gp.avg_price = sum(prices) / len(prices)
            gp.low_price = min(prices)
            gp.high_price = max(prices)
            gp.median_price = sorted(prices)[len(prices) // 2]

            # Calculate 30-day change
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_sales = grade_sales.filter(sale_date__gte=thirty_days_ago)
            if recent_sales.exists():
                recent_avg = recent_sales.aggregate(Avg('sale_price'))['sale_price__avg']
                if gp.avg_price and recent_avg:
                    gp.price_change_30d = ((recent_avg - gp.avg_price) / gp.avg_price) * 100

            last_sale = grade_sales.order_by('-sale_date').first()
            gp.last_sale_price = last_sale.sale_price
            gp.last_sale_date = last_sale.sale_date

            gp.save()

    return f"Updated stats for {item.name}"


@shared_task
def record_sale_from_order(order_id):
    """When an order completes, record it in price guide"""
    from marketplace.models import Order
    from .models import SaleRecord

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return f"Order {order_id} not found"

    listing = order.listing

    if listing and listing.price_guide_item:
        SaleRecord.objects.create(
            price_guide_item=listing.price_guide_item,
            sale_price=order.item_price,
            sale_date=order.created,
            source='heroesandmore',
            grading_company=listing.grading_service or '',
            grade=Decimal(listing.grade) if listing.grade else None,
            cert_number=listing.cert_number or '',
            listing=listing,
        )

        # Trigger stats update
        update_price_guide_stats.delay(listing.price_guide_item.id)

        return f"Recorded sale for {listing.title}"

    return f"No price guide item for order {order_id}"


@shared_task
def update_all_price_guide_stats():
    """Periodic task to update all price guide stats"""
    from .models import PriceGuideItem

    items = PriceGuideItem.objects.all()
    count = 0

    for item in items:
        update_price_guide_stats.delay(item.id)
        count += 1

    return f"Queued {count} items for stats update"


@shared_task
def check_price_alerts():
    """Check all active price alerts and notify users"""
    from alerts.models import PriceAlert, Alert
    from marketplace.models import Listing

    alerts = PriceAlert.objects.filter(is_active=True, is_triggered=False)
    triggered_count = 0

    for alert in alerts:
        # Find listings below target price
        listings = Listing.objects.filter(
            price_guide_item=alert.price_guide_item,
            status='active',
            price__lte=alert.target_price
        )

        if alert.grade:
            listings = listings.filter(grade=alert.grade)

        listing = listings.order_by('price').first()

        if listing:
            # Trigger alert
            alert.is_triggered = True
            alert.triggered_at = timezone.now()
            alert.triggered_listing = listing
            alert.save()

            # Create notification
            Alert.objects.create(
                user=alert.user,
                alert_type='price_drop',
                title=f'Price Alert: {alert.price_guide_item.name}',
                message=f'A listing for {alert.price_guide_item.name} is now available for ${listing.price}, below your target of ${alert.target_price}.',
                link=listing.get_absolute_url(),
                listing=listing,
            )

            triggered_count += 1

    return f"Triggered {triggered_count} price alerts"


# =============================================================================
# Market Data Import Tasks (run twice daily)
# =============================================================================

@shared_task
def import_ebay_market_data(category_slug: str = None, limit: int = 100):
    """
    Import sold listings data from eBay.

    Runs twice daily at 6 AM and 6 PM.
    """
    from .models import PriceGuideItem
    from .services.market_data import EbayMarketData, MarketDataImporter, download_image_for_item

    logger.info(f"Starting eBay market data import (category: {category_slug})")

    importer = MarketDataImporter()
    items = PriceGuideItem.objects.all()

    if category_slug:
        items = items.filter(category__slug=category_slug)

    items = items.order_by('-total_sales')[:limit]
    total_imported = 0

    for item in items:
        try:
            search_query = importer._build_search_query(item)
            results = importer.ebay.search_sold_items(search_query, limit=20)

            for result in results:
                if importer._record_sale(item, result):
                    total_imported += 1

            # Download image if item doesn't have one
            if not item.image:
                for result in results:
                    if result.get('image_url'):
                        if download_image_for_item(item, result['image_url'], 'ebay'):
                            break

            # Update stats after import
            if results:
                update_price_guide_stats.delay(item.id)

        except Exception as e:
            logger.error(f"eBay import failed for {item.name}: {e}")

    logger.info(f"eBay import complete: {total_imported} new sales recorded")
    return f"Imported {total_imported} sales from eBay"


@shared_task
def import_heritage_market_data(category: str = 'sports', days_back: int = 7):
    """
    Import auction results from Heritage Auctions.

    Runs twice daily at 6 AM and 6 PM.
    """
    from .models import PriceGuideItem
    from .services.market_data import HeritageAuctionsData, MarketDataImporter, download_image_for_item

    logger.info(f"Starting Heritage Auctions import (category: {category})")

    heritage = HeritageAuctionsData()
    importer = MarketDataImporter()

    # Get recent sales from Heritage
    results = heritage.get_recent_sales(category=category, days_back=days_back, limit=200)
    total_imported = 0
    matched_items = set()

    for result in results:
        # Try to match to existing price guide items
        items = PriceGuideItem.objects.all()

        for item in items[:500]:  # Limit for performance
            if importer._is_match(item, result.get('title', '')):
                if importer._record_sale(item, result):
                    total_imported += 1
                    matched_items.add(item.id)
                # Download image if item doesn't have one
                if not item.image and result.get('image_url'):
                    download_image_for_item(item, result['image_url'], 'heritage')
                break

    # Update stats for matched items
    for item_id in matched_items:
        update_price_guide_stats.delay(item_id)

    logger.info(f"Heritage import complete: {total_imported} new sales, {len(matched_items)} items matched")
    return f"Imported {total_imported} sales from Heritage Auctions"


@shared_task
def import_gocollect_market_data(limit: int = 50):
    """
    Import comic book price data from GoCollect.

    Runs twice daily at 6 AM and 6 PM.
    """
    from .models import PriceGuideItem
    from .services.market_data import GoCollectData, MarketDataImporter, download_image_for_item

    logger.info("Starting GoCollect market data import")

    gocollect = GoCollectData()
    importer = MarketDataImporter()

    # Get comic items from our price guide
    comic_items = PriceGuideItem.objects.filter(
        category__slug__icontains='comic'
    ).order_by('-total_sales')[:limit]

    total_imported = 0

    for item in comic_items:
        try:
            search_query = importer._build_search_query(item)
            results = gocollect.search_comics(search_query, limit=10)

            for result in results:
                # Download image if item doesn't have one
                if not item.image and result.get('image_url'):
                    download_image_for_item(item, result['image_url'], 'gocollect')

                # Get detailed sales for this comic
                sales = gocollect.get_comic_sales(result.get('url', ''), limit=10)

                for sale in sales:
                    sale['title'] = result.get('title', item.name)
                    if importer._record_sale(item, sale):
                        total_imported += 1

            # Update stats after import
            if results:
                update_price_guide_stats.delay(item.id)

        except Exception as e:
            logger.error(f"GoCollect import failed for {item.name}: {e}")

    logger.info(f"GoCollect import complete: {total_imported} new sales recorded")
    return f"Imported {total_imported} sales from GoCollect"


@shared_task
def import_all_market_data():
    """
    Master task to import data from all sources.

    This is the task scheduled to run twice daily.
    Chains together all individual import tasks.
    """
    logger.info("Starting full market data import from all sources")

    results = {
        'ebay': 0,
        'heritage_sports': 0,
        'heritage_comics': 0,
        'gocollect': 0,
    }

    # Import from eBay (all categories)
    try:
        ebay_result = import_ebay_market_data(limit=200)
        logger.info(f"eBay: {ebay_result}")
    except Exception as e:
        logger.error(f"eBay import failed: {e}")

    # Import from Heritage (sports)
    try:
        heritage_sports = import_heritage_market_data(category='sports', days_back=3)
        logger.info(f"Heritage Sports: {heritage_sports}")
    except Exception as e:
        logger.error(f"Heritage Sports import failed: {e}")

    # Import from Heritage (comics)
    try:
        heritage_comics = import_heritage_market_data(category='comics', days_back=3)
        logger.info(f"Heritage Comics: {heritage_comics}")
    except Exception as e:
        logger.error(f"Heritage Comics import failed: {e}")

    # Import from GoCollect (comics only)
    try:
        gocollect_result = import_gocollect_market_data(limit=100)
        logger.info(f"GoCollect: {gocollect_result}")
    except Exception as e:
        logger.error(f"GoCollect import failed: {e}")

    logger.info("Full market data import complete")
    return "Market data import complete from all sources"
