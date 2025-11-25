import json
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging

from khazesh.models import BrandAccessories, CategoryAccessories
from khazesh.models import ProductAccessories
from khazesh.tasks.save_accessories_object_to_database import save_obj
from khazesh.tasks.save_accessories_crawler_status import accessories_update_code_execution_state
import time
import traceback
from django.utils import timezone


def retry_request(url: str, headers, max_retries: int = 1, retry_delay: int = 1):
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            logging.info("Connection successful")
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            logging.error(f"{url} - {error_message}")
            accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
            print(f"{url} - {error_message}")
            if i < max_retries - 1:
                logging.info("Retrying...")
                time.sleep(retry_delay)
        except requests.RequestException as re:
            error_message = f"Request error: {re}"
            logging.error(f"{url} - {error_message}")
            accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
            print(f"{url} - {error_message}")
            return None
        except Exception:
            error_message = traceback.format_exc()
            accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
            print(error_message)
            return None
    return None


HEADERS = {
    'From': 'behnammohammadi149@gmail.com',
}


def get_mobile_info(headers, url):
    try:
        res = retry_request(url, headers=headers)
        if not res:
            return [], True
        soup = BeautifulSoup(res.text, 'html.parser')
        if soup.find('script', id='__NEXT_DATA__'):
            try:
                tenco_page_obj = json.loads(soup.find('script', id='__NEXT_DATA__').string.encode().decode())
            except Exception:
                accessories_update_code_execution_state('Tecnolife', 'watchs', False, '❌ JSON parse error in get_mobile_info')
                print('❌ JSON parse error in get_mobile_info')
                return [], True

            tecno_queries = tenco_page_obj.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
            if len(tecno_queries) < 6:
                accessories_update_code_execution_state('Tecnolife', 'watchs', False, '❌ Unexpected query structure in get_mobile_info')
                return [], True

            mobile_lists_obj = tecno_queries[5]
            mobiles = mobile_lists_obj.get('state', {}).get('data', {}).get('results', [])
            mobile_urls = []
            page_number_flag = False

            for mobile in mobiles:
                if not mobile.get('available'):
                    page_number_flag = True
                    break
                mobile_title = mobile.get('name', '').replace(' ', '-').strip()
                mobile_code_parts = mobile.get('code', '').split('-')
                if len(mobile_code_parts) < 2:
                    continue
                mobile_code = mobile_code_parts[1]
                mobile_url = f"https://www.technolife.ir/product-{mobile_code}/{mobile_title}"
                mobile_urls.append(mobile_url)

            return mobile_urls, page_number_flag
        else:
            print('⚠️ No __NEXT_DATA__ found in page')
            return [], True
    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
        print(f"Error in scraping {url}:\n{error_message}")
        print('Error come from get_mobile_info (function)')
        return [], True


def extract_model_form_title_en(title_en):
    title_en_list = title_en
    model = ''
    for word in title_en_list[1:]:
        if 'GB' in word:
            break
        if word in ['Dual', 'Single', 'DualSIM']:
            break
        model += word + ' '
        if word == 'Mini':
            break
    return model.strip()


def set_other_obj_data(other_data_obj, mobile_obj, url, category):
    try:
        fa_title = mobile_obj['product_info']['title']
        other_data_obj['title'] = fa_title

        en_title = []
        brand_slug = 'نامشخص'
        model = ''

        try:
            model_str = mobile_obj['product_info'].get('model', None)
            if not model_str or len(model_str.strip()) == 0:
                model = extract_model_form_title_en([])
            else:
                en_title = model_str.split(' ')
                if len(en_title) > 0:
                    brand_slug = en_title[0]
                else:
                    brand_slug = 'نامشخص'
                model = fa_title
        except Exception:
            brand_slug = 'نامشخص'
            model = extract_model_form_title_en([])

        known_brands = ['kieslect', 'xiaomi', 'TCH', 'huawei', 'mibro', 'haylou', 'imilab', 'amazfit', 'samsung', 'apple']
        if brand_slug.lower() in known_brands:
            brand = BrandAccessories.objects.filter(name_en=brand_slug).first()
            if not brand:
                brand = BrandAccessories.objects.create(name_fa=brand_slug, name_en=brand_slug)
        else:
            brand = BrandAccessories.objects.filter(name_fa='نامشخص').first()

        other_data_obj['category'] = category
        other_data_obj['brand'] = brand
        other_data_obj['model'] = model
        other_data_obj['stock'] = True
        other_data_obj['site'] = 'Tecnolife'
        other_data_obj['url'] = url
        other_data_obj['max_price'] = 1
        other_data_obj['fake'] = False
        other_data_obj['description'] = ''
    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
        print(f"Error in set_other_obj_data:\n{error_message}")


