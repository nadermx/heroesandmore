from django.contrib import admin
from .models import Follow, Message, Comment, ForumCategory, ForumThread, ForumPost, Activity


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ['follower', 'following', 'created']
    raw_id_fields = ['follower', 'following']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'subject', 'read', 'created']
    list_filter = ['read', 'created']
    search_fields = ['sender__username', 'recipient__username', 'subject', 'content']
    raw_id_fields = ['sender', 'recipient', 'parent', 'listing']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'listing', 'created']
    list_filter = ['created']
    search_fields = ['author__username', 'content']
    raw_id_fields = ['listing', 'author', 'parent']


@admin.register(ForumCategory)
class ForumCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'thread_count', 'post_count']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'author', 'pinned', 'locked', 'views', 'created']
    list_filter = ['category', 'pinned', 'locked', 'created']
    search_fields = ['title', 'author__username']
    raw_id_fields = ['category', 'author', 'last_post_by']


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ['thread', 'author', 'edited', 'created']
    list_filter = ['edited', 'created']
    search_fields = ['content', 'author__username']
    raw_id_fields = ['thread', 'author']


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['user', 'activity_type', 'content', 'created']
    list_filter = ['activity_type', 'created']
    search_fields = ['user__username', 'content']
    raw_id_fields = ['user', 'listing', 'target_user']
