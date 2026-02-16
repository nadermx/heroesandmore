"""
Market Data Import Services

Pulls pricing data from external sources:
- eBay (via scraping sold listings)
- Heritage Auctions (via scraping completed auctions)
- GoCollect (via scraping for comics)

Run twice daily via Celery beat.
"""

import os
import requests
import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)

# Free proxy list — refreshed on first use per process
_proxy_cache = {'proxies': [], 'fetched': None}


def _get_free_proxies() -> List[str]:
    """Fetch and cache a list of free HTTP proxies. Returns list of proxy URLs."""
    now = datetime.now()
    # Refresh every 30 minutes
    if _proxy_cache['proxies'] and _proxy_cache['fetched'] and (now - _proxy_cache['fetched']).seconds < 1800:
        return _proxy_cache['proxies']

    proxies = []
    try:
        r = requests.get(
            'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies'
            '&proxy_format=protocolipport&format=text&protocol=http&timeout=5000',
            timeout=10,
        )
        for line in r.text.strip().split('\n'):
            line = line.strip()
            if line:
                proxies.append(line)
    except Exception as e:
        logger.debug(f"Failed to fetch proxy list: {e}")

    if proxies:
        _proxy_cache['proxies'] = proxies
        _proxy_cache['fetched'] = now
        logger.info(f"Loaded {len(proxies)} free proxies")

    return proxies


def _make_proxied_request(url: str, session: requests.Session, timeout: int = 30, **kwargs) -> Optional[requests.Response]:
    """
    Try a request through free proxies. Falls back to direct if all fail.
    Tries up to 5 random proxies before giving up.
    """
    import random
    proxies = _get_free_proxies()

    if proxies:
        sample = random.sample(proxies, min(5, len(proxies)))
        for proxy in sample:
            try:
                resp = session.get(url, proxies={'http': proxy, 'https': proxy}, timeout=timeout, **kwargs)
                if resp.status_code == 200 and 'Pardon Our Interruption' not in resp.text:
                    return resp
            except Exception:
                continue

    # Fallback: try direct
    try:
        return session.get(url, timeout=timeout, **kwargs)
    except Exception as e:
        logger.error(f"Direct request also failed for {url}: {e}")
        return None


def download_image_for_item(price_guide_item, image_url: str, source: str) -> bool:
    """
    Download an image from a URL and attach it to a PriceGuideItem.

    Skips if item already has an image or if the URL was already tried.
    Returns True if image was saved, False otherwise.
    """
    if not image_url:
        return False

    # Skip if item already has an image
    if price_guide_item.image:
        return False

    # Skip if we already tried this URL
    if image_url == price_guide_item.image_source_url:
        return False

    try:
        # For eBay: upgrade thumbnail to larger image
        if 'ebay' in image_url and 's-l225' in image_url:
            image_url = image_url.replace('s-l225', 's-l500')

        resp = requests.get(
            image_url,
            timeout=15,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            stream=True,
        )
        resp.raise_for_status()

        # Validate content type
        content_type = resp.headers.get('content-type', '')
        if not content_type.startswith('image/'):
            logger.debug(f"Not an image content-type for {image_url}: {content_type}")
            return False

        content = resp.content

        # Validate size (1KB - 5MB)
        if len(content) < 1024 or len(content) > 5 * 1024 * 1024:
            logger.debug(f"Image size out of range for {image_url}: {len(content)} bytes")
            return False

        # Build filename
        filename = image_url.split('/')[-1].split('?')[0] or 'image.jpg'
        filename = os.path.basename(filename)[:100]

        price_guide_item.image.save(filename, ContentFile(content), save=False)
        price_guide_item.image_source_url = image_url
        price_guide_item.image_source = source
        price_guide_item.save(update_fields=['image', 'image_source_url', 'image_source'])

        logger.info(f"Downloaded image for '{price_guide_item.name}' from {source}")
        return True

    except Exception as e:
        logger.debug(f"Failed to download image for '{price_guide_item.name}' from {image_url}: {e}")
        return False


