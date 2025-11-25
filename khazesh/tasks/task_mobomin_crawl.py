import requests
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from celery import shared_task
from requests import Response
import logging
import time
import re
from typing import List, Dict, Optional
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback
from khazesh.models import Mobile
from django.utils import timezone
import uuid


crowled_mobile_brands: List[str] = ['اپل', 'موبایل-سامسونگ', 'موبایل-شیائومی', 'موبایل-ریلمی', 'موبایل-نوکیا', 'موبایل-ناتینگ']
ResponseType = Optional[Response]
Bs4Element = Optional[element.Tag]


def retry_request(url: str, max_retries: int = 1, retry_delay: int = 1) -> ResponseType:
    """ارسال درخواست GET با چندبار تلاش مجدد"""
    for i in range(max_retries):
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            print(f"{url} - {error_message}")
            update_code_execution_state('Mobomin', False, error_message)
            if i < max_retries - 1:
                time.sleep(retry_delay)
        except RequestException as re:
            error_message = f"Request error on attempt {i+1}: {re}"
            print(f"{url} - {error_message}")
            update_code_execution_state('Mobomin', False, error_message)
            return None
        except Exception:
            error_message = traceback.format_exc()
            print(f"{url} - Unexpected error: {error_message}")
            update_code_execution_state('Mobomin', False, error_message)
            return None
    return None


def extract_details(en_title: str) -> tuple:
    """استخراج مدل، برند، وضعیت فعال بودن و ویتنامی بودن از عنوان"""
    try:
        en_model_pattern = r'.*?(?=\b\d{1,3}(GB|MB|TB)\b)'
        model_match = re.search(en_model_pattern, en_title)
        model = model_match.group(0).strip() if model_match else en_title.strip()

        brand = 'apple' if 'iPhone' in en_title else en_title.split(' ')[0].strip()
        vietnam = 'Vietnam' in en_title
        not_active = 'non active' in en_title.lower()
        return model, brand, not_active, vietnam
    except Exception:
        err = traceback.format_exc()
        update_code_execution_state('Mobomin', False, f"extract_details error: {err}")
        return en_title, "Unknown", False, False


@shared_task(bind=True, max_retries=1)
def mobomin_crawler(self):
    try:
        batch_id = f"Mobomin-{uuid.uuid4().hex[:12]}"
        SITE = 'Mobomin'
        GUARANTEE = 'ذکر نشده'
        SELLER = 'Mobomin'
        all_mobile_objects: List[Dict] = []

        for brand_fa in crowled_mobile_brands:
            break_page_num_for = False
            print(f"Processing {brand_fa}...")

            for page_num in range(1, 4):  # فقط ۳ صفحه اول
                if break_page_num_for:
                    break

                category_url = f"https://mobomin.com/search/{brand_fa}?page={page_num}"
                response: ResponseType = retry_request(category_url)
                if not response:
                    print(f"⚠️ No response for {brand_fa} page {page_num}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                all_mobile_products_div = soup.find(class_='row row-list-item')
                if not all_mobile_products_div:
                    print('❌ div با کلاس row row-list-item پیدا نشد')
                    continue

                all_mobile_products = all_mobile_products_div.find_all(
                    'div', class_='col-12 col-md-4 col-lg-3 item-category pl-2 pr-2'
                )
                print(f"Found {len(all_mobile_products)} products on page {page_num}")

                for product in all_mobile_products:
                    try:
                        mobile_price_div = product.find(class_="c-price__value-wrapper")
                        mobile_price = (
                            mobile_price_div.text.replace('تومان', '').strip().replace(',', '')
                            if mobile_price_div else ''
                        )
                        if mobile_price == 'ناموجود':
                            break_page_num_for = True
                            break

                        mobile_link = product.find('a')['href']
                        single_product_page_res = retry_request(mobile_link)
                        if not single_product_page_res:
                            print(f"⚠️ Could not fetch product page {mobile_link}")
                            continue

                        single_product_page = BeautifulSoup(single_product_page_res.text, 'html.parser')

                        # استخراج رم و حافظه
                        memory_ram_tag = single_product_page.find('ul', class_="product-detail")
                        ram, memory = 'ندارد', 'ندارد'
                        if memory_ram_tag:
                            try:
                                memory_text = [li.find('span').text for li in memory_ram_tag.find_all('li')
                                               if li.find('b') and 'حافظه' in li.find('b').text][0]
                                ram_text = [li.find('span').text for li in memory_ram_tag.find_all('li')
                                            if li.find('b') and 'رم' in li.find('b').text][0]
                                memory = ''.join(memory_text.replace('گیگ', 'GB')
                                                 .replace('ترابایت', 'T').split(' ')).strip()
                                ram = ''.join(ram_text.replace('گیگ', '').strip().split()) + 'GB'
                            except Exception:
                                print("⚠️ Error parsing RAM/memory info")
                                pass

                        # عنوان و مدل
                        title = single_product_page.find('h1', class_='c-product__title')
                        en_title = title.text.strip() if title else 'بدون عنوان'
                        model, brand, not_active, vietnam = extract_details(en_title)

                        mobile_object = {
                            'model': model,
                            'memory': memory,
                            'ram': ram,
                            'brand': brand,
                            'vietnam': vietnam,
                            'not_active': not_active,
                            'title': en_title,
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

                        mobile_color_tag = single_product_page.find('div', class_="col-lg-7 col-md-7 col-12")
                        mobile_colors_div = mobile_color_tag.find_all('div', 'row mt-3') if mobile_color_tag else []
                        if not mobile_colors_div:
                            continue

                        for mobile_color_div in mobile_colors_div:
                            try:
                                color_name = " ".join(mobile_color_div.find('h5').text.strip().split(' ')[1:])
                                price_tag = mobile_color_div.find('h6').find('span')
                                color_price = price_tag.text.strip().split(' ')[0].replace(',', '') if price_tag else '0'
                                all_mobile_objects.append({
                                    'min_price': int(color_price.strip()) * 10,
                                    'color_name': color_name,
                                    'color_hex': '',
                                    **mobile_object
                                })
                            except Exception:
                                err = traceback.format_exc()
                                update_code_execution_state('Mobomin', False, f"color parse error: {err}")
                                continue

                    except Exception:
                        err = traceback.format_exc()
                        update_code_execution_state('Mobomin', False, f"product parse error: {err}")
                        continue

        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site="Mobomin", mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state('Mobomin', bool(all_mobile_objects), 'هیچ محصولی پیدا نشد.' if not all_mobile_objects else '')

    except Exception:
        error_message = traceback.format_exc()
        print(f"Error {error_message}")
        update_code_execution_state('Mobomin', False, error_message)
        raise self.retry(exc=Exception(error_message), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site='Mobomin',
            status=True,
            mobile=True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
