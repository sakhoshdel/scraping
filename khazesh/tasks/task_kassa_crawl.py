import json
import re
import traceback
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
from requests.exceptions import ConnectionError, RequestException
import time
from typing import List, Optional
from requests import Response
import uuid

from khazesh.models import Mobile
from django.utils import timezone

ResponseType = Optional[Response]


# --------------------- تابع درخواست با ریتری ---------------------
def retry_request(
    url: str,
    site: str,
    max_retries: int = 1,
    retry_delay: int = 0,
) -> ResponseType:
    HEADERS = {
        "From": "behnammohammadi148@gmail.com",
    }
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            print("Connection successful Kasra")
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            print(url, error_message)
            update_code_execution_state(site, False, error_message)
            if i < max_retries - 1:
                print("Retrying...")
                time.sleep(retry_delay)
        except RequestException as re:
            error_message = f"Other request error: {re}"
            update_code_execution_state(site, False, error_message)
            return None
        except Exception:
            error_message = traceback.format_exc()
            update_code_execution_state(site, False, error_message)
            print(error_message)
            return None
    return None


HEADERS = {'From': 'behnammohammadi149@gmail.com'}


# --------------------- گرفتن لیست موبایل‌ها ---------------------
def get_mobile_info(headers, url):
    try:
        res = retry_request(url, site='Tecnolife')
        if not res or res.status_code != 200:
            raise Exception(f"Invalid response: {res.status_code if res else 'No response'}")

        soup = BeautifulSoup(res.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag:
            raise Exception("Script with id='__NEXT_DATA__' not found.")

        try:
            tenco_page_obj = json.loads(script_tag.string.encode().decode())
        except json.JSONDecodeError as je:
            update_code_execution_state('Tecnolife', False, f"JSON decode error: {je}")
            return [], True

        tecno_queries = tenco_page_obj.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        if len(tecno_queries) < 5:
            update_code_execution_state('Tecnolife', False, "Unexpected structure in dehydratedState.queries")
            return [], True

        mobile_lists_obj = tecno_queries[4]
        mobiles = mobile_lists_obj.get('state', {}).get('data', {}).get('results', [])
        if not mobiles:
            print(f"No mobiles found on page {url}")
            return [], True

        mobile_urls = []
        page_number_flag = False

        for mobile in mobiles:
            if not mobile.get('available'):
                page_number_flag = True
                break
            mobile_title = mobile.get('name')
            mobile_code = mobile.get('code', '').split('-')[1] if '-' in mobile.get('code', '') else ''
            mobile_url = f"https://www.technolife.ir/product-{mobile_code}/{mobile_title.replace(' ', '-').strip()}"
            mobile_urls.append(mobile_url)

        return mobile_urls, page_number_flag

    except Exception as e:
        error_message = f"Error in scraping {url}: {traceback.format_exc()}"
        print(error_message)
        update_code_execution_state('Tecnolife', False, error_message)
        return [], True


# --------------------- جمع‌آوری همه‌ی صفحات ---------------------
def main():
    phone_model_list = [
        '69_70_73/apple/',
        '69_70_77/samsung',
        '69_70_79/xiaomi',
        '69_70_799/poco',
        '69_70_80/nokia',
        '69_70_780/motorola',
        '69_70_798/huawei',
        '69_70_74/honor',
        '69_70_804/گوشی-موبایل-ریلمی-realme/',
        '69_70_85/nothing-phone/'
    ]

    mobile_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):
            url = f'https://www.technolife.ir/product/list/{phone_model}?page={i + 1}'
            urls, page_flag = get_mobile_info(HEADERS, url)
            mobile_all_urls.extend(urls)
            if page_flag:
                break

    print(f"Total collected URLs: {len(mobile_all_urls)}")
    return mobile_all_urls


# --------------------- ریتری در صورت خطا ---------------------
def retry_main(max_retries=2, delay=5):
    retries = 0
    all_mobile_urls = main()
    while len(all_mobile_urls) == 0 and retries < max_retries:
        print(f"Retrying... attempt {retries + 1}")
        time.sleep(delay)
        all_mobile_urls = main()
        retries += 1

    if len(all_mobile_urls) == 0:
        raise Exception("No mobile URLs found after maximum retries")
    return all_mobile_urls


