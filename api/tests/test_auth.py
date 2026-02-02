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
