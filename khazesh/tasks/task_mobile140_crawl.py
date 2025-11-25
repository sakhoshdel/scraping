import requests, json
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from requests import Response
import logging
import time 
import re
from urllib.parse import quote
from typing import List,Dict, Tuple, Optional
import copy
import uuid
from celery import shared_task
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback

from khazesh.models import Mobile
from django.utils import timezone


# --------------------------------------------------------------------------
# تنظیمات کلی
HEADERS = {
    'From': 'behnammohammadi149@gmail.cm',
}

SITE = 'Mobile140'
GUARANTEE = 'گارانتی 18 ماهه - رجیستر شده'
SELLER = 'mobile140'

kilo_mega_giga_tra = {
    'کیلوبایت': 'KB',
    'مگابایت': 'MB',
    'گیگابایت': 'GB',
    'ترابایت': 'TB'
}

persian_digit_to_english = {
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
    '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
}
def rgb_to_hex(rgb: dict) -> str:
    try:
        r = int(rgb.get("r", 0))
        g = int(rgb.get("g", 0))
        b = int(rgb.get("b", 0))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return None
    

crawled_mobile_brands: List[str] = ['iphone', 'samsung', 'xiaomi', 'nokia', 'realme', 'huawei', 'honor']

ResponseType = Optional[requests.Response]
Bs4Element = Optional[element.Tag]


# --------------------------------------------------------------------------
# ابزارهای کمکی

def retry_request(url: str, max_retries: int = 1, retry_delay: int = 1) -> ResponseType:
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=20)
            logging.info("Connection successful")
            return response
        except requests.ConnectionError as ce:
            err_msg = f"{url} - Connection error on attempt {i+1}: {ce}"
            print(err_msg)
            update_code_execution_state(SITE, False, err_msg)
            if i < max_retries - 1:
                time.sleep(retry_delay)
        except requests.RequestException as re:
            err_msg = f"{url} - Request error: {re}"
            print(err_msg)
            update_code_execution_state(SITE, False, err_msg)
            return None
        except Exception:
            err_msg = traceback.format_exc()
            print(err_msg)
            update_code_execution_state(SITE, False, err_msg)
            return None
    return None


def color_data_extractor(color_li_tag: Bs4Element) -> dict:
    input_tag_attrs = color_li_tag.find('input').attrs
    color_name = input_tag_attrs.get('data-title', '').strip()
    color_value = input_tag_attrs.get('data-val', '').strip()
    b_tag = color_li_tag.find('b')
    
    span = b_tag.find('span') if b_tag else None
    color_hex = None
    if span and span.has_attr('style'):
        match = re.search(r'background-color:\s*([^;]+)', span['style'])
        if match:
            color_hex = match.group(1).strip()

    color_checked = 'checked' in input_tag_attrs

    return {
        'color_hex': color_hex,
        'color_name': color_name,
        'color_value': color_value,
        'color_checked': color_checked
    }


def extract_details(title_en: str, title_fa: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], bool, bool]:
    try:
        en_model_pattern = r'(([^A-Za-z]+\s*).*?\s)(?=[0-9]{1,3}(GB|MB|T))'
        fa_model_pattern = r'مدل\s+([^\s]+(?:\s+[^\s(]+)*)'
        memory_pattern = r'(\d+\s*GB|\d+\s*MB|\d+\s*TB)'
        ram_pattern = r'Ram\s+(\d+\s*GB|\d+\s*MB|\d+\s*TB)'

        model_match = re.search(en_model_pattern, title_en)
        if not model_match:
            model_match = re.search(fa_model_pattern, title_fa)
        model = model_match.group(1).strip() if model_match else None

        memory_match = re.search(memory_pattern, title_en)
        ram_match = re.search(ram_pattern, title_en)

        memory = memory_match.group(1) if memory_match else None
        ram = ram_match.group(1) if ram_match else None

        brand = title_en.split(' ')[0] if title_en else 'Unknown'
        vietnam = 'ویتنام' in title_fa
        not_active = 'نان اکتیو' in title_fa

        return model, memory, ram, brand, vietnam, not_active
    except Exception:
        err = traceback.format_exc()
        update_code_execution_state(SITE, False, f"extract_details error: {err}")
        return None, None, None, None, False, False


# --------------------------------------------------------------------------
# وظیفه اصلی خزنده

