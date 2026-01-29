from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.db.models import Q, F
from django.core.paginator import Paginator
from django.utils import timezone
from django.conf import settings
from decimal import Decimal

from .models import Listing, Bid, Offer, Order, Review, SavedListing
from .forms import ListingForm, OfferForm, ReviewForm, ShippingForm
from items.models import Category


def listing_list(request):
    """Browse all active listings"""
    listings = Listing.objects.filter(status='active').select_related('seller', 'category')

    # Filters
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        listings = listings.filter(category=category)

    condition = request.GET.get('condition')
    if condition:
        listings = listings.filter(condition=condition)

    listing_type = request.GET.get('type')
    if listing_type:
        listings = listings.filter(listing_type=listing_type)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        listings = listings.filter(price__gte=min_price)
    if max_price:
        listings = listings.filter(price__lte=max_price)

    # Sort
    sort = request.GET.get('sort', '-created')
    sort_options = {
        'price_low': 'price',
        'price_high': '-price',
        'newest': '-created',
        'ending': 'auction_end',
    }
    listings = listings.order_by(sort_options.get(sort, '-created'))

    paginator = Paginator(listings, 24)
    page = request.GET.get('page')
    listings = paginator.get_page(page)

    categories = Category.objects.filter(parent=None, is_active=True)

    context = {
        'listings': listings,
        'categories': categories,
    }
    return render(request, 'marketplace/listing_list.html', context)


def listing_detail(request, pk):
    """Individual listing page"""
    listing = get_object_or_404(Listing.objects.select_related('seller', 'category'), pk=pk)

    # Increment view count (simple approach)
    Listing.objects.filter(pk=pk).update(views=F('views') + 1)

    # Check if user has saved this listing
    is_saved = False
    if request.user.is_authenticated:
        is_saved = SavedListing.objects.filter(user=request.user, listing=listing).exists()

    # Get bids if auction
    bids = None
    if listing.listing_type == 'auction':
        bids = listing.bids.select_related('bidder').order_by('-amount')[:10]

    # Offer form
    offer_form = OfferForm() if listing.allow_offers else None

    # Related listings
    related = Listing.objects.filter(
        category=listing.category,
        status='active'
    ).exclude(pk=pk).order_by('-created')[:4]

    # Seller's other listings
    seller_listings = Listing.objects.filter(
        seller=listing.seller,
        status='active'
    ).exclude(pk=pk).order_by('-created')[:4]

    context = {
        'listing': listing,
        'is_saved': is_saved,
        'bids': bids,
        'offer_form': offer_form,
        'related': related,
        'seller_listings': seller_listings,
    }
    return render(request, 'marketplace/listing_detail.html', context)


@login_required
def listing_create(request):
    """Create new listing"""
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.seller = request.user
            if form.cleaned_data.get('auction_end'):
                listing.auction_end = form.cleaned_data['auction_end']
            listing.save()
            messages.success(request, 'Listing created! Review and publish when ready.')
            return redirect('marketplace:listing_edit', pk=listing.pk)
    else:
        form = ListingForm()

    categories = Category.objects.filter(is_active=True).order_by('name')

    context = {
        'form': form,
        'categories': categories,
    }
    return render(request, 'marketplace/listing_form.html', context)


@login_required
def listing_edit(request, pk):
    """Edit listing"""
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if listing.status not in ['draft', 'active']:
        messages.error(request, "This listing can no longer be edited.")
        return redirect('marketplace:listing_detail', pk=pk)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            listing = form.save(commit=False)
            if form.cleaned_data.get('auction_end'):
                listing.auction_end = form.cleaned_data['auction_end']
            listing.save()
            messages.success(request, 'Listing updated.')
            return redirect('marketplace:listing_detail', pk=pk)
    else:
        form = ListingForm(instance=listing)

    categories = Category.objects.filter(is_active=True).order_by('name')

    context = {
        'form': form,
        'listing': listing,
        'categories': categories,
    }
    return render(request, 'marketplace/listing_form.html', context)


@login_required
def listing_publish(request, pk):
    """Publish draft listing"""
    listing = get_object_or_404(Listing, pk=pk, seller=request.user, status='draft')

    # Verify seller has Stripe account set up
    if not request.user.profile.stripe_account_complete:
        messages.warning(request, 'Please complete your seller setup before publishing listings.')
        return redirect('marketplace:seller_setup')

    listing.status = 'active'
    listing.save()
    messages.success(request, 'Your listing is now live!')
    return redirect('marketplace:listing_detail', pk=pk)


