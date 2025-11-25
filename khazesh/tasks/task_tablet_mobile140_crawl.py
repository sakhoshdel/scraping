import json
import re
import time
import traceback
import requests
from celery import shared_task
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
from requests.exceptions import RequestException, ConnectionError, Timeout
from typing import List, Dict, Optional
import uuid
from khazesh.models import Mobile
from django.utils import timezone

# ------------------ تنظیمات کلی ------------------
SITE = 'Mobile140-tablet'
GUARANTEE = 'گارانتی 18 ماهه - رجیستر شده'
SELLER = 'mobile140'
crawled_mobile_brands = ['samsung']


def rgb_to_hex(rgb: dict) -> Optional[str]:
    try:
        r = int(rgb.get("r", 0))
        g = int(rgb.get("g", 0))
        b = int(rgb.get("b", 0))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None


# ------------------ درخواست ایمن ------------------
def safe_post(url, json_data=None, headers=None, retries=2, delay=2):
    for i in range(retries):
        try:
            r = requests.post(url, json=json_data, headers=headers, timeout=15)
            r.raise_for_status()
            return r.json()
        except (ConnectionError, Timeout) as e:
            print(f"⚠️ اتصال ناموفق ({i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
        except RequestException as e:
            print(f"⚠️ خطای درخواست: {e}")
            update_code_execution_state(SITE, False, f"Request error: {e}")
            return None
        except Exception:
            update_code_execution_state(SITE, False, traceback.format_exc())
            return None
    return None


def extract_details(title_en: str, title_fa: str):
    brand = title_en.split(' ')[0] if title_en else 'Unknown'
    vietnam = 'ویتنام' in title_fa
    not_active = 'نات اکتیو' in title_fa or 'not active' in title_en.lower()
    return brand, vietnam, not_active


# ------------------ وظیفه اصلی خزنده ------------------
@shared_task(bind=True, max_retries=1)
def tablet_mobile140_crawler(self):
    try:
        batch_id = f"{SITE}-{uuid.uuid4().hex[:12]}"
        all_tablets: List[Dict] = []
        print("🟢 شروع کرول تبلت‌های Mobile140")

        for brand in crawled_mobile_brands:
            print(f"Processing brand: {brand}")

            payload = {
                "category": "tablet",
                "title": None,
                "brands": [brand],
                "propertyOptionIds": None,
                "minAmount": None,
                "maxAmount": None,
                "inStock": True,
                "order": 3,
                "page": "1",
                "pageSize": 24
            }

            headers = {
                "Domain": "mobile140.com",
                "Origin": "https://mobile140.com",
                "Referer": f"https://mobile140.com/product-search/category-tablet?brands={brand}&page=1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }

            # مرحله اول: دریافت لیست محصولات
            data = safe_post("https://services.mobile140.com/client/ProductSearch/Category", json_data=payload, headers=headers)
            if not data or "data" not in data or "products" not in data["data"]:
                update_code_execution_state(SITE, False, f"❌ عدم دریافت داده از ProductSearch برای برند {brand}")
                continue

            items = data["data"]["products"].get("items", [])
            if not items:
                print(f"⚠️ هیچ آیتمی برای {brand} یافت نشد")
                continue

            # مرحله دوم: پردازش هر محصول
            for prod in items:
                try:
                    slug = prod.get("slug")
                    if not slug:
                        continue

                    api_url = "https://services.mobile140.com/client/Product/Preview"
                    payload_preview = {"slug": slug, "commentCount": 0}
                    headers["Referer"] = f"https://mobile140.com/product-single/{slug}"

                    product_data = safe_post(api_url, json_data=payload_preview, headers=headers)
                    if not product_data or "data" not in product_data:
                        continue
                    data = product_data["data"]

                    if "variants" not in data or not data["variants"]:
                        continue

                    # استخراج اطلاعات variantها
                    for variant in data["variants"]:
                        try:
                            option = variant.get("options", [{}])[0]
                            price_rial = int(option.get("amount", 0)) * 10
                            if option.get("stock") != "inStock":
                                continue

                            attributes = {a["title"]: a for a in variant.get("attributes", [])}
                            color = attributes.get("رنگ", {})
                            color_name = color.get("display", "نامشخص")
                            color_rgb = None
                            try:
                                color_rgb = rgb_to_hex(json.loads(color.get("color", "{}")))
                            except json.JSONDecodeError:
                                pass

                            warranty = attributes.get("گارانتی", {}).get("display", GUARANTEE)

                            title_fa = data.get("title", "نامشخص")
                            title_en = data.get("slug", "").replace('-', ' ')
                            brand, vietnam, not_active = extract_details(title_en, title_fa)

                            properties = {a["title"]: a for a in data.get("properties", [])}
                            ram_list = properties.get("مقدار رم", {}).get("values", [])
                            mem_list = properties.get("حافظه داخلی", {}).get("values", [])
                            ram = ram_list[0].replace("گیگابایت", "GB") if ram_list else "نامشخص"
                            memory = mem_list[0].replace("گیگابایت", "GB") if mem_list else "نامشخص"

                            english_parts = re.findall(r"[A-Za-z0-9 ]+", title_fa)
                            model = " ".join(p.strip() for p in english_parts if p.strip())

                            tablet = {
                                "model": model,
                                "memory": memory,
                                "ram": ram,
                                "brand": brand,
                                "vietnam": vietnam,
                                "not_active": not_active,
                                "title": title_fa,
                                "url": f"https://mobile140.com/product-single/{slug}",
                                "site": SITE,
                                "seller": SELLER,
                                "guarantee": warranty,
                                "max_price": 1,
                                "mobile_digi_id": "",
                                "dual_sim": True,
                                "active": True,
                                "mobile": True,
                                "color_name": color_name,
                                "color_hex": color_rgb,
                                "min_price": price_rial,
                            }

                            all_tablets.append(tablet.copy())

                        except Exception:
                            update_code_execution_state(SITE, False, traceback.format_exc())
                            continue
                except Exception:
                    update_code_execution_state(SITE, False, traceback.format_exc())
                    continue

        # ذخیره در دیتابیس
        for tablet in all_tablets:
            save_obj(tablet, batch_id=batch_id)

        Mobile.objects.filter(site=SITE, mobile=False).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(SITE, bool(all_tablets), "هیچ محصولی ثبت نشد." if not all_tablets else "")

    except Exception:
        error = traceback.format_exc()
        update_code_execution_state(SITE, False, error)
        print(f"Error: {error}")
        raise self.retry(exc=Exception(error), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site=SITE, status=True, mobile=False, updated_at__lt=ten_min_ago).update(status=False)
