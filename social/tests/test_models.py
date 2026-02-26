"""
Tests for social app - forums, messaging, follows.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from social.models import Follow, Message, ForumCategory, ForumThread, ForumPost


class FollowModelTests(TestCase):
    """Tests for Follow model."""

    def setUp(self):
        self.user1 = User.objects.create_user('user1', 'user1@test.com', 'pass123')
        self.user2 = User.objects.create_user('user2', 'user2@test.com', 'pass123')

    def test_follow_creation(self):
        """Should create follow relationship."""
        follow = Follow.objects.create(follower=self.user1, following=self.user2)
        self.assertEqual(follow.follower, self.user1)
        self.assertEqual(follow.following, self.user2)

    def test_follow_unique(self):
        """Should prevent duplicate follows."""
        Follow.objects.create(follower=self.user1, following=self.user2)
        with self.assertRaises(Exception):
            Follow.objects.create(follower=self.user1, following=self.user2)


class MessageModelTests(TestCase):
    """Tests for Message model."""

    def setUp(self):
        self.sender = User.objects.create_user('sender', 'sender@test.com', 'pass123')
        self.recipient = User.objects.create_user('recipient', 'recipient@test.com', 'pass123')

    def test_message_creation(self):
        """Should create message."""
        msg = Message.objects.create(
            sender=self.sender,
            recipient=self.recipient,
            content='Hello there!',
        )
        self.assertEqual(msg.sender, self.sender)
        self.assertEqual(msg.content, 'Hello there!')
        self.assertFalse(msg.read)


class ForumModelTests(TestCase):
    """Tests for forum models."""

    def setUp(self):
        self.user = User.objects.create_user('forumuser', 'forum@test.com', 'pass123')
        self.category = ForumCategory.objects.create(
            name='General Discussion',
            slug='general',
            description='General discussions',
        )

    def test_category_creation(self):
        """Should create forum category."""
        self.assertEqual(self.category.name, 'General Discussion')

    def test_thread_creation(self):
        """Should create forum thread."""
        thread = ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Test Thread',
        )
        self.assertEqual(thread.title, 'Test Thread')
        self.assertEqual(thread.author, self.user)

    def test_post_creation(self):
        """Should create forum post."""
        thread = ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Test Thread',
        )
        post = ForumPost.objects.create(
            thread=thread,
            author=self.user,
            content='This is a post',
        )
        self.assertEqual(post.content, 'This is a post')


class SocialViewTests(TestCase):
    """Tests for social views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('socialuser', 'social@test.com', 'pass123')
        self.category = ForumCategory.objects.create(
            name='General',
            slug='general',
        )

    def test_forums_home_loads(self):
        """Forums home should load."""
        response = self.client.get('/social/forums/')
        self.assertIn(response.status_code, [200, 302])

    def test_forum_category_loads(self):
        """Forum category should load."""
        response = self.client.get(f'/social/forums/{self.category.slug}/')
        self.assertIn(response.status_code, [200, 404])

    def test_messages_requires_login(self):
        """Messages should require login."""
        response = self.client.get('/social/messages/')
        self.assertEqual(response.status_code, 302)

    def test_messages_loads_for_logged_in(self):
        """Messages should load for logged in user."""
        self.client.login(username='socialuser', password='pass123')
        response = self.client.get('/social/messages/')
        self.assertIn(response.status_code, [200, 302])


class ForumThreadDetailTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('poster', 'poster@test.com', 'pass123')
        self.category = ForumCategory.objects.create(name='General', slug='general')
        self.thread = ForumThread.objects.create(
            category=self.category,
            author=self.user,
            title='Thread Title',
            last_post_by=self.user,
        )
        self.first_post = ForumPost.objects.create(
            thread=self.thread,
            author=self.user,
            content='First post content',
        )

    def test_thread_detail_shows_first_post_content(self):
        response = self.client.get(f'/social/thread/{self.thread.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'First post content')

    def test_reply_thread_creates_post(self):
        self.client.login(username='poster', password='pass123')
        response = self.client.post(
            f'/social/thread/{self.thread.pk}/reply/',
            {'content': 'Reply body'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ForumPost.objects.filter(thread=self.thread, content='Reply body').exists()
        )
