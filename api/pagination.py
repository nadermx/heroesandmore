from rest_framework.pagination import PageNumberPagination, CursorPagination


class StandardResultsPagination(PageNumberPagination):
    """Standard pagination for most endpoints"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class LargeResultsPagination(PageNumberPagination):
    """Larger pagination for browsing endpoints"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class SmallResultsPagination(PageNumberPagination):
    """Smaller pagination for nested/detail endpoints"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class MessagesCursorPagination(CursorPagination):
    """Cursor pagination for messages (infinite scroll)"""
    page_size = 25
    ordering = '-created'
    cursor_query_param = 'cursor'


class ActivityFeedPagination(CursorPagination):
    """Cursor pagination for activity feeds"""
    page_size = 20
    ordering = '-created'
    cursor_query_param = 'cursor'
