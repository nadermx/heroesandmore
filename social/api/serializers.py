from rest_framework import serializers
from django.contrib.auth.models import User
from social.models import (
    Follow, Message, Comment, ForumCategory, ForumThread, ForumPost, Activity
)


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user info for social features"""
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'avatar_url']

    def get_avatar_url(self, obj):
        if hasattr(obj, 'profile') and obj.profile.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile.avatar.url)
            return obj.profile.avatar.url
        return None


class FollowSerializer(serializers.ModelSerializer):
    """Serializer for follows"""
    follower = UserMinimalSerializer(read_only=True)
    following = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ['id', 'follower', 'following', 'created']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for messages"""
    sender = UserMinimalSerializer(read_only=True)
    recipient = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'recipient', 'subject', 'content',
            'listing', 'read', 'read_at', 'parent', 'created'
        ]


class MessageCreateSerializer(serializers.Serializer):
    """Serializer for creating messages"""
    content = serializers.CharField(max_length=5000)
    subject = serializers.CharField(max_length=200, required=False, allow_blank=True)
    listing = serializers.IntegerField(required=False, allow_null=True)


class ConversationSerializer(serializers.Serializer):
    """Serializer for conversation list"""
    user = UserMinimalSerializer()
    last_message = serializers.CharField()
    last_message_at = serializers.DateTimeField()
    unread_count = serializers.IntegerField()


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for comments"""
    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'author', 'content', 'parent', 'created', 'updated']


class ForumCategorySerializer(serializers.ModelSerializer):
    """Serializer for forum categories"""
    thread_count = serializers.SerializerMethodField()
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = ForumCategory
        fields = ['id', 'name', 'slug', 'description', 'icon', 'thread_count', 'post_count']

    def get_thread_count(self, obj):
        return obj.thread_count()

    def get_post_count(self, obj):
        return obj.post_count()


class ForumThreadListSerializer(serializers.ModelSerializer):
    """Serializer for thread list"""
    author = UserMinimalSerializer(read_only=True)
    last_post_by = UserMinimalSerializer(read_only=True)
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = ForumThread
        fields = [
            'id', 'title', 'author', 'pinned', 'locked', 'views',
            'reply_count', 'last_post_at', 'last_post_by', 'created'
        ]

    def get_reply_count(self, obj):
        return obj.reply_count()


class ForumPostSerializer(serializers.ModelSerializer):
    """Serializer for forum posts"""
    author = UserMinimalSerializer(read_only=True)

    class Meta:
        model = ForumPost
        fields = ['id', 'author', 'content', 'edited', 'created', 'updated']


class ForumThreadDetailSerializer(serializers.ModelSerializer):
    """Full thread serializer with posts"""
    author = UserMinimalSerializer(read_only=True)
    posts = ForumPostSerializer(many=True, read_only=True)

    class Meta:
        model = ForumThread
        fields = [
            'id', 'category', 'title', 'author', 'pinned', 'locked',
            'views', 'posts', 'created', 'updated'
        ]


class ActivitySerializer(serializers.ModelSerializer):
    """Serializer for activity feed"""
    user = UserMinimalSerializer(read_only=True)
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)

    class Meta:
        model = Activity
        fields = [
            'id', 'user', 'activity_type', 'activity_type_display',
            'content', 'link', 'listing', 'created'
        ]
