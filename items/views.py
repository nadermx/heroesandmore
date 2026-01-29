from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

from .models import Category, Item
from marketplace.models import Listing


def home(request):
    """Homepage with featured items and categories"""
    # Get top-level categories
    categories = Category.objects.filter(parent=None, is_active=True).order_by('order')[:12]

    # Get recent listings
    recent_listings = Listing.objects.filter(status='active').select_related(
        'seller', 'category'
    ).order_by('-created')[:12]

    # Get featured/trending (most viewed)
    trending_listings = Listing.objects.filter(status='active').select_related(
        'seller', 'category'
    ).order_by('-views')[:8]

    # Get ending soon auctions
    from django.utils import timezone
    ending_soon = Listing.objects.filter(
        status='active',
        listing_type='auction',
        auction_end__gt=timezone.now()
    ).select_related('seller', 'category').order_by('auction_end')[:4]

    context = {
        'categories': categories,
        'recent_listings': recent_listings,
        'trending_listings': trending_listings,
        'ending_soon': ending_soon,
    }
    return render(request, 'home.html', context)


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
    }
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
    }
    return render(request, 'items/search.html', context)
