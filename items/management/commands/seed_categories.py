from django.core.management.base import BaseCommand
from items.models import Category


class Command(BaseCommand):
    help = 'Seed initial categories'

    def handle(self, *args, **options):
        categories = [
            {
                'name': 'Trading Cards',
                'slug': 'trading-cards',
                'icon': 'bi-stack',
                'description': 'Sports cards, Pokemon, Magic: The Gathering, and more',
                'children': [
                    {'name': 'Sports Cards', 'slug': 'sports-cards'},
                    {'name': 'Pokemon', 'slug': 'pokemon'},
                    {'name': 'Magic: The Gathering', 'slug': 'mtg'},
                    {'name': 'Yu-Gi-Oh!', 'slug': 'yugioh'},
                    {'name': 'Other TCG', 'slug': 'other-tcg'},
                ]
            },
            {
                'name': 'Comics',
                'slug': 'comics',
                'icon': 'bi-book',
                'description': 'Comic books, graphic novels, and manga',
                'children': [
                    {'name': 'Marvel', 'slug': 'marvel'},
                    {'name': 'DC', 'slug': 'dc'},
                    {'name': 'Image', 'slug': 'image'},
                    {'name': 'Manga', 'slug': 'manga'},
                    {'name': 'Independent', 'slug': 'indie-comics'},
                ]
            },
            {
                'name': 'Action Figures',
                'slug': 'action-figures',
                'icon': 'bi-person-standing',
                'description': 'Action figures, statues, and articulated collectibles',
                'children': [
                    {'name': 'Marvel Legends', 'slug': 'marvel-legends'},
                    {'name': 'Star Wars', 'slug': 'star-wars-figures'},
                    {'name': 'NECA', 'slug': 'neca'},
                    {'name': 'McFarlane', 'slug': 'mcfarlane'},
                    {'name': 'Hot Toys', 'slug': 'hot-toys'},
                ]
            },
            {
                'name': 'Funko',
                'slug': 'funko',
                'icon': 'bi-box-seam',
                'description': 'Funko Pops, Sodas, and other Funko collectibles',
                'children': [
                    {'name': 'Pop! Vinyl', 'slug': 'funko-pop'},
                    {'name': 'Soda', 'slug': 'funko-soda'},
                    {'name': 'Exclusives', 'slug': 'funko-exclusives'},
                ]
            },
            {
                'name': 'Video Games',
                'slug': 'video-games',
                'icon': 'bi-controller',
                'description': 'Retro and modern video games and consoles',
                'children': [
                    {'name': 'Nintendo', 'slug': 'nintendo'},
                    {'name': 'PlayStation', 'slug': 'playstation'},
                    {'name': 'Xbox', 'slug': 'xbox'},
                    {'name': 'Retro', 'slug': 'retro-games'},
                    {'name': 'Handhelds', 'slug': 'handheld-games'},
                ]
            },
            {
                'name': 'Coins & Currency',
                'slug': 'coins',
                'icon': 'bi-coin',
                'description': 'Coins, paper currency, and bullion',
                'children': [
                    {'name': 'US Coins', 'slug': 'us-coins'},
                    {'name': 'World Coins', 'slug': 'world-coins'},
                    {'name': 'Paper Currency', 'slug': 'paper-currency'},
                    {'name': 'Bullion', 'slug': 'bullion'},
                ]
            },
            {
                'name': 'Stamps',
                'slug': 'stamps',
                'icon': 'bi-postage',
                'description': 'Postage stamps and philatelic items',
            },
            {
                'name': 'Memorabilia',
                'slug': 'memorabilia',
                'icon': 'bi-star',
                'description': 'Movie props, autographs, and entertainment memorabilia',
                'children': [
                    {'name': 'Autographs', 'slug': 'autographs'},
                    {'name': 'Movie Props', 'slug': 'movie-props'},
                    {'name': 'Sports Memorabilia', 'slug': 'sports-memorabilia'},
                    {'name': 'Music', 'slug': 'music-memorabilia'},
                ]
            },
            {
                'name': 'LEGO',
                'slug': 'lego',
                'icon': 'bi-bricks',
                'description': 'LEGO sets, minifigures, and parts',
                'children': [
                    {'name': 'Sets', 'slug': 'lego-sets'},
                    {'name': 'Minifigures', 'slug': 'lego-minifigures'},
                    {'name': 'Parts', 'slug': 'lego-parts'},
                ]
            },
            {
                'name': 'Die-Cast & Vehicles',
                'slug': 'diecast',
                'icon': 'bi-truck',
                'description': 'Hot Wheels, Matchbox, and model vehicles',
                'children': [
                    {'name': 'Hot Wheels', 'slug': 'hot-wheels'},
                    {'name': 'Matchbox', 'slug': 'matchbox'},
                    {'name': 'Scale Models', 'slug': 'scale-models'},
                ]
            },
            {
                'name': 'Art & Prints',
                'slug': 'art',
                'icon': 'bi-palette',
                'description': 'Original art, prints, and posters',
            },
            {
                'name': 'Vintage & Antiques',
                'slug': 'vintage',
                'icon': 'bi-hourglass',
                'description': 'Vintage toys, antiques, and nostalgia items',
            },
        ]

        order = 0
        for cat_data in categories:
            children = cat_data.pop('children', [])
            cat_data['order'] = order
            order += 1

            category, created = Category.objects.update_or_create(
                slug=cat_data['slug'],
                defaults=cat_data
            )

            if created:
                self.stdout.write(f"Created category: {category.name}")
            else:
                self.stdout.write(f"Updated category: {category.name}")

            # Create children
            child_order = 0
            for child_data in children:
                child_data['parent'] = category
                child_data['order'] = child_order
                child_order += 1

                child, child_created = Category.objects.update_or_create(
                    slug=child_data['slug'],
                    defaults=child_data
                )

                if child_created:
                    self.stdout.write(f"  Created subcategory: {child.name}")

        self.stdout.write(self.style.SUCCESS('Categories seeded successfully!'))
