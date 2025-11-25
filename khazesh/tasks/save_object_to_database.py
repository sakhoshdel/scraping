from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from khazesh.models import Brand, Mobile

def save_obj(mobile_dict, batch_id: str):
    brand_name = mobile_dict.pop("brand").lower()
    now_time = timezone.now()
    mobile_dict.pop("extra_attributes", None)


    if mobile_dict.get("active"):
        # دریافت یا ایجاد برند
        brand_obj, _ = Brand.objects.get_or_create(name=brand_name)

        queryset = Mobile.objects.filter(
            color_hex=mobile_dict.get("color_hex"),
            color_name=mobile_dict.get("color_name"),
            title=mobile_dict["title"],
            model=mobile_dict["model"],
            mobile=mobile_dict["mobile"],
            site=mobile_dict.get("site"),
            guarantee=mobile_dict.get("guarantee"),
        )


        if queryset.exists():
            mobile_obj = queryset.first()
            mobile_obj.updated_at = now_time
            mobile_obj.url = mobile_dict.get("url")
            mobile_obj.status = True
            mobile_obj.last_batch_id = batch_id
            mobile_obj.last_seen_instock_at = now_time

            # بررسی تغییر قیمت
            if mobile_dict.get("min_price") is not None:
                new_price = Decimal(mobile_dict.get("min_price"))
                if mobile_obj.min_price != new_price:
                    price_diff = new_price - mobile_obj.min_price
                    mobile_obj.old_min_price = mobile_obj.min_price
                    mobile_obj.min_price = new_price
                    mobile_obj.seller = mobile_dict.get("seller", mobile_obj.seller)
                    mobile_obj.guarantee = mobile_dict.get("guarantee", mobile_obj.guarantee)
                    mobile_obj.price_change_time = now_time

                    # مدیریت تغییرات قیمت 24 ساعت
                    changes = list(mobile_obj.price_changes_24h or [])
                    filtered_changes = []

                    for c in changes:
                        change_time = datetime.fromisoformat(c["time"])
                        if timezone.is_naive(change_time):
                            change_time = timezone.make_aware(change_time)
                        else:
                            change_time = change_time.astimezone(timezone.get_current_timezone())

                        if now_time - change_time <= timedelta(hours=24):
                            filtered_changes.append(c)

                    filtered_changes.append({
                        "change": float(price_diff),
                        "time": now_time.isoformat()
                    })
                    mobile_obj.price_changes_24h = filtered_changes

            mobile_obj.save()

        else:
            # ایجاد موبایل جدید
            if mobile_dict.get("min_price") is not None:
                mobile_dict["price_changes_24h"] = []

            Mobile.objects.create(
                brand=brand_obj,
                **mobile_dict,
                updated_at=now_time,
                status=True,
                last_batch_id=batch_id,
                last_seen_instock_at=now_time
            )
