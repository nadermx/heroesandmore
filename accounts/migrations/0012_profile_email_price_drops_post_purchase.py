from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_paypal_integration'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='email_price_drops',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='email_post_purchase',
            field=models.BooleanField(default=True),
        ),
    ]
