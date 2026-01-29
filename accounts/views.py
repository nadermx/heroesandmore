from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Sum
from django.http import Http404

from .models import Profile
from .forms import ProfileForm, UserForm
from marketplace.models import Listing, Order, Review
from social.models import Follow


def profile_view(request, username):
    user = get_object_or_404(User, username=username)
    profile = user.profile

    # Check privacy
    if not profile.is_public and request.user != user:
        raise Http404("This profile is private")

    # Get user's listings
    listings = Listing.objects.filter(seller=user, status='active').order_by('-created')[:8]

    # Get stats
    stats = {
        'listings_count': Listing.objects.filter(seller=user).count(),
        'sales_count': Order.objects.filter(seller=user, status='completed').count(),
        'followers_count': Follow.objects.filter(following=user).count(),
        'following_count': Follow.objects.filter(follower=user).count(),
    }

    # Check if current user follows this user
    is_following = False
    if request.user.is_authenticated and request.user != user:
        is_following = Follow.objects.filter(follower=request.user, following=user).exists()

    # Get recent reviews
    reviews = Review.objects.filter(seller=user).order_by('-created')[:5]

    context = {
        'profile_user': user,
        'profile': profile,
        'listings': listings,
        'stats': stats,
        'is_following': is_following,
        'reviews': reviews,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def settings_view(request):
    profile = request.user.profile

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated.')
            return redirect('accounts:settings')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'accounts/settings.html', context)


@login_required
def dashboard_view(request):
    user = request.user

    # Get recent orders (as buyer)
    recent_purchases = Order.objects.filter(buyer=user).order_by('-created')[:5]

    # Get recent sales (as seller)
    recent_sales = Order.objects.filter(seller=user).order_by('-created')[:5]

    # Get active listings
    active_listings = Listing.objects.filter(seller=user, status='active').count()

    # Get stats
    stats = {
        'active_listings': active_listings,
        'total_sales': Order.objects.filter(seller=user, status='completed').count(),
        'total_purchases': Order.objects.filter(buyer=user, status='completed').count(),
        'pending_orders': Order.objects.filter(seller=user, status='pending').count(),
    }

    context = {
        'recent_purchases': recent_purchases,
        'recent_sales': recent_sales,
        'stats': stats,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def seller_dashboard(request):
    user = request.user

    # Get seller stats
    listings = Listing.objects.filter(seller=user)
    orders = Order.objects.filter(seller=user)

    stats = {
        'active_listings': listings.filter(status='active').count(),
        'draft_listings': listings.filter(status='draft').count(),
        'sold_listings': listings.filter(status='sold').count(),
        'total_revenue': orders.filter(status='completed').aggregate(Sum('amount'))['amount__sum'] or 0,
        'pending_orders': orders.filter(status='pending').count(),
        'completed_orders': orders.filter(status='completed').count(),
    }

    # Recent orders needing attention
    pending_orders = orders.filter(status='pending').order_by('-created')[:10]

    # Recent reviews
    reviews = Review.objects.filter(seller=user).order_by('-created')[:5]

    context = {
        'stats': stats,
        'pending_orders': pending_orders,
        'reviews': reviews,
        'profile': user.profile,
    }
    return render(request, 'accounts/seller_dashboard.html', context)
