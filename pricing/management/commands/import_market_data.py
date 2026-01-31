"""
Management command to import market data from external sources.

Usage:
    # Import from all sources
    python manage.py import_market_data

    # Import from specific source
    python manage.py import_market_data --source ebay
    python manage.py import_market_data --source heritage
    python manage.py import_market_data --source gocollect

    # Import for specific category
    python manage.py import_market_data --category trading-cards

    # Limit number of items
    python manage.py import_market_data --limit 50

    # Dry run (don't save)
    python manage.py import_market_data --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import market data from eBay, Heritage Auctions, and GoCollect'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            choices=['all', 'ebay', 'heritage', 'gocollect'],
            default='all',
            help='Data source to import from (default: all)'
        )
        parser.add_argument(
            '--category',
            type=str,
            default=None,
            help='Category slug to filter items (e.g., trading-cards, comics)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Maximum number of items to process (default: 100)'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Days back to search for Heritage (default: 7)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without saving'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        source = options['source']
        category = options['category']
        limit = options['limit']
        days = options['days']
        dry_run = options['dry_run']
        verbose = options['verbose']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No data will be saved'))

        self.stdout.write(f'Starting market data import at {timezone.now()}')
        self.stdout.write(f'Source: {source}, Category: {category or "all"}, Limit: {limit}')
        self.stdout.write('')

        total_imported = 0

        try:
            if source in ('all', 'ebay'):
                count = self.import_ebay(category, limit, dry_run, verbose)
                total_imported += count
                self.stdout.write(self.style.SUCCESS(f'eBay: {count} sales imported'))

            if source in ('all', 'heritage'):
                # Sports
                count = self.import_heritage('sports', days, dry_run, verbose)
                total_imported += count
                self.stdout.write(self.style.SUCCESS(f'Heritage (sports): {count} sales imported'))

                # Comics
                count = self.import_heritage('comics', days, dry_run, verbose)
                total_imported += count
                self.stdout.write(self.style.SUCCESS(f'Heritage (comics): {count} sales imported'))

            if source in ('all', 'gocollect'):
                count = self.import_gocollect(limit, dry_run, verbose)
                total_imported += count
                self.stdout.write(self.style.SUCCESS(f'GoCollect: {count} sales imported'))

        except Exception as e:
            raise CommandError(f'Import failed: {e}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Total imported: {total_imported} sales'))
        self.stdout.write(f'Completed at {timezone.now()}')

    def import_ebay(self, category, limit, dry_run, verbose):
        """Import from eBay"""
        from pricing.models import PriceGuideItem
        from pricing.services.market_data import EbayMarketData, MarketDataImporter

        self.stdout.write('Importing from eBay...')

        ebay = EbayMarketData()
        importer = MarketDataImporter()

        items = PriceGuideItem.objects.all()
        if category:
            items = items.filter(category__slug=category)
        items = items.order_by('-total_sales')[:limit]

        count = 0
        for item in items:
            search_query = importer._build_search_query(item)

            if verbose:
                self.stdout.write(f'  Searching: {search_query}')

            results = ebay.search_sold_items(search_query, limit=20)

            for result in results:
                if verbose:
                    self.stdout.write(f'    Found: {result["title"][:60]}... ${result["price"]}')

                if not dry_run:
                    if importer._record_sale(item, result):
                        count += 1

        return count

    def import_heritage(self, heritage_category, days, dry_run, verbose):
        """Import from Heritage Auctions"""
        from pricing.models import PriceGuideItem
        from pricing.services.market_data import HeritageAuctionsData, MarketDataImporter

        self.stdout.write(f'Importing from Heritage Auctions ({heritage_category})...')

        heritage = HeritageAuctionsData()
        importer = MarketDataImporter()

        results = heritage.get_recent_sales(category=heritage_category, days_back=days, limit=200)

        if verbose:
            self.stdout.write(f'  Found {len(results)} recent sales')

        count = 0
        for result in results:
            if verbose:
                self.stdout.write(f'    {result["title"][:60]}... ${result["price"]}')

            # Try to match to existing items
            items = PriceGuideItem.objects.all()[:500]
            for item in items:
                if importer._is_match(item, result.get('title', '')):
                    if not dry_run:
                        if importer._record_sale(item, result):
                            count += 1
                    break

        return count

    def import_gocollect(self, limit, dry_run, verbose):
        """Import from GoCollect"""
        from pricing.models import PriceGuideItem
        from pricing.services.market_data import GoCollectData, MarketDataImporter

        self.stdout.write('Importing from GoCollect...')

        gocollect = GoCollectData()
        importer = MarketDataImporter()

        # Only comic items
        items = PriceGuideItem.objects.filter(
            category__slug__icontains='comic'
        ).order_by('-total_sales')[:limit]

        if verbose:
            self.stdout.write(f'  Found {items.count()} comic items to search')

        count = 0
        for item in items:
            search_query = importer._build_search_query(item)

            if verbose:
                self.stdout.write(f'  Searching: {search_query}')

            results = gocollect.search_comics(search_query, limit=10)

            for result in results:
                sales = gocollect.get_comic_sales(result.get('url', ''), limit=10)

                for sale in sales:
                    if verbose:
                        self.stdout.write(f'    Sale: ${sale.get("price", 0)} ({sale.get("grading_company", "raw")} {sale.get("grade", "")})')

                    sale['title'] = result.get('title', item.name)
                    if not dry_run:
                        if importer._record_sale(item, sale):
                            count += 1

        return count
