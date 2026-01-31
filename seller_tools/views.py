from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth, TruncDay
from django.utils import timezone
from datetime import timedelta
import csv

from .models import SellerSubscription, BulkImport, BulkImportRow, InventoryItem
from marketplace.models import Listing, Order
from items.models import Category


@login_required
def seller_dashboard(request):
    """Main seller dashboard"""
    # Get or create subscription
    subscription, created = SellerSubscription.objects.get_or_create(
        user=request.user,
        defaults={'tier': 'starter'}
    )

    # Stats
    active_listings = Listing.objects.filter(seller=request.user, status='active').count()
    pending_orders = Order.objects.filter(seller=request.user, status='paid').count()

    # Recent sales
    recent_sales = Order.objects.filter(
        seller=request.user,
        status__in=['paid', 'shipped', 'delivered', 'completed']
    ).order_by('-created')[:10]

    # Sales this month
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_sales = Order.objects.filter(
        seller=request.user,
        status__in=['paid', 'shipped', 'delivered', 'completed'],
        created__gte=month_start
    ).aggregate(
        total=Sum('item_price'),
        count=Count('id')
    )

    return render(request, 'seller_tools/dashboard.html', {
        'subscription': subscription,
        'active_listings': active_listings,
        'pending_orders': pending_orders,
        'recent_sales': recent_sales,
        'monthly_sales': monthly_sales,
    })


@login_required
def subscription_manage(request):
    """Manage seller subscription"""
    subscription, created = SellerSubscription.objects.get_or_create(
        user=request.user,
        defaults={'tier': 'starter'}
    )

    # Sync with Stripe if there's an active subscription
    if subscription.stripe_subscription_id:
        from marketplace.services.subscription_service import SubscriptionService
        try:
            SubscriptionService.get_subscription_status(request.user)
            subscription.refresh_from_db()
        except Exception:
            pass

    tiers = SellerSubscription.TIER_DETAILS

    return render(request, 'seller_tools/subscription.html', {
        'subscription': subscription,
        'tiers': tiers,
    })


@login_required
def subscription_upgrade(request, tier):
    """Upgrade seller subscription via Stripe Checkout"""
    from marketplace.services.subscription_service import SubscriptionService

    if tier not in ['basic', 'featured', 'premium']:
        messages.error(request, 'Invalid subscription tier')
        return redirect('seller_tools:subscription')

    try:
        session = SubscriptionService.create_checkout_session(
            request.user,
            tier,
            success_url=request.build_absolute_uri('/seller/subscription/success/'),
            cancel_url=request.build_absolute_uri('/seller/subscription/')
        )
        return redirect(session.url)
    except Exception as e:
        messages.error(request, f'Unable to start subscription: {e}')
        return redirect('seller_tools:subscription')


@login_required
def subscription_success(request):
    """Handle successful subscription signup"""
    messages.success(request, 'Welcome! Your subscription is now active.')
    return redirect('seller_tools:subscription')


@login_required
@require_POST
def subscription_cancel(request):
    """Cancel seller subscription"""
    from marketplace.services.subscription_service import SubscriptionService

    subscription = get_object_or_404(SellerSubscription, user=request.user)

    if subscription.stripe_subscription_id:
        try:
            # Cancel at period end (graceful cancellation)
            SubscriptionService.cancel_subscription(request.user, at_period_end=True)
            messages.success(request, 'Your subscription will be cancelled at the end of the billing period.')
        except Exception as e:
            messages.error(request, f'Unable to cancel subscription: {e}')
    else:
        # No Stripe subscription, just downgrade
        starter_info = SellerSubscription.TIER_DETAILS['starter']
        subscription.tier = 'starter'
        subscription.max_active_listings = starter_info['max_listings']
        subscription.commission_rate = starter_info['commission_rate']
        subscription.featured_slots = starter_info['featured_slots']
        subscription.save()
        messages.success(request, 'You are now on the Starter tier.')

    return redirect('seller_tools:subscription')


