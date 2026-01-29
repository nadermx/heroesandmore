import csv
from io import TextIOWrapper
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Sum

from .models import Collection, CollectionItem
from .forms import CollectionForm, CollectionItemForm, CSVImportForm
from items.models import Category


def collection_list(request, username=None):
    """List collections - public or user's own"""
    if username:
        user = get_object_or_404(User, username=username)
        collections = Collection.objects.filter(user=user)
        if request.user != user:
            collections = collections.filter(is_public=True)
        title = f"{user.username}'s Collections"
    else:
        # Browse all public collections
        collections = Collection.objects.filter(is_public=True).select_related('user')
        title = "Browse Collections"

    paginator = Paginator(collections, 24)
    page = request.GET.get('page')
    collections = paginator.get_page(page)

    context = {
        'collections': collections,
        'title': title,
    }
    return render(request, 'user_collections/collection_list.html', context)


@login_required
def my_collections(request):
    """Current user's collections"""
    collections = Collection.objects.filter(user=request.user)

    # Calculate totals
    total_value = sum(c.get_total_value() for c in collections)
    total_cost = sum(c.get_total_cost() for c in collections)
    total_items = sum(c.item_count() for c in collections)

    context = {
        'collections': collections,
        'total_value': total_value,
        'total_cost': total_cost,
        'total_items': total_items,
    }
    return render(request, 'user_collections/my_collections.html', context)


def collection_detail(request, pk):
    """View single collection"""
    collection = get_object_or_404(Collection.objects.select_related('user'), pk=pk)

    # Check privacy
    if not collection.is_public and request.user != collection.user:
        raise Http404("This collection is private")

    items = collection.items.all().select_related('item', 'category')

    # Sorting
    sort = request.GET.get('sort', '-created')
    if sort == 'name':
        items = items.order_by('name')
    elif sort == 'value_high':
        items = items.order_by('-current_value')
    elif sort == 'value_low':
        items = items.order_by('current_value')
    elif sort == 'date':
        items = items.order_by('-purchase_date')
    else:
        items = items.order_by('-created')

    paginator = Paginator(items, 24)
    page = request.GET.get('page')
    items = paginator.get_page(page)

    context = {
        'collection': collection,
        'items': items,
        'is_owner': request.user == collection.user,
    }
    return render(request, 'user_collections/collection_detail.html', context)


@login_required
def collection_create(request):
    """Create new collection"""
    if request.method == 'POST':
        form = CollectionForm(request.POST, request.FILES)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.user = request.user
            collection.save()
            messages.success(request, 'Collection created!')
            return redirect('collections:collection_detail', pk=collection.pk)
    else:
        form = CollectionForm()

    context = {
        'form': form,
        'title': 'Create Collection',
    }
    return render(request, 'user_collections/collection_form.html', context)


@login_required
def collection_edit(request, pk):
    """Edit collection"""
    collection = get_object_or_404(Collection, pk=pk, user=request.user)

    if request.method == 'POST':
        form = CollectionForm(request.POST, request.FILES, instance=collection)
        if form.is_valid():
            form.save()
            messages.success(request, 'Collection updated!')
            return redirect('collections:collection_detail', pk=pk)
    else:
        form = CollectionForm(instance=collection)

    context = {
        'form': form,
        'collection': collection,
        'title': 'Edit Collection',
    }
    return render(request, 'user_collections/collection_form.html', context)


@login_required
def collection_delete(request, pk):
    """Delete collection"""
    collection = get_object_or_404(Collection, pk=pk, user=request.user)

    if request.method == 'POST':
        collection.delete()
        messages.success(request, 'Collection deleted.')
        return redirect('collections:my_collections')

    context = {
        'collection': collection,
    }
    return render(request, 'user_collections/collection_confirm_delete.html', context)


