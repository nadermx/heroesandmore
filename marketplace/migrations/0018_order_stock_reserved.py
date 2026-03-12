from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0017_paypal_integration'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='stock_reserved',
            field=models.BooleanField(default=False),
        ),
    ]
