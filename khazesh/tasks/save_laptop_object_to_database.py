from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from khazesh.models import ProductLaptop


def save_laptop_obj(laptop_dict):
    queryset = ProductLaptop.objects.filter(
        color_hex=laptop_dict.get("color_hex"),
        color_name=laptop_dict.get("color_name"),
        title=laptop_dict["title"],
        model=laptop_dict["model"],
        site=laptop_dict["site"],
    )

    now_time = timezone.now()

    if queryset.exists():
        laptop_obj = queryset.first()

        if laptop_dict.get("stock"):
            laptop_obj.updated_at = now_time
            laptop_obj.description = laptop_dict.get("description")
            laptop_obj.status = True
            laptop_obj.url = laptop_dict.get("url")

            # مشخصات سخت‌افزاری → اگر داده جدید اومده آپدیت کن
            laptop_obj.ram = laptop_dict.get("ram", laptop_obj.ram)
            laptop_obj.storage = laptop_dict.get("storage", laptop_obj.storage)
            laptop_obj.cpu = laptop_dict.get("cpu", laptop_obj.cpu)
            laptop_obj.gpu = laptop_dict.get("gpu", laptop_obj.gpu)
            laptop_obj.display_size = laptop_dict.get("display_size", laptop_obj.display_size)
            laptop_obj.display_resolution = laptop_dict.get("display_resolution", laptop_obj.display_resolution)
            laptop_obj.weight = laptop_dict.get("weight", laptop_obj.weight)
            laptop_obj.battery = laptop_dict.get("battery", laptop_obj.battery)
            laptop_obj.os = laptop_dict.get("os", laptop_obj.os)

            # بررسی تغییر قیمت
            if laptop_dict.get("min_price") is not None:
                new_price = Decimal(laptop_dict.get("min_price"))
                if laptop_obj.min_price != new_price:
                    price_diff = new_price - laptop_obj.min_price
                    laptop_obj.old_min_price = laptop_obj.min_price
                    laptop_obj.min_price = new_price
                    laptop_obj.stock = laptop_dict.get("stock")
                    laptop_obj.seller = laptop_dict.get("seller", laptop_obj.seller)
                    laptop_obj.guarantee = laptop_dict.get("guarantee", laptop_obj.guarantee)
                    laptop_obj.price_change_time = now_time

                    # مدیریت تغییرات قیمت 24 ساعت
                    changes = list(laptop_obj.price_changes_24h or [])
                    filtered_changes = []

                    for c in changes:
                        change_time = datetime.fromisoformat(c["time"])
                        if timezone.is_naive(change_time):
                            change_time = timezone.make_aware(change_time)
                        else:
                            change_time = change_time.astimezone(timezone.get_current_timezone())

                        if now_time - change_time <= timedelta(hours=24):
                            filtered_changes.append(c)

                    # اضافه کردن تغییر جدید
                    filtered_changes.append({"change": float(price_diff), "time": now_time.isoformat()})
                    laptop_obj.price_changes_24h = filtered_changes

            laptop_obj.save()
        else:
            # اگر موجودی صفر شد فقط استاتوس و توضیحات رو آپدیت کن
            laptop_obj.stock = laptop_dict.get("stock")
            laptop_obj.description = laptop_dict.get("description")
            laptop_obj.save()

    else:
        # ایجاد لپ‌تاپ جدید
        if laptop_dict.get("min_price") is not None:
            laptop_dict["price_changes_24h"] = []
        ProductLaptop.objects.create(
            **laptop_dict,
            updated_at=now_time,
            status=True
        )
