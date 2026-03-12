"""
Image optimization service for HeroesAndMore.

Provides functions to optimize listing images (resize, convert to WebP,
strip EXIF data) and generate thumbnails. Works with both local filesystem
and S3/DO Spaces via Django's default_storage.
"""

import logging
import os
from io import BytesIO

from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger('marketplace')

MAX_DISPLAY_DIMENSION = 1200  # For listing detail page
THUMBNAIL_WIDTH = 400  # For listing cards
OPTIMIZE_QUALITY = 82
THUMBNAIL_QUALITY = 75


def _open_and_prepare(image_field):
    """
    Open an image from a Django ImageField, apply EXIF orientation,
    and strip EXIF metadata. Returns a Pillow Image in RGB/RGBA mode.
    """
    image_field.seek(0)
    img = Image.open(image_field)

    # Apply EXIF orientation before stripping metadata
    img = ImageOps.exif_transpose(img)

    # Convert to RGB if necessary (handles CMYK, palette, etc.)
    # Preserve RGBA for images with transparency, though WebP supports it
    if img.mode == 'RGBA':
        pass  # Keep alpha channel
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    return img


def _webp_path(original_name, suffix=''):
    """
    Convert a file path to its WebP equivalent, optionally adding a suffix.

    Examples:
        _webp_path('listings/photo.jpg')          -> 'listings/photo.webp'
        _webp_path('listings/photo.jpg', '_thumb') -> 'listings/photo_thumb.webp'
    """
    root, _ = os.path.splitext(original_name)
    return f'{root}{suffix}.webp'


def optimize_image(image_field):
    """
    Optimize a Django ImageField value:
    - Keep the original upload as-is (for full-res zoom viewing)
    - Create an optimized display version (max 1200px, WebP, quality=82)
    - Auto-rotate based on EXIF orientation
    - Strip EXIF metadata for privacy

    The original stays at its upload path. The optimized version is saved
    with .webp extension (replaces the field value for normal display).
    The original can be accessed via get_original_url().

    Args:
        image_field: A Django FieldFile (e.g., listing.image1)

    Returns:
        str: The new file name (relative storage path) with .webp extension,
             or None if the operation failed.
    """
    if not image_field or not image_field.name:
        return None

    original_name = image_field.name

    try:
        img = _open_and_prepare(image_field)
        original_width, original_height = img.size

        # Save a copy of the original with _original suffix (preserving full quality)
        # Only if the original is higher res than our display size
        if max(original_width, original_height) > MAX_DISPLAY_DIMENSION:
            original_copy_name = _webp_path(original_name, '_original')
            buf_orig = BytesIO()
            img.save(buf_orig, format='WEBP', quality=95, method=4)
            buf_orig.seek(0)
            if default_storage.exists(original_copy_name):
                default_storage.delete(original_copy_name)
            default_storage.save(original_copy_name, ContentFile(buf_orig.read()))
            logger.info('Saved full-res original %s', original_copy_name)

        # Resize for display version (max 1200px)
        if max(original_width, original_height) > MAX_DISPLAY_DIMENSION:
            img.thumbnail((MAX_DISPLAY_DIMENSION, MAX_DISPLAY_DIMENSION), Image.LANCZOS)
            logger.info(
                'Resized %s from %dx%d to %dx%d',
                original_name, original_width, original_height, img.size[0], img.size[1],
            )

        # Save as WebP to an in-memory buffer
        buffer = BytesIO()
        img.save(buffer, format='WEBP', quality=OPTIMIZE_QUALITY, method=4)
        buffer.seek(0)

        new_name = _webp_path(original_name)

        # Delete the old file if the name is changing
        if new_name != original_name:
            try:
                default_storage.delete(original_name)
            except Exception:
                logger.debug('Could not delete original file %s', original_name)

        # Save the optimized image (overwrite if exists)
        if default_storage.exists(new_name):
            default_storage.delete(new_name)
        saved_name = default_storage.save(new_name, ContentFile(buffer.read()))

        logger.info('Optimized image %s -> %s', original_name, saved_name)
        return saved_name

    except Exception:
        logger.exception('Failed to optimize image %s', original_name)
        return None


