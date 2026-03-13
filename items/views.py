from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q, Avg, Sum
from django.core.paginator import Paginator
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.auth.models import User

from .models import Category, Item
from marketplace.models import Listing, Order, Review, AuctionEvent


def _get_site_stats():
    """Get real site-wide stats for homepage and about page."""
    active_listings = Listing.objects.filter(status='active').count()
    collectors = User.objects.filter(is_active=True).count()
    sold_total = Order.objects.filter(
        status__in=['paid', 'shipped', 'delivered', 'completed']
    ).aggregate(total=Sum('item_price'))['total'] or 0
    avg_rating = Review.objects.aggregate(avg=Avg('rating'))['avg']
    return {
        'stat_active_listings': active_listings,
        'stat_collectors': collectors,
        'stat_sold_total': sold_total,
        'stat_avg_rating': round(avg_rating, 1) if avg_rating else None,
    }


def home(request):
    """Homepage with featured items and categories"""
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    one_hour_ago = now - timedelta(hours=1)

    # Get top-level categories
    categories = Category.objects.filter(parent=None, is_active=True).order_by('order')[:12]

    # Get recent listings (Featured Lots)
    recent_listings = Listing.objects.filter(status='active').select_related(
        'seller', 'category'
    ).order_by('-created')[:12]

    # Get featured/trending (most viewed)
    trending_listings = Listing.objects.filter(status='active').select_related(
        'seller', 'category'
    ).order_by('-views')[:8]

    # Get ending soon auctions — annotated with save/bid counts for HOT LOT badge
    ending_soon = Listing.objects.filter(
        status='active',
        listing_type='auction',
        auction_end__gt=now,
    ).select_related('seller', 'category').annotate(
        save_count=Count('saves'),
        bid_count_total=Count('bids'),
        recent_bids=Count('bids', filter=Q(bids__created__gte=one_hour_ago)),
    ).order_by('auction_end')[:8]

    # Bid Wars — auctions with most bidding activity in last hour
    bid_wars = Listing.objects.filter(
        status='active',
        listing_type='auction',
        auction_end__gt=now,
        bids__created__gte=one_hour_ago,
    ).select_related('seller', 'category').annotate(
        recent_bids=Count('bids', filter=Q(bids__created__gte=one_hour_ago)),
    ).order_by('-recent_bids')[:6]

    # Curated Listings — high-grade/high-value graded items
    curated_listings = Listing.objects.filter(
        status='active',
        is_graded=True,
    ).select_related('seller', 'category').order_by('-price')[:8]

    # Get live/upcoming/accepting-submissions platform auction events
    platform_events = AuctionEvent.objects.filter(
        is_platform_event=True,
    ).filter(
        Q(status__in=['live', 'preview'], bidding_end__gt=now) |
        Q(accepting_submissions=True, status='draft')
    ).order_by('bidding_start')[:3]

    context = {
        'categories': categories,
        'recent_listings': recent_listings,
        'trending_listings': trending_listings,
        'ending_soon': ending_soon,
        'bid_wars': bid_wars,
        'curated_listings': curated_listings,
        'platform_events': platform_events,
        **_get_site_stats(),
    }
    return render(request, 'home.html', context)


def about(request):
    """About page with real site stats."""
    return render(request, 'pages/about.html', _get_site_stats())


def category_list(request):
    """All categories page"""
    categories = Category.objects.filter(parent=None, is_active=True).prefetch_related(
        'children'
    ).annotate(
        listing_count=Count('listings', filter=Q(listings__status='active'))
    ).order_by('order')

    context = {
        'categories': categories,
    }
    return render(request, 'items/category_list.html', context)


