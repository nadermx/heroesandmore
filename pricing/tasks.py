from celery import shared_task
from django.db.models import Avg, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


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
