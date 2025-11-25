import requests
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from requests import Response
import logging
import time
import re
import json
import urllib.parse
from typing import List, Dict, Optional
from celery import shared_task
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback
import uuid
from khazesh.models import Mobile
from django.utils import timezone


HEADERS = {'From': 'behnammohammadi149@gmail.com'}

SITE = 'Taavrizh'
GUARANTEE = '18 ماه گارانتی شرکتی'
SELLER = 'Taavrizh'

crowled_mobile_brands: List[str] = ['اپل', 'سامسونگ', 'شیائومی', 'ریلمی', "نوکیا", "هواوی"]
brand_dict_key = {
    'سامسونگ': 'samsung',
    'شیائومی': 'xiaomi',
    'نوکیا': 'nokia',
    'اپل': 'apple',
    'ریلمی': 'realme',
    'هواوی': 'huawei'
}

ResponseType = Optional[Response]


def retry_request(url: str, max_retries: int = 1, retry_delay: int = 1) -> ResponseType:
    """درخواست HTTP با چند بار تلاش مجدد"""
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            print(f"{url} - {error_message}")
            update_code_execution_state(SITE, False, error_message)
            if i < max_retries - 1:
                time.sleep(retry_delay)
        except RequestException as re:
            error_message = f"Request error: {re}"
            print(f"{url} - {error_message}")
            update_code_execution_state(SITE, False, error_message)
            return None
        except Exception:
            err = traceback.format_exc()
            print(f"{url} - Unexpected error: {err}")
            update_code_execution_state(SITE, False, err)
            return None
    return None


def extract_details(en_title: str) -> tuple:
    try:
        en_model_pattern = r'.*?(?=\b\d{1,3}(GB|MB|TB|G|M|T)\b)'
        model_match = re.search(en_model_pattern, en_title)
        model = model_match.group(0).strip() if model_match else en_title.strip()
        brand = en_title.split(' ')[0]
        vietnam = 'Vietnam' in en_title
        not_active = 'non active' in en_title.lower()
        return model, brand, not_active, vietnam
    except Exception:
        err = traceback.format_exc()
        update_code_execution_state(SITE, False, f"extract_details error: {err}")
        return en_title, "unknown", False, False


