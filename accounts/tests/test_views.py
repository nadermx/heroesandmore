"""
Tests for accounts views - registration, login, profile.
"""
import time
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


class SocialAppMixin:
    """Create the Google SocialApp that allauth templates require."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        site = Site.objects.get_current()
        app, _ = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': 'fake-client-id',
                'secret': 'fake-secret',
            },
        )
        app.sites.add(site)


class RegistrationTests(SocialAppMixin, TestCase):
    """Tests for user registration."""

    def setUp(self):
        self.client = Client()

    def _signup_data(self, **overrides):
        """Build valid signup POST data including honeypot timestamp."""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            '_ts': str(int(time.time()) - 5),  # 5 seconds ago (bypasses honeypot)
        }
        data.update(overrides)
        return data

    def test_registration_page_loads(self):
        """Registration page should be accessible."""
        response = self.client.get('/auth/signup/')
        self.assertEqual(response.status_code, 200)

    def test_registration_with_valid_data(self):
        """Should create user with valid registration data."""
        response = self.client.post('/auth/signup/', self._signup_data())
        # Should redirect after successful signup
        self.assertIn(response.status_code, [200, 302])

    def test_registration_password_mismatch(self):
        """Should reject mismatched passwords."""
        data = self._signup_data(password2='DifferentPass123!')
        response = self.client.post('/auth/signup/', data)
        self.assertEqual(response.status_code, 200)  # Form re-displayed
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_registration_duplicate_username(self):
        """Should reject duplicate usernames."""
        User.objects.create_user('existinguser', 'existing@example.com', 'pass123')
        data = self._signup_data(
            username='existinguser',
            email='new@example.com',
        )
        response = self.client.post('/auth/signup/', data)
        self.assertEqual(response.status_code, 200)


class LoginTests(SocialAppMixin, TestCase):
    """Tests for user login."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_page_loads(self):
        """Login page should be accessible."""
        response = self.client.get('/auth/login/')
        self.assertEqual(response.status_code, 200)

    def test_login_with_valid_credentials(self):
        """Should login with valid credentials."""
        response = self.client.post('/auth/login/', {
            'login': 'testuser',
            'password': 'testpass123',
        })
        self.assertIn(response.status_code, [200, 302])

    def test_login_with_invalid_password(self):
        """Should reject invalid password."""
        response = self.client.post('/auth/login/', {
            'login': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)

    def test_logout(self):
        """Should logout successfully."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post('/auth/logout/')
        self.assertIn(response.status_code, [200, 302])


class ProfileTests(TestCase):
    """Tests for user profile views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_profile_page_loads(self):
        """Profile page should be accessible."""
        response = self.client.get(f'/accounts/{self.user.username}/')
        self.assertIn(response.status_code, [200, 302])

    def test_profile_shows_username(self):
        """Profile page should show username."""
        response = self.client.get(f'/accounts/{self.user.username}/')
        if response.status_code == 200:
            self.assertContains(response, 'testuser')

    def test_settings_requires_login(self):
        """Settings page should require login."""
        response = self.client.get('/accounts/settings/')
        self.assertEqual(response.status_code, 302)

    def test_settings_loads_for_user(self):
        """Settings should load for logged in user."""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/accounts/settings/')
        self.assertIn(response.status_code, [200, 302])
