from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.contrib import messages

from affiliates.models import Affiliate, AffiliateCommission


@login_required
def join(request):
    if hasattr(request.user, 'affiliate'):
        return redirect('affiliates:dashboard')

    if request.method == 'POST':
        Affiliate.objects.create(user=request.user)
        messages.success(request, "Welcome to the affiliate program!")
        return redirect('affiliates:dashboard')

    return render(request, 'affiliates/join.html')


@login_required
def dashboard(request):
    try:
        affiliate = request.user.affiliate
    except Affiliate.DoesNotExist:
        return redirect('affiliates:join')

    recent_commissions = affiliate.commissions.select_related('order').order_by('-created')[:10]
    context = {
        'affiliate': affiliate,
        'recent_commissions': recent_commissions,
    }
    return render(request, 'affiliates/dashboard.html', context)


@login_required
def referrals(request):
    try:
        affiliate = request.user.affiliate
    except Affiliate.DoesNotExist:
        return redirect('affiliates:join')

    referral_list = affiliate.referrals.select_related('referred_user').order_by('-created')
    paginator = Paginator(referral_list, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'affiliates/referrals.html', {
        'affiliate': affiliate,
        'page_obj': page,
    })


@login_required
def commissions(request):
    try:
        affiliate = request.user.affiliate
    except Affiliate.DoesNotExist:
        return redirect('affiliates:join')

    commission_list = affiliate.commissions.select_related('order').order_by('-created')
    status = request.GET.get('status')
    if status in ('pending', 'approved', 'paid', 'reversed'):
        commission_list = commission_list.filter(status=status)

    paginator = Paginator(commission_list, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'affiliates/commissions.html', {
        'affiliate': affiliate,
        'page_obj': page,
        'current_status': status,
    })


@login_required
def payouts(request):
    try:
        affiliate = request.user.affiliate
    except Affiliate.DoesNotExist:
        return redirect('affiliates:join')

    payout_list = affiliate.payouts.order_by('-created')
    paginator = Paginator(payout_list, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'affiliates/payouts.html', {
        'affiliate': affiliate,
        'page_obj': page,
    })


@login_required
def payout_settings(request):
    try:
        affiliate = request.user.affiliate
    except Affiliate.DoesNotExist:
        return redirect('affiliates:join')

    if request.method == 'POST':
        paypal_email = request.POST.get('paypal_email', '').strip()
        if paypal_email:
            affiliate.paypal_email = paypal_email
            affiliate.save(update_fields=['paypal_email'])
            messages.success(request, "PayPal email updated.")
        else:
            messages.error(request, "Please enter a valid PayPal email.")
        return redirect('affiliates:settings')

    return render(request, 'affiliates/payout_settings.html', {
        'affiliate': affiliate,
    })
