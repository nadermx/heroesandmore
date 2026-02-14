from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Create or update the platform user account (heroesandmore)'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username='heroesandmore',
            defaults={
                'email': 'noreply@heroesandmore.com',
                'first_name': 'HeroesAndMore',
                'last_name': 'Official',
                'is_active': True,
            }
        )

        if created:
            user.set_unusable_password()
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created platform user: {user.username}'))
        else:
            self.stdout.write(f'Platform user already exists: {user.username}')

        profile = user.profile
        if not profile.is_platform_account:
            profile.is_platform_account = True
            profile.is_seller_verified = True
            profile.save(update_fields=['is_platform_account', 'is_seller_verified'])
            self.stdout.write(self.style.SUCCESS('Set is_platform_account=True, is_seller_verified=True'))
        else:
            self.stdout.write('Profile already marked as platform account')

        self.stdout.write(self.style.SUCCESS('Done.'))
