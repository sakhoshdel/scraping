from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from khazesh.models import Brand, ProductAccessories

def save_obj(accessory_dict):
    queryset = ProductAccessories.objects.filter(
        color_hex=accessory_dict.get("color_hex"),
        color_name=accessory_dict.get("color_name"),
        title=accessory_dict["title"],
        model=accessory_dict["model"],
        site=accessory_dict["site"],
    )

    now_time = timezone.now()

    if queryset.exists():
        accessory_obj = queryset.first()

        if accessory_dict.get("stock"):
            accessory_obj.updated_at = now_time
            accessory_obj.description = accessory_dict.get("description")
            accessory_obj.status = True
            accessory_obj.url = accessory_dict.get("url")

            # بررسی تغییر قیمت
            if accessory_dict.get("min_price") is not None:
                new_price = Decimal(accessory_dict.get("min_price"))
                if accessory_obj.min_price != new_price:
                    price_diff = new_price - accessory_obj.min_price
                    accessory_obj.old_min_price = accessory_obj.min_price
                    accessory_obj.min_price = new_price
                    accessory_obj.stock = accessory_dict.get("stock")
                    accessory_obj.seller = accessory_dict.get("seller", accessory_obj.seller)
                    accessory_obj.guarantee = accessory_dict.get("guarantee", accessory_obj.guarantee)
                    accessory_obj.price_change_time = now_time

                    # مدیریت تغییرات قیمت 24 ساعت
                    changes = list(accessory_obj.price_changes_24h or [])
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
                    accessory_obj.price_changes_24h = filtered_changes

            accessory_obj.save()
        else:
            # اگر موجودی صفر شد فقط استاتوس و توضیحات رو آپدیت کن
            accessory_obj.stock = accessory_dict.get("stock")
            accessory_obj.description = accessory_dict.get("description")
            accessory_obj.save()
        
    else:
        # ایجاد اکسسوری جدید
        if accessory_dict.get("min_price") is not None:
            accessory_dict["price_changes_24h"] = []
        ProductAccessories.objects.create(
            **accessory_dict,
            updated_at=now_time,
            status=True
        )
