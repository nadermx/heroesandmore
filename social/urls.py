from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # Following
    path('follow/<str:username>/', views.follow_user, name='follow_user'),
    path('feed/', views.activity_feed, name='activity_feed'),

    # Messages
    path('messages/', views.inbox, name='inbox'),
    path('messages/sent/', views.sent_messages, name='sent_messages'),
    path('messages/compose/', views.compose_message, name='compose'),
    path('messages/compose/<str:username>/', views.compose_message, name='compose_to'),
    path('messages/<int:pk>/', views.message_detail, name='message_detail'),
    path('messages/<int:pk>/reply/', views.reply_message, name='reply_message'),

    # Comments
    path('comment/<int:listing_pk>/', views.add_comment, name='add_comment'),

    # Forums
    path('forums/', views.forum_index, name='forum_index'),
    path('forums/<slug:slug>/', views.forum_category, name='forum_category'),
    path('forums/<slug:slug>/new/', views.create_thread, name='create_thread'),
    path('thread/<int:pk>/', views.thread_detail, name='thread_detail'),
    path('thread/<int:pk>/reply/', views.reply_thread, name='reply_thread'),
    path('post/<int:pk>/edit/', views.edit_post, name='edit_post'),
]
