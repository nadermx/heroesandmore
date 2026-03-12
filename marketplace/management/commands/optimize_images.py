"""
Management command to optimize existing listing images.
Processes all listings that have non-WebP images, creating optimized
display versions, thumbnails, and preserving originals.

Usage:
    python manage.py optimize_images              # Process all unoptimized
    python manage.py optimize_images --batch=50   # Process 50 at a time
    python manage.py optimize_images --listing=123 # Process specific listing
"""
from django.core.management.base import BaseCommand

from marketplace.models import Listing
from marketplace.services.image_service import process_listing_images


class Command(BaseCommand):
    help = 'Optimize listing images (resize, WebP, thumbnails)'

    def add_arguments(self, parser):
        parser.add_argument('--batch', type=int, default=0, help='Process N listings then stop')
        parser.add_argument('--listing', type=int, default=0, help='Process a specific listing ID')

    def handle(self, *args, **options):
        if options['listing']:
            try:
                listing = Listing.objects.get(pk=options['listing'])
                self.stdout.write(f'Processing listing {listing.pk}: {listing.title}')
                process_listing_images(listing)
                self.stdout.write(self.style.SUCCESS('Done'))
            except Listing.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Listing {options["listing"]} not found'))
            return

        # Find listings with non-WebP images
        from django.db.models import Q
        q = Q()
        for field in ['image1', 'image2', 'image3', 'image4', 'image5']:
            q |= Q(**{f'{field}__isnull': False}) & ~Q(**{f'{field}': ''}) & ~Q(**{f'{field}__endswith': '.webp'})

        listings = Listing.objects.filter(q).order_by('-created')
        total = listings.count()
        self.stdout.write(f'Found {total} listings with unoptimized images')

        if options['batch'] > 0:
            listings = listings[:options['batch']]

        processed = 0
        for listing in listings:
            try:
                self.stdout.write(f'  [{processed + 1}/{total}] Listing {listing.pk}: {listing.title[:50]}')
                process_listing_images(listing)
                processed += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'    Error: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Processed {processed} listings'))
