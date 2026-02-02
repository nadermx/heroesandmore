from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Permission check for object ownership.
    """
    def has_object_permission(self, request, view, obj):
        # Check various ownership patterns
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'seller'):
            return obj.seller == request.user
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'author'):
            return obj.author == request.user
        return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Allow read for anyone, write only for owner.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check ownership
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'seller'):
            return obj.seller == request.user
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'author'):
            return obj.author == request.user
        return False


class IsSellerOrReadOnly(permissions.BasePermission):
    """
    Allow read for anyone, write only for verified sellers.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user.is_authenticated:
            return False

        # Check if user has profile and is seller verified
        if hasattr(request.user, 'profile'):
            return request.user.profile.stripe_account_complete
        return False


class IsVerifiedSeller(permissions.BasePermission):
    """
    Only allow access for verified sellers.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if hasattr(request.user, 'profile'):
            return request.user.profile.stripe_account_complete
        return False


class IsBuyerOrSeller(permissions.BasePermission):
    """
    Allow access if user is either the buyer or seller of an order.
    """
    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'buyer') and hasattr(obj, 'seller'):
            return obj.buyer == request.user or obj.seller == request.user
        return False
