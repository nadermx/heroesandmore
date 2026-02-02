"""
Tests for API authentication - JWT tokens.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status


class JWTAuthenticationTests(TestCase):
    """Tests for JWT authentication."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='apiuser',
            email='api@test.com',
            password='testpass123'
        )

    def test_obtain_token_with_valid_credentials(self):
        """Should return tokens with valid credentials."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'apiuser',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_obtain_token_with_invalid_credentials(self):
        """Should reject invalid credentials."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'apiuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        """Should refresh access token."""
        # First get tokens
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'apiuser',
            'password': 'testpass123',
        })
        refresh_token = response.data['refresh']
        
        # Then refresh
        response = self.client.post('/api/v1/auth/token/refresh/', {
            'refresh': refresh_token,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_access_protected_endpoint_without_token(self):
        """Should reject requests without token."""
        response = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_protected_endpoint_with_token(self):
        """Should allow requests with valid token."""
        # Get token
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'apiuser',
            'password': 'testpass123',
        })
        access_token = response.data['access']

        # Use token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PasswordResetTests(TestCase):
    """Tests for password reset endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='resetuser',
            email='reset@test.com',
            password='oldpassword123'
        )

    def test_password_reset_request(self):
        """Should accept password reset request."""
        response = self.client.post('/api/v1/auth/password/reset/', {
            'email': 'reset@test.com',
        })
        # Should always return success to prevent email enumeration
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    def test_password_reset_request_invalid_email(self):
        """Should still return success for non-existent email."""
        response = self.client.post('/api/v1/auth/password/reset/', {
            'email': 'nonexistent@test.com',
        })
        # Should return success to prevent email enumeration
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_invalid_token(self):
        """Should reject invalid reset token."""
        response = self.client.post('/api/v1/auth/password/reset/confirm/', {
            'uid': 'invalid',
            'token': 'invalid',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordChangeTests(TestCase):
    """Tests for password change endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='changeuser',
            email='change@test.com',
            password='oldpassword123'
        )

    def get_token(self):
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'changeuser',
            'password': 'oldpassword123',
        })
        return response.data['access']

    def test_password_change_requires_auth(self):
        """Should require authentication."""
        response = self.client.post('/api/v1/auth/password/change/', {
            'old_password': 'oldpassword123',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_change_success(self):
        """Should change password with valid credentials."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.get_token()}')
        response = self.client.post('/api/v1/auth/password/change/', {
            'old_password': 'oldpassword123',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify old password no longer works
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'changeuser',
            'password': 'oldpassword123',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Verify new password works
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'changeuser',
            'password': 'newpassword123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_change_wrong_old_password(self):
        """Should reject wrong old password."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.get_token()}')
        response = self.client.post('/api/v1/auth/password/change/', {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
