from decimal import Decimal

from django.utils import timezone

from khazesh.models import Brand, Mobile


def save_obj(mobile_dict):
    brand = mobile_dict.pop("brand").lower()
    if mobile_dict.get("active"):
        obj, created = Brand.objects.get_or_create(name=brand)

        queryset = Mobile.objects.filter(
            color_hex=mobile_dict.get("color_hex"),
            color_name=mobile_dict.get("color_name"),
            title=mobile_dict["title"],
            model=mobile_dict["model"],
            mobile=mobile_dict["mobile"],
        )

        if queryset.exists():
            mobile_obj = queryset.first()
            now_time = timezone.now()
            mobile_obj.updated_at = now_time
            mobile_obj.url = mobile_dict.get("url")
            mobile_obj.status = True
            mobile_obj.save()

            if mobile_dict.get("min_price") and (
                mobile_obj.min_price != Decimal(mobile_dict.get("min_price"))
            ):
                mobile_obj.price_change_time = now_time
                mobile_obj.old_min_price = mobile_obj.min_price
                mobile_obj.min_price = mobile_dict.get(
                    "min_price", mobile_obj.min_price
                )
                mobile_obj.seller = mobile_dict.get("seller", mobile_obj.seller)
                mobile_obj.guarantee = mobile_dict.get(
                    "guarantee", mobile_obj.guarantee
                )
                mobile_obj.save()
        else:
            if obj:
                Mobile.objects.create(brand=obj, **mobile_dict, updated_at=timezone.now(), status=True)
