from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0005_add_autobid_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='listing',
            name='image1',
            field=models.ImageField(blank=True, null=True, upload_to='listings/'),
        ),
    ]
