from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator

from .models import Wishlist, WishlistItem, Alert, SavedSearch
from .forms import WishlistForm, WishlistItemForm, SavedSearchForm
from items.models import Category


@login_required
def alerts_list(request):
    """View all alerts/notifications"""
    alerts = Alert.objects.filter(user=request.user)

    # Filter by type
    alert_type = request.GET.get('type')
    if alert_type:
        alerts = alerts.filter(alert_type=alert_type)

    # Unread filter
    if request.GET.get('unread'):
        alerts = alerts.filter(read=False)

    paginator = Paginator(alerts, 50)
    page = request.GET.get('page')
    alerts = paginator.get_page(page)

    unread_count = Alert.objects.filter(user=request.user, read=False).count()

    context = {
        'alerts': alerts,
        'unread_count': unread_count,
    }
    return render(request, 'alerts/alerts_list.html', context)


@login_required
def mark_read(request, pk):
    """Mark alert as read"""
    alert = get_object_or_404(Alert, pk=pk, user=request.user)
    alert.read = True
    alert.save()

    if request.headers.get('HX-Request'):
        return JsonResponse({'success': True})

    if alert.link:
        return redirect(alert.link)

    return redirect('alerts:alerts_list')


@login_required
def mark_all_read(request):
    """Mark all alerts as read"""
    Alert.objects.filter(user=request.user, read=False).update(read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('alerts:alerts_list')


@login_required
def delete_alert(request, pk):
    """Delete an alert"""
    alert = get_object_or_404(Alert, pk=pk, user=request.user)
    alert.delete()

    if request.headers.get('HX-Request'):
        return JsonResponse({'success': True})

    return redirect('alerts:alerts_list')


# Wishlists
@login_required
def wishlist_list(request):
    """User's wishlists"""
    wishlists = Wishlist.objects.filter(user=request.user)

    context = {
        'wishlists': wishlists,
    }
    return render(request, 'alerts/wishlist_list.html', context)


@login_required
def wishlist_create(request):
    """Create new wishlist"""
    if request.method == 'POST':
        form = WishlistForm(request.POST)
        if form.is_valid():
            wishlist = form.save(commit=False)
            wishlist.user = request.user
            wishlist.save()
            messages.success(request, 'Wishlist created!')
            return redirect('alerts:wishlist_detail', pk=wishlist.pk)
    else:
        form = WishlistForm()

    context = {
        'form': form,
    }
    return render(request, 'alerts/wishlist_form.html', context)


@login_required
def wishlist_detail(request, pk):
    """View wishlist and matches"""
    wishlist = get_object_or_404(Wishlist, pk=pk)

    # Check access
    if wishlist.user != request.user and not wishlist.is_public:
        messages.error(request, "This wishlist is private.")
        return redirect('alerts:wishlist_list')

    items = wishlist.items.all()

    # Get matches for each item
    for item in items:
        item.matches = item.get_matching_listings()[:4]

    context = {
        'wishlist': wishlist,
        'items': items,
        'is_owner': request.user == wishlist.user,
    }
    return render(request, 'alerts/wishlist_detail.html', context)


@login_required
def wishlist_edit(request, pk):
    """Edit wishlist"""
    wishlist = get_object_or_404(Wishlist, pk=pk, user=request.user)

    if request.method == 'POST':
        form = WishlistForm(request.POST, instance=wishlist)
        if form.is_valid():
            form.save()
            messages.success(request, 'Wishlist updated!')
            return redirect('alerts:wishlist_detail', pk=pk)
    else:
        form = WishlistForm(instance=wishlist)

    context = {
        'form': form,
        'wishlist': wishlist,
    }
    return render(request, 'alerts/wishlist_form.html', context)


@login_required
def wishlist_delete(request, pk):
    """Delete wishlist"""
    wishlist = get_object_or_404(Wishlist, pk=pk, user=request.user)

    if request.method == 'POST':
        wishlist.delete()
        messages.success(request, 'Wishlist deleted.')
        return redirect('alerts:wishlist_list')

    context = {
        'wishlist': wishlist,
    }
    return render(request, 'alerts/wishlist_confirm_delete.html', context)


@login_required
def wishlist_item_add(request, pk):
    """Add item to wishlist"""
    wishlist = get_object_or_404(Wishlist, pk=pk, user=request.user)

    if request.method == 'POST':
        form = WishlistItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.wishlist = wishlist
            item.save()
            messages.success(request, 'Item added to wishlist!')
            return redirect('alerts:wishlist_detail', pk=pk)
    else:
        form = WishlistItemForm()

    categories = Category.objects.filter(is_active=True)

    context = {
        'form': form,
        'wishlist': wishlist,
        'categories': categories,
    }
    return render(request, 'alerts/wishlist_item_form.html', context)


@login_required
def wishlist_item_edit(request, pk):
    """Edit wishlist item"""
    item = get_object_or_404(WishlistItem, pk=pk, wishlist__user=request.user)

    if request.method == 'POST':
        form = WishlistItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item updated!')
            return redirect('alerts:wishlist_detail', pk=item.wishlist.pk)
    else:
        form = WishlistItemForm(instance=item)

    categories = Category.objects.filter(is_active=True)

    context = {
        'form': form,
        'item': item,
        'categories': categories,
    }
    return render(request, 'alerts/wishlist_item_form.html', context)


@login_required
def wishlist_item_delete(request, pk):
    """Delete wishlist item"""
    item = get_object_or_404(WishlistItem, pk=pk, wishlist__user=request.user)
    wishlist_pk = item.wishlist.pk

    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Item removed from wishlist.')
        return redirect('alerts:wishlist_detail', pk=wishlist_pk)

    context = {
        'item': item,
    }
    return render(request, 'alerts/wishlist_item_confirm_delete.html', context)


# Saved Searches
@login_required
def saved_search_list(request):
    """List saved searches"""
    searches = SavedSearch.objects.filter(user=request.user)

    context = {
        'searches': searches,
    }
    return render(request, 'alerts/saved_search_list.html', context)


@login_required
def saved_search_create(request):
    """Save current search"""
    if request.method == 'POST':
        form = SavedSearchForm(request.POST)
        if form.is_valid():
            search = form.save(commit=False)
            search.user = request.user
            search.save()
            messages.success(request, 'Search saved!')
            return redirect('alerts:saved_search_list')
    else:
        # Pre-populate from query params
        initial = {
            'query': request.GET.get('q', ''),
            'min_price': request.GET.get('min_price'),
            'max_price': request.GET.get('max_price'),
            'condition': request.GET.get('condition'),
            'listing_type': request.GET.get('type'),
        }
        category_slug = request.GET.get('category')
        if category_slug:
            try:
                initial['category'] = Category.objects.get(slug=category_slug)
            except Category.DoesNotExist:
                pass

        form = SavedSearchForm(initial=initial)

    categories = Category.objects.filter(is_active=True)

    context = {
        'form': form,
        'categories': categories,
    }
    return render(request, 'alerts/saved_search_form.html', context)


@login_required
def saved_search_delete(request, pk):
    """Delete saved search"""
    search = get_object_or_404(SavedSearch, pk=pk, user=request.user)

    if request.method == 'POST':
        search.delete()
        messages.success(request, 'Saved search deleted.')
        return redirect('alerts:saved_search_list')

    context = {
        'search': search,
    }
    return render(request, 'alerts/saved_search_confirm_delete.html', context)