@login_required
@require_POST
def subscription_reactivate(request):
    """Reactivate a subscription that was set to cancel"""
    from marketplace.services.subscription_service import SubscriptionService

    try:
        SubscriptionService.reactivate_subscription(request.user)
        messages.success(request, 'Your subscription has been reactivated.')
    except Exception as e:
        messages.error(request, f'Unable to reactivate subscription: {e}')

    return redirect('seller_tools:subscription')


@login_required
def subscription_billing_portal(request):
    """Redirect to Stripe Billing Portal"""
    from marketplace.services.subscription_service import SubscriptionService

    try:
        session = SubscriptionService.create_billing_portal_session(
            request.user,
            return_url=request.build_absolute_uri('/seller/subscription/')
        )
        return redirect(session.url)
    except Exception as e:
        messages.error(request, f'Unable to access billing portal: {e}')
        return redirect('seller_tools:subscription')


@login_required
def bulk_import_list(request):
    """List all bulk imports"""
    imports = BulkImport.objects.filter(user=request.user)

    return render(request, 'seller_tools/import_list.html', {
        'imports': imports,
    })


@login_required
def bulk_import_create(request):
    """Create a new bulk import"""
    if request.method == 'POST':
        if 'file' not in request.FILES:
            messages.error(request, 'Please upload a file')
            return redirect('seller_tools:import_create')

        file = request.FILES['file']
        file_type = file.name.split('.')[-1].lower()

        if file_type not in ['csv', 'xlsx']:
            messages.error(request, 'Only CSV and Excel files are supported')
            return redirect('seller_tools:import_create')

        bulk_import = BulkImport.objects.create(
            user=request.user,
            file=file,
            file_name=file.name,
            file_type=file_type,
            auto_publish=request.POST.get('auto_publish') == 'on',
        )

        # Parse the file and count rows
        if file_type == 'csv':
            content = file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(content)
            rows = list(reader)
            bulk_import.total_rows = len(rows)

            # Create row records
            for i, row in enumerate(rows, 1):
                BulkImportRow.objects.create(
                    bulk_import=bulk_import,
                    row_number=i,
                    data=dict(row)
                )

            bulk_import.status = 'validating'
            bulk_import.save()

        messages.success(request, f'Imported {bulk_import.total_rows} rows. Review and process.')
        return redirect('seller_tools:import_detail', pk=bulk_import.pk)

    categories = Category.objects.filter(parent__isnull=True)

    return render(request, 'seller_tools/import_create.html', {
        'categories': categories,
    })


@login_required
def bulk_import_detail(request, pk):
    """View bulk import details"""
    bulk_import = get_object_or_404(BulkImport, pk=pk, user=request.user)
    rows = bulk_import.rows.all()[:100]  # Limit for display

    return render(request, 'seller_tools/import_detail.html', {
        'bulk_import': bulk_import,
        'rows': rows,
    })


@login_required
@require_POST
def bulk_import_process(request, pk):
    """Process bulk import and create listings"""
    bulk_import = get_object_or_404(BulkImport, pk=pk, user=request.user)

    if bulk_import.status not in ['validating', 'partial']:
        messages.error(request, 'This import cannot be processed')
        return redirect('seller_tools:import_detail', pk=pk)

    # In production, trigger Celery task
    # process_bulk_import.delay(bulk_import.id)

    bulk_import.status = 'processing'
    bulk_import.started_at = timezone.now()
    bulk_import.save()

    messages.success(request, 'Import processing started. This may take a few minutes.')
    return redirect('seller_tools:import_detail', pk=pk)