def category_detail(request, slug):
    """Category page with listings"""
    category = get_object_or_404(Category, slug=slug, is_active=True)

    # Get all category IDs (including children)
    category_ids = [category.id] + [c.id for c in category.get_descendants()]

    # Get listings in this category
    listings = Listing.objects.filter(
        category_id__in=category_ids,
        status='active'
    ).select_related('seller', 'category')

    # Filtering
    condition = request.GET.get('condition')
    if condition:
        listings = listings.filter(condition=condition)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        listings = listings.filter(price__gte=min_price)
    if max_price:
        listings = listings.filter(price__lte=max_price)

    listing_type = request.GET.get('type')
    if listing_type:
        listings = listings.filter(listing_type=listing_type)

    # Sorting
    sort = request.GET.get('sort', '-created')
    if sort == 'price_low':
        listings = listings.order_by('price')
    elif sort == 'price_high':
        listings = listings.order_by('-price')
    elif sort == 'ending':
        listings = listings.filter(listing_type='auction').order_by('auction_end')
    else:
        listings = listings.order_by('-created')

    # Pagination
    paginator = Paginator(listings, 24)
    page = request.GET.get('page')
    listings = paginator.get_page(page)

    # Subcategories
    subcategories = category.children.filter(is_active=True).annotate(
        listing_count=Count('listings', filter=Q(listings__status='active'))
    )

    context = {
        'category': category,
        'listings': listings,
        'subcategories': subcategories,
        'ancestors': category.get_ancestors(),
        'query_params': request.GET.copy(),
    }
    if 'page' in context['query_params']:
        context['query_params'].pop('page')
    context['query_params'] = context['query_params'].urlencode()
    return render(request, 'items/category_detail.html', context)


def item_detail(request, category_slug, slug):
    """Item detail page (from database)"""
    category = get_object_or_404(Category, slug=category_slug)
    item = get_object_or_404(Item, slug=slug, category=category)

    # Get active listings for this item
    listings = Listing.objects.filter(
        item=item,
        status='active'
    ).select_related('seller').order_by('price')

    # Get price history
    price_history = item.price_history.all()[:30]

    context = {
        'item': item,
        'category': category,
        'listings': listings,
        'price_history': price_history,
    }
    return render(request, 'items/item_detail.html', context)


def search(request):
    """Search listings"""
    query = request.GET.get('q', '').strip()
    listings = Listing.objects.filter(status='active').select_related('seller', 'category')

    if query:
        # Use PostgreSQL full-text search if available
        try:
            search_vector = SearchVector('title', weight='A') + SearchVector('description', weight='B')
            search_query = SearchQuery(query)
            listings = listings.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).order_by('-rank')
        except Exception:
            # Fallback to simple search for SQLite
            listings = listings.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            )

    # Category filter
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        category_ids = [category.id] + [c.id for c in category.get_descendants()]
        listings = listings.filter(category_id__in=category_ids)

    # Condition filter
    condition = request.GET.get('condition')
    if condition:
        listings = listings.filter(condition=condition)

    # Price filters
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        listings = listings.filter(price__gte=min_price)
    if max_price:
        listings = listings.filter(price__lte=max_price)

    # Sort
    sort = request.GET.get('sort', '-created')
    if sort == 'price_low':
        listings = listings.order_by('price')
    elif sort == 'price_high':
        listings = listings.order_by('-price')
    elif sort == 'relevance' and query:
        pass  # Already sorted by rank
    else:
        listings = listings.order_by('-created')

    # Pagination
    paginator = Paginator(listings, 24)
    page = request.GET.get('page')
    listings = paginator.get_page(page)

    # Categories for filter
    categories = Category.objects.filter(parent=None, is_active=True)

    context = {
        'query': query,
        'listings': listings,
        'categories': categories,
        'query_params': request.GET.copy(),
    }
    if 'page' in context['query_params']:
        context['query_params'].pop('page')
    context['query_params'] = context['query_params'].urlencode()
    return render(request, 'items/search.html', context)


def autocomplete(request):
    """AJAX endpoint for search autocomplete suggestions"""
    from django.http import JsonResponse

    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'suggestions': []})

    suggestions = []

    # Search listings
    listings = Listing.objects.filter(
        status='active',
        title__icontains=query
    ).values_list('title', flat=True).distinct()[:5]
    suggestions.extend([{'text': t, 'type': 'listing'} for t in listings])

    # Search categories
    categories = Category.objects.filter(
        is_active=True,
        name__icontains=query
    ).values('name', 'slug')[:3]
    suggestions.extend([{'text': c['name'], 'type': 'category', 'slug': c['slug']} for c in categories])

    # Search price guide items if available
    try:
        from pricing.models import PriceGuideItem
        price_items = PriceGuideItem.objects.filter(
            name__icontains=query
        ).values('name', 'slug')[:3]
        suggestions.extend([{'text': p['name'], 'type': 'price_guide', 'slug': p['slug']} for p in price_items])
    except Exception:
        pass

    return JsonResponse({'suggestions': suggestions[:10]})