@login_required
def listing_cancel(request, pk):
    """Cancel listing"""
    listing = get_object_or_404(Listing, pk=pk, seller=request.user)

    if listing.status not in ['draft', 'active']:
        messages.error(request, "This listing cannot be cancelled.")
        return redirect('marketplace:listing_detail', pk=pk)

    # Check for pending orders
    if listing.orders.filter(status__in=['pending', 'paid']).exists():
        messages.error(request, "Cannot cancel listing with pending orders.")
        return redirect('marketplace:listing_detail', pk=pk)

    listing.status = 'cancelled'
    listing.save()
    messages.success(request, 'Listing cancelled.')
    return redirect('accounts:seller_dashboard')


@login_required
def place_bid(request, pk):
    """Place bid on auction"""
    listing = get_object_or_404(Listing, pk=pk, status='active', listing_type='auction')

    if request.user == listing.seller:
        messages.error(request, "You cannot bid on your own listing.")
        return redirect('marketplace:listing_detail', pk=pk)

    if listing.is_auction_ended():
        messages.error(request, "This auction has ended.")
        return redirect('marketplace:listing_detail', pk=pk)

    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount', 0))
        except:
            messages.error(request, "Invalid bid amount.")
            return redirect('marketplace:listing_detail', pk=pk)

        current_price = listing.get_current_price()
        min_bid = current_price + Decimal('1.00')

        if amount < min_bid:
            messages.error(request, f"Minimum bid is ${min_bid:.2f}")
            return redirect('marketplace:listing_detail', pk=pk)

        Bid.objects.create(listing=listing, bidder=request.user, amount=amount)
        messages.success(request, f'You are now the high bidder at ${amount:.2f}!')

    return redirect('marketplace:listing_detail', pk=pk)


@login_required
def make_offer(request, pk):
    """Make offer on listing"""
    listing = get_object_or_404(Listing, pk=pk, status='active', allow_offers=True)

    if request.user == listing.seller:
        messages.error(request, "You cannot make offers on your own listing.")
        return redirect('marketplace:listing_detail', pk=pk)

    if request.method == 'POST':
        form = OfferForm(request.POST)
        if form.is_valid():
            offer = form.save(commit=False)
            offer.listing = listing
            offer.buyer = request.user
            offer.save()
            messages.success(request, 'Your offer has been sent to the seller.')

    return redirect('marketplace:listing_detail', pk=pk)


@login_required
def respond_offer(request, pk):
    """Seller responds to offer"""
    offer = get_object_or_404(Offer, pk=pk, listing__seller=request.user, status='pending')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'accept':
            offer.status = 'accepted'
            offer.save()
            # Create order
            listing = offer.listing
            platform_fee = offer.amount * Decimal(str(settings.PLATFORM_FEE_PERCENT)) / 100
            Order.objects.create(
                listing=listing,
                buyer=offer.buyer,
                seller=request.user,
                item_price=offer.amount,
                shipping_price=listing.shipping_price,
                amount=offer.amount + listing.shipping_price,
                platform_fee=platform_fee,
                seller_payout=offer.amount - platform_fee,
                shipping_address='',  # Will be collected at checkout
            )
            listing.status = 'sold'
            listing.save()
            messages.success(request, 'Offer accepted! Waiting for buyer payment.')

        elif action == 'decline':
            offer.status = 'declined'
            offer.save()
            messages.success(request, 'Offer declined.')

        elif action == 'counter':
            counter = request.POST.get('counter_amount')
            if counter:
                offer.status = 'countered'
                offer.counter_amount = Decimal(counter)
                offer.save()
                messages.success(request, 'Counter offer sent.')

    return redirect('accounts:seller_dashboard')


@login_required
def checkout(request, pk):
    """Checkout page for buying"""
    listing = get_object_or_404(Listing, pk=pk, status='active')

    if request.user == listing.seller:
        raise Http404("Cannot buy your own listing")

    platform_fee = listing.price * Decimal(str(settings.PLATFORM_FEE_PERCENT)) / 100
    total = listing.price + listing.shipping_price

    if request.method == 'POST':
        shipping_address = request.POST.get('shipping_address', '').strip()
        if not shipping_address:
            messages.error(request, 'Please enter a shipping address.')
        else:
            # Create order
            order = Order.objects.create(
                listing=listing,
                buyer=request.user,
                seller=listing.seller,
                item_price=listing.price,
                shipping_price=listing.shipping_price,
                amount=total,
                platform_fee=platform_fee,
                seller_payout=listing.price - platform_fee,
                shipping_address=shipping_address,
            )
            # Mark listing as sold
            listing.status = 'sold'
            listing.save()
            # Redirect to payment
            return redirect('marketplace:payment', pk=order.pk)

    context = {
        'listing': listing,
        'platform_fee': platform_fee,
        'total': total,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    }
    return render(request, 'marketplace/checkout.html', context)


