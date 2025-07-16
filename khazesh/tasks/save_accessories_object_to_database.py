from decimal import Decimal

from django.utils import timezone

from khazesh.models import Brand, ProductAccessories


def save_obj(mobile_dict):
    queryset = ProductAccessories.objects.filter(
        color_hex=mobile_dict.get("color_hex"),
        color_name=mobile_dict.get("color_name"),
        title=mobile_dict["title"],
        model=mobile_dict["model"],
        site=mobile_dict["site"],
    )

    if queryset.exists():
        if mobile_dict.get("stock"):
            mobile_obj = queryset.first()
            now_time = timezone.now()
            mobile_obj.updated_at = now_time
            mobile_obj.description = mobile_dict.get("description")
            mobile_obj.status = True
            mobile_obj.url = mobile_dict.get("url")
            

            if mobile_dict.get("min_price") and (
                mobile_obj.min_price != Decimal(mobile_dict.get("min_price"))
            ):
                mobile_obj.price_change_time = now_time
                mobile_obj.old_min_price = mobile_obj.min_price
                mobile_obj.stock = mobile_dict.get("stock")
                mobile_obj.min_price = mobile_dict.get(
                    "min_price", mobile_obj.min_price
                )
                mobile_obj.seller = mobile_dict.get("seller", mobile_obj.seller)
                mobile_obj.guarantee = mobile_dict.get(
                    "guarantee", mobile_obj.guarantee
                )
                
            mobile_obj.save()
        else:
            mobile_obj = queryset.first()
            mobile_obj.stock = mobile_dict.get("stock")
            mobile_obj.description = mobile_dict.get("description")
            mobile_obj.save()
        
    else:
        ProductAccessories.objects.create(**mobile_dict, updated_at=timezone.now(), status=True)
