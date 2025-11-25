import requests
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from requests import Response
import logging
import time
import re
import json
from typing import List, Dict, Optional
from celery import shared_task
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback
import uuid
from khazesh.models import Mobile
from django.utils import timezone


HEADERS = {'From': 'behnammohammadi149@gmail.com'}

SITE = 'Tellstar'
GUARANTEE = 'گارانتی 18 ماهه - رجیستر شده'
SELLER = 'Tellstar'

crowled_mobile_brands: List[str] = ['APPLE', 'SAMSUNG', 'XIAOMI', 'Nothing-Phone', 'HONOR', 'HUAWEI', 'MOTOROLA', 'Realme']

ResponseType = Optional[Response]
remove_pattern = r'^\s*product\(\s*|,\s*[\d]+\s*\)$'

SITE_MOBILE_ATTRIBUTE_KEYS = {
    'وضعیت گارانتی': 'guarantee',
    'رنگ بندی': 'color',
    'دیگر ویژگی ها': 'not_active',
    'سفارش': 'which_country',
    'پک': 'pack'
}

SITE_MOBILE_ATTRIBUTE_CODE = {
    '70': 'guarantee',
    '71': 'color',
    '129': 'not_active',
    '137': 'which_country',
    '162': 'pack'
}


# -------------------- Helper --------------------
def retry_request(url: str, max_retries: int = 1, retry_delay: int = 1) -> ResponseType:
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response
        except (ConnectionError, requests.Timeout) as ce:
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
            error_message = traceback.format_exc()
            print(f"{url} - Unexpected error: {error_message}")
            update_code_execution_state(SITE, False, error_message)
            return None
    return None


