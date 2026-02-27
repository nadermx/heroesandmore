from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.views.decorators.http import require_POST
from urllib.parse import parse_qs

from .models import Wishlist, WishlistItem, Alert, SavedSearch, NewsletterSubscriber
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
def unread_count(request):
    """AJAX: Return unread alert count as JSON."""
    count = Alert.objects.filter(user=request.user, read=False).count()
    return JsonResponse({'count': count})


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
        if request.headers.get('HX-Request'):
            raw = request.POST.get('query', '')
            parsed = parse_qs(raw, keep_blank_values=True)

            query = parsed.get('q', [''])[0]
            category_slug = parsed.get('category', [''])[0]
            min_price = parsed.get('min_price', [''])[0] or None
            max_price = parsed.get('max_price', [''])[0] or None
            condition = parsed.get('condition', [''])[0]
            listing_type = parsed.get('type', [''])[0]
            graded_only = parsed.get('graded', [''])

            category = None
            if category_slug:
                category = Category.objects.filter(slug=category_slug).first()

            name = request.POST.get('name')
            if not name:
                if query:
                    name = f"Search: {query[:60]}"
                elif category:
                    name = f"Category: {category.name}"
                else:
                    name = f"Saved search {timezone.now().strftime('%Y-%m-%d')}"

            saved = SavedSearch.objects.create(
                user=request.user,
                name=name,
                query=query,
                category=category,
                min_price=min_price or None,
                max_price=max_price or None,
                condition=condition,
                listing_type=listing_type,
                filters={'graded_only': bool(graded_only and graded_only[0])}
            )
            return JsonResponse({'success': True, 'id': saved.id})

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


# Newsletter
def newsletter_subscribe(request):
    """Subscribe to the newsletter. Accepts POST (standard or HTMX)."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        is_htmx = request.headers.get('HX-Request')

        if not email:
            if is_htmx:
                return HttpResponse('<span class="text-danger">Please enter an email address.</span>')
            messages.error(request, 'Please enter an email address.')
            return redirect('home')

        # Check if already subscribed
        existing = NewsletterSubscriber.objects.filter(email=email).first()
        if existing:
            if existing.is_verified and existing.is_active:
                if is_htmx:
                    return HttpResponse('<span class="text-info">You are already subscribed!</span>')
                messages.info(request, 'You are already subscribed!')
                return redirect('home')
            elif not existing.is_verified:
                # Resend verification
                _send_verification_email(existing)
                if is_htmx:
                    return HttpResponse('<span class="text-success">Verification email resent. Check your inbox!</span>')
                messages.info(request, 'Verification email resent. Check your inbox!')
                return redirect('home')
            else:
                # Reactivate
                existing.is_active = True
                existing.unsubscribed_at = None
                existing.save(update_fields=['is_active', 'unsubscribed_at'])
                if is_htmx:
                    return HttpResponse('<span class="text-success">Welcome back! Your subscription has been reactivated.</span>')
                messages.success(request, 'Welcome back! Your subscription has been reactivated.')
                return redirect('home')

        # Create new subscriber
        subscriber = NewsletterSubscriber(email=email)
        if request.user.is_authenticated:
            subscriber.user = request.user
        subscriber.save()

        # Save category preferences if provided
        cat_ids = request.POST.getlist('categories')
        if cat_ids:
            subscriber.categories.set(Category.objects.filter(id__in=cat_ids))

        # Send verification email
        _send_verification_email(subscriber)

        if is_htmx:
            return HttpResponse('<span class="text-success">Check your email to verify your subscription!</span>')
        messages.success(request, 'Check your email to verify your subscription!')
        return redirect('home')

    # GET — show standalone subscribe page
    categories = Category.objects.filter(parent=None, is_active=True).order_by('order')
    return render(request, 'alerts/newsletter_subscribe.html', {'categories': categories})


def newsletter_verify(request, token):
    """Verify newsletter email address."""
    subscriber = get_object_or_404(NewsletterSubscriber, verification_token=token)

    if subscriber.is_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('newsletter_preferences', token=subscriber.unsubscribe_token)

    subscriber.is_verified = True
    subscriber.verified_at = timezone.now()
    subscriber.save(update_fields=['is_verified', 'verified_at'])

    # Send welcome email
    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'subscriber': subscriber, 'site_url': site_url}
    html_content = render_to_string('alerts/emails/newsletter_welcome.html', context)
    try:
        send_mail(
            subject='Welcome to the HeroesAndMore Newsletter!',
            message='You are now subscribed to the HeroesAndMore newsletter.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscriber.email],
            html_message=html_content,
            fail_silently=True,
        )
    except Exception:
        pass

    messages.success(request, 'Email verified! You can manage your preferences below.')
    return redirect('newsletter_preferences', token=subscriber.unsubscribe_token)


def newsletter_preferences(request, token):
    """Manage newsletter category preferences and frequency."""
    subscriber = get_object_or_404(NewsletterSubscriber, unsubscribe_token=token, is_active=True)

    if request.method == 'POST':
        # Update frequency
        frequency = request.POST.get('frequency', 'weekly')
        if frequency in dict(NewsletterSubscriber.FREQUENCY_CHOICES):
            subscriber.frequency = frequency
            subscriber.save(update_fields=['frequency'])

        # Update categories
        cat_ids = request.POST.getlist('categories')
        if cat_ids:
            subscriber.categories.set(Category.objects.filter(id__in=cat_ids))
        else:
            subscriber.categories.clear()

        messages.success(request, 'Preferences updated!')
        return redirect('newsletter_preferences', token=token)

    categories = Category.objects.filter(parent=None, is_active=True).order_by('order')
    selected_cat_ids = set(subscriber.categories.values_list('id', flat=True))

    return render(request, 'alerts/newsletter_preferences.html', {
        'subscriber': subscriber,
        'categories': categories,
        'selected_cat_ids': selected_cat_ids,
    })


def newsletter_unsubscribe(request, token):
    """One-click unsubscribe."""
    subscriber = get_object_or_404(NewsletterSubscriber, unsubscribe_token=token)

    if not subscriber.is_active:
        messages.info(request, 'You are already unsubscribed.')
        return render(request, 'alerts/newsletter_unsubscribed.html')

    subscriber.is_active = False
    subscriber.unsubscribed_at = timezone.now()
    subscriber.save(update_fields=['is_active', 'unsubscribed_at'])

    messages.success(request, 'You have been unsubscribed from the newsletter.')
    return render(request, 'alerts/newsletter_unsubscribed.html')


def _send_verification_email(subscriber):
    """Send newsletter verification email."""
    site_url = getattr(settings, 'SITE_URL', 'https://heroesandmore.com')
    context = {'subscriber': subscriber, 'site_url': site_url}
    html_content = render_to_string('alerts/emails/newsletter_verify.html', context)
    try:
        send_mail(
            subject='Verify your HeroesAndMore newsletter subscription',
            message=f'Verify your email: {site_url}/newsletter/verify/{subscriber.verification_token}/',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscriber.email],
            html_message=html_content,
            fail_silently=True,
        )
    except Exception:
        pass
