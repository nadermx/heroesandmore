from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone

from .models import ScanResult, ScanSession
from .services.identification import quick_identify_scan
from marketplace.models import Listing
from user_collections.models import Collection, CollectionItem


@login_required
def scanner_home(request):
    """Scanner landing page"""
    recent_scans = ScanResult.objects.filter(user=request.user)[:10]

    return render(request, 'scanner/home.html', {
        'recent_scans': recent_scans,
    })


@login_required
@require_POST
def upload_scan(request):
    """Handle image upload for scanning"""
    if 'image' not in request.FILES:
        return JsonResponse({'error': 'No image provided'}, status=400)

    image = request.FILES['image']

    # Create scan result
    scan = ScanResult.objects.create(
        user=request.user,
        image=image,
        status='pending'
    )

    # Process immediately with a safe fallback matcher so result pages don't stall.
    quick_identify_scan(scan)

    return JsonResponse({
        'scan_id': scan.id,
        'status': scan.status,
        'redirect_url': f'/scanner/result/{scan.id}/'
    })


@login_required
def scan_result(request, pk):
    """View scan result"""
    scan = get_object_or_404(ScanResult, pk=pk, user=request.user)

    # Get suggested listings based on scan
    suggested_listings = []
    if scan.identified_item:
        suggested_listings = Listing.objects.filter(
            price_guide_item=scan.identified_item,
            status='active'
        )[:5]

    # Get user's collections for adding
    collections = Collection.objects.filter(user=request.user)

    return render(request, 'scanner/result.html', {
        'scan': scan,
        'suggested_listings': suggested_listings,
        'collections': collections,
    })


@login_required
def scan_session(request):
    """Start a bulk scanning session"""
    if request.method == 'POST':
        session = ScanSession.objects.create(
            user=request.user,
            name=request.POST.get('name', f'Session {timezone.now().strftime("%Y-%m-%d %H:%M")}')
        )
        return redirect('scanner:session_detail', pk=session.pk)

    sessions = ScanSession.objects.filter(user=request.user)[:20]
    return render(request, 'scanner/session_list.html', {
        'sessions': sessions,
    })


@login_required
def session_detail(request, pk):
    """View scanning session details"""
    session = get_object_or_404(ScanSession, pk=pk, user=request.user)
    scans = ScanResult.objects.filter(
        user=request.user,
        created__gte=session.created
    ).order_by('-created')

    return render(request, 'scanner/session_detail.html', {
        'session': session,
        'scans': scans,
    })


@login_required
@require_POST
def create_listing_from_scan(request, pk):
    """Create a listing from scan result"""
    scan = get_object_or_404(ScanResult, pk=pk, user=request.user)

    # Pre-populate listing form data
    form_data = {
        'title': scan.get_suggested_title(),
        'price_guide_item': scan.identified_item_id,
    }

    # Add extracted data
    data = scan.extracted_data
    if data.get('grading_company'):
        form_data['grading_service'] = data['grading_company'].lower()
    if data.get('grade'):
        form_data['grade'] = data['grade']
    if data.get('cert_number'):
        form_data['cert_number'] = data['cert_number']

    # Store in session for listing create view
    request.session['listing_prefill'] = form_data
    request.session['scan_image'] = scan.image.url if scan.image else None

    messages.success(request, 'Scan data loaded. Complete your listing details.')
    return redirect('marketplace:listing_create')


@login_required
@require_POST
def add_to_collection_from_scan(request, pk):
    """Add scan result to a collection"""
    scan = get_object_or_404(ScanResult, pk=pk, user=request.user)
    collection_id = request.POST.get('collection_id')

    if not collection_id:
        return JsonResponse({'error': 'No collection specified'}, status=400)

    collection = get_object_or_404(Collection, pk=collection_id, user=request.user)

    # Create collection item
    data = scan.extracted_data
    item = CollectionItem.objects.create(
        collection=collection,
        price_guide_item=scan.identified_item,
        name=scan.get_suggested_title(),
        grading_company=data.get('grading_company', ''),
        grade=data.get('grade', ''),
        cert_number=data.get('cert_number', ''),
        image=scan.image,
    )

    # Update scan with reference
    scan.added_to_collection = item
    scan.save(update_fields=['added_to_collection'])

    messages.success(request, f'Added to {collection.name}')
    return redirect('collections:collection_detail', pk=collection.pk)


@login_required
@require_POST
def api_scan(request):
    """API endpoint for scanning (for AJAX uploads)"""
    if 'image' not in request.FILES:
        return JsonResponse({'error': 'No image provided'}, status=400)

    image = request.FILES['image']

    scan = ScanResult.objects.create(
        user=request.user,
        image=image,
        status='pending'
    )

    # Process immediately with a safe fallback matcher.
    quick_identify_scan(scan)

    return JsonResponse({
        'scan_id': scan.id,
        'status': scan.status,
    })


@login_required
def api_scan_status(request, pk):
    """Check scan status (for polling)"""
    scan = get_object_or_404(ScanResult, pk=pk, user=request.user)

    response = {
        'status': scan.status,
        'confidence': float(scan.confidence) if scan.confidence else None,
    }

    if scan.status == 'success' and scan.identified_item:
        response['identified'] = {
            'id': scan.identified_item.id,
            'name': scan.identified_item.name,
            'avg_price': float(scan.identified_item.avg_sale_price) if scan.identified_item.avg_sale_price else None,
        }
        response['extracted_data'] = scan.extracted_data

    elif scan.status == 'failed':
        response['error'] = scan.error_message

    return JsonResponse(response)
