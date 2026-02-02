# Generated manually for internal subscription billing

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0004_stripeevent_order_paid_at_order_refund_amount_and_more'),  # For PaymentMethod FK
        ('seller_tools', '0002_sellersubscription_cancel_at_period_end_and_more'),
    ]

    operations = [
        # Add new internal billing fields to SellerSubscription
        migrations.AddField(
            model_name='sellersubscription',
            name='default_payment_method',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='subscriptions',
                to='marketplace.paymentmethod',
            ),
        ),
        migrations.AddField(
            model_name='sellersubscription',
            name='last_billed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sellersubscription',
            name='last_payment_intent_id',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='sellersubscription',
            name='failed_payment_attempts',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='sellersubscription',
            name='next_retry_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sellersubscription',
            name='grace_period_end',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Remove deprecated stripe_subscription_id and stripe_price_id
        # Note: Keeping stripe_customer_id for now as it may be in use
        # These can be removed in a future migration after data migration
        migrations.RemoveField(
            model_name='sellersubscription',
            name='stripe_subscription_id',
        ),
        migrations.RemoveField(
            model_name='sellersubscription',
            name='stripe_price_id',
        ),
        # Create SubscriptionBillingHistory model
        migrations.CreateModel(
            name='SubscriptionBillingHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transaction_type', models.CharField(
                    choices=[
                        ('charge', 'Charge'),
                        ('refund', 'Refund'),
                        ('proration_credit', 'Proration Credit'),
                        ('proration_charge', 'Proration Charge'),
                    ],
                    max_length=20,
                )),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('tier', models.CharField(max_length=20)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('succeeded', 'Succeeded'),
                        ('failed', 'Failed'),
                        ('refunded', 'Refunded'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('stripe_payment_intent_id', models.CharField(blank=True, max_length=100)),
                ('period_start', models.DateTimeField()),
                ('period_end', models.DateTimeField()),
                ('failure_reason', models.TextField(blank=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('subscription', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='billing_history',
                    to='seller_tools.sellersubscription',
                )),
            ],
            options={
                'verbose_name': 'Subscription Billing History',
                'verbose_name_plural': 'Subscription Billing History',
                'ordering': ['-created'],
            },
        ),
    ]
