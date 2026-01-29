from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.utils import timezone

from .models import Follow, Message, Comment, ForumCategory, ForumThread, ForumPost, Activity
from .forms import MessageForm, CommentForm, ThreadForm, PostForm


@login_required
def follow_user(request, username):
    """Follow/unfollow a user"""
    user_to_follow = get_object_or_404(User, username=username)

    if request.user == user_to_follow:
        messages.error(request, "You cannot follow yourself.")
        return redirect('accounts:profile', username=username)

    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=user_to_follow
    )

    if not created:
        follow.delete()
        is_following = False
    else:
        is_following = True
        # Create activity
        Activity.objects.create(
            user=request.user,
            activity_type='follow',
            content=f"Started following {user_to_follow.username}",
            target_user=user_to_follow,
        )

    if request.headers.get('HX-Request'):
        return JsonResponse({'is_following': is_following})

    return redirect('accounts:profile', username=username)


@login_required
def activity_feed(request):
    """Activity feed from followed users"""
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list('following_id', flat=True)

    activities = Activity.objects.filter(
        user_id__in=following_ids
    ).select_related('user', 'listing', 'target_user').order_by('-created')

    paginator = Paginator(activities, 50)
    page = request.GET.get('page')
    activities = paginator.get_page(page)

    context = {
        'activities': activities,
    }
    return render(request, 'social/activity_feed.html', context)


# Messages
@login_required
def inbox(request):
    """User's message inbox"""
    received = Message.objects.filter(
        recipient=request.user,
        parent=None  # Only top-level messages
    ).select_related('sender').order_by('-created')

    unread_count = received.filter(read=False).count()

    paginator = Paginator(received, 20)
    page = request.GET.get('page')
    received = paginator.get_page(page)

    context = {
        'messages': received,
        'unread_count': unread_count,
        'active_tab': 'inbox',
    }
    return render(request, 'social/inbox.html', context)


@login_required
def sent_messages(request):
    """User's sent messages"""
    sent = Message.objects.filter(
        sender=request.user,
        parent=None
    ).select_related('recipient').order_by('-created')

    paginator = Paginator(sent, 20)
    page = request.GET.get('page')
    sent = paginator.get_page(page)

    context = {
        'messages': sent,
        'active_tab': 'sent',
    }
    return render(request, 'social/inbox.html', context)


@login_required
def message_detail(request, pk):
    """View message thread"""
    message = get_object_or_404(Message, pk=pk)

    # Check access
    if request.user not in [message.sender, message.recipient]:
        raise Http404()

    # Mark as read
    if message.recipient == request.user and not message.read:
        message.read = True
        message.read_at = timezone.now()
        message.save()

    # Get replies
    replies = message.replies.all().order_by('created')

    context = {
        'message': message,
        'replies': replies,
    }
    return render(request, 'social/message_detail.html', context)


@login_required
def compose_message(request, username=None):
    """Compose new message"""
    recipient = None
    if username:
        recipient = get_object_or_404(User, username=username)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        recipient_username = request.POST.get('recipient')
        recipient = get_object_or_404(User, username=recipient_username)

        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.recipient = recipient
            message.save()
            messages.success(request, 'Message sent!')
            return redirect('social:inbox')
    else:
        form = MessageForm()

    context = {
        'form': form,
        'recipient': recipient,
    }
    return render(request, 'social/compose.html', context)


@login_required
def reply_message(request, pk):
    """Reply to message"""
    parent = get_object_or_404(Message, pk=pk)

    # Check access
    if request.user not in [parent.sender, parent.recipient]:
        raise Http404()

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            # Determine recipient (the other person in the conversation)
            recipient = parent.sender if parent.recipient == request.user else parent.recipient

            Message.objects.create(
                sender=request.user,
                recipient=recipient,
                content=content,
                parent=parent,
            )

    return redirect('social:message_detail', pk=pk)


# Comments
@login_required
def add_comment(request, listing_pk):
    """Add comment to listing"""
    from marketplace.models import Listing
    listing = get_object_or_404(Listing, pk=listing_pk)

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.listing = listing
            comment.author = request.user

            parent_id = request.POST.get('parent')
            if parent_id:
                comment.parent = get_object_or_404(Comment, pk=parent_id)

            comment.save()

    return redirect('marketplace:listing_detail', pk=listing_pk)


# Forums
def forum_index(request):
    """Forum home - list categories"""
    categories = ForumCategory.objects.all().order_by('order')

    context = {
        'categories': categories,
    }
    return render(request, 'social/forum_index.html', context)


def forum_category(request, slug):
    """Forum category - list threads"""
    category = get_object_or_404(ForumCategory, slug=slug)
    threads = category.threads.select_related('author', 'last_post_by')

    paginator = Paginator(threads, 25)
    page = request.GET.get('page')
    threads = paginator.get_page(page)

    context = {
        'category': category,
        'threads': threads,
    }
    return render(request, 'social/forum_category.html', context)


def thread_detail(request, pk):
    """View thread and posts"""
    thread = get_object_or_404(ForumThread.objects.select_related('category', 'author'), pk=pk)

    # Increment views
    ForumThread.objects.filter(pk=pk).update(views=F('views') + 1)

    posts = thread.posts.select_related('author').order_by('created')

    paginator = Paginator(posts, 25)
    page = request.GET.get('page')
    posts = paginator.get_page(page)

    # Reply form
    reply_form = PostForm() if request.user.is_authenticated and not thread.locked else None

    context = {
        'thread': thread,
        'posts': posts,
        'reply_form': reply_form,
    }
    return render(request, 'social/thread_detail.html', context)


@login_required
def create_thread(request, slug):
    """Create new thread"""
    category = get_object_or_404(ForumCategory, slug=slug)

    if request.method == 'POST':
        form = ThreadForm(request.POST)
        if form.is_valid():
            thread = form.save(commit=False)
            thread.category = category
            thread.author = request.user
            thread.last_post_by = request.user
            thread.save()

            # Create first post
            ForumPost.objects.create(
                thread=thread,
                author=request.user,
                content=form.cleaned_data['content']
            )

            return redirect('social:thread_detail', pk=thread.pk)
    else:
        form = ThreadForm()

    context = {
        'form': form,
        'category': category,
    }
    return render(request, 'social/create_thread.html', context)


@login_required
def reply_thread(request, pk):
    """Reply to thread"""
    thread = get_object_or_404(ForumThread, pk=pk)

    if thread.locked:
        messages.error(request, "This thread is locked.")
        return redirect('social:thread_detail', pk=pk)

    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.author = request.user
            post.save()

    return redirect('social:thread_detail', pk=pk)


@login_required
def edit_post(request, pk):
    """Edit forum post"""
    post = get_object_or_404(ForumPost, pk=pk)

    if post.author != request.user and not request.user.is_staff:
        raise Http404()

    if post.thread.locked:
        messages.error(request, "This thread is locked.")
        return redirect('social:thread_detail', pk=post.thread.pk)

    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            post.edited = True
            post.save()
            return redirect('social:thread_detail', pk=post.thread.pk)
    else:
        form = PostForm(instance=post)

    context = {
        'form': form,
        'post': post,
    }
    return render(request, 'social/edit_post.html', context)
