from django.urls import path
from . import views

app_name = 'social_api'

urlpatterns = [
    # Activity feed
    path('feed/', views.ActivityFeedView.as_view(), name='feed'),

    # Following/followers
    path('following/', views.FollowingListView.as_view(), name='following'),
    path('followers/', views.FollowersListView.as_view(), name='followers'),
    path('follow/<int:user_id>/', views.FollowUserView.as_view(), name='follow'),

    # Messages
    path('messages/', views.ConversationsListView.as_view(), name='conversations'),
    path('messages/<int:user_id>/', views.MessagesView.as_view(), name='messages'),

    # Forums
    path('forums/', views.ForumCategoryListView.as_view(), name='forum_categories'),
    path('forums/<slug:slug>/', views.ForumCategoryDetailView.as_view(), name='forum_category'),
    path('forums/<slug:slug>/threads/', views.ForumThreadListView.as_view(), name='forum_threads'),
    path('threads/<int:pk>/', views.ForumThreadDetailView.as_view(), name='thread_detail'),
    path('threads/<int:pk>/posts/', views.ForumPostCreateView.as_view(), name='create_post'),
    path('posts/<int:post_pk>/', views.ForumPostUpdateView.as_view(), name='update_post'),
]