def main():
    phone_model_list = ['30_162_330/ساعت-هوشمند?manufacturer_id=152_44_149_20_26_45_227_15_546_23&only_available=true']
    mobile_all_urls = []
    try:
        for phone_model in phone_model_list:
            for i in range(4):
                url = f'https://www.technolife.ir/product/list/{phone_model}&page={i + 1}'
                mobile_urls, mobile_page_flag = get_mobile_info(HEADERS, url)
                mobile_all_urls.extend(mobile_urls)
                if mobile_page_flag:
                    break
        print(mobile_all_urls)
        print(len(mobile_all_urls))
        return mobile_all_urls
    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
        print(f"Error in main():\n{error_message}")
        return []


def retry_main(max_retries=3, delay=5):
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


@shared_task(bind=True, max_retries=1)
def accessories_watchs_tecnolife_crawler(self):
    try:
        all_mobile_urls = retry_main()
        all_mobiles_objects = []

        category = CategoryAccessories.objects.filter(name_en='watchs').first()
        for url in all_mobile_urls:
            try:
                res = retry_request(url, headers=HEADERS)
                if not res:
                    continue
                soup = BeautifulSoup(res.text, 'html.parser')

                script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
                if not script_tag:
                    continue
                obj = json.loads(script_tag.get_text())
                mobile_obj = obj['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']

                if mobile_obj is not None:
                    all_color_bojects = []
                    same_color_seller_obj = []

                    for obj in mobile_obj['seller_items_component']:
                        color_name = obj['color']['value']
                        color_hex = obj['color']['code']
                        seller_items = obj['seller_items']

                        for seller in seller_items:
                            if seller['available']:
                                same_color_seller_obj.append({
                                    'color_name': color_name,
                                    'color_hex': color_hex,
                                    "seller": seller['seller'],
                                    'guarantee': seller['guarantee'],
                                    'min_price': seller['discounted_price'] * 10
                                })

                        all_color_bojects.append(same_color_seller_obj)
                        same_color_seller_obj = []

                    all_color_bojects = list(filter(lambda x: bool(x), all_color_bojects))
                    last_mobil_objests = []
                    for same_color_mobiles in all_color_bojects:
                        min_price_obj = min(same_color_mobiles, key=lambda x: x['min_price'])
                        last_mobil_objests.append(min_price_obj)

                    other_data_obj = {}
                    set_other_obj_data(other_data_obj, mobile_obj, url, category)
                    print(url)
                    for mobile in last_mobil_objests:
                        mobile.update(other_data_obj)

                    all_mobiles_objects.extend(last_mobil_objests)

            except Exception:
                error_message = traceback.format_exc()
                accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
                print(f"Error in processing url {url}:\n{error_message}")
                continue

        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        ProductAccessories.objects.filter(
            site='Tecnolife',
            status=True,
            updated_at__lt=ten_min_ago,
            category__name_en='watchs'
        ).update(status=False)

        for mobile_dict in all_mobiles_objects:
            save_obj(mobile_dict)

        accessories_update_code_execution_state('Tecnolife', 'watchs', True)

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Tecnolife', 'watchs', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)