# --------------------- کرالر اصلی ---------------------
@shared_task(bind=True, max_retries=1)
def kassa_crawler(self):
    try:
        batch_id = f"Kasrapars-{uuid.uuid4().hex[:12]}"
        SITE = "Kasrapars"

        brands_key = {
            "شیائومی": "xiaomi",
            "سامسونگ": "samsung",
            "اپل": "apple",
            "پوکو": "poco",
            "آنر": "honor",
            "نوکیا": "nokia",
        }

        all_mobile_objects = []
        for page_num in range(0, 6):
            response: ResponseType = retry_request(
                f"https://api.Kasrapars.ir/api/web/v10/product/index-brand?expand=letMeKnowOnAvailability%2Cvarieties%2CcartFeatures%2CcoworkerShortName%2CpromotionCoworker%2Cbrand&status_available=1&category_slug=mobilephone&page={page_num}&responseFields%5B0%5D=items",
                'Kasrapars'
            )
            if not response:
                update_code_execution_state('Kasrapars', False, f"Response failed on page {page_num}")
                continue

            try:
                data = json.loads(response.text)
            except json.JSONDecodeError as je:
                update_code_execution_state('Kasrapars', False, f"JSON decode error on page {page_num}: {je}")
                continue

            print('------------------ Kasrapars ------------------')

            for item in data.get('items', {}).get('items', []):
                try:
                    mobile_object = {}
                    brand = item['brand']['brand_name']
                    if brand not in brands_key:
                        continue

                    en_title = item.get('product_name_en', '')
                    fa_title = item.get('product_name', '')
                    slug = item.get('slug', '')

                    model_pattern = r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T|gb)?|^(samsung|xiaomi|apple|nokia|honor|huawei|nothing\sphone)\s*|\s*vietnam\s*"
                    model = re.sub(model_pattern, "", en_title.lower())
                    if not model:
                        m = re.search(r"(?<=مدل\s)[\w\s]*\s*(?=ظرفیت)", fa_title)
                        model = m.group().strip() if m else "نامشخص"

                    for varieties in item.get('varieties', []):
                        guarantee = varieties.get('guarantee', {}).get('guranty_name', '')

                        ram_match = re.search(r"\s*رم\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?", fa_title)
                        if ram_match:
                            ram = ram_match.group()
                            ram = re.sub(r"\s*رم\s*", "", ram)
                            ram = re.sub(r"\s*گیگابایت\s*|\s*گگیابایت\s*", "GB", ram)
                        else:
                            ram = "ندارد"

                        memory_match = re.search(r"\s*ظرفیت\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?", fa_title)
                        if memory_match:
                            memory = memory_match.group()
                            memory = re.sub(r"\s*ظرفیت\s*", "", memory)
                            memory = re.sub(r"\s*گیگابایت\s*", "GB", memory)
                            memory = re.sub(r"\s*ترابایت\s*", "TB", memory)
                        else:
                            memory = "ندارد"

                        vietnam = False
                        if varieties.get('pack') and 'VIT' in varieties['pack'].get('en_name', ''):
                            vietnam = True

                        mobile_object.update({
                            "model": model,
                            "memory": memory,
                            "ram": ram,
                            "brand": brands_key.get(brand, brand),
                            "title": fa_title,
                            "url": f"https://plus.Kasrapars.ir/product/{slug}",
                            "site": 'Kasrapars',
                            "seller": varieties.get('company', {}).get('company_name', ''),
                            "guarantee": guarantee,
                            "max_price": 1,
                            "mobile_digi_id": "",
                            "dual_sim": True,
                            "active": True,
                            "mobile": True,
                            "vietnam": vietnam,
                            "not_active": "نات اکتیو" in fa_title or "not active" in en_title.lower(),
                            "color_name": varieties.get('color', {}).get('color_name', ''),
                            "color_hex": varieties.get('color', {}).get('hexcode', ''),
                            "min_price": varieties.get('price_off', 0),
                        })

                        all_mobile_objects.append(mobile_object.copy())

                except Exception:
                    err = traceback.format_exc()
                    update_code_execution_state('Kasrapars', False, f"Error parsing item: {err}")
                    continue

        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site="Kasrapars", mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state('Kasrapars', bool(all_mobile_objects), 'هیچ محصولی پیدا نشد.' if not all_mobile_objects else '')

    except Exception as e:
        error_message = traceback.format_exc()
        update_code_execution_state('Kasrapars', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site='Kasrapars',
            status=True,
            mobile=True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
