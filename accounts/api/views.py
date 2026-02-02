from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

from accounts.models import Profile, RecentlyViewed
from .serializers import (
    ProfileSerializer, PublicProfileSerializer, ProfileUpdateSerializer,
    RegisterSerializer, ChangePasswordSerializer, RecentlyViewedSerializer,
    DeviceTokenSerializer
)


class RegisterView(generics.CreateAPIView):
    """
    Register a new user account.
    Returns JWT tokens on successful registration.
    """
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    """
    Get or update the current user's profile.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProfileUpdateSerializer
        return ProfileSerializer

    def get_object(self):
        return self.request.user.profile


class AvatarUploadView(views.APIView):
    """
    Upload avatar image for current user.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        profile = request.user.profile
        if 'avatar' not in request.FILES:
            return Response(
                {'error': 'No avatar file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        profile.avatar = request.FILES['avatar']
        profile.save()

        serializer = ProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)


class ChangePasswordView(views.APIView):
    """
    Change password for current user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Wrong password'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'message': 'Password changed successfully'})


class PublicProfileView(generics.RetrieveAPIView):
    """
    Get public profile by username.
    """
    serializer_class = PublicProfileSerializer
    permission_classes = [AllowAny]
    lookup_field = 'user__username'
    lookup_url_kwarg = 'username'

    def get_queryset(self):
        return Profile.objects.filter(is_public=True)


class UserListingsView(generics.ListAPIView):
    """
    Get active listings for a user.
    """
    permission_classes = [AllowAny]

    def get_queryset(self):
        from marketplace.models import Listing
        username = self.kwargs['username']
        return Listing.objects.filter(
            seller__username=username,
            status='active'
        ).order_by('-created')

    def get_serializer_class(self):
        from marketplace.api.serializers import ListingListSerializer
        return ListingListSerializer


class UserReviewsView(generics.ListAPIView):
    """
    Get reviews for a user.
    """
    permission_classes = [AllowAny]

    def get_queryset(self):
        from marketplace.models import Review
        username = self.kwargs['username']
        return Review.objects.filter(
            seller__username=username
        ).order_by('-created')

    def get_serializer_class(self):
        from marketplace.api.serializers import ReviewSerializer
        return ReviewSerializer


class RecentlyViewedListView(generics.ListAPIView):
    """
    Get recently viewed listings for current user.
    """
    serializer_class = RecentlyViewedSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return RecentlyViewed.objects.filter(
            user=self.request.user
        ).select_related('listing')[:50]


class RecentlyViewedClearView(views.APIView):
    """
    Clear recently viewed listings.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        RecentlyViewed.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterDeviceTokenView(views.APIView):
    """
    Register device token for push notifications.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DeviceTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Import DeviceToken model (will be created)
        from accounts.models import DeviceToken

        token = serializer.validated_data['token']
        platform = serializer.validated_data['platform']

        # Deactivate any existing tokens with this value
        DeviceToken.objects.filter(token=token).update(active=False)

        # Create or update token for this user
        DeviceToken.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={'platform': platform, 'active': True}
        )

        return Response({'message': 'Device registered successfully'})

    def delete(self, request):
        """Unregister device token"""
        from accounts.models import DeviceToken

        token = request.data.get('token')
        if token:
            DeviceToken.objects.filter(user=request.user, token=token).delete()

        return Response(status=status.HTTP_204_NO_CONTENT)
