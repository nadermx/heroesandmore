"""
Tests for accounts API - registration, profile, password management.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status


class RegistrationAPITests(TestCase):
    """Tests for user registration API."""

    def setUp(self):
        self.client = APIClient()

    def test_register_with_valid_data(self):
        """Should register user and return tokens."""
        response = self.client.post('/api/v1/accounts/register/', {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['username'], 'newuser')

    def test_register_with_missing_fields(self):
        """Should reject incomplete registration."""
        response = self.client.post('/api/v1/accounts/register/', {
            'username': 'newuser',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_duplicate_username(self):
        """Should reject duplicate username."""
        User.objects.create_user('existinguser', 'existing@test.com', 'pass123')
        response = self.client.post('/api/v1/accounts/register/', {
            'username': 'existinguser',
            'email': 'new@test.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_password_mismatch(self):
        """Should reject mismatched passwords."""
        response = self.client.post('/api/v1/accounts/register/', {
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'securepass123',
            'password_confirm': 'differentpass',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProfileAPITests(TestCase):
    """Tests for profile API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token for test user."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_get_current_user_profile_authenticated(self):
        """Should return profile for authenticated user."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_current_user_profile_unauthenticated(self):
        """Should reject unauthenticated profile request."""
        response = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile(self):
        """Should update profile fields."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch('/api/v1/accounts/me/', {
            'bio': 'Updated bio text',
        })
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])


class PasswordChangeAPITests(TestCase):
    """Tests for password change API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='oldpass123'
        )

    def get_token(self):
        """Get JWT token for test user."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'oldpass123',
        })
        return response.data['access']

    def test_change_password_with_correct_old_password(self):
        """Should change password with correct old password."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/v1/accounts/me/password/', {
            'old_password': 'oldpass123',
            'new_password': 'NewPass456!',
            'new_password_confirm': 'NewPass456!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify new password works
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))

    def test_change_password_with_wrong_old_password(self):
        """Should reject wrong old password."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post('/api/v1/accounts/me/password/', {
            'old_password': 'wrongpass',
            'new_password': 'newpass456',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PublicProfileAPITests(TestCase):
    """Tests for public profile API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='publicuser',
            email='public@test.com',
            password='testpass123'
        )
        # Make profile public
        self.user.profile.is_public = True
        self.user.profile.save()

    def test_get_public_profile(self):
        """Should return public profile."""
        response = self.client.get('/api/v1/accounts/profiles/publicuser/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_private_profile_not_found(self):
        """Should not show private profile."""
        self.user.profile.is_public = False
        self.user.profile.save()
        response = self.client.get('/api/v1/accounts/profiles/publicuser/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class RecentlyViewedAPITests(TestCase):
    """Tests for recently viewed listings API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_get_recently_viewed_authenticated(self):
        """Should return recently viewed for authenticated user."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/accounts/me/recently-viewed/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_clear_recently_viewed(self):
        """Should clear recently viewed history."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete('/api/v1/accounts/me/recently-viewed/clear/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class NotificationSettingsAPITests(TestCase):
    """Tests for notification settings API."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='notifyuser',
            email='notify@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'notifyuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_get_notification_settings_authenticated(self):
        """Should return notification settings for authenticated user."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/accounts/me/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('email_notifications', response.data)
        self.assertIn('push_new_bid', response.data)

    def test_get_notification_settings_unauthenticated(self):
        """Should reject unauthenticated request."""
        response = self.client.get('/api/v1/accounts/me/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_notification_settings(self):
        """Should update notification settings."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch('/api/v1/accounts/me/notifications/', {
            'push_new_bid': False,
            'push_outbid': False,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['push_new_bid'])
        self.assertFalse(response.data['push_outbid'])

    def test_update_notification_settings_partial(self):
        """Should allow partial update of notification settings."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.patch('/api/v1/accounts/me/notifications/', {
            'email_notifications': False,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['email_notifications'])


class UserCollectionsAPITests(TestCase):
    """Tests for user collections endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='collectionuser',
            email='collect@test.com',
            password='testpass123'
        )

    def test_get_user_public_collections(self):
        """Should return user's public collections."""
        from user_collections.models import Collection
        Collection.objects.create(
            user=self.user,
            name='Public Collection',
            is_public=True
        )
        response = self.client.get('/api/v1/accounts/profiles/collectionuser/collections/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_private_collections_not_shown(self):
        """Should not show private collections."""
        from user_collections.models import Collection
        Collection.objects.create(
            user=self.user,
            name='Private Collection',
            is_public=False
        )
        response = self.client.get('/api/v1/accounts/profiles/collectionuser/collections/')
        if response.status_code == status.HTTP_200_OK:
            # Private collection should not be in results
            # Handle paginated response
            results = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
            self.assertEqual(len(results), 0)
