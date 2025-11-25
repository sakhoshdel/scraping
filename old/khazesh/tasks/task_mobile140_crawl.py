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
    except:
        return None
    

crawled_mobile_brands: List[str] = ['apple', 'samsung', 'xiaomi', 'nokia', 'realme', 'huawei', 'honor']

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
            # update_code_execution_state(SITE, False, error_message)
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

    brand = title_en.split(' ')[0]
    vietnam = 'ویتنام' in title_fa
    not_active = 'نان اکتیو' in title_fa

    return model, memory, ram, brand, vietnam, not_active


# --------------------------------------------------------------------------
# وظیفه اصلی خزنده


@shared_task(bind=True, max_retries=0)
def mobile140_crawler(self):
    try:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = SITE,
            status = True,
            mobile = True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        
        all_mobile_objects: List[Dict] = []

        for brand in crawled_mobile_brands:
            print(f"Processing {brand}...")

            payload_category = {
                "category": f"{brand}-phone",       # دسته‌بندی
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
                "Referer": f"https://mobile140.com/product-search/category-{brand}-phone?page=1",
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
                update_code_execution_state(SITE, False, '❌ خطا در اتصال به سرور یا دریافت پاسخ:')

                print(e)
                continue
            except ValueError:
                update_code_execution_state(SITE, False, 'خطا در تبدیل پاسخ به JSON')
                print("❌ خطا در تبدیل پاسخ به JSON")
                continue

            # بررسی داده دریافتی
            if "data" not in data or not isinstance(data["data"], dict):
                print("❌ کلید 'data' در پاسخ موجود نیست یا ساختار نادرست دارد.")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                update_code_execution_state(SITE, False, "❌ کلید 'data' در پاسخ موجود نیست یا ساختار نادرست دارد.")
                continue

            dataProd = data["data"]

            if "products" not in dataProd or not dataProd["products"]:
                print("⚠️ کلید 'products' وجود ندارد یا مقدار آن خالی است.")
                print(json.dumps(dataProd, indent=2, ensure_ascii=False))
                continue

            if "items" not in dataProd["products"] or not dataProd["products"]["items"]:
                print("⚠️ کلید 'items' در 'products' موجود نیست یا خالی است.")
                print(json.dumps(dataProd["products"], indent=2, ensure_ascii=False))
                continue



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

    
        
        
        print(len(all_mobile_objects))
        # ذخیره یا پرینت نهایی
        for mobile_dict in all_mobile_objects:
            print(mobile_dict)
            print('\n' + '-'*40 + '\n')
            save_obj(mobile_dict)
            
        update_code_execution_state(SITE, True)

    except Exception as e:
        error_message = traceback.format_exc()
        update_code_execution_state(SITE, False, error_message)
        print(f"Error: {error_message}")
        raise self.retry(exc=e, countdown=30)