@login_required
def item_add(request, pk):
    """Add item to collection"""
    collection = get_object_or_404(Collection, pk=pk, user=request.user)

    if request.method == 'POST':
        form = CollectionItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.collection = collection
            item.save()
            messages.success(request, 'Item added to collection!')
            return redirect('collections:collection_detail', pk=pk)
    else:
        form = CollectionItemForm()

    categories = Category.objects.filter(is_active=True)

    context = {
        'form': form,
        'collection': collection,
        'categories': categories,
    }
    return render(request, 'user_collections/item_form.html', context)


@login_required
def item_edit(request, pk):
    """Edit collection item"""
    item = get_object_or_404(CollectionItem, pk=pk, collection__user=request.user)

    if request.method == 'POST':
        form = CollectionItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Item updated!')
            return redirect('collections:collection_detail', pk=item.collection.pk)
    else:
        form = CollectionItemForm(instance=item)

    categories = Category.objects.filter(is_active=True)

    context = {
        'form': form,
        'item': item,
        'collection': item.collection,
        'categories': categories,
    }
    return render(request, 'user_collections/item_form.html', context)


@login_required
def item_delete(request, pk):
    """Delete collection item"""
    item = get_object_or_404(CollectionItem, pk=pk, collection__user=request.user)
    collection_pk = item.collection.pk

    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Item removed from collection.')
        return redirect('collections:collection_detail', pk=collection_pk)

    context = {
        'item': item,
    }
    return render(request, 'user_collections/item_confirm_delete.html', context)


@login_required
def collection_export(request, pk):
    """Export collection to CSV"""
    collection = get_object_or_404(Collection, pk=pk, user=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{collection.name}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Name', 'Category', 'Condition', 'Grade', 'Quantity',
        'Purchase Price', 'Purchase Date', 'Current Value', 'Notes'
    ])

    for item in collection.items.all():
        writer.writerow([
            item.get_name(),
            item.category.name if item.category else '',
            item.get_condition_display() if item.condition else '',
            item.grade,
            item.quantity,
            item.purchase_price or '',
            item.purchase_date or '',
            item.current_value or '',
            item.notes,
        ])

    return response


@login_required
def collection_import(request, pk):
    """Import items from CSV"""
    collection = get_object_or_404(Collection, pk=pk, user=request.user)

    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = TextIOWrapper(request.FILES['csv_file'].file, encoding='utf-8')
            reader = csv.DictReader(csv_file)

            imported = 0
            for row in reader:
                try:
                    # Find category if provided
                    category = None
                    if row.get('Category'):
                        category = Category.objects.filter(name__iexact=row['Category']).first()

                    CollectionItem.objects.create(
                        collection=collection,
                        name=row.get('Name', ''),
                        category=category,
                        condition=row.get('Condition', '').lower().replace(' ', '_'),
                        grade=row.get('Grade', ''),
                        quantity=int(row.get('Quantity', 1) or 1),
                        purchase_price=row.get('Purchase Price') or None,
                        purchase_date=row.get('Purchase Date') or None,
                        current_value=row.get('Current Value') or None,
                        notes=row.get('Notes', ''),
                    )
                    imported += 1
                except Exception as e:
                    continue

            messages.success(request, f'Imported {imported} items.')
            return redirect('collections:collection_detail', pk=pk)
    else:
        form = CSVImportForm()

    context = {
        'form': form,
        'collection': collection,
    }
    return render(request, 'user_collections/import.html', context)


@login_required
def add_listing_to_collection(request, listing_pk):
    """Quick add listing to a collection"""
    from marketplace.models import Listing

    listing = get_object_or_404(Listing, pk=listing_pk)
    collections = Collection.objects.filter(user=request.user)

    if request.method == 'POST':
        collection_pk = request.POST.get('collection')
        collection = get_object_or_404(Collection, pk=collection_pk, user=request.user)

        CollectionItem.objects.create(
            collection=collection,
            listing=listing,
            name=listing.title,
            category=listing.category,
            condition=listing.condition,
            grade=listing.grade if listing.grading_service else '',
        )

        messages.success(request, f'Added to {collection.name}!')
        return redirect('marketplace:listing_detail', pk=listing_pk)

    context = {
        'listing': listing,
        'collections': collections,
    }
    return render(request, 'user_collections/add_to_collection.html', context)
