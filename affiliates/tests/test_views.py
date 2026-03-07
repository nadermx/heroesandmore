from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from affiliates.models import Affiliate, Referral


class AffiliateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@example.com', 'pass123')
        self.client.login(username='testuser', password='pass123')

    def test_join_page(self):
        response = self.client.get(reverse('affiliates:join'))
        self.assertEqual(response.status_code, 200)

    def test_join_creates_affiliate(self):
        response = self.client.post(reverse('affiliates:join'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Affiliate.objects.filter(user=self.user).exists())

    def test_join_redirects_if_already_affiliate(self):
        Affiliate.objects.create(user=self.user)
        response = self.client.get(reverse('affiliates:join'))
        self.assertRedirects(response, reverse('affiliates:dashboard'))

    def test_dashboard_requires_affiliate(self):
        response = self.client.get(reverse('affiliates:dashboard'))
        self.assertRedirects(response, reverse('affiliates:join'))

    def test_dashboard_renders(self):
        Affiliate.objects.create(user=self.user)
        response = self.client.get(reverse('affiliates:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Affiliate Dashboard')

    def test_payout_settings(self):
        Affiliate.objects.create(user=self.user)
        response = self.client.post(reverse('affiliates:settings'), {'paypal_email': 'test@paypal.com'})
        self.assertEqual(response.status_code, 302)
        self.user.affiliate.refresh_from_db()
        self.assertEqual(self.user.affiliate.paypal_email, 'test@paypal.com')

    def test_requires_login(self):
        self.client.logout()
        for url_name in ['affiliates:dashboard', 'affiliates:join', 'affiliates:referrals', 'affiliates:commissions', 'affiliates:payouts', 'affiliates:settings']:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 302, f"{url_name} should redirect to login")


class AffiliateMiddlewareTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.aff_user = User.objects.create_user('affiliate', 'aff@example.com', 'pass123')
        self.affiliate = Affiliate.objects.create(user=self.aff_user)

    def test_ref_cookie_set(self):
        response = self.client.get(f'/?ref={self.affiliate.referral_code}')
        self.assertEqual(response.cookies.get('ham_ref').value, self.affiliate.referral_code)

    def test_invalid_ref_no_cookie(self):
        response = self.client.get('/?ref=INVALID123')
        self.assertNotIn('ham_ref', response.cookies)

    def test_inactive_affiliate_no_cookie(self):
        self.affiliate.is_active = False
        self.affiliate.save()
        response = self.client.get(f'/?ref={self.affiliate.referral_code}')
        self.assertNotIn('ham_ref', response.cookies)
