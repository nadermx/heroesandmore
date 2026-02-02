from django.urls import path
from . import views

app_name = 'accounts_api'

urlpatterns = [
    # Current user
    path('me/', views.CurrentUserProfileView.as_view(), name='current_profile'),
    path('me/avatar/', views.AvatarUploadView.as_view(), name='avatar_upload'),
    path('me/password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('me/recently-viewed/', views.RecentlyViewedListView.as_view(), name='recently_viewed'),
    path('me/recently-viewed/clear/', views.RecentlyViewedClearView.as_view(), name='clear_recently_viewed'),
    path('me/device/', views.RegisterDeviceTokenView.as_view(), name='device_token'),

    # Registration
    path('register/', views.RegisterView.as_view(), name='register'),

    # Public profiles
    path('profiles/<str:username>/', views.PublicProfileView.as_view(), name='public_profile'),
    path('profiles/<str:username>/listings/', views.UserListingsView.as_view(), name='user_listings'),
    path('profiles/<str:username>/reviews/', views.UserReviewsView.as_view(), name='user_reviews'),
]