@shared_task(bind=True, max_retries=1)
def mobile140_crawler(self):
    try:
        batch_id = f"{SITE}-{uuid.uuid4().hex[:12]}"
        all_mobile_objects: List[Dict] = []

        for brand in crawled_mobile_brands:
            print(f"Processing {brand}...")

            payload_category = {
                "category": f"{brand}-phone",
                "title": None,
                "brands": None,
                "propertyOptionIds": None,
                "minAmount": None,
                "maxAmount": None,
                "inStock": True,
                "order": 3,
                "page": "1",
                "pageSize": 24
            }

            headers_category = {
                "Domain": "mobile140.com",
                "Origin": "https://mobile140.com",
                "Referer": f"https://mobile140.com/product-search/category-{brand}-phone?page=1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }

            try:
                resProd = requests.post(
                    'https://services.mobile140.com/client/ProductSearch/Category',
                    json=payload_category,
                    headers=headers_category,
                    timeout=20
                )
                resProd.raise_for_status()
                data = resProd.json()
            except requests.exceptions.RequestException as e:
                err = f"خطا در اتصال به سرور برای برند {brand}: {e}"
                print(err)
                update_code_execution_state(SITE, False, err)
                continue
            except ValueError:
                update_code_execution_state(SITE, False, f"خطا در تبدیل پاسخ {brand} به JSON")
                continue

            if "data" not in data or not isinstance(data["data"], dict):
                update_code_execution_state(SITE, False, f"ساختار نادرست در پاسخ برای برند {brand}")
                continue

            dataProd = data["data"]

            if "products" not in dataProd or not dataProd["products"]:
                print(f"⚠️ products در برند {brand} خالی است.")
                continue

            if "items" not in dataProd["products"] or not dataProd["products"]["items"]:
                print(f"⚠️ items در برند {brand} خالی است.")
                continue

            for prodItem in dataProd["products"]['items']:
                try:
                    slug = prodItem['slug']
                    mobile_link = f"https://mobile140.com/product-single/{slug}"

                    api_url = "https://services.mobile140.com/client/Product/Preview"
                    payload = {"slug": slug, "commentCount": 0}

                    resp = requests.post(api_url, json=payload, headers=headers_category, timeout=20)
                    resp.raise_for_status()
                    data = resp.json().get('data', {})
                    if not isinstance(data, dict):
                        continue

                    if "variants" not in data or not data["variants"]:
                        continue

                    variants_info = []
                    for variant in data["variants"]:
                        try:
                            option = variant["options"][0]
                            price_rial = option.get("amount", 0) * 10
                            stock_status = option.get("stock") == "inStock"

                            attributes = {attr["title"]: attr for attr in variant.get("attributes", [])}
                            color = attributes.get("رنگ", {})
                            color_rgb = json.loads(color.get("color", '{}')) if color.get("color") else {}

                            warranty = attributes.get("گارانتی", {}).get("display", "نامشخص")

                            if stock_status:
                                variants_info.append({
                                    "color_fa": color.get("display", "نامشخص"),
                                    "color_en": color.get("name", "unknown"),
                                    "color_rgb": rgb_to_hex(color_rgb),
                                    "price": price_rial,
                                    "in_stock": stock_status,
                                    "warranty": warranty
                                })
                        except Exception:
                            err = traceback.format_exc()
                            update_code_execution_state(SITE, False, f"variant parse error: {err}")
                            continue

                    for v in variants_info:
                        title_fa = data.get('title', '')
                        title_en = data.get('enTitle', '')
                        model, memory, ram, brand, vietnam, not_active = extract_details(title_en, title_fa)

                        mobile_object = {
                            'model': model,
                            'memory': memory,
                            'ram': ram,
                            'brand': brand,
                            'vietnam': vietnam,
                            'not_active': not_active,
                            'title': title_fa,
                            'url': mobile_link,
                            'site': SITE,
                            'seller': SELLER,
                            'guarantee': v['warranty'],
                            'max_price': 1,
                            'mobile_digi_id': '',
                            'dual_sim': True,
                            'active': True,
                            'mobile': True,
                            'color_name': v['color_fa'],
                            'color_hex': v['color_rgb'],
                            'min_price': v['price']
                        }

                        all_mobile_objects.append(copy.deepcopy(mobile_object))

                except Exception:
                    err = traceback.format_exc()
                    update_code_execution_state(SITE, False, f"خطا در پردازش آیتم {prodItem.get('slug', 'unknown')}: {err}")
                    continue

        print(f"{len(all_mobile_objects)} محصولات پیدا شد")
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site=SITE, mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(SITE, bool(all_mobile_objects), 'هیچ محصولی پیدا نشد.' if not all_mobile_objects else '')

    except Exception:
        err = traceback.format_exc()
        update_code_execution_state(SITE, False, err)
        print(f"Error: {err}")
        raise self.retry(exc=Exception(err), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site=SITE,
            status=True,
            mobile=True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
