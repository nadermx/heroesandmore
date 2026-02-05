import json
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta

from .models import PriceGuideItem, GradePrice, SaleRecord
from items.models import Category
from marketplace.models import Listing


class PriceGuideListView(ListView):
    """Browse price guide by category"""
    model = PriceGuideItem
    template_name = 'pricing/price_guide_list.html'
    context_object_name = 'items'
    paginate_by = 48

    def get_queryset(self):
        qs = super().get_queryset()

        # Category filter
        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            qs = qs.filter(category__slug=category_slug)

        # Search
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)

        # Year filter
        year = self.request.GET.get('year')
        if year:
            qs = qs.filter(year=year)

        # Set filter
        set_name = self.request.GET.get('set')
        if set_name:
            qs = qs.filter(set_name__icontains=set_name)

        # Sort
        sort = self.request.GET.get('sort', 'popular')
        if sort == 'popular':
            qs = qs.order_by('-total_sales')
        elif sort == 'newest':
            qs = qs.order_by('-created')
        elif sort == 'price_high':
            qs = qs.order_by('-avg_sale_price')
        elif sort == 'price_low':
            qs = qs.order_by('avg_sale_price')
        elif sort == 'name':
            qs = qs.order_by('name')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(parent__isnull=True)
        context['current_category'] = None

        category_slug = self.kwargs.get('category_slug')
        if category_slug:
            context['current_category'] = get_object_or_404(Category, slug=category_slug)

        context['q'] = self.request.GET.get('q', '')
        context['sort'] = self.request.GET.get('sort', 'popular')
        return context


class PriceGuideDetailView(DetailView):
    """Individual item price guide with charts"""
    model = PriceGuideItem
    template_name = 'pricing/price_guide_detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.object

        # Grade prices
        context['grade_prices'] = item.grade_prices.all().order_by('-grade')

        # Recent sales
        context['recent_sales'] = item.sales.order_by('-sale_date')[:20]

        # Price history for charts (last 12 months)
        context['price_history'] = self.get_price_history(item)

        # Active listings for this item
        context['active_listings'] = Listing.objects.filter(
            price_guide_item=item,
            status='active'
        ).order_by('price')[:10]

        # Related items
        context['related_items'] = PriceGuideItem.objects.filter(
            category=item.category,
            year=item.year
        ).exclude(pk=item.pk)[:8]

        return context

    def get_price_history(self, item):
        """Get price history grouped by month for charts - returns JSON string"""
        twelve_months_ago = timezone.now() - timedelta(days=365)

        history = item.sales.filter(
            sale_date__gte=twelve_months_ago
        ).annotate(
            month=TruncMonth('sale_date')
        ).values('month').annotate(
            avg_price=Avg('sale_price'),
            count=Count('id')
        ).order_by('month')

        # Convert to JSON-serializable format
        data = [{
            'month': h['month'].isoformat(),
            'avg_price': float(h['avg_price']),
            'count': h['count']
        } for h in history]

        return json.dumps(data)


def price_guide_search(request):
    """Search the price guide"""
    q = request.GET.get('q', '')
    category = request.GET.get('category')

    items = PriceGuideItem.objects.all()

    if q:
        items = items.filter(name__icontains=q)
    if category:
        items = items.filter(category__slug=category)

    items = items[:50]

    return render(request, 'pricing/price_guide_search.html', {
        'items': items,
        'q': q,
    })


def get_price_suggestion(request):
    """AJAX endpoint for price suggestions when listing"""
    item_name = request.GET.get('name', '')
    category_id = request.GET.get('category')
    grade = request.GET.get('grade')
    grading_company = request.GET.get('grading_company', 'raw')

    # Find matching price guide item
    items = PriceGuideItem.objects.all()
    if category_id:
        items = items.filter(category_id=category_id)

    item = items.filter(name__icontains=item_name).first()

    if not item:
        return JsonResponse({'found': False})

    # Get price for grade
    grade_price = None
    if grade:
        try:
            grade_decimal = float(grade)
            grade_price = item.grade_prices.filter(
                grading_company=grading_company,
                grade=grade_decimal
            ).first()
        except (ValueError, TypeError):
            pass

    if grade_price:
        return JsonResponse({
            'found': True,
            'item_id': item.id,
            'item_name': item.name,
            'suggested_price': float(grade_price.avg_price or 0),
            'low_price': float(grade_price.low_price or 0),
            'high_price': float(grade_price.high_price or 0),
            'num_sales': grade_price.num_sales,
            'last_sale': grade_price.last_sale_date.isoformat() if grade_price.last_sale_date else None,
        })

    return JsonResponse({
        'found': True,
        'item_id': item.id,
        'item_name': item.name,
        'suggested_price': float(item.avg_sale_price or 0),
        'no_grade_data': True,
    })


def get_price_history(request, item_id):
    """AJAX endpoint for price history data"""
    item = get_object_or_404(PriceGuideItem, pk=item_id)

    months = int(request.GET.get('months', 12))
    start_date = timezone.now() - timedelta(days=months * 30)

    history = item.sales.filter(
        sale_date__gte=start_date
    ).annotate(
        month=TruncMonth('sale_date')
    ).values('month').annotate(
        avg_price=Avg('sale_price'),
        count=Count('id')
    ).order_by('month')

    data = [{
        'month': h['month'].strftime('%Y-%m'),
        'avg_price': float(h['avg_price']),
        'count': h['count']
    } for h in history]

    return JsonResponse({'history': data})


def trending_items(request):
    """Show trending items based on recent sales activity"""
    # Items with most sales in last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)

    trending = PriceGuideItem.objects.filter(
        sales__sale_date__gte=thirty_days_ago
    ).annotate(
        recent_sales=Count('sales')
    ).order_by('-recent_sales')[:50]

    return render(request, 'pricing/trending.html', {
        'items': trending,
    })


def popular_items(request):
    """Show most popular items by total sales"""
    items = PriceGuideItem.objects.order_by('-total_sales')[:50]

    return render(request, 'pricing/popular.html', {
        'items': items,
    })
