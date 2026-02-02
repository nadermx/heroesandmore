from rest_framework import serializers
from user_collections.models import Collection, CollectionItem, CollectionValueSnapshot


class CollectionItemSerializer(serializers.ModelSerializer):
    """Serializer for collection items"""
    item_name = serializers.SerializerMethodField()
    current_value = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    image_url = serializers.SerializerMethodField()
    gain_loss = serializers.SerializerMethodField()
    gain_loss_percent = serializers.SerializerMethodField()

    class Meta:
        model = CollectionItem
        fields = [
            'id', 'item_name', 'name', 'condition', 'grading_company', 'grade',
            'cert_number', 'quantity', 'purchase_price', 'purchase_date',
            'current_value', 'image_url', 'notes', 'gain_loss', 'gain_loss_percent',
            'created'
        ]

    def get_item_name(self, obj):
        return obj.get_name()

    def get_image_url(self, obj):
        image = obj.get_image()
        if image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.url)
            return image.url
        return None

    def get_gain_loss(self, obj):
        gl = obj.get_gain_loss()
        return str(gl) if gl is not None else None

    def get_gain_loss_percent(self, obj):
        glp = obj.get_gain_loss_percent()
        return float(glp) if glp is not None else None


class CollectionItemCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating collection items"""
    class Meta:
        model = CollectionItem
        fields = [
            'name', 'item', 'category', 'description', 'image',
            'price_guide_item', 'condition', 'grading_company', 'grade',
            'cert_number', 'quantity', 'purchase_price', 'purchase_date',
            'current_value', 'notes'
        ]


class CollectionSerializer(serializers.ModelSerializer):
    """Serializer for collections"""
    owner_username = serializers.CharField(source='user.username', read_only=True)
    item_count = serializers.SerializerMethodField()
    total_value = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    gain_loss = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Collection
        fields = [
            'id', 'name', 'description', 'is_public', 'owner_username',
            'cover_image', 'cover_image_url', 'item_count', 'total_value',
            'total_cost', 'gain_loss', 'created', 'updated'
        ]
        read_only_fields = ['total_value', 'total_cost']

    def get_item_count(self, obj):
        return obj.items.count()

    def get_gain_loss(self, obj):
        if obj.total_value and obj.total_cost:
            return str(obj.total_value - obj.total_cost)
        return '0.00'

    def get_cover_image_url(self, obj):
        if obj.cover_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.cover_image.url)
            return obj.cover_image.url
        return None


class CollectionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating collections"""
    class Meta:
        model = Collection
        fields = ['name', 'description', 'is_public', 'cover_image']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class CollectionValueSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for collection value history"""
    gain_loss = serializers.SerializerMethodField()

    class Meta:
        model = CollectionValueSnapshot
        fields = ['date', 'total_value', 'total_cost', 'item_count', 'gain_loss']

    def get_gain_loss(self, obj):
        return str(obj.get_gain_loss())
