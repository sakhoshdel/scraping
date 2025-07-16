from rest_framework import serializers
from khazesh.models import Brand, Mobile
from django.utils import timezone

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
        fields = ('instock',
                  'brand',
                  'full_name',
                  'model',
                  'capacity',
                  'source',
                  'min_price',
                  'color_name',
                  'color_hex',
                  'url',
                  'seller',
                  'price_change_time',
                  'price_change',
                  'update_time',
                  'active',
                  'vietnam',
                  'product_id',
                  'product_id',
                  'validity',
                  )
        
        
    def get_min_price(self, obj):
        return int(int(obj.min_price) / 10) 
  
    def get_instock(self, obj):
        current_time = timezone.now()
        updated_at = obj.updated_at

        # print(current_time)
        # print(updated_at)
        # Calculate the time delta between current time and updated_at time
        time_delta = current_time - updated_at

        # Check if the time difference is greater than 4 and one min hours
        if time_delta.total_seconds() > 4 * 3600 + 60:
            return False
        else:
            return True
    
    def get_validity(self, obj):
        status = obj.status

        # print(current_time)
        # print(updated_at)
        # Calculate the time delta between current time and updated_at time
        

        # Check if the time difference is greater than 4 and one min hours
        if status:
            return True
        else:
            return False




    def get_brand(self, obj):
        return obj.brand.name
    
    def get_price_change(self, obj):
        old_min_price =  obj.old_min_price
        if not old_min_price:
            return 0
        return int((int(obj.min_price) - old_min_price) / 10)
    
    def get_active(self, obj):
        
        if obj.brand.name == 'apple' and obj.not_active == False:
            return True
        
        return False
            
    def get_capacity(self, obj):
        return f'{obj.ram}/{obj.memory}'