class EbayMarketData:
    """
    Fetch sold listings from eBay by scraping search results.

    No API key required - scrapes the public sold listings page.
    """

    BASE_URL = "https://www.ebay.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def search_sold_items(self, query: str, category_id: str = None, limit: int = 50) -> List[Dict]:
        """
        Search for sold/completed listings on eBay.

        Args:
            query: Search terms (e.g., "PSA 10 Michael Jordan Fleer 1986")
            category_id: eBay category ID to filter (optional)
            limit: Max results to return

        Returns:
            List of sold item dicts with price, date, title, url
        """
        # Build eBay sold listings search URL
        # LH_Complete=1 = Completed listings
        # LH_Sold=1 = Sold listings only
        encoded_query = quote_plus(query)
        url = f"{self.BASE_URL}/sch/i.html?_nkw={encoded_query}&LH_Complete=1&LH_Sold=1&_sop=13"

        if category_id:
            url += f"&_sacat={category_id}"

        try:
            response = _make_proxied_request(url, self.session, timeout=30)
            if not response:
                return []
            response.raise_for_status()

            return self._parse_search_results(response.text, limit)

        except Exception as e:
            logger.error(f"eBay scrape failed for '{query}': {e}")
            return []

    def _parse_search_results(self, html: str, limit: int) -> List[Dict]:
        """Parse eBay search results page (handles both old .s-item and new .s-card layouts)"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Try new layout first (.s-card), fall back to old (.s-item)
        cards = soup.select('.s-card--horizontal')
        if cards:
            return self._parse_card_results(cards, limit)

        # Legacy .s-item layout
        items = soup.select('.s-item, .srp-results .s-item__wrapper')[:limit]

        for item in items:
            try:
                # Skip "Shop on eBay" promotional items
                shop_on_ebay = item.select_one('.s-item__title--tag')
                if shop_on_ebay and 'Shop on eBay' in shop_on_ebay.get_text():
                    continue

                # Extract title
                title_elem = item.select_one('.s-item__title, .s-item__title span')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # Skip placeholder items
                if not title or title == 'Shop on eBay':
                    continue

                # Extract price
                price_elem = item.select_one('.s-item__price, .s-item__price span')
                if not price_elem:
                    continue
                price = self._parse_price(price_elem.get_text(strip=True))

                if price <= 0:
                    continue

                # Extract URL
                link = item.select_one('a.s-item__link, a[href*="/itm/"]')
                item_url = link['href'] if link else ''

                # Extract image URL
                image_url = ''
                img_elem = item.select_one('.s-item__image img')
                if img_elem:
                    img_src = img_elem.get('src', '')
                    if img_src and 'ebaystatic.com/images/a/' not in img_src:
                        image_url = img_src

                # Extract sale date
                date_elem = item.select_one('.s-item__title--tagblock, .s-item__ended-date, .POSITIVE')
                sale_date = None
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    sale_date = self._parse_sold_date(date_text)

                if not sale_date:
                    sale_date = timezone.now()

                results.append({
                    'title': title,
                    'price': price,
                    'currency': 'USD',
                    'sale_date': sale_date,
                    'url': item_url,
                    'image_url': image_url,
                    'source': 'ebay'
                })

            except Exception as e:
                logger.debug(f"Failed to parse eBay item: {e}")
                continue

        return results

    def _parse_card_results(self, cards: list, limit: int) -> List[Dict]:
        """Parse new eBay .s-card layout (2025+)"""
        results = []

        for card in cards[:limit]:
            try:
                # Extract title
                title_div = card.select_one('.s-card__title')
                if not title_div:
                    continue
                title = title_div.get_text(strip=True)

                # Skip promo cards
                if not title or 'Shop on eBay' in title:
                    continue

                # Extract price
                price_el = card.select_one('.s-card__price')
                if not price_el:
                    continue
                price = self._parse_price(price_el.get_text(strip=True))
                if price <= 0:
                    continue

                # Extract URL
                link = card.select_one('a.s-card__link[href*="/itm/"]')
                item_url = link['href'] if link else ''

                # Extract image URL
                image_url = ''
                img_elem = card.select_one('img.s-card__image')
                if img_elem:
                    # Prefer data-defer-load (full size) over src (may be lazy placeholder)
                    img_src = img_elem.get('data-defer-load') or img_elem.get('src', '')
                    if img_src and 'ebaystatic.com/rs/' not in img_src:
                        image_url = img_src

                # Extract sale date
                sale_date = None
                tagline = card.select_one('.s-card__tagline')
                if tagline:
                    sale_date = self._parse_sold_date(tagline.get_text(strip=True))
                if not sale_date:
                    sale_date = timezone.now()

                results.append({
                    'title': title,
                    'price': price,
                    'currency': 'USD',
                    'sale_date': sale_date,
                    'url': item_url,
                    'image_url': image_url,
                    'source': 'ebay'
                })

            except Exception as e:
                logger.debug(f"Failed to parse eBay card: {e}")
                continue

        return results

    def _parse_price(self, price_text: str) -> Decimal:
        """Parse price string like '$1,234.56' to Decimal"""
        try:
            # Handle price ranges like "$100.00 to $200.00" - take the first price
            if ' to ' in price_text.lower():
                price_text = price_text.split(' to ')[0]

            # Remove currency symbols, commas, and whitespace
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return Decimal(cleaned) if cleaned else Decimal('0')
        except:
            return Decimal('0')

    def _parse_sold_date(self, date_text: str) -> Optional[datetime]:
        """Parse eBay sold date like 'Sold Jan 15, 2024'"""
        if not date_text:
            return None

        try:
            # Remove "Sold " prefix if present
            date_text = re.sub(r'^Sold\s+', '', date_text, flags=re.IGNORECASE)

            # Try various formats
            for fmt in ['%b %d, %Y', '%B %d, %Y', '%m/%d/%Y', '%d %b %Y']:
                try:
                    return datetime.strptime(date_text.strip(), fmt)
                except ValueError:
                    continue

            # Handle relative dates like "Sold 3d ago"
            if 'd ago' in date_text.lower():
                match = re.search(r'(\d+)d', date_text)
                if match:
                    days = int(match.group(1))
                    return datetime.now() - timedelta(days=days)

        except:
            pass

        return None


class HeritageAuctionsData:
    """
    Fetch auction results from Heritage Auctions.

    Scrapes their completed auctions pages for sports cards, comics, etc.
    """

    BASE_URL = "https://www.ha.com"

    # Category URLs on Heritage
    CATEGORIES = {
        'sports': '/sports-collectibles/search-results.s',
        'comics': '/comics-comic-art/search-results.s',
        'trading_cards': '/trading-card-games/search-results.s',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_recent_sales(self, category: str = 'sports', days_back: int = 7, limit: int = 100) -> List[Dict]:
        """
        Get recent auction results from Heritage.

        Args:
            category: 'sports', 'comics', or 'trading_cards'
            days_back: How many days back to search
            limit: Max results

        Returns:
            List of sale dicts
        """
        if category not in self.CATEGORIES:
            logger.warning(f"Unknown Heritage category: {category}")
            return []

        url = f"{self.BASE_URL}{self.CATEGORIES[category]}"
        params = {
            'N': '790+231',  # Completed auctions filter
            'Nf': f'lot_closedate|GTEQ+{self._days_ago_timestamp(days_back)}',
            'ic': '16',  # Results per page
            'type': 'surl-sold'
        }

        try:
            response = _make_proxied_request(url, self.session, timeout=30, params=params)
            if not response:
                return []
            response.raise_for_status()

            return self._parse_results_page(response.text, limit)

        except Exception as e:
            logger.error(f"Heritage scrape failed for {category}: {e}")
            return []

    def _parse_results_page(self, html: str, limit: int) -> List[Dict]:
        """Parse Heritage auction results page"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Find auction result items
        items = soup.select('.auction-item, .lot-item, [data-lot-id]')[:limit]

        for item in items:
            try:
                # Extract title
                title_elem = item.select_one('.lot-title, .item-title, h3 a')
                title = title_elem.get_text(strip=True) if title_elem else ''

                # Extract price
                price_elem = item.select_one('.price-realized, .winning-bid, .lot-price')
                price_text = price_elem.get_text(strip=True) if price_elem else '0'
                price = self._parse_price(price_text)

                # Extract URL
                link = item.select_one('a[href*="/lot/"]')
                url = f"{self.BASE_URL}{link['href']}" if link else ''

                # Extract image URL
                image_url = ''
                img_elem = item.select_one('img')
                if img_elem:
                    img_src = img_elem.get('data-src') or img_elem.get('src', '')
                    if img_src:
                        image_url = img_src if img_src.startswith('http') else f"{self.BASE_URL}{img_src}"

                # Extract date
                date_elem = item.select_one('.lot-date, .auction-date')
                sale_date = self._parse_heritage_date(date_elem.get_text(strip=True) if date_elem else '')

                if title and price > 0:
                    results.append({
                        'title': title,
                        'price': price,
                        'sale_date': sale_date or timezone.now(),
                        'url': url,
                        'image_url': image_url,
                        'source': 'heritage'
                    })

            except Exception as e:
                logger.debug(f"Failed to parse Heritage item: {e}")
                continue

        return results

    def _parse_price(self, price_text: str) -> Decimal:
        """Parse price string like '$1,234.56' to Decimal"""
        try:
            # Remove currency symbols and commas
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return Decimal(cleaned) if cleaned else Decimal('0')
        except:
            return Decimal('0')

    def _parse_heritage_date(self, date_text: str) -> Optional[datetime]:
        """Parse Heritage date formats"""
        if not date_text:
            return None
        try:
            # Try common formats
            for fmt in ['%b %d, %Y', '%m/%d/%Y', '%B %d, %Y']:
                try:
                    return datetime.strptime(date_text, fmt)
                except ValueError:
                    continue
        except:
            pass
        return None

    def _days_ago_timestamp(self, days: int) -> str:
        """Get Unix timestamp for N days ago"""
        dt = datetime.now() - timedelta(days=days)
        return str(int(dt.timestamp()))


