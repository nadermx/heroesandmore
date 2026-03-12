from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0018_order_stock_reserved'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='previous_price',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Stored automatically when price is lowered, for price drop notifications',
                max_digits=10,
                null=True,
            ),
        ),
    ]
