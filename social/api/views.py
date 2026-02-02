from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.db.models import Q, Max, Count
from django.utils import timezone

from social.models import (
    Follow, Message, Comment, ForumCategory, ForumThread, ForumPost, Activity
)
from api.pagination import StandardResultsPagination, MessagesCursorPagination, ActivityFeedPagination
from api.permissions import IsOwnerOrReadOnly
from .serializers import (
    FollowSerializer, MessageSerializer, MessageCreateSerializer,
    ConversationSerializer, CommentSerializer,
    ForumCategorySerializer, ForumThreadListSerializer, ForumThreadDetailSerializer,
    ForumPostSerializer, ActivitySerializer, UserMinimalSerializer
)


class ActivityFeedView(generics.ListAPIView):
    """Get activity feed from followed users"""
    serializer_class = ActivitySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ActivityFeedPagination

    def get_queryset(self):
        # Get users the current user follows
        following_ids = Follow.objects.filter(
            follower=self.request.user
        ).values_list('following_id', flat=True)

        return Activity.objects.filter(
            user_id__in=following_ids
        ).select_related('user')


class FollowingListView(generics.ListAPIView):
    """Get users the current user follows"""
    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Follow.objects.filter(
            follower=self.request.user
        ).select_related('following', 'following__profile')


class FollowersListView(generics.ListAPIView):
    """Get users following the current user"""
    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Follow.objects.filter(
            following=self.request.user
        ).select_related('follower', 'follower__profile')


class FollowUserView(APIView):
    """Follow/unfollow a user"""
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        """Follow a user"""
        user_to_follow = get_object_or_404(User, pk=user_id)

        if user_to_follow == request.user:
            return Response(
                {'error': 'Cannot follow yourself'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Follow.objects.get_or_create(
            follower=request.user,
            following=user_to_follow
        )

        return Response({'status': 'following'})

    def delete(self, request, user_id):
        """Unfollow a user"""
        Follow.objects.filter(
            follower=request.user,
            following_id=user_id
        ).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    def get(self, request, user_id):
        """Check if following"""
        is_following = Follow.objects.filter(
            follower=request.user,
            following_id=user_id
        ).exists()

        return Response({'is_following': is_following})


class ConversationsListView(generics.ListAPIView):
    """Get conversations (unique users messaged)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get all users we have messages with
        sent_to = Message.objects.filter(sender=user).values_list('recipient', flat=True)
        received_from = Message.objects.filter(recipient=user).values_list('sender', flat=True)
        user_ids = set(list(sent_to) + list(received_from))

        conversations = []
        for uid in user_ids:
            other_user = User.objects.get(pk=uid)

            # Get last message
            last_msg = Message.objects.filter(
                Q(sender=user, recipient_id=uid) |
                Q(sender_id=uid, recipient=user)
            ).order_by('-created').first()

            # Count unread
            unread = Message.objects.filter(
                sender_id=uid, recipient=user, read=False
            ).count()

            conversations.append({
                'user': UserMinimalSerializer(other_user, context={'request': request}).data,
                'last_message': last_msg.content[:100] if last_msg else '',
                'last_message_at': last_msg.created if last_msg else None,
                'unread_count': unread
            })

        # Sort by last message
        conversations.sort(key=lambda x: x['last_message_at'] or timezone.now(), reverse=True)

        return Response(conversations)


class MessagesView(generics.ListCreateAPIView):
    """Get/send messages with a user"""
    permission_classes = [IsAuthenticated]
    pagination_class = MessagesCursorPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return MessageCreateSerializer
        return MessageSerializer

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        return Message.objects.filter(
            Q(sender=self.request.user, recipient_id=user_id) |
            Q(sender_id=user_id, recipient=self.request.user)
        ).select_related('sender', 'recipient').order_by('-created')

    def list(self, request, *args, **kwargs):
        # Mark messages as read
        user_id = self.kwargs['user_id']
        Message.objects.filter(
            sender_id=user_id, recipient=request.user, read=False
        ).update(read=True, read_at=timezone.now())

        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipient = get_object_or_404(User, pk=self.kwargs['user_id'])

        message = Message.objects.create(
            sender=request.user,
            recipient=recipient,
            content=serializer.validated_data['content'],
            subject=serializer.validated_data.get('subject', ''),
            listing_id=serializer.validated_data.get('listing')
        )

        return Response(
            MessageSerializer(message, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ForumCategoryListView(generics.ListAPIView):
    """List forum categories"""
    serializer_class = ForumCategorySerializer
    permission_classes = [AllowAny]
    queryset = ForumCategory.objects.all()


class ForumCategoryDetailView(generics.RetrieveAPIView):
    """Get forum category with threads"""
    serializer_class = ForumCategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    queryset = ForumCategory.objects.all()


class ForumThreadListView(generics.ListCreateAPIView):
    """List threads in a category or create new thread"""
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ForumThreadDetailSerializer
        return ForumThreadListSerializer

    def get_queryset(self):
        slug = self.kwargs['slug']
        return ForumThread.objects.filter(
            category__slug=slug
        ).select_related('author', 'last_post_by')

    def create(self, request, *args, **kwargs):
        category = get_object_or_404(ForumCategory, slug=self.kwargs['slug'])

        # Create thread
        thread = ForumThread.objects.create(
            category=category,
            author=request.user,
            title=request.data.get('title', '')
        )

        # Create first post
        ForumPost.objects.create(
            thread=thread,
            author=request.user,
            content=request.data.get('content', '')
        )

        serializer = ForumThreadDetailSerializer(thread, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ForumThreadDetailView(generics.RetrieveAPIView):
    """Get thread with posts"""
    serializer_class = ForumThreadDetailSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return ForumThread.objects.prefetch_related('posts', 'posts__author')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Increment views
        instance.views += 1
        instance.save(update_fields=['views'])
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ForumPostCreateView(generics.CreateAPIView):
    """Create a post (reply) in a thread"""
    serializer_class = ForumPostSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        thread = get_object_or_404(ForumThread, pk=self.kwargs['pk'])

        if thread.locked:
            return Response(
                {'error': 'Thread is locked'},
                status=status.HTTP_400_BAD_REQUEST
            )

        post = ForumPost.objects.create(
            thread=thread,
            author=request.user,
            content=request.data.get('content', '')
        )

        serializer = ForumPostSerializer(post, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ForumPostUpdateView(generics.UpdateAPIView, generics.DestroyAPIView):
    """Update or delete a post"""
    serializer_class = ForumPostSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    queryset = ForumPost.objects.all()
    lookup_url_kwarg = 'post_pk'

    def perform_update(self, serializer):
        serializer.save(edited=True)