@shared_task(bind=True, max_retries=1)
def taavrizh_crawler(self):
    try:
        batch_id = f"Taavrizh-{uuid.uuid4().hex[:12]}"
        all_mobile_objects: List[Dict] = []

        for brand in crowled_mobile_brands:
            break_page_num_for = False
            print(f"Processing {brand}...")

            for page_num in range(1, 4):
                if break_page_num_for:
                    break

                url = f'https://taavrizh.com/product-category/product-rands/{brand}/page/{page_num}'
                response: ResponseType = retry_request(url)
                if not response:
                    print(f"⚠️ No response for {brand_dict_key.get(brand, brand)} page {page_num}")
                    continue

                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    all_mobile_products_ul = soup.find('ul', class_='products columns-4')
                    if not all_mobile_products_ul:
                        print('⚠️ No product list found')
                        continue

                    all_mobile_products = all_mobile_products_ul.find_all('li')
                except Exception:
                    err = traceback.format_exc()
                    update_code_execution_state(SITE, False, f"HTML parsing error on {url}: {err}")
                    continue

                for product in all_mobile_products:
                    try:
                        mobile_info = product.find('div', class_='info-product')
                        if not mobile_info:
                            continue

                        mobile_inner_product_info = mobile_info.find('div', class_="products__item-info")
                        if not mobile_inner_product_info:
                            continue

                        title_tag = mobile_inner_product_info.find('p', class_="products__item-fatitle force-rtl")
                        if not title_tag:
                            continue

                        a_tag = title_tag.find('a')
                        if not a_tag:
                            continue

                        mobile_fa_title = a_tag.get('title', '').strip()
                        mobile_link = a_tag.get('href', '').strip()
                        if not mobile_fa_title or not mobile_link:
                            continue

                        if not mobile_fa_title.startswith('گوشی'):
                            continue

                        mobile_price_tag = mobile_inner_product_info.find('span', class_='products__item-price')
                        mobile_price = (mobile_price_tag.text or '').strip().replace('تومان', '').replace(',', '') if mobile_price_tag else ''
                        if mobile_price == 'ناموجود':
                            break_page_num_for = True
                            break

                        single_product_page_res = retry_request(mobile_link)
                        if not single_product_page_res:
                            continue

                        single_product_page = BeautifulSoup(single_product_page_res.text, 'html.parser')
                        spec_ul = single_product_page.find('ul', class_='bakala-product-specifications-list')
                        mobile_short_attributes_li = spec_ul.find_all('li', class_='bakala-product-specification-item') if spec_ul else []

                        not_active = 'Not Active' in mobile_fa_title
                        vietnam = 'ویتنام' in mobile_fa_title
                        model = ''
                        ram = 'ندارد'
                        memory = 'ندارد'
                        en_title = ''

                        # استخراج اطلاعات اصلی از صفحه
                        for attribute_li in mobile_short_attributes_li:
                            try:
                                attr_wrap = attribute_li.find('div', class_='bakala-product-specification-item-wrap')
                                if not attr_wrap:
                                    continue
                                label = attr_wrap.find('p', class_='bakala-product-specification-item-label')
                                value_tag = attr_wrap.find('p', class_='bakala-product-specification-item-value')
                                if not label or not value_tag:
                                    continue
                                label_text = label.text.strip()
                                value_text = value_tag.text.strip()
                                if label_text == 'مدل':
                                    en_title = value_text.replace('-', ' ').lower()
                                    model = en_title.replace(brand_dict_key.get(brand, ''), '').strip()
                                elif label_text == 'حافظه داخلی':
                                    memory = ''.join(value_text.replace('گیگابایت', 'GB').replace('ترابایت', 'T').split())
                                elif label_text == 'مقدار RAM':
                                    ram = ''.join(value_text.replace('گیگابایت', 'GB').split())
                            except Exception:
                                continue

                        # اگر حافظه یا رم هنوز خالی است
                        if ram == 'ندارد' or memory == 'ندارد':
                            try:
                                all_spec_div = single_product_page.find(id='tab-additional_information')
                                all_uls = all_spec_div.find_all('ul', class_="spec-list") if all_spec_div else []
                                for ul in all_uls:
                                    for li in ul.find_all('li'):
                                        title_span = li.find('span', class_='technicalspecs-title')
                                        value_span = li.find('span', class_='technicalspecs-value')
                                        if not title_span or not value_span:
                                            continue
                                        key = title_span.text.strip()
                                        val = value_span.text.strip()
                                        if key == 'مقدار RAM' and ram == 'ندارد':
                                            ram = ''.join(val.replace('گیگابایت', 'GB').split())
                                        elif key == 'حافظه داخلی' and memory == 'ندارد':
                                            memory = ''.join(val.replace('گیگابایت', 'GB').replace('ترابایت', 'T').split())
                            except Exception:
                                pass

                        mobile_object = {
                            'model': model,
                            'memory': memory,
                            'ram': ram,
                            'brand': brand_dict_key.get(brand, brand),
                            'title': mobile_fa_title,
                            'url': mobile_link,
                            'site': SITE,
                            'seller': SELLER,
                            'guarantee': GUARANTEE,
                            'max_price': 1,
                            'mobile_digi_id': '',
                            'dual_sim': True,
                            'active': True,
                            'mobile': True
                        }

                        try:
                            product_obj = product.find('form', class_="variations_form wpcvs_archive")
                            json_data = product_obj.get("data-product_variations", "[]") if product_obj else "[]"
                            mobile_obj_form_json = json.loads(json_data)
                        except Exception:
                            mobile_obj_form_json = []

                        for item in mobile_obj_form_json:
                            try:
                                if not item.get('is_in_stock', False):
                                    continue
                                attributes = item.get('attributes', {})
                                mobile_object['vietnam'] = vietnam or any('vietnam' in v for v in attributes.values())
                                mobile_object['not_active'] = not_active or any('not active' in v.lower() for v in attributes.values())

                                color_key = next(iter(attributes), '')
                                color_value = attributes.get(color_key, '')
                                decoded_color = urllib.parse.unquote(color_value).split('-')[0]
                                display_price = int(item.get('display_price', 0)) * 10

                                all_mobile_objects.append({
                                    'min_price': display_price,
                                    'color_name': decoded_color,
                                    'color_hex': '',
                                    **mobile_object
                                })
                            except Exception:
                                continue

                    except Exception:
                        err = traceback.format_exc()
                        update_code_execution_state(SITE, False, f"Error parsing product for {brand}: {err}")
                        continue

        # ذخیره نهایی
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site=SITE, mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(SITE, bool(all_mobile_objects), 'هیچ محصولی پیدا نشد.' if not all_mobile_objects else '')

    except Exception:
        err = traceback.format_exc()
        update_code_execution_state(SITE, False, err)
        print(f"Error {err}")
        raise self.retry(exc=Exception(err), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site=SITE,
            status=True,
            mobile=True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