# -------------------- Main Task --------------------
@shared_task(bind=True, max_retries=1)
def tellstar_crawler(self):
    try:
        batch_id = f"{SITE}-{uuid.uuid4().hex[:12]}"
        all_mobile_objects: List[Dict] = []

        for brand in crowled_mobile_brands:
            break_page_num_for = False
            print(f"Processing {brand}...")

            for page_num in range(1, 5):
                if break_page_num_for:
                    break

                url = f'https://tellstar.ir/search/product_{brand}/?page={page_num}'
                response = retry_request(url)
                if not response:
                    print(f"⚠️ No response for {brand}")
                    continue

                try:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    category_items = soup.find(id='category-items')
                    if not category_items:
                        continue
                    product_rows = category_items.find('div', class_='row g-3')
                    if not product_rows:
                        continue
                    all_mobile_divs = product_rows.find_all('div', class_='col-lg-3')
                except Exception:
                    update_code_execution_state(SITE, False, traceback.format_exc())
                    continue

                for mobile in all_mobile_divs:
                    try:
                        mobile_object: Dict = {}
                        mobile_attributer_dict = {k: [] for k in ['guarantee', 'not_active', 'color', 'which_country', 'pack']}

                        mobile_title_box = mobile.find('div', class_='product-title')
                        title_tag = mobile_title_box.find('div', class_='title').find('a', class_='text-overflow-1') if mobile_title_box else None
                        if not title_tag:
                            continue

                        mobile_fa_title = title_tag.text.strip()
                        mobile_link = title_tag.get('href', '')
                        if not mobile_fa_title or not mobile_link or 'گوشی' not in mobile_fa_title:
                            continue

                        price_tag = mobile.find('a', class_='product-action')
                        mobile_price = ''
                        if price_tag:
                            price_tag_p = price_tag.find('p', class_='new-price')
                            mobile_price = price_tag_p.text.replace('تومان', '').strip() if price_tag_p else ''
                        if mobile_price == 'نا موجود':
                            break_page_num_for = True
                            break

                        single_page_url = f'https://tellstar.ir/{mobile_link}'
                        single_product_page_res = retry_request(single_page_url)
                        if not single_product_page_res:
                            continue

                        single_product_page = BeautifulSoup(single_product_page_res.text, 'html.parser')
                        single_mobile_div = single_product_page.find(lambda tag: tag.name == 'div' and tag.has_attr('x-data') and 'product(' in tag['x-data'])
                        if not single_mobile_div:
                            continue

                        xdata = single_mobile_div.attrs.get('x-data', '')
                        try:
                            normalize_to_json_obj = '[' + re.sub(remove_pattern, '', xdata) + ']'
                            mobile_variatoins = json.loads(normalize_to_json_obj)
                            mobile_variants_all = mobile_variatoins[0]
                        except Exception:
                            update_code_execution_state(SITE, False, f"JSON parsing error for {single_page_url}")
                            continue

                        moible_varients_in_stock = list(filter(lambda m: m.get('in_stock'), mobile_variants_all.values()))

                        # Extract attributes
                        try:
                            content_box = single_mobile_div.find(id='content-box')
                            product_meta_feature = content_box.find('div', class_="product-meta-feature") if content_box else None
                            next_sibling = product_meta_feature.find_next_sibling() if product_meta_feature else None
                            all_color_divs = next_sibling.find_all('div', class_='product-meta-color') if next_sibling else []
                        except Exception:
                            all_color_divs = []

                        for item in all_color_divs:
                            try:
                                attribute_type = item.find('h5', class_='font-16').text.strip()
                                attribute_items = item.find('div', class_='product-meta-color-items').find_all('label', class_='btn')
                                attribute_key = SITE_MOBILE_ATTRIBUTE_KEYS.get(attribute_type, '')
                                for attribute in attribute_items:
                                    code = attribute.get('for', '').replace('attribute-', '')
                                    name = attribute.text.strip()
                                    color_hex = ''
                                    if attribute_key == 'color':
                                        span = attribute.find('span')
                                        if span and span.has_attr('style'):
                                            match = re.search(r'#[a-zA-Z0-9]{3,}', span['style'])
                                            if match:
                                                color_hex = match.group()
                                    mobile_attributer_dict[attribute_key].append({'code': code, 'name': name, 'color_hex': color_hex})
                            except Exception:
                                continue

                        # Extract RAM and memory
                        ram_match = re.search(r'\s*رم\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?', mobile_fa_title)
                        if ram_match:
                            ram = re.sub(r'\s*رم\s*', '', ram_match.group()).replace('گیگابایت', 'GB')
                        else:
                            ram = 'ندارد'

                        memory_match = re.search(r'\s*حافظه\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?', mobile_fa_title)
                        if memory_match:
                            memory = re.sub(r'\s*حافظه\s*', '', memory_match.group()).replace('گیگابایت', 'GB')
                        else:
                            memory = 'ندارد'

                        mobile_object['ram'] = ram
                        mobile_object['memory'] = memory
                        model_match = re.search(r'[\w\s]*\s*', mobile_fa_title)
                        model = model_match.group().strip() if model_match else ''
                        mobile_object['model'] = model
                        mobile_object['brand'] = brand.lower()
                        mobile_object['url'] = f'https://tellstar.ir{mobile_link}'
                        mobile_object['title'] = mobile_fa_title
                        mobile_object['site'] = SITE
                        mobile_object['seller'] = SELLER
                        mobile_object['max_price'] = 1
                        mobile_object['mobile_digi_id'] = ''
                        mobile_object['dual_sim'] = True
                        mobile_object['active'] = True
                        mobile_object['mobile'] = True
                        mobile_object['vietnam'] = any(k in mobile_fa_title for k in ['VIT', 'ویتنام'])

                        mobile_guarantee = (mobile_attributer_dict.get('guarantee') or [{}])[0]
                        mobile_colors = mobile_attributer_dict.get('color', [])
                        mobile_not_active = mobile_attributer_dict.get('not_active', [])

                        for mobile_in_stock in moible_varients_in_stock:
                            try:
                                off_price = mobile_in_stock.get('off_price', 0)
                                price = int(off_price or mobile_in_stock.get('price', 0)) * 10
                                mobile_object['min_price'] = price
                                attributes = mobile_in_stock.get('attribute_values', {})

                                for idd, value in attributes.items():
                                    key = SITE_MOBILE_ATTRIBUTE_CODE.get(idd)
                                    if key == 'guarantee':
                                        mobile_object[key] = mobile_guarantee.get('name', '')
                                    elif key == 'color':
                                        match_color = next((c for c in mobile_colors if c['code'] == f'{idd}-{value}'), {})
                                        mobile_object['color_name'] = match_color.get('name', '')
                                        mobile_object['color_hex'] = match_color.get('color_hex', '')
                                    elif key == 'not_active':
                                        match_na = next((n for n in mobile_not_active if n['code'] == f'{idd}-{value}'), {})
                                        mobile_object['not_active'] = 'غیرفعال' in match_na.get('name', '')

                                all_mobile_objects.append(mobile_object.copy())
                            except Exception:
                                continue

                    except Exception:
                        update_code_execution_state(SITE, False, traceback.format_exc())
                        continue

        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site=SITE, mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(SITE, bool(all_mobile_objects), 'هیچ محصولی پیدا نشد.' if not all_mobile_objects else '')

    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state(SITE, False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)
    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site=SITE, status=True, mobile=True, updated_at__lt=ten_min_ago
        ).update(status=False)