class GoCollectData:
    """
    Fetch comic book price data from GoCollect.

    Scrapes their price guide for recent sales data.
    """

    BASE_URL = "https://www.gocollect.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_comics(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search for comic sales data on GoCollect.

        Args:
            query: Search terms (e.g., "Amazing Spider-Man 300 CGC 9.8")
            limit: Max results

        Returns:
            List of sale dicts
        """
        url = f"{self.BASE_URL}/search"
        params = {'q': query}

        try:
            response = _make_proxied_request(url, self.session, timeout=30, params=params)
            if not response:
                return []
            response.raise_for_status()

            return self._parse_search_results(response.text, limit)

        except Exception as e:
            logger.error(f"GoCollect search failed for '{query}': {e}")
            return []

    def get_comic_sales(self, comic_url: str, limit: int = 20) -> List[Dict]:
        """
        Get recent sales for a specific comic from its GoCollect page.

        Args:
            comic_url: Full URL or path to comic on GoCollect
            limit: Max sales to return

        Returns:
            List of sale dicts with grade, price, date
        """
        if not comic_url.startswith('http'):
            comic_url = f"{self.BASE_URL}{comic_url}"

        try:
            response = _make_proxied_request(comic_url, self.session, timeout=30)
            if not response:
                return []
            response.raise_for_status()

            return self._parse_comic_sales(response.text, limit)

        except Exception as e:
            logger.error(f"GoCollect comic fetch failed for '{comic_url}': {e}")
            return []

    def _parse_search_results(self, html: str, limit: int) -> List[Dict]:
        """Parse GoCollect search results"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        items = soup.select('.search-result, .comic-item, [data-comic-id]')[:limit]

        for item in items:
            try:
                title_elem = item.select_one('.title, h3, h4')
                title = title_elem.get_text(strip=True) if title_elem else ''

                link = item.select_one('a[href*="/guide/"]')
                url = link['href'] if link else ''

                # Extract image URL
                image_url = ''
                img_elem = item.select_one('img')
                if img_elem:
                    img_src = img_elem.get('data-src') or img_elem.get('src', '')
                    if img_src:
                        image_url = img_src if img_src.startswith('http') else f"{self.BASE_URL}{img_src}"

                # Get fair market value if shown
                fmv_elem = item.select_one('.fmv, .price, .value')
                fmv = self._parse_price(fmv_elem.get_text(strip=True) if fmv_elem else '0')

                if title:
                    results.append({
                        'title': title,
                        'price': fmv,
                        'url': url if url.startswith('http') else f"{self.BASE_URL}{url}",
                        'image_url': image_url,
                        'source': 'gocollect'
                    })

            except Exception as e:
                logger.debug(f"Failed to parse GoCollect item: {e}")
                continue

        return results

    def _parse_comic_sales(self, html: str, limit: int) -> List[Dict]:
        """Parse individual comic sales history"""
        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Find sales history table/list
        sales = soup.select('.sale-row, .sales-history tr, [data-sale-id]')[:limit]

        for sale in sales:
            try:
                # Extract grade (e.g., "CGC 9.8")
                grade_elem = sale.select_one('.grade, .cgc-grade, td:nth-child(1)')
                grade_text = grade_elem.get_text(strip=True) if grade_elem else ''

                # Parse grading company and grade
                grading_company, grade = self._parse_grade(grade_text)

                # Extract price
                price_elem = sale.select_one('.price, .sale-price, td:nth-child(2)')
                price = self._parse_price(price_elem.get_text(strip=True) if price_elem else '0')

                # Extract date
                date_elem = sale.select_one('.date, .sale-date, td:nth-child(3)')
                sale_date = self._parse_date(date_elem.get_text(strip=True) if date_elem else '')

                if price > 0:
                    results.append({
                        'grading_company': grading_company,
                        'grade': grade,
                        'price': price,
                        'sale_date': sale_date or timezone.now(),
                        'source': 'gocollect'
                    })

            except Exception as e:
                logger.debug(f"Failed to parse GoCollect sale: {e}")
                continue

        return results

    def _parse_grade(self, grade_text: str) -> tuple:
        """Parse grade string like 'CGC 9.8' into (company, grade)"""
        grade_text = grade_text.upper().strip()

        companies = ['CGC', 'CBCS', 'PGX', 'RAW']
        for company in companies:
            if company in grade_text:
                # Extract numeric grade
                match = re.search(r'(\d+\.?\d*)', grade_text)
                grade = Decimal(match.group(1)) if match else None
                return (company.lower(), grade)

        return ('', None)

    def _parse_price(self, price_text: str) -> Decimal:
        """Parse price string to Decimal"""
        try:
            cleaned = re.sub(r'[^\d.]', '', price_text)
            return Decimal(cleaned) if cleaned else Decimal('0')
        except:
            return Decimal('0')

    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse date string"""
        if not date_text:
            return None
        try:
            for fmt in ['%m/%d/%Y', '%b %d, %Y', '%Y-%m-%d', '%B %d, %Y']:
                try:
                    return datetime.strptime(date_text.strip(), fmt)
                except ValueError:
                    continue
        except:
            pass
        return None


class MarketDataImporter:
    """
    Main class to coordinate market data imports from all sources.
    """

    def __init__(self):
        self.ebay = EbayMarketData()
        self.heritage = HeritageAuctionsData()
        self.gocollect = GoCollectData()

    def import_for_item(self, price_guide_item) -> int:
        """
        Import market data for a specific PriceGuideItem.

        Returns count of new sales recorded.
        """
        from pricing.models import SaleRecord

        count = 0
        best_image_url = ''
        best_image_source = ''
        search_query = self._build_search_query(price_guide_item)

        # Search eBay
        ebay_results = self.ebay.search_sold_items(search_query, limit=20)
        for result in ebay_results:
            if self._record_sale(price_guide_item, result):
                count += 1
            if not best_image_url and result.get('image_url'):
                best_image_url = result['image_url']
                best_image_source = 'ebay'

        # Search Heritage if it's a sports card or comic
        category = price_guide_item.category.slug if price_guide_item.category else ''
        if 'card' in category or 'sport' in category:
            heritage_results = self.heritage.get_recent_sales('sports', days_back=7, limit=50)
            # Filter to matching items
            for result in heritage_results:
                if self._is_match(price_guide_item, result['title']):
                    if self._record_sale(price_guide_item, result):
                        count += 1
                    if not best_image_url and result.get('image_url'):
                        best_image_url = result['image_url']
                        best_image_source = 'heritage'

        # Search GoCollect if it's a comic
        if 'comic' in category:
            gocollect_results = self.gocollect.search_comics(search_query, limit=20)
            for result in gocollect_results:
                if not best_image_url and result.get('image_url'):
                    best_image_url = result['image_url']
                    best_image_source = 'gocollect'
                # Get detailed sales for each comic
                sales = self.gocollect.get_comic_sales(result.get('url', ''), limit=10)
                for sale in sales:
                    sale['title'] = result.get('title', '')
                    if self._record_sale(price_guide_item, sale):
                        count += 1

        # Download image if item doesn't have one yet
        if not price_guide_item.image and best_image_url:
            download_image_for_item(price_guide_item, best_image_url, best_image_source)

        return count

    def import_all_sources(self, category_slug: str = None) -> Dict[str, int]:
        """
        Import data from all sources for items in a category.

        Returns dict with counts per source.
        """
        from pricing.models import PriceGuideItem

        items = PriceGuideItem.objects.all()
        if category_slug:
            items = items.filter(category__slug=category_slug)

        # Limit to avoid rate limits
        items = items[:100]

        counts = {'ebay': 0, 'heritage': 0, 'gocollect': 0, 'total': 0}

        for item in items:
            imported = self.import_for_item(item)
            counts['total'] += imported

        return counts

    def _build_search_query(self, item) -> str:
        """Build search query from PriceGuideItem"""
        parts = []

        if item.year:
            parts.append(str(item.year))
        if item.set_name:
            parts.append(item.set_name)
        if item.name:
            parts.append(item.name)
        if item.card_number:
            parts.append(f"#{item.card_number}")

        # For comics
        if item.publisher:
            parts.append(item.publisher)
        if item.issue_number:
            parts.append(f"#{item.issue_number}")

        return ' '.join(parts)

    def _is_match(self, item, title: str) -> bool:
        """Check if a result title matches our item (fuzzy match)"""
        title_lower = title.lower()

        # Check key fields are present
        if item.name and item.name.lower() not in title_lower:
            return False

        if item.year and str(item.year) not in title:
            return False

        if item.card_number and item.card_number not in title:
            return False

        return True

    def _record_sale(self, price_guide_item, sale_data: Dict) -> bool:
        """
        Record a sale in the database.

        Returns True if new record created, False if duplicate or error.
        """
        from pricing.models import SaleRecord

        try:
            # Check for duplicate (same item, source, date, price)
            existing = SaleRecord.objects.filter(
                price_guide_item=price_guide_item,
                source=sale_data.get('source', 'manual'),
                sale_price=sale_data.get('price', 0),
                sale_date__date=sale_data.get('sale_date', timezone.now()).date() if sale_data.get('sale_date') else timezone.now().date()
            ).exists()

            if existing:
                return False

            # Create new record
            SaleRecord.objects.create(
                price_guide_item=price_guide_item,
                sale_price=sale_data.get('price', 0),
                sale_date=sale_data.get('sale_date') or timezone.now(),
                source=sale_data.get('source', 'manual'),
                source_url=sale_data.get('url', ''),
                grading_company=sale_data.get('grading_company', ''),
                grade=sale_data.get('grade'),
                cert_number=sale_data.get('cert_number', ''),
            )

            return True

        except Exception as e:
            logger.error(f"Failed to record sale: {e}")
            return False
