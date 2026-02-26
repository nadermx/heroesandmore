"""
Tests for custom error pages.
"""
from django.test import TestCase, Client, override_settings


class ErrorPageTests(TestCase):
    """Tests for custom error pages."""

    def setUp(self):
        self.client = Client()

    def test_404_page_renders(self):
        """Should render custom 404 page for non-existent URLs."""
        response = self.client.get('/this-page-does-not-exist-12345/')
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    def test_404_contains_helpful_links(self):
        """404 page should contain a link back to the home page."""
        response = self.client.get('/this-page-does-not-exist-12345/')
        content = response.content.decode()
        self.assertIn('Go to home', content)
        self.assertIn('href="/"', content)

    def test_403_template_exists(self):
        """403 template should exist and be valid."""
        from django.template.loader import get_template
        template = get_template('403.html')
        self.assertIsNotNone(template)

    def test_500_template_exists(self):
        """500 template should exist and be valid."""
        from django.template.loader import get_template
        template = get_template('500.html')
        self.assertIsNotNone(template)

    def test_404_template_exists(self):
        """404 template should exist and be valid."""
        from django.template.loader import get_template
        template = get_template('404.html')
        self.assertIsNotNone(template)

    def test_error_pages_are_standalone(self):
        """Error pages should not depend on base template context."""
        from django.template.loader import render_to_string

        # These should render without any context (standalone HTML)
        for template_name in ['404.html', '403.html', '500.html']:
            try:
                content = render_to_string(template_name, {})
                self.assertIn('<!doctype html>', content)
                self.assertIn('Go to home', content)
            except Exception as e:
                self.fail(f"Error page {template_name} failed to render: {e}")

    def test_500_page_content(self):
        """500 page should tell user something went wrong."""
        from django.template.loader import render_to_string
        content = render_to_string('500.html', {})
        self.assertIn('Something went wrong', content)
