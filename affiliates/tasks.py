import logging
from datetime import timedelta
from decimal import Decimal
from celery import shared_task
from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger('affiliates')


@shared_task
def create_affiliate_commission(order_id):
    from marketplace.models import Order
    from affiliates.models import Affiliate, Referral, AffiliateCommission

    try:
        order = Order.objects.select_related('buyer', 'listing__seller').get(id=order_id)
    except Order.DoesNotExist:
        return

    # Skip guest orders (no user = no attribution)
    if not order.buyer:
        return

    # Skip if commission already exists
    if AffiliateCommission.objects.filter(order=order).exists():
        return

    # Check if buyer was referred
    try:
        referral = Referral.objects.select_related('affiliate').get(referred_user=order.buyer)
    except Referral.DoesNotExist:
        return

    affiliate = referral.affiliate
    if not affiliate.is_active:
        return

    # Skip self-dealing (affiliate is the seller)
    if order.seller == affiliate.user:
        return

    item_price = order.item_price if hasattr(order, 'item_price') and order.item_price else order.amount
    commission_amount = (item_price * Affiliate.COMMISSION_RATE).quantize(Decimal('0.01'))

    if commission_amount <= 0:
        return

    with transaction.atomic():
        AffiliateCommission.objects.create(
            affiliate=affiliate,
            order=order,
            referral=referral,
            order_item_price=item_price,
            commission_rate=Affiliate.COMMISSION_RATE,
            commission_amount=commission_amount,
            status='pending',
        )
        Affiliate.objects.filter(pk=affiliate.pk).update(
            pending_balance=F('pending_balance') + commission_amount,
            total_earnings=F('total_earnings') + commission_amount,
        )

    logger.info(f"Affiliate commission ${commission_amount} created for order {order_id}, affiliate {affiliate.user.username}")


@shared_task
def reverse_affiliate_commission(order_id):
    from affiliates.models import AffiliateCommission, Affiliate

    try:
        commission = AffiliateCommission.objects.select_related('affiliate').get(
            order_id=order_id,
            status__in=['pending', 'approved'],
        )
    except AffiliateCommission.DoesNotExist:
        return

    with transaction.atomic():
        commission.status = 'reversed'
        commission.save(update_fields=['status'])

        Affiliate.objects.filter(pk=commission.affiliate_id).update(
            pending_balance=F('pending_balance') - commission.commission_amount,
            total_earnings=F('total_earnings') - commission.commission_amount,
        )

    logger.info(f"Affiliate commission reversed for order {order_id}")


@shared_task
def approve_pending_commissions():
    from affiliates.models import AffiliateCommission

    cutoff = timezone.now() - timedelta(days=30)
    updated = AffiliateCommission.objects.filter(
        status='pending',
        created__lte=cutoff,
    ).update(status='approved')

    if updated:
        logger.info(f"Approved {updated} affiliate commissions")


@shared_task
def process_affiliate_payouts():
    from affiliates.models import Affiliate, AffiliateCommission, AffiliatePayout
    from marketplace.services.paypal_service import PayPalService

    today = timezone.now().date()
    period_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    period_end = today.replace(day=1) - timedelta(days=1)

    affiliates = Affiliate.objects.filter(
        is_active=True,
        commissions__status='approved',
    ).distinct()

    for affiliate in affiliates:
        if not affiliate.paypal_email:
            logger.warning(f"Affiliate {affiliate.user.username} has no PayPal email, skipping payout")
            continue

        approved_commissions = AffiliateCommission.objects.filter(
            affiliate=affiliate,
            status='approved',
        )

        total = sum(c.commission_amount for c in approved_commissions)
        if total < Affiliate.MINIMUM_PAYOUT:
            logger.info(f"Affiliate {affiliate.user.username} balance ${total} below minimum ${Affiliate.MINIMUM_PAYOUT}")
            continue

        with transaction.atomic():
            payout = AffiliatePayout.objects.create(
                affiliate=affiliate,
                amount=total,
                paypal_email=affiliate.paypal_email,
                status='processing',
                period_start=period_start,
                period_end=period_end,
            )
            approved_commissions.update(status='paid', payout=payout)

        # Send PayPal payout
        try:
            result = PayPalService.send_payout(
                email=affiliate.paypal_email,
                amount=float(total),
                note=f"HeroesAndMore affiliate payout ({period_start} to {period_end})",
                sender_batch_id=f"aff_{payout.pk}_{today.isoformat()}",
            )
            payout.paypal_payout_batch_id = result.get('batch_header', {}).get('payout_batch_id', '')
            payout.status = 'completed'
            payout.save(update_fields=['paypal_payout_batch_id', 'status'])

            Affiliate.objects.filter(pk=affiliate.pk).update(
                pending_balance=F('pending_balance') - total,
                paid_balance=F('paid_balance') + total,
            )
            logger.info(f"Affiliate payout ${total} sent to {affiliate.user.username}")

        except Exception as e:
            payout.status = 'failed'
            payout.error_message = str(e)
            payout.save(update_fields=['status', 'error_message'])

            # Revert commission status back to approved
            AffiliateCommission.objects.filter(payout=payout).update(status='approved', payout=None)
            logger.error(f"Affiliate payout failed for {affiliate.user.username}: {e}")
