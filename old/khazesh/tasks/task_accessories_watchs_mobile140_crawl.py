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

from celery import shared_task
from khazesh.tasks.save_accessories_crawler_status import accessories_update_code_execution_state

from khazesh.tasks.save_accessories_object_to_database import save_obj
import traceback

from khazesh.models import ProductAccessories
from khazesh.models import BrandAccessories, CategoryAccessories

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
    except:
        return None
    

crawled_mobile_brands: List[str] = ['mibro', 'haylou', 'imilab', 'apple', 'samsung', 'amazfit', 'kieslect', 'xiaomi', 'tch', 'huawei']

ResponseType = Optional[requests.Response]
Bs4Element = Optional[element.Tag]


# --------------------------------------------------------------------------
# ابزارهای کمکی

def retry_request(url: str, max_retries: int = 1, retry_delay: int = 1) -> ResponseType:
    for i in range(max_retries):
        try:
            response = requests.get(url)
            logging.info("Connection successful")
            return response
        except requests.ConnectionError as ce:
            logging.error(f"{url} - Connection error on attempt {i+1}: {ce}")
            print(f"{url} - Connection error on attempt {i+1}: {ce}")
            if i < max_retries - 1:
                logging.info("Retrying...")
                time.sleep(retry_delay)
        except requests.RequestException as re:
            logging.error(f"{url} - Request error: {re}")
            print(f"{url} - Request error: {re}")
            # accessories_update_code_execution_state(SITE, False, error_message)
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




# --------------------------------------------------------------------------
# وظیفه اصلی خزنده


