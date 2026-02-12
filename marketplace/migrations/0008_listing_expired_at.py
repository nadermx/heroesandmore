from django.db import migrations, models


def backfill_expired_at(apps, schema_editor):
    """Set expired_at = updated for existing expired listings."""
    Listing = apps.get_model('marketplace', 'Listing')
    Listing.objects.filter(status='expired', expired_at__isnull=True).update(
        expired_at=models.F('updated')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0007_add_quantity_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='expired_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_expired_at, migrations.RunPython.noop),
    ]
