from django.core.management.base import BaseCommand
import csv
from khazesh.models import Brand, Mobile
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
    

class Command(BaseCommand):
    help = 'Save csv files data into database'

    def handle(self, *args, **options):
        time = datetime.now()
        self.stdout.write("It's now %s" % time.strftime('%Y-%m-%d, %H:%M:%s'))


with open('/home/bm7/projects/scraping_bartardigital/khazesh/mobile140.csv', "r") as f:
    reader = csv.reader(f)
    header = next(reader)
    try: 
        for row in reader:
            if len(row) !=18:
                continue

            _object_dict = {key: value for key, value in zip(header, row)}
            brand = _object_dict.pop('brand').lower()

            if _object_dict.get('active'):
                if brand:
                    obj, created = Brand.objects.get_or_create(name=brand)
                    # Mobile.objects.create(brand=obj, **_object_dict)

                queryset = Mobile.objects.filter(color_hex=_object_dict.get(
                    'color_hex'), color_name=_object_dict.get(
                    'color_name'), title=_object_dict['title'], model=_object_dict['model'])
                if queryset.exists():   

                    mobile_obj = queryset.first()
                    now_time =  timezone.now()
                    mobile_obj.updated_at = now_time
                    mobile_obj.save()
                    if _object_dict.get('min_price') and (mobile_obj.min_price != Decimal(_object_dict.get('min_price'))):

                        #
                        # price_diff_time_delta = timezone.now() - mobile_obj.updated_at
                        # # price_diff_time = datetime.fromisoformat(price_diff_time)
                        # # prcie_diff_time  = datetime.strptime(str(price_diff_time_delta), "YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ]")
                        # # mobile_obj.price_diff_time = prcie_diff_time
                        # days, hours = price_diff_time_delta.days, price_diff_time_delta.seconds // 3600
                        # print(days, hours)
                        # mobile_obj.price_diff_time = f"تغییر قیمت در {days}  روز و {hours} ساعت قبل بوده. "
                        # # print(price_diff_time_delta)

                        mobile_obj.price_change_time = now_time

        
                        mobile_obj.old_min_price = mobile_obj.min_price

                        mobile_obj.min_price = _object_dict.get(
                            'min_price', mobile_obj.min_price)
                        mobile_obj.seller = _object_dict.get(
                            'seller', mobile_obj.seller)
                        mobile_obj.guarantee = _object_dict.get(
                            'guarantee', mobile_obj.guarantee)
                        mobile_obj.save()
                else:
                    Mobile.objects.create(brand=obj, **_object_dict, updated_at=timezone.now())
    except Exception as e: 
            print(e)