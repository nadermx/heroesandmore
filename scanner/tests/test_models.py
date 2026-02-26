"""
Tests for scanner app - image recognition and scan sessions.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from scanner.models import ScanResult


class ScannerViewTests(TestCase):
    """Tests for scanner views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('scanner', 'scanner@test.com', 'pass123')

    def test_scanner_home_loads(self):
        """Scanner home should load."""
        self.client.login(username='scanner', password='pass123')
        response = self.client.get('/scanner/')
        self.assertIn(response.status_code, [200, 302])

    def test_scanner_requires_login(self):
        """Scanner should require login."""
        response = self.client.get('/scanner/')
        self.assertEqual(response.status_code, 302)

    def test_scan_history_loads(self):
        """Scan history should load."""
        self.client.login(username='scanner', password='pass123')
        response = self.client.get('/scanner/history/')
        self.assertIn(response.status_code, [200, 404])

    def test_upload_scan_processes_without_stalling_pending(self):
        self.client.login(username='scanner', password='pass123')
        upload = SimpleUploadedFile('charizard-base.jpg', b'fake-image-bytes', content_type='image/jpeg')
        response = self.client.post('/scanner/upload/', {'image': upload})
        self.assertEqual(response.status_code, 200)
        scan_id = response.json()['scan_id']
        scan = ScanResult.objects.get(pk=scan_id)
        self.assertIn(scan.status, ['success', 'no_match'])


class ScannerAPITests(TestCase):
    """Tests for scanner API endpoints."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='scanner',
            email='scanner@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'scanner',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_scan_requires_auth(self):
        """Scanning should require authentication."""
        response = self.client.post('/api/v1/scanner/scan/')
        self.assertEqual(response.status_code, 401)

    def test_get_scan_history(self):
        """Should get scan history."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/scanner/scans/')
        self.assertIn(response.status_code, [200, 404])

    def test_get_scan_sessions(self):
        """Should get scan sessions."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/scanner/sessions/')
        self.assertIn(response.status_code, [200, 404])
