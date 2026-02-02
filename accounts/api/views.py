from rest_framework import generics, status, views
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings

from accounts.models import Profile, RecentlyViewed
from .serializers import (
    ProfileSerializer, PublicProfileSerializer, ProfileUpdateSerializer,
    RegisterSerializer, ChangePasswordSerializer, RecentlyViewedSerializer,
    DeviceTokenSerializer, GoogleAuthSerializer, PasswordResetSerializer,
    PasswordResetConfirmSerializer, NotificationSettingsSerializer
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


class GoogleAuthView(views.APIView):
    """
    Authenticate with Google OAuth.
    Expects an id_token from Google Sign-In.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token = serializer.validated_data['id_token']

        try:
            # Verify the token with Google
            from google.oauth2 import id_token as google_id_token
            from google.auth.transport import requests as google_requests

            idinfo = google_id_token.verify_oauth2_token(
                id_token,
                google_requests.Request(),
                getattr(settings, 'GOOGLE_CLIENT_ID', None)
            )

            email = idinfo.get('email')
            if not email:
                return Response(
                    {'error': 'Email not provided by Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0][:30],
                    'first_name': idinfo.get('given_name', ''),
                    'last_name': idinfo.get('family_name', ''),
                }
            )

            # Handle username collision for new users
            if created:
                base_username = user.username
                counter = 1
                while User.objects.filter(username=user.username).exclude(pk=user.pk).exists():
                    user.username = f"{base_username}{counter}"
                    counter += 1
                user.save()

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
                },
                'created': created,
            })

        except ValueError as e:
            return Response(
                {'error': 'Invalid Google token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except ImportError:
            return Response(
                {'error': 'Google authentication not configured'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )


class PasswordResetView(views.APIView):
    """
    Request a password reset email.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email__iexact=email)
            # Generate token and uid
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Send reset email
            reset_url = f"{getattr(settings, 'FRONTEND_URL', 'https://heroesandmore.com')}/reset-password/{uid}/{token}/"

            send_mail(
                subject='Reset your HeroesAndMore password',
                message=f'Click the link to reset your password: {reset_url}',
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@mail.heroesandmore.com'),
                recipient_list=[email],
                fail_silently=True,
            )
        except User.DoesNotExist:
            # Don't reveal whether email exists
            pass

        # Always return success to prevent email enumeration
        return Response({
            'message': 'If an account exists with this email, a password reset link has been sent.'
        })


class PasswordResetConfirmView(views.APIView):
    """
    Confirm password reset with token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            uid = force_str(urlsafe_base64_decode(serializer.validated_data['uid']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {'error': 'Invalid reset link'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not default_token_generator.check_token(user, serializer.validated_data['token']):
            return Response(
                {'error': 'Invalid or expired reset link'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({'message': 'Password has been reset successfully'})


class NotificationSettingsView(views.APIView):
    """
    Get or update notification settings.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = NotificationSettingsSerializer(request.user.profile)
        return Response(serializer.data)

    def patch(self, request):
        serializer = NotificationSettingsSerializer(
            request.user.profile,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserCollectionsView(generics.ListAPIView):
    """
    Get public collections for a user.
    """
    permission_classes = [AllowAny]

    def get_queryset(self):
        from user_collections.models import Collection
        username = self.kwargs['username']
        return Collection.objects.filter(
            user__username=username,
            is_public=True
        ).order_by('-updated')

    def get_serializer_class(self):
        from user_collections.api.serializers import CollectionSerializer
        return CollectionSerializer