@login_required
def payment(request, pk):
    """Handle Stripe payment"""
    order = get_object_or_404(Order, pk=pk, buyer=request.user, status='pending')

    context = {
        'order': order,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
    }
    return render(request, 'marketplace/payment.html', context)


@login_required
def order_detail(request, pk):
    """Order detail page"""
    order = get_object_or_404(Order, pk=pk)

    # Only buyer or seller can view
    if request.user not in [order.buyer, order.seller]:
        raise Http404()

    is_seller = request.user == order.seller
    shipping_form = ShippingForm() if is_seller and order.status == 'paid' else None
    review_form = None

    # Show review form if buyer and order completed
    if request.user == order.buyer and order.status == 'completed':
        if not hasattr(order, 'review'):
            review_form = ReviewForm()

    context = {
        'order': order,
        'is_seller': is_seller,
        'shipping_form': shipping_form,
        'review_form': review_form,
    }
    return render(request, 'marketplace/order_detail.html', context)


@login_required
def order_ship(request, pk):
    """Mark order as shipped"""
    order = get_object_or_404(Order, pk=pk, seller=request.user, status='paid')

    if request.method == 'POST':
        form = ShippingForm(request.POST)
        if form.is_valid():
            order.tracking_number = form.cleaned_data['tracking_number']
            order.tracking_carrier = form.cleaned_data['tracking_carrier']
            order.status = 'shipped'
            order.shipped_at = timezone.now()
            order.save()
            messages.success(request, 'Order marked as shipped. Buyer has been notified.')

    return redirect('marketplace:order_detail', pk=pk)


@login_required
def order_received(request, pk):
    """Buyer confirms receipt"""
    order = get_object_or_404(Order, pk=pk, buyer=request.user, status='shipped')

    order.status = 'completed'
    order.delivered_at = timezone.now()
    order.save()
    messages.success(request, 'Order marked as received. Please leave a review!')

    return redirect('marketplace:order_detail', pk=pk)


@login_required
def leave_review(request, pk):
    """Leave review for order"""
    order = get_object_or_404(Order, pk=pk, buyer=request.user, status='completed')

    if hasattr(order, 'review'):
        messages.error(request, 'You have already reviewed this order.')
        return redirect('marketplace:order_detail', pk=pk)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.order = order
            review.reviewer = request.user
            review.seller = order.seller
            review.save()
            messages.success(request, 'Thank you for your review!')

    return redirect('marketplace:order_detail', pk=pk)


@login_required
def save_listing(request, pk):
    """Save/unsave listing"""
    listing = get_object_or_404(Listing, pk=pk)

    saved, created = SavedListing.objects.get_or_create(user=request.user, listing=listing)

    if not created:
        saved.delete()
        is_saved = False
    else:
        is_saved = True

    if request.headers.get('HX-Request'):
        return JsonResponse({'is_saved': is_saved})

    return redirect('marketplace:listing_detail', pk=pk)


@login_required
def saved_listings(request):
    """User's saved listings"""
    saved = SavedListing.objects.filter(user=request.user).select_related(
        'listing__seller', 'listing__category'
    ).order_by('-created')

    paginator = Paginator(saved, 24)
    page = request.GET.get('page')
    saved = paginator.get_page(page)

    context = {
        'saved': saved,
    }
    return render(request, 'marketplace/saved_listings.html', context)


@login_required
def my_listings(request):
    """User's own listings"""
    listings = Listing.objects.filter(seller=request.user).order_by('-created')

    status = request.GET.get('status')
    if status:
        listings = listings.filter(status=status)

    paginator = Paginator(listings, 24)
    page = request.GET.get('page')
    listings = paginator.get_page(page)

    context = {
        'listings': listings,
    }
    return render(request, 'marketplace/my_listings.html', context)


@login_required
def my_orders(request):
    """User's purchase history"""
    orders = Order.objects.filter(buyer=request.user).select_related('listing', 'seller')

    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)

    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders = paginator.get_page(page)

    context = {
        'orders': orders,
    }
    return render(request, 'marketplace/my_orders.html', context)


@login_required
def seller_setup(request):
    """Stripe Connect onboarding"""
    # Placeholder - will implement Stripe Connect
    context = {
        'profile': request.user.profile,
    }
    return render(request, 'marketplace/seller_setup.html', context)
