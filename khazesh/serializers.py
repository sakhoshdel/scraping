from rest_framework import serializers
from django.utils import timezone
from khazesh.models import Mobile, ProductLaptop, ProductAccessories


class MobileSerilizer(serializers.ModelSerializer):
    instock = serializers.SerializerMethodField(read_only=True)
    brand = serializers.SerializerMethodField(read_only=True)
    price_change = serializers.SerializerMethodField(read_only=True)
    active = serializers.SerializerMethodField(read_only=True)
    capacity = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.CharField(source='title')
    source = serializers.CharField(source='site')
    update_time = serializers.DateTimeField(source='updated_at')
    product_id = serializers.CharField(source='custom_id')
    min_price = serializers.SerializerMethodField(read_only=True)
    validity = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Mobile
        fields = (
            'instock', 'brand', 'full_name', 'model', 'capacity',
            'source', 'min_price', 'color_name', 'color_hex',
            'url', 'seller', 'price_change_time', 'price_change',
            'update_time', 'active', 'vietnam', 'product_id', 'validity',
        )

    def get_min_price(self, obj):
        return int(int(obj.min_price) / 10)

    def get_instock(self, obj):
        current_time = timezone.now()
        return (current_time - obj.updated_at).total_seconds() <= 4 * 3600 + 60

    def get_validity(self, obj):
        return bool(obj.status)

    def get_brand(self, obj):
        return obj.brand.name

    def get_price_change(self, obj):
        if not obj.old_min_price:
            return 0
        return int((int(obj.min_price) - obj.old_min_price) / 10)

    def get_active(self, obj):
        return obj.brand.name.lower() == 'apple' and not obj.not_active

    def get_capacity(self, obj):
        return f'{obj.ram}/{obj.memory}'


class LaptopSerializer(serializers.ModelSerializer):
    instock = serializers.SerializerMethodField(read_only=True)
    brand = serializers.SerializerMethodField(read_only=True)
    price_change = serializers.SerializerMethodField(read_only=True)
    capacity = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.CharField(source='title')
    source = serializers.CharField(source='site')
    update_time = serializers.DateTimeField(source='updated_at')
    product_id = serializers.CharField(source='custom_id')
    min_price = serializers.SerializerMethodField(read_only=True)
    validity = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductLaptop
        fields = (
            'instock', 'brand', 'full_name', 'model', 'capacity',
            'source', 'min_price', 'color_name', 'color_hex',
            'url', 'seller', 'price_change_time', 'price_change',
            'update_time', 'product_id', 'validity',
        )

    def get_min_price(self, obj):
        return int(int(obj.min_price) / 10)

    def get_instock(self, obj):
        return (timezone.now() - obj.updated_at).total_seconds() <= 4 * 3600 + 60

    def get_validity(self, obj):
        return bool(obj.status)

    def get_brand(self, obj):
        return obj.brand.name_fa

    def get_price_change(self, obj):
        if not obj.old_min_price:
            return 0
        return int((int(obj.min_price) - obj.old_min_price) / 10)

    def get_capacity(self, obj):
        return f'{obj.ram}/{obj.storage}' if obj.ram and obj.storage else None


class AccessoriesSerializer(serializers.ModelSerializer):
    instock = serializers.SerializerMethodField(read_only=True)
    brand = serializers.SerializerMethodField(read_only=True)
    category = serializers.SerializerMethodField(read_only=True)
    price_change = serializers.SerializerMethodField(read_only=True)
    full_name = serializers.CharField(source='title')
    source = serializers.CharField(source='site')
    update_time = serializers.DateTimeField(source='updated_at')
    product_id = serializers.CharField(source='custom_id')
    min_price = serializers.SerializerMethodField(read_only=True)
    validity = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductAccessories
        fields = (
            'instock', 'brand', 'category', 'full_name', 'model',
            'source', 'min_price', 'color_name', 'color_hex',
            'url', 'seller', 'price_change_time', 'price_change',
            'update_time', 'product_id', 'validity',
        )

    def get_min_price(self, obj):
        return int(int(obj.min_price) / 10)

    def get_instock(self, obj):
        return (timezone.now() - obj.updated_at).total_seconds() <= 4 * 3600 + 60

    def get_validity(self, obj):
        return bool(obj.status)

    def get_brand(self, obj):
        return obj.brand.name_fa

    def get_category(self, obj):
        return obj.category.name_fa

    def get_price_change(self, obj):
        if not obj.old_min_price:
            return 0
        return int((int(obj.min_price) - obj.old_min_price) / 10)
