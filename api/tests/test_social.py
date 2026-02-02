"""
Tests for social API - follows, messages, forums.
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from social.models import Follow, Message, ForumCategory, ForumThread


class FollowAPITests(TestCase):
    """Tests for follow API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_follow_user(self):
        """Should follow a user."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/social/follow/{self.other_user.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Follow.objects.filter(follower=self.user, following=self.other_user).exists()
        )

    def test_cannot_follow_self(self):
        """Should not allow following self."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/social/follow/{self.user.pk}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unfollow_user(self):
        """Should unfollow a user."""
        Follow.objects.create(follower=self.user, following=self.other_user)
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(f'/api/v1/social/follow/{self.other_user.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Follow.objects.filter(follower=self.user, following=self.other_user).exists()
        )

    def test_check_if_following(self):
        """Should check if following a user."""
        Follow.objects.create(follower=self.user, following=self.other_user)
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(f'/api/v1/social/follow/{self.other_user.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_following'])

    def test_get_following_list(self):
        """Should get list of users being followed."""
        Follow.objects.create(follower=self.user, following=self.other_user)
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/social/following/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_followers_list(self):
        """Should get list of followers."""
        Follow.objects.create(follower=self.other_user, following=self.user)
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/social/followers/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_activity_feed(self):
        """Should get activity feed from followed users."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/social/feed/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class MessageAPITests(TestCase):
    """Tests for messaging API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@test.com',
            password='testpass123'
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_get_conversations(self):
        """Should get list of conversations."""
        Message.objects.create(
            sender=self.user,
            recipient=self.other_user,
            content='Hello!',
        )
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/v1/social/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_messages_with_user(self):
        """Should get messages with specific user."""
        Message.objects.create(
            sender=self.user,
            recipient=self.other_user,
            content='Hello!',
        )
        Message.objects.create(
            sender=self.other_user,
            recipient=self.user,
            content='Hi there!',
        )
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(f'/api/v1/social/messages/{self.other_user.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_send_message(self):
        """Should send message to user."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/social/messages/{self.other_user.pk}/', {
            'content': 'Hey, interested in your listing',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_messages_require_auth(self):
        """Should require authentication for messages."""
        response = self.client.get('/api/v1/social/messages/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ForumAPITests(TestCase):
    """Tests for forum API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.category = ForumCategory.objects.create(
            name='General Discussion',
            slug='general',
            description='General discussions',
        )

    def get_token(self):
        """Get JWT token."""
        response = self.client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'testpass123',
        })
        return response.data['access']

    def test_list_forum_categories(self):
        """Should list forum categories publicly."""
        response = self.client.get('/api/v1/social/forums/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_get_forum_category_detail(self):
        """Should get forum category detail."""
        response = self.client.get(f'/api/v1/social/forums/{self.category.slug}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_threads_in_category(self):
        """Should list threads in a category."""
        ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Test Thread',
        )
        response = self.client.get(f'/api/v1/social/forums/{self.category.slug}/threads/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_thread_authenticated(self):
        """Should create thread when authenticated."""
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/social/forums/{self.category.slug}/threads/', {
            'title': 'New Thread',
            'content': 'Thread content here',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_thread_unauthenticated(self):
        """Should reject unauthenticated thread creation."""
        response = self.client.post(f'/api/v1/social/forums/{self.category.slug}/threads/', {
            'title': 'New Thread',
            'content': 'Thread content',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_thread_detail(self):
        """Should get thread detail with posts."""
        thread = ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Test Thread',
        )
        response = self.client.get(f'/api/v1/social/threads/{thread.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_thread_view_count_increments(self):
        """Should increment thread view count."""
        thread = ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Test Thread',
        )
        initial_views = thread.views
        self.client.get(f'/api/v1/social/threads/{thread.pk}/')
        thread.refresh_from_db()
        self.assertEqual(thread.views, initial_views + 1)

    def test_reply_to_thread(self):
        """Should reply to thread when authenticated."""
        thread = ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Test Thread',
        )
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/social/threads/{thread.pk}/posts/', {
            'content': 'This is a reply',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cannot_reply_to_locked_thread(self):
        """Should not allow replies to locked thread."""
        thread = ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Locked Thread',
            locked=True,
        )
        token = self.get_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(f'/api/v1/social/threads/{thread.pk}/posts/', {
            'content': 'Trying to reply',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
