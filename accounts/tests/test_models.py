"""
Tests for accounts models.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import Profile


class ProfileModelTests(TestCase):
    """Tests for Profile model."""

    def test_profile_created_on_user_creation(self):
        """Profile should be auto-created when User is created."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, Profile)

    def test_profile_default_values(self):
        """Profile should have correct default values."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        profile = user.profile
        
        self.assertEqual(profile.seller_tier, 'starter')
        self.assertFalse(profile.is_seller_verified)
        self.assertFalse(profile.stripe_account_complete)
        self.assertEqual(profile.stripe_account_id, '')
        self.assertEqual(profile.rating, 0)
        self.assertEqual(profile.total_sales_count, 0)

    def test_profile_str_representation(self):
        """Profile __str__ should return username."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.assertIn('testuser', str(user.profile))

    def test_stripe_fields_can_be_cleared(self):
        """Stripe fields should accept empty string."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        profile = user.profile
        profile.stripe_account_id = 'acct_test123'
        profile.save()
        
        profile.stripe_account_id = ''
        profile.save()
        
        profile.refresh_from_db()
        self.assertEqual(profile.stripe_account_id, '')


class ProfileSellerTierTests(TestCase):
    """Tests for seller tier functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_valid_seller_tiers(self):
        """Should accept all valid seller tiers."""
        valid_tiers = ['starter', 'basic', 'featured', 'premium']
        
        for tier in valid_tiers:
            self.user.profile.seller_tier = tier
            self.user.profile.save()
            self.user.profile.refresh_from_db()
            self.assertEqual(self.user.profile.seller_tier, tier)

    def test_get_tier_display(self):
        """Should return human-readable tier name."""
        self.user.profile.seller_tier = 'premium'
        self.assertEqual(self.user.profile.get_seller_tier_display(), 'Premium')
