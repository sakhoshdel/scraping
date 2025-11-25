from django.core.management.base import BaseCommand
import csv
from khazesh.models import Brand, Mobile
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

class Command(BaseCommand):
    help = 'Save CSV files data into the database'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='The file path to the CSV file you want to import'
        )

    def handle(self, *args, **options):
        file_path = options['file_path']  # Get the file path from arguments
        time = datetime.now()
        self.stdout.write("It's now %s" % time.strftime('%Y-%m-%d, %H:%M:%S'))

        with open(file_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader)

            try:
                for row in reader:
                    if len(row) != 18:
                        continue

                    _object_dict = {key: value for key, value in zip(header, row)}
                    brand = _object_dict.pop('brand').lower()

                    if _object_dict.get('active'):
                        if brand:
                            obj, created = Brand.objects.get_or_create(name=brand)

                        queryset = Mobile.objects.filter(
                            color_hex=_object_dict.get('color_hex'), 
                            color_name=_object_dict.get('color_name'), 
                            title=_object_dict['title'], 
                            model=_object_dict['model']
                        )

                        if queryset.exists():
                            mobile_obj = queryset.first()
                            now_time = timezone.now()
                            mobile_obj.updated_at = now_time
                            mobile_obj.save()

                            if _object_dict.get('min_price') and (mobile_obj.min_price != Decimal(_object_dict.get('min_price'))):
                                mobile_obj.price_change_time = now_time
                                mobile_obj.old_min_price = mobile_obj.min_price
                                mobile_obj.min_price = _object_dict.get('min_price', mobile_obj.min_price)
                                mobile_obj.seller = _object_dict.get('seller', mobile_obj.seller)
                                mobile_obj.guarantee = _object_dict.get('guarantee', mobile_obj.guarantee)
                                mobile_obj.save()
                        else:
                            Mobile.objects.create(brand=obj, **_object_dict, updated_at=timezone.now())
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error: {e}"))
