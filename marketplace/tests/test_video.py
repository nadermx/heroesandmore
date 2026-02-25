"""
Tests for listing video upload and YouTube/Vimeo URL support.
"""
import os
from decimal import Decimal
from unittest.mock import MagicMock
from io import BytesIO

from PIL import Image

from django.test import TestCase, Client, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User

from items.models import Category
from marketplace.models import Listing
from marketplace.forms import ListingForm


def _make_video_file(name='test.mp4', size=1024, content_type='video/mp4'):
    """Create a small fake video file for testing."""
    return SimpleUploadedFile(name, b'\x00' * size, content_type=content_type)


def _make_image_file(name='test.jpg'):
    """Create a valid tiny JPEG image for form tests."""
    buf = BytesIO()
    img = Image.new('RGB', (10, 10), color='red')
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile(name, buf.read(), content_type='image/jpeg')


class ListingVideoModelTests(TestCase):
    """Tests for video fields on Listing model."""

    def setUp(self):
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_video_fields_exist(self):
        """Listing should have video1, video2, video3, video_url fields."""
        listing = Listing.objects.create(
            seller=self.user,
            title='Video Test',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
        )
        self.assertFalse(listing.video1)
        self.assertFalse(listing.video2)
        self.assertFalse(listing.video3)
        self.assertEqual(listing.video_url, '')

    def test_get_videos_empty(self):
        """get_videos() should return empty list when no videos."""
        listing = Listing.objects.create(
            seller=self.user,
            title='No Video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
        )
        self.assertEqual(listing.get_videos(), [])

    def test_get_videos_with_files(self):
        """get_videos() should return list of non-empty video fields."""
        listing = Listing.objects.create(
            seller=self.user,
            title='Has Video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
        )
        listing.video1.save('test1.mp4', BytesIO(b'\x00' * 100), save=True)
        self.assertEqual(len(listing.get_videos()), 1)
        # Clean up
        listing.video1.delete(save=False)

    def test_has_video_false(self):
        """has_video should be False when no videos."""
        listing = Listing.objects.create(
            seller=self.user,
            title='No Video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
        )
        self.assertFalse(listing.has_video)

    def test_has_video_with_url(self):
        """has_video should be True when video_url is set."""
        listing = Listing.objects.create(
            seller=self.user,
            title='URL Video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        )
        self.assertTrue(listing.has_video)

    def test_get_video_url_embed_youtube(self):
        """Should return youtube-nocookie embed URL for YouTube links."""
        listing = Listing.objects.create(
            seller=self.user,
            title='YT',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        )
        embed = listing.get_video_url_embed()
        self.assertEqual(embed, 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')

    def test_get_video_url_embed_youtube_short(self):
        """Should handle youtu.be short links."""
        listing = Listing.objects.create(
            seller=self.user,
            title='YT Short',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            video_url='https://youtu.be/dQw4w9WgXcQ',
        )
        embed = listing.get_video_url_embed()
        self.assertEqual(embed, 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ')

    def test_get_video_url_embed_vimeo(self):
        """Should return Vimeo embed URL with dnt=1."""
        listing = Listing.objects.create(
            seller=self.user,
            title='Vimeo',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            video_url='https://vimeo.com/123456789',
        )
        embed = listing.get_video_url_embed()
        self.assertEqual(embed, 'https://player.vimeo.com/video/123456789?dnt=1')

    def test_get_video_url_embed_invalid(self):
        """Should return None for non-YouTube/Vimeo URLs."""
        listing = Listing.objects.create(
            seller=self.user,
            title='Bad URL',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            video_url='https://example.com/video.mp4',
        )
        self.assertIsNone(listing.get_video_url_embed())

    def test_get_video_url_embed_empty(self):
        """Should return None when video_url is empty."""
        listing = Listing.objects.create(
            seller=self.user,
            title='Empty URL',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
        )
        self.assertIsNone(listing.get_video_url_embed())


@override_settings(VIDEO_TIER_LIMITS={
    'starter': {'max_count': 1, 'max_size_mb': 250},
    'basic': {'max_count': 1, 'max_size_mb': 500},
    'featured': {'max_count': 2, 'max_size_mb': 1024},
    'premium': {'max_count': 3, 'max_size_mb': 2048},
}, VIDEO_ALLOWED_EXTENSIONS=['mp4', 'webm', 'mov'])
class ListingVideoFormTests(TestCase):
    """Tests for video validation in ListingForm."""

    def setUp(self):
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')

    def _base_data(self):
        """Return minimum valid form data."""
        return {
            'title': 'Test Listing',
            'description': 'A test listing',
            'category': self.category.pk,
            'condition': 'good',
            'price': '99.99',
            'listing_type': 'fixed',
            'shipping_price': '0.00',
            'quantity': '1',
        }

    def test_valid_video_upload(self):
        """Should accept a valid MP4 video for starter tier."""
        data = self._base_data()
        files = {
            'image1': _make_image_file(),
            'video1': _make_video_file('test.mp4', size=1024),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_webm_upload(self):
        """Should accept WebM format."""
        data = self._base_data()
        files = {
            'image1': _make_image_file(),
            'video1': _make_video_file('test.webm', size=1024, content_type='video/webm'),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_mov_upload(self):
        """Should accept MOV format."""
        data = self._base_data()
        files = {
            'image1': _make_image_file(),
            'video1': _make_video_file('test.mov', size=1024, content_type='video/quicktime'),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_reject_unsupported_format(self):
        """Should reject unsupported video formats like AVI."""
        data = self._base_data()
        files = {
            'image1': _make_image_file(),
            'video1': _make_video_file('test.avi', size=1024, content_type='video/x-msvideo'),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('not supported', str(form.errors))

    def test_reject_oversized_video(self):
        """Should reject video exceeding tier size limit."""
        # Starter limit is 250MB, so make a file that reports > 250MB
        big_video = _make_video_file('big.mp4', size=1024)
        big_video.size = 300 * 1024 * 1024  # 300MB
        data = self._base_data()
        files = {
            'image1': _make_image_file(),
            'video1': big_video,
        }
        form = ListingForm(data, files, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('maximum size', str(form.errors))

    def test_reject_too_many_videos_starter(self):
        """Starter tier should only allow 1 video."""
        data = self._base_data()
        files = {
            'image1': _make_image_file(),
            'video1': _make_video_file('v1.mp4', size=1024),
            'video2': _make_video_file('v2.mp4', size=1024),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('allows 1 video', str(form.errors))

    def test_valid_youtube_url(self):
        """Should accept valid YouTube URLs."""
        data = self._base_data()
        data['video_url'] = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        files = {
            'image1': _make_image_file(),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_vimeo_url(self):
        """Should accept valid Vimeo URLs."""
        data = self._base_data()
        data['video_url'] = 'https://vimeo.com/123456789'
        files = {
            'image1': _make_image_file(),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_reject_random_url(self):
        """Should reject non-YouTube/Vimeo URLs."""
        data = self._base_data()
        data['video_url'] = 'https://example.com/video.mp4'
        files = {
            'image1': _make_image_file(),
        }
        form = ListingForm(data, files, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('video_url', str(form.errors))


class ListingVideoDetailViewTests(TestCase):
    """Tests for video display on listing detail page."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_detail_with_video_url(self):
        """Listing detail should show video embed for YouTube URL."""
        listing = Listing.objects.create(
            seller=self.user,
            title='Video Listing',
            description='Has a video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        )
        response = self.client.get(f'/marketplace/{listing.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'youtube-nocookie.com/embed/dQw4w9WgXcQ')
        self.assertContains(response, 'videoSection')

    def test_detail_without_video(self):
        """Listing detail should not show video section when no videos."""
        listing = Listing.objects.create(
            seller=self.user,
            title='No Video',
            description='No video here',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
        )
        response = self.client.get(f'/marketplace/{listing.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'videoSection')

    def test_detail_video_badge(self):
        """Listing detail should show Video badge when has video."""
        listing = Listing.objects.create(
            seller=self.user,
            title='Badge Test',
            description='Has video badge',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
            video_url='https://vimeo.com/123456789',
        )
        response = self.client.get(f'/marketplace/{listing.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'bi-camera-video')

    def test_detail_video_json_ld(self):
        """Listing detail should include VideoObject JSON-LD for YouTube URL."""
        listing = Listing.objects.create(
            seller=self.user,
            title='JSON-LD Test',
            description='Has structured data',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
            video_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        )
        response = self.client.get(f'/marketplace/{listing.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'VideoObject')


class ListingVideoAPITests(TestCase):
    """Tests for video fields in API serializers."""

    def setUp(self):
        self.user = User.objects.create_user('seller', 'seller@test.com', 'pass123')
        self.category = Category.objects.create(name='Cards', slug='cards')

    def test_list_serializer_has_video_false(self):
        """ListingListSerializer should include has_video=False when no videos."""
        from marketplace.api.serializers import ListingListSerializer
        listing = Listing.objects.create(
            seller=self.user,
            title='No Video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
        )
        serializer = ListingListSerializer(listing)
        self.assertFalse(serializer.data['has_video'])

    def test_list_serializer_has_video_true(self):
        """ListingListSerializer should include has_video=True when video_url set."""
        from marketplace.api.serializers import ListingListSerializer
        listing = Listing.objects.create(
            seller=self.user,
            title='Has Video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
            video_url='https://www.youtube.com/watch?v=abc123',
        )
        serializer = ListingListSerializer(listing)
        self.assertTrue(serializer.data['has_video'])

    def test_detail_serializer_video_fields(self):
        """ListingDetailSerializer should include videos, video_url, video_embed_url."""
        from marketplace.api.serializers import ListingDetailSerializer
        listing = Listing.objects.create(
            seller=self.user,
            title='Detail Video',
            category=self.category,
            price=Decimal('10.00'),
            condition='good',
            status='active',
            video_url='https://www.youtube.com/watch?v=abc123',
        )
        serializer = ListingDetailSerializer(listing)
        self.assertIn('videos', serializer.data)
        self.assertIn('video_url', serializer.data)
        self.assertIn('video_embed_url', serializer.data)
        self.assertEqual(serializer.data['video_embed_url'],
                         'https://www.youtube-nocookie.com/embed/abc123')
        self.assertEqual(serializer.data['videos'], [])  # No file uploads