@login_required
def download_import_template(request):
    """Download CSV template for bulk import"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="listing_import_template.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'title',
        'description',
        'category',
        'condition',
        'price',
        'quantity',
        'grading_service',
        'grade',
        'cert_number',
        'shipping_price',
        'listing_type',
        'auction_duration_days',
        'allow_offers',
    ])

    # Example row
    writer.writerow([
        '1986 Fleer Michael Jordan #57 PSA 10',
        'Beautiful PSA 10 gem mint example of the iconic rookie card.',
        'trading-cards',
        'mint',
        '500000.00',
        '1',
        'psa',
        '10',
        '12345678',
        '25.00',
        'fixed',
        '',
        'no',
    ])

    return response


@login_required
def inventory_list(request):
    """List inventory items"""
    items = InventoryItem.objects.filter(user=request.user)

    # Filters
    is_listed = request.GET.get('listed')
    if is_listed == 'yes':
        items = items.filter(is_listed=True)
    elif is_listed == 'no':
        items = items.filter(is_listed=False)

    category = request.GET.get('category')
    if category:
        items = items.filter(category__slug=category)

    return render(request, 'seller_tools/inventory_list.html', {
        'items': items,
        'categories': Category.objects.filter(parent__isnull=True),
    })


@login_required
def inventory_add(request):
    """Add inventory item"""
    if request.method == 'POST':
        item = InventoryItem.objects.create(
            user=request.user,
            title=request.POST.get('title'),
            category_id=request.POST.get('category') or None,
            condition=request.POST.get('condition', ''),
            grading_company=request.POST.get('grading_company', ''),
            grade=request.POST.get('grade') or None,
            cert_number=request.POST.get('cert_number', ''),
            purchase_price=request.POST.get('purchase_price') or None,
            purchase_date=request.POST.get('purchase_date') or None,
            purchase_source=request.POST.get('purchase_source', ''),
            target_price=request.POST.get('target_price') or None,
            minimum_price=request.POST.get('minimum_price') or None,
            notes=request.POST.get('notes', ''),
        )

        # Handle images
        for i in range(1, 4):
            img_field = f'image{i}'
            if img_field in request.FILES:
                setattr(item, img_field, request.FILES[img_field])
        item.save()

        messages.success(request, 'Inventory item added')
        return redirect('seller_tools:inventory_list')

    categories = Category.objects.filter(parent__isnull=True)

    return render(request, 'seller_tools/inventory_add.html', {
        'categories': categories,
    })


@login_required
def inventory_detail(request, pk):
    """View inventory item"""
    item = get_object_or_404(InventoryItem, pk=pk, user=request.user)

    return render(request, 'seller_tools/inventory_detail.html', {
        'item': item,
    })


@login_required
def inventory_edit(request, pk):
    """Edit inventory item"""
    item = get_object_or_404(InventoryItem, pk=pk, user=request.user)

    if request.method == 'POST':
        item.title = request.POST.get('title')
        item.category_id = request.POST.get('category') or None
        item.condition = request.POST.get('condition', '')
        item.grading_company = request.POST.get('grading_company', '')
        item.grade = request.POST.get('grade') or None
        item.cert_number = request.POST.get('cert_number', '')
        item.purchase_price = request.POST.get('purchase_price') or None
        item.purchase_date = request.POST.get('purchase_date') or None
        item.purchase_source = request.POST.get('purchase_source', '')
        item.target_price = request.POST.get('target_price') or None
        item.minimum_price = request.POST.get('minimum_price') or None
        item.notes = request.POST.get('notes', '')
        item.save()

        messages.success(request, 'Inventory item updated')
        return redirect('seller_tools:inventory_detail', pk=pk)

    categories = Category.objects.filter(parent__isnull=True)

    return render(request, 'seller_tools/inventory_edit.html', {
        'item': item,
        'categories': categories,
    })


@login_required
def inventory_create_listing(request, pk):
    """Create listing from inventory item"""
    item = get_object_or_404(InventoryItem, pk=pk, user=request.user)

    # Pre-populate session data for listing create
    request.session['listing_prefill'] = {
        'title': item.title,
        'category': item.category_id,
        'condition': item.condition,
        'grading_service': item.grading_company,
        'grade': str(item.grade) if item.grade else '',
        'cert_number': item.cert_number,
        'price': str(item.target_price) if item.target_price else '',
        'price_guide_item': item.price_guide_item_id,
    }

    messages.info(request, 'Complete your listing with additional details.')
    return redirect('marketplace:listing_create')


@login_required
def seller_analytics(request):
    """Seller analytics dashboard"""
    # Date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    # Sales over time
    sales_by_day = Order.objects.filter(
        seller=request.user,
        status__in=['paid', 'shipped', 'delivered', 'completed'],
        created__gte=start_date
    ).annotate(
        day=TruncDay('created')
    ).values('day').annotate(
        total=Sum('item_price'),
        count=Count('id')
    ).order_by('day')

    # Top selling items
    top_items = Order.objects.filter(
        seller=request.user,
        status__in=['paid', 'shipped', 'delivered', 'completed'],
        created__gte=start_date
    ).values(
        'listing__title', 'listing__category__name'
    ).annotate(
        total=Sum('item_price'),
        count=Count('id')
    ).order_by('-total')[:10]

    # Total stats
    totals = Order.objects.filter(
        seller=request.user,
        status__in=['paid', 'shipped', 'delivered', 'completed'],
        created__gte=start_date
    ).aggregate(
        revenue=Sum('item_price'),
        orders=Count('id'),
        fees=Sum('platform_fee')
    )

    return render(request, 'seller_tools/analytics.html', {
        'sales_by_day': list(sales_by_day),
        'top_items': top_items,
        'totals': totals,
        'days': days,
    })


@login_required
def sales_report(request):
    """Detailed sales report"""
    # Date range
    start = request.GET.get('start')
    end = request.GET.get('end')

    orders = Order.objects.filter(
        seller=request.user,
        status__in=['paid', 'shipped', 'delivered', 'completed']
    ).order_by('-created')

    if start:
        orders = orders.filter(created__date__gte=start)
    if end:
        orders = orders.filter(created__date__lte=end)

    totals = orders.aggregate(
        revenue=Sum('item_price'),
        fees=Sum('platform_fee'),
        net=Sum('seller_payout')
    )

    return render(request, 'seller_tools/sales_report.html', {
        'orders': orders[:100],
        'totals': totals,
    })


@login_required
def export_analytics(request):
    """Export sales data as CSV"""
    orders = Order.objects.filter(
        seller=request.user,
        status__in=['paid', 'shipped', 'delivered', 'completed']
    ).order_by('-created')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Order ID', 'Date', 'Item', 'Buyer', 'Item Price', 'Shipping',
        'Total', 'Platform Fee', 'Your Payout', 'Status'
    ])

    for order in orders:
        writer.writerow([
            order.id,
            order.created.strftime('%Y-%m-%d %H:%M'),
            order.listing.title if order.listing else 'Deleted',
            order.buyer.username,
            order.item_price,
            order.shipping_price,
            order.amount,
            order.platform_fee,
            order.seller_payout,
            order.status,
        ])

    return response


@login_required
def payout_settings(request):
    """Seller payout settings and history"""
    from marketplace.services.connect_service import ConnectService

    profile = request.user.profile

    if not profile.stripe_account_id:
        messages.info(request, 'Please complete your seller account setup first.')
        return redirect('marketplace:seller_setup')

    # Get account details
    try:
        account = ConnectService.retrieve_account(profile.stripe_account_id)
        balance = ConnectService.get_balance(profile.stripe_account_id)
        transfers = ConnectService.list_transfers(profile.stripe_account_id, limit=20)
    except Exception as e:
        messages.error(request, f'Unable to load payout information: {e}')
        account = None
        balance = {'available': [], 'pending': []}
        transfers = []

    return render(request, 'seller_tools/payout_settings.html', {
        'account': account,
        'balance': balance,
        'transfers': transfers.data if hasattr(transfers, 'data') else [],
    })
