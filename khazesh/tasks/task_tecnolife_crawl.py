import json
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
import time
import traceback
from khazesh.models import Mobile
from django.utils import timezone
import uuid


# -------------------------- Request Helper --------------------------
def retry_request(url: str, headers, max_retries: int = 1, retry_delay: int = 1):
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            logging.info("Connection successful")
            return response
        except (requests.ConnectionError, requests.Timeout) as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            print(f"{url} - {error_message}")
            update_code_execution_state("Tecnolife", False, error_message)
            if i < max_retries - 1:
                time.sleep(retry_delay)
        except requests.RequestException as re:
            error_message = f"Request error: {re}"
            print(f"{url} - {error_message}")
            update_code_execution_state("Tecnolife", False, error_message)
            return None
        except Exception:
            error_message = traceback.format_exc()
            print(f"{url} - Unexpected error: {error_message}")
            update_code_execution_state("Tecnolife", False, error_message)
            return None
    return None


HEADERS = {'From': 'behnammohammadi149@gmail.com'}


# -------------------------- Get mobile list from category --------------------------
def get_mobile_info(headers, url):
    try:
        res = retry_request(url, headers=headers)
        if not res:
            return [], True

        soup = BeautifulSoup(res.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag or not script_tag.string:
            raise Exception("Could not find __NEXT_DATA__ script")

        page_data = json.loads(script_tag.string)
        queries = (
            page_data.get('props', {})
            .get('pageProps', {})
            .get('dehydratedState', {})
            .get('queries', [])
        )

        if not queries or len(queries) < 6:
            print("⚠️ Queries missing or short, skipping")
            return [], True

        mobile_lists_obj = queries[5]
        mobiles = (
            mobile_lists_obj.get('state', {}).get('data', {}).get('results', [])
        )
        mobile_urls = []
        page_number_flag = False

        for mobile in mobiles:
            if not mobile.get('available'):
                page_number_flag = True
                break

            mobile_title = mobile.get('name', '').strip()
            mobile_code = mobile.get('code', '').split('-')[-1]
            if not mobile_title or not mobile_code:
                continue

            mobile_url = f"https://www.technolife.ir/product-{mobile_code}/{mobile_title.replace(' ','-')}"
            mobile_urls.append(mobile_url)

        return mobile_urls, page_number_flag

    except Exception:
        error_message = traceback.format_exc()
        print(f"Error in scraping {url}: {error_message}")
        update_code_execution_state("Tecnolife", False, error_message)
        return [], True


# -------------------------- Iterate all categories --------------------------
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
        '69_70_85/nothing-phone/',
    ]

    all_urls = []
    for phone_model in phone_model_list:
        for i in range(1, 5):
            url = f'https://www.technolife.ir/product/list/{phone_model}?page={i}'
            urls, stop_flag = get_mobile_info(HEADERS, url)
            all_urls.extend(urls)
            if stop_flag:
                break
    print(f"Total collected: {len(all_urls)} URLs")
    return all_urls


# -------------------------- Retry wrapper --------------------------
def retry_main(max_retries=2, delay=5):
    retries = 0
    urls = main()
    while not urls and retries < max_retries:
        print(f"Retrying ({retries+1})...")
        time.sleep(delay)
        urls = main()
        retries += 1
    if not urls:
        raise Exception("No mobile URLs found after retries")
    return urls


# -------------------------- Utility --------------------------
not_active_texts = [
    'Not Active', 'Not Activate', 'Not Activated', 'not active',
    'not-active', "Not_Active", 'NOT_ACTIVE', 'Not-Active',
    'NOT-ACTIVE', 'ٔNOT ACTIVE', 'نات اکتیو', 'نات-اکتیو'
]

kilo_mega_giga_tra = {
    'کیلوبایت': 'KB', 'مگابایت': 'MB', 'گيگابايت': 'GB',
    'گیگابایت': 'GB', 'ترابایت': 'TB'
}


letter_to_digit_obj = {
    '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۶': '6', '۸': '8',
    '۱۲': '12', '۱۶': '16', '۳۲': '32', '۴۸': '48', '۶۴': '64',
    '۱۲۸': '128', '۲۵۶': '256', '۵۱۲': '512',
    'یک': '1', 'دو': '2', 'سه': '3', 'چهار': '4', 'شش': '6', 'هشت': '8'
}


def extract_model_form_title_en(title_en):
    try:
        model = ''
        for word in title_en[1:]:
            if 'GB' in word or word in ['Dual', 'Single', 'DualSIM']:
                break
            model += word + ' '
            if word == 'Mini':
                break
        return model.strip()
    except Exception:
        return ''


def extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, value):
    try:
        memory_ram = value.split(' ')
        if len(memory_ram) < 2:
            return 'ندارد'

        for key, val in kilo_mega_giga_tra.items():
            memory_ram = [x.replace(key, val) for x in memory_ram]

        for key, val in letter_to_digit_obj.items():
            memory_ram = [x.replace(key, val) for x in memory_ram]

        return ''.join(memory_ram[:2])
    except Exception:
        err = traceback.format_exc()
        update_code_execution_state("Tecnolife", False, err)
        return 'ندارد'


def set_other_obj_data(other_data_obj, mobile_obj, url):
    try:
        en_title = mobile_obj['product_info']['model'].split(' ')
        fa_title = mobile_obj['product_info']['title']
        other_data_obj['title'] = fa_title
        other_data_obj['vietnam'] = 'Vietnam' in en_title
        brand = en_title[0]
        other_data_obj['brand'] = 'xiaomi' if brand.lower() == 'poco' else brand
        other_data_obj['model'] = extract_model_form_title_en(en_title)
        other_data_obj['active'] = True
        other_data_obj['mobile'] = True
        other_data_obj['site'] = 'Tecnolife'
        other_data_obj['dual_sim'] = True
        other_data_obj['url'] = url
        other_data_obj['max_price'] = 1

        # بررسی نات اکتیو بودن
        joined_en = " ".join(en_title)
        is_not_active = any(txt in joined_en or txt in fa_title for txt in not_active_texts)
        other_data_obj['not_active'] = is_not_active
    except Exception:
        err = traceback.format_exc()
        update_code_execution_state("Tecnolife", False, err)


# -------------------------- Main Crawler --------------------------
@shared_task(bind=True, max_retries=1)
def tecnolife_crawler(self):
    all_mobile_urls = retry_main()
    try:
        batch_id = f"Tecnolife-{uuid.uuid4().hex[:12]}"
        all_mobiles_objects = []

        for url in all_mobile_urls:
            try:
                res = retry_request(url, headers=HEADERS)
                if not res:
                    continue
                soup = BeautifulSoup(res.text, 'html.parser')
                data_script = soup.find('script', {'id': '__NEXT_DATA__'})
                if not data_script:
                    continue

                obj = json.loads(data_script.get_text())
                mobile_obj = obj['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']

                all_color_bojects = []
                for color_item in mobile_obj.get('seller_items_component', []):
                    same_color_sellers = []
                    color_name = color_item.get('color', {}).get('value', 'نامشخص')
                    color_hex = color_item.get('color', {}).get('code', '#000')

                    for seller in color_item.get('seller_items', []):
                        if seller.get('available'):
                            same_color_sellers.append({
                                'color_name': color_name,
                                'color_hex': color_hex,
                                'seller': seller.get('seller', 'نامشخص'),
                                'guarantee': seller.get('guarantee', ''),
                                'mobile_digi_id': seller.get('_id', ''),
                                'min_price': seller.get('discounted_price', 0) * 10
                            })

                    if same_color_sellers:
                        min_price_obj = min(same_color_sellers, key=lambda x: x['min_price'])
                        all_color_bojects.append(min_price_obj)

                # مشخصات فنی
                other_data_obj = {}
                for conf in mobile_obj.get('configurations_component', []):
                    if conf.get('title') == 'حافظه':
                        for info in conf.get('info', []):
                            item = info.get('item', '')
                            val = info.get('value', '')
                            if item == 'حافظه داخلی':
                                other_data_obj['memory'] = extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, val)
                            if item == 'حافظه RAM':
                                other_data_obj['ram'] = extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, val)

                        other_data_obj.setdefault('ram', 'ندارد')
                        other_data_obj.setdefault('memory', 'ندارد')

                set_other_obj_data(other_data_obj, mobile_obj, url)
                for mobile in all_color_bojects:
                    mobile.update(other_data_obj)

                all_mobiles_objects.extend(all_color_bojects)

            except Exception:
                err = traceback.format_exc()
                update_code_execution_state("Tecnolife", False, f"Error in {url}: {err}")
                continue

        for mobile_dict in all_mobiles_objects:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site="Tecnolife", mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(
            "Tecnolife",
            bool(all_mobiles_objects),
            'هیچ محصولی پیدا نشد.' if not all_mobiles_objects else ''
        )

    except Exception:
        error_message = traceback.format_exc()
        print(f"Error {error_message}")
        update_code_execution_state("Tecnolife", False, error_message)
        raise self.retry(exc=Exception(error_message), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site='Tecnolife',
            status=True,
            mobile=True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
