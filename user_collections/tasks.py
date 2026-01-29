from celery import shared_task
from django.utils import timezone
from django.db.models import Sum
from datetime import date
from decimal import Decimal


@shared_task
def update_collection_values(collection_id):
    """Update cached values for a collection"""
    from .models import Collection, CollectionItem

    try:
        collection = Collection.objects.get(id=collection_id)
    except Collection.DoesNotExist:
        return f"Collection {collection_id} not found"

    total_value = Decimal('0')
    total_cost = Decimal('0')

    for item in collection.items.all():
        # Update item value from price guide if linked
        if item.price_guide_item:
            # Get price for grade
            grade_price = item.price_guide_item.get_price_for_grade(
                grading_company=item.grading_company or 'raw',
                grade=Decimal(item.grade) if item.grade else None
            )

            if grade_price and grade_price.avg_price:
                item.current_value = grade_price.avg_price
                item.value_updated_at = timezone.now()
                item.save(update_fields=['current_value', 'value_updated_at'])

        # Add to totals
        if item.current_value:
            total_value += item.current_value * item.quantity
        if item.purchase_price:
            total_cost += item.purchase_price * item.quantity

    # Update collection totals
    collection.total_value = total_value
    collection.total_cost = total_cost
    collection.value_updated_at = timezone.now()
    collection.save(update_fields=['total_value', 'total_cost', 'value_updated_at'])

    return f"Updated values for collection {collection.name}: ${total_value}"


@shared_task
def create_collection_snapshot(collection_id):
    """Create a daily snapshot of collection value"""
    from .models import Collection, CollectionValueSnapshot

    try:
        collection = Collection.objects.get(id=collection_id)
    except Collection.DoesNotExist:
        return f"Collection {collection_id} not found"

    today = date.today()

    # Check if snapshot already exists for today
    if CollectionValueSnapshot.objects.filter(collection=collection, date=today).exists():
        return f"Snapshot already exists for {collection.name} on {today}"

    # Calculate value by category
    value_by_category = {}
    for item in collection.items.select_related('category').all():
        if item.current_value and item.category:
            cat_name = item.category.name
            if cat_name not in value_by_category:
                value_by_category[cat_name] = 0
            value_by_category[cat_name] += float(item.current_value * item.quantity)

    # Create snapshot
    snapshot = CollectionValueSnapshot.objects.create(
        collection=collection,
        date=today,
        total_value=collection.total_value or Decimal('0'),
        total_cost=collection.total_cost or Decimal('0'),
        item_count=collection.items.count(),
        value_by_category=value_by_category,
    )

    return f"Created snapshot for {collection.name}: ${snapshot.total_value}"


@shared_task
def update_all_collection_values():
    """Periodic task to update all collection values"""
    from .models import Collection

    collections = Collection.objects.all()
    count = 0

    for collection in collections:
        update_collection_values.delay(collection.id)
        count += 1

    return f"Queued {count} collections for value update"


@shared_task
def create_daily_snapshots():
    """Periodic task to create daily snapshots for all collections"""
    from .models import Collection

    collections = Collection.objects.all()
    count = 0

    for collection in collections:
        # First update values
        update_collection_values.delay(collection.id)
        # Then create snapshot
        create_collection_snapshot.delay(collection.id)
        count += 1

    return f"Queued {count} collections for daily snapshots"
