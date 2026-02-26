import re
from pathlib import Path

from django.utils import timezone

from pricing.models import PriceGuideItem


def quick_identify_scan(scan):
    """
    Best-effort synchronous matcher so scans don't stay pending forever.
    Uses filename token matching as a fallback when async OCR is unavailable.
    """
    file_stem = Path(scan.image.name).stem if scan.image else ""
    normalized = re.sub(r"[_\-]+", " ", file_stem).strip()
    tokens = [t for t in re.split(r"\s+", normalized) if len(t) >= 3]

    item = None
    if tokens:
        qs = PriceGuideItem.objects.all()
        for token in tokens[:5]:
            qs = qs.filter(name__icontains=token)
        item = qs.order_by('-total_sales', '-updated').first()

    if not item and normalized:
        item = PriceGuideItem.objects.filter(name__icontains=normalized[:80]).order_by('-total_sales', '-updated').first()

    scan.extracted_data = {
        **(scan.extracted_data or {}),
        'filename_hint': normalized,
    }
    scan.processed_at = timezone.now()

    if item:
        confidence = min(95, 40 + (10 * min(len(tokens), 5)))
        scan.identified_item = item
        scan.confidence = confidence
        scan.status = 'success'
        scan.error_message = ''
    else:
        scan.identified_item = None
        scan.confidence = None
        scan.status = 'no_match'
        scan.error_message = ''

    scan.save(update_fields=[
        'identified_item', 'confidence', 'status', 'error_message',
        'extracted_data', 'processed_at'
    ])
    return scan
