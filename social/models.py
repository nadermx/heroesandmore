from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse

from marketplace.models import Listing


class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['follower', 'following']

    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    # For threaded messages
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username}"


class Comment(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(max_length=1000)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created']

    def __str__(self):
        return f"Comment by {self.author.username} on {self.listing.title}"


class ForumCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = 'Forum categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('social:forum_category', kwargs={'slug': self.slug})

    def thread_count(self):
        return self.threads.count()

    def post_count(self):
        return ForumPost.objects.filter(thread__category=self).count()


class ForumThread(models.Model):
    category = models.ForeignKey(ForumCategory, on_delete=models.CASCADE, related_name='threads')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_threads')
    title = models.CharField(max_length=200)
    pinned = models.BooleanField(default=False)
    locked = models.BooleanField(default=False)
    views = models.PositiveIntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    last_post_at = models.DateTimeField(auto_now_add=True)
    last_post_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='last_posts'
    )

    class Meta:
        ordering = ['-pinned', '-last_post_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('social:thread_detail', kwargs={'pk': self.pk})

    def reply_count(self):
        return self.posts.count() - 1  # Exclude first post


class ForumPost(models.Model):
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name='posts')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='forum_posts')
    content = models.TextField()

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    edited = models.BooleanField(default=False)

    class Meta:
        ordering = ['created']

    def __str__(self):
        return f"Post by {self.author.username} in {self.thread.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update thread last post info
        self.thread.last_post_at = self.created
        self.thread.last_post_by = self.author
        self.thread.save(update_fields=['last_post_at', 'last_post_by'])


class Activity(models.Model):
    """Activity feed for followed users"""
    ACTIVITY_TYPES = [
        ('listing', 'New Listing'),
        ('sale', 'Made a Sale'),
        ('collection', 'Added to Collection'),
        ('follow', 'Started Following'),
        ('review', 'Left a Review'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    content = models.CharField(max_length=255)
    link = models.CharField(max_length=200, blank=True)
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, blank=True)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='mentioned_in')

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f"{self.user.username}: {self.content}"
