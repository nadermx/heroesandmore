import django_filters
from marketplace.models import Listing, Order


class ListingFilter(django_filters.FilterSet):
    """Filter for listings"""
    min_price = django_filters.NumberFilter(field_name='price', lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name='price', lookup_expr='lte')
    category = django_filters.CharFilter(field_name='category__slug')
    condition = django_filters.CharFilter(field_name='condition')
    listing_type = django_filters.CharFilter(field_name='listing_type')
    grading_service = django_filters.CharFilter(field_name='grading_service')
    min_grade = django_filters.NumberFilter(field_name='grade', lookup_expr='gte')
    seller = django_filters.CharFilter(field_name='seller__username')
    is_graded = django_filters.BooleanFilter(field_name='is_graded')

    class Meta:
        model = Listing
        fields = [
            'category', 'condition', 'listing_type', 'grading_service',
            'min_price', 'max_price', 'seller', 'is_graded'
        ]


class OrderFilter(django_filters.FilterSet):
    """Filter for orders"""
    status = django_filters.CharFilter(field_name='status')
    role = django_filters.CharFilter(method='filter_by_role')

    class Meta:
        model = Order
        fields = ['status']

    def filter_by_role(self, queryset, name, value):
        user = self.request.user
        if value == 'buyer':
            return queryset.filter(buyer=user)
        elif value == 'seller':
            return queryset.filter(seller=user)
        return queryset