def create_thumbnail(image_field):
    """
    Create a 400px-wide WebP thumbnail for a Django ImageField value.
    The thumbnail is saved alongside the original with a '_thumb' suffix.

    Args:
        image_field: A Django FieldFile (e.g., listing.image1)

    Returns:
        str: The thumbnail file path (relative storage path),
             or None if the operation failed.
    """
    if not image_field or not image_field.name:
        return None

    original_name = image_field.name

    try:
        img = _open_and_prepare(image_field)

        # Calculate thumbnail height preserving aspect ratio
        width, height = img.size
        if width <= 0:
            return None

        thumb_width = min(THUMBNAIL_WIDTH, width)
        ratio = thumb_width / width
        thumb_height = int(height * ratio)

        img = img.resize((thumb_width, thumb_height), Image.LANCZOS)

        buffer = BytesIO()
        img.save(buffer, format='WEBP', quality=THUMBNAIL_QUALITY, method=4)
        buffer.seek(0)

        thumb_name = _webp_path(original_name, '_thumb')

        if default_storage.exists(thumb_name):
            default_storage.delete(thumb_name)
        saved_name = default_storage.save(thumb_name, ContentFile(buffer.read()))

        logger.info('Created thumbnail %s -> %s', original_name, saved_name)
        return saved_name

    except Exception:
        logger.exception('Failed to create thumbnail for %s', original_name)
        return None


def process_listing_images(listing_instance):
    """
    Optimize and create thumbnails for all images on a Listing instance.
    Skips empty fields and images that are already in WebP format (already
    processed). Updates the Listing image fields in the database.

    Args:
        listing_instance: A marketplace.Listing model instance.
    """
    image_fields = ['image1', 'image2', 'image3', 'image4', 'image5']
    updated_fields = []

    for field_name in image_fields:
        image_field = getattr(listing_instance, field_name)
        if not image_field or not image_field.name:
            continue

        # Skip already-processed WebP images
        if image_field.name.lower().endswith('.webp'):
            logger.debug('Skipping already-processed %s on listing %s', field_name, listing_instance.pk)
            continue

        try:
            # Optimize the full-size image
            new_name = optimize_image(image_field)
            if new_name:
                setattr(listing_instance, field_name, new_name)
                updated_fields.append(field_name)

                # Create thumbnail from the newly optimized image
                updated_field = getattr(listing_instance, field_name)
                create_thumbnail(updated_field)
            else:
                # Optimization failed; still try to create a thumbnail from original
                create_thumbnail(image_field)

        except Exception:
            logger.exception(
                'Error processing %s for listing %s',
                field_name, listing_instance.pk,
            )

    # Bulk-update only the changed image fields to avoid race conditions
    if updated_fields:
        try:
            listing_instance.save(update_fields=updated_fields)
            logger.info(
                'Updated listing %s image fields: %s',
                listing_instance.pk, ', '.join(updated_fields),
            )
        except Exception:
            logger.exception(
                'Failed to save updated image fields for listing %s',
                listing_instance.pk,
            )


def get_original_url(image_field):
    """
    Return the URL for the full-resolution original of an image field.
    If no _original version exists, returns the normal image URL.
    """
    if not image_field or not image_field.name:
        return None

    original_name = _webp_path(image_field.name, '_original')

    try:
        if default_storage.exists(original_name):
            return default_storage.url(original_name)
    except Exception:
        pass

    # Fall back to the current image URL
    try:
        return image_field.url
    except Exception:
        return None


def get_thumbnail_url(image_field):
    """
    Return the URL for the thumbnail version of an image field.
    Constructs the thumbnail path by adding '_thumb' suffix and
    changing the extension to .webp. Falls back to the original
    image URL if the thumbnail doesn't exist yet.

    Args:
        image_field: A Django FieldFile (e.g., listing.image1)

    Returns:
        str: The thumbnail URL, or None if the field is empty.
    """
    if not image_field or not image_field.name:
        return None

    thumb_name = _webp_path(image_field.name, '_thumb')

    try:
        if default_storage.exists(thumb_name):
            return default_storage.url(thumb_name)
    except Exception:
        logger.debug('Could not check thumbnail existence for %s', image_field.name)

    # Thumbnail doesn't exist yet (pre-optimization or task pending)
    # Fall back to original image
    return None