@shared_task(bind=True, max_retries=1)
def accessories_watchs_mobile140_crawler(self):
    try:
        all_mobile_objects: List[Dict] = []

        # The above code is written in Python and it appears to be querying a database using Django
        # ORM. It is trying to retrieve the first object from the CategoryAccessories model where the
        # name_en field is equal to 'watchs'.
        category = CategoryAccessories.objects.filter(name_en='watchs').first()
        for brand in crawled_mobile_brands:
            if brand == 'apple' or brand == 'tch':
                type = 'watch'
            else:
                type = 'smartwatch'
            print(f"Processing Accessories Watchs  {brand}...")

            payload_category = {
                "category": f"{brand}-{type}",       # دسته‌بندی
                "title": None,                     # جستجو در عنوان محصول
                "brands": None,                    # برندها (مقدار خاصی انتخاب نشده)
                "propertyOptionIds": None,         # فیلتر بر اساس ویژگی‌های خاص
                "minAmount": None,                 # حداقل قیمت
                "maxAmount": None,                 # حداکثر قیمت
                "inStock": True,                  # فقط کالاهای موجود؟ False یعنی همه را بیاور
                "order": 3,                        # ترتیب نمایش (مثلاً 3: جدیدترین یا ارزان‌ترین)
                "page": "1",                       # صفحه نتایج
                "pageSize": 100                    # تعداد آیتم‌ها در هر صفحه
            }

            headers_category = {
                "Domain": "mobile140.com",
                "Origin": "https://mobile140.com",
                "Referer": f"https://mobile140.com/product-search/category-{brand}-{type}?page=1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }

            try:
                resProd = requests.post(
                    'https://services.developzseh.ir/client/ProductSearch/Category',
                    json=payload_category,
                    headers=headers_category,
                    timeout=15
                )
                resProd.raise_for_status()
                data = resProd.json()
            except requests.exceptions.RequestException as e:
                print("❌ خطا در اتصال به سرور یا دریافت پاسخ:")
                accessories_update_code_execution_state(SITE, 'watchs', False, '❌ خطا در اتصال به سرور یا دریافت پاسخ:')

                print(e)
                continue
            except ValueError:
                accessories_update_code_execution_state(SITE, 'watchs', False, 'خطا در تبدیل پاسخ به JSON')
                print("❌ خطا در تبدیل پاسخ به JSON")
                continue

            # بررسی داده دریافتی
            if "data" not in data or not isinstance(data["data"], dict):
                print("❌ کلید 'data' در پاسخ موجود نیست یا ساختار نادرست دارد.")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                accessories_update_code_execution_state(SITE, 'watchs', False, "❌ کلید 'data' در پاسخ موجود نیست یا ساختار نادرست دارد.")
                continue

            dataProd = data["data"]

            if "products" not in dataProd or not dataProd["products"]:
                print("Not Products")
                continue

            if "items" not in dataProd["products"] or not dataProd["products"]["items"]:
                print("Not Products")
                continue

            brand = BrandAccessories.objects.filter(name_en=brand).first()
            if not brand:
                brand = BrandAccessories.objects.create(name_fa=brand, name_en=brand)   

            if True:
                for prodItem in dataProd["products"]['items']:
                    slug = prodItem['slug']

                    mobile_link = f"https://mobile140.com/product-single/{slug}"
                
                    api_url = "https://services.developzseh.ir/client/Product/Preview"

                    payload = {
                        "slug": slug,
                        "commentCount": 0
                    }

                    headers = {
                        "Domain":  "mobile140.com",
                        "Origin":  "https://mobile140.com",
                        "Referer": f"https://mobile140.com/product-single/{slug}",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                                    " AppleWebKit/537.36 (KHTML, like Gecko)"
                                    " Chrome/122.0.0.0 Safari/537.36",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest"
                    }
                    
                    try:
                        resp = requests.post(api_url, json=payload, headers=headers, timeout=15)
                        resp.raise_for_status()  # خطای HTTP (مثل 500 یا 404)
                        data = resp.json()
                        data = data['data']
                    except requests.exceptions.RequestException as e:
                        print("❌ خطا در اتصال به سرور یا دریافت پاسخ:")
                        continue
                    except ValueError:
                        print("❌ خطا در تبدیل پاسخ به JSON")
                        continue

                    if not isinstance(data, dict):
                        print("❌ پاسخ دریافتی ساختار JSON معتبری ندارد.")
                        continue

                    if "variants" not in data or not data["variants"]:
                        print("⚠️ هیچ تنوعی (variant) برای این محصول یافت نشد.")
                        continue

                    
                    # استخراج اطلاعات تنوع‌ها
                    variants_info = []

                    for variant in data["variants"]:
                        try:
                            option = variant["options"][0]
                            price_toman = option.get("amount", 0)
                            price_rial = price_toman * 10
                            stock_status = option.get("stock") == "inStock"

                            attributes = {attr["title"]: attr for attr in variant.get("attributes", [])}

                            color = attributes.get("رنگ", {})
                            color_name_fa = color.get("display", "نامشخص")
                            color_name_en = color.get("name", "unknown")
                            color_rgb = json.loads(color.get("color", ''))
                        

                            warranty = attributes.get("گارانتی", {}).get("display", "نامشخص")
                            if(option.get("stock") == "inStock"):
                                variants_info.append({
                                    "color_fa": color_name_fa,
                                    "color_en": color_name_en,
                                    "color_rgb": rgb_to_hex(color_rgb),
                                    "price": price_rial,
                                    "in_stock": stock_status,
                                    "warranty": warranty
                                })
                        except Exception as e:
                            print("❌ خطا در پردازش یک تنوع محصول:")
                            print(e)
                            continue
                    
                    
                    # نمایش نهایی
                    for v in variants_info:    
                        
                        title_fa = data['title']
                        title_en = data['enTitle']
                        
                        

                        mobile_object = {
                            'model': title_fa,
                            'category': category,
                            'brand': brand,
                            'title': title_fa, 
                            'url': mobile_link,
                            'site': SITE,
                            'seller': SELLER,
                            'guarantee': v['warranty'], 
                            'max_price': 1,
                            'stock': True,
                            'fake': False,
                            'description': '',
                            'color_name': v['color_fa'],
                            'color_hex': v['color_rgb'],
                            'min_price': v['price']
                        }

                        
                        all_mobile_objects.append(copy.deepcopy(mobile_object))

    
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        ProductAccessories.objects.filter(
            site = SITE,
            status = True,
            updated_at__lt=ten_min_ago,
            category__name_en='watchs'

        ).update(status=False)
        
        print(len(all_mobile_objects))
        # ذخیره یا پرینت نهایی
        for mobile_dict in all_mobile_objects:
            print(mobile_dict)
            print('\n' + '-'*40 + '\n')
            save_obj(mobile_dict)
            
        accessories_update_code_execution_state(SITE, 'watchs', True)

    except Exception as e:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state(SITE, 'watchs', False, error_message)
        print(f"Error: {error_message}")
        raise self.retry(exc=e, countdown=30)


