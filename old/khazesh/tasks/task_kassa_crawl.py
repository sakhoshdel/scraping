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
import traceback
from typing import List, Optional, Tuple
from requests import Response

from khazesh.models import Mobile
from django.utils import timezone

ResponseType = Optional[Response]
OptionalList = Optional[List]
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
            response = requests.get(url, headers=HEADERS)
            # response.raise_for_status()
            
            print("Connection successful Kasra")
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+0}: {ce}"
            # save_error_to_log(url, error_message)
            print(url, error_message)
            if i < max_retries - 0:
                print("Retrying...")
                time.sleep(retry_delay)
        except RequestException as re:
            error_message = f"Other request error: {re}"
            # print(url, error_message)
            update_code_execution_state(site, False, error_message)
            return None
    return None

HEADERS = {
    'From': 'behnammohammadi149@gmail.com', }


def get_mobile_info(headers, url):
    try:
        res = retry_request(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        tenco_page_obj = json.loads(soup.find('script', id='__NEXT_DATA__').string.encode().decode())
        tecno_queries =tenco_page_obj.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        mobile_lists_obj = tecno_queries[4]
        
        mobiles = mobile_lists_obj.get('state', {}).get('data').get('results', [])
        mobile_urls = []
        # available_mobiles = list(filter(lambda mobile: mobile.get('available', 0), mobiles))
        page_number_flag = False
        for mobile in mobiles:
            if not mobile.get('available'):
                page_number_flag = True
                break
            mobile_title = mobile.get('name')
            mobile_code = mobile.get('code', '').split('-')[1]
            mobile_url = f"https://www.technolife.ir/product-{mobile_code}/{mobile_title.replace(' ','-').strip()}"
            mobile_urls.append(mobile_url)
            

        return mobile_urls, page_number_flag
    except Exception as e:
        print(f"Error in scraping {url}: {str(e)}")
        print('Error come from get_mobile_info (function)')
        return [], True

def main():
    phone_model_list = ['69_70_73/apple/',
                        '69_70_77/samsung',
                        '69_70_79/xiaomi',
                        '69_70_799/poco',
                        '69_70_80/nokia',
                        '69_70_780/motorola',
                        '69_70_798/huawei',
                        '69_70_74/honor',
                        '69_70_804/گوشی-موبایل-ریلمی-realme/',
                        '69_70_85/nothing-phone/']
    # phone_model_list = [ '69_70_80/nokia', ]


    mobile_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):

            url = f'https://www.technolife.ir/product/list/{phone_model}?page={i + 1}'
            mobile_urls, mobile_page_flag = get_mobile_info(HEADERS, url)
            mobile_all_urls.extend(mobile_urls)
            if mobile_page_flag:
                break
    print(mobile_all_urls)
    print(len(mobile_all_urls))
    return mobile_all_urls


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

not_active_texts = ['Not Active','Not Activate','Not Activated',  'not active', 'not-active', "Not_Active", 'NOT_ACTIVE', 'Not-Active', 'NOT-ACTIVE', 'ٔNOT ACTIVE', 'نات اکتیو', 'نات-اکتیو'] 

kilo_mega_giga_tra = {
    'کیلوبایت': 'KB',
    'مگابایت': 'MB',
    'گيگابايت': 'GB',
    'گیگابایت': 'GB',
    'ترابایت': 'TB'
}

letter_to_digit_obj = {
    '1': '1',
    '۱': '1',
    'یک': '1',
    '2': '2',
    '۲': '2',
    'دو': '2',
    '3': '3',
    '۳': '3',
    'سه': '3',
    '4': '4',
    '۴': '4',
    'چهار': '4',
    '6': '6',
    '۶': '6',
    'شش': '6',
    '8': '8',
    '۸': '8',
    'هشت': '8',
    '12': '12',
    '۱۲': '12',
    '16': '16',
    '۱۶': '16',
    '32': '32',
    '۳۲': '32',
    '48': '48',
    '۴۸': '48',
    '64': '64',
    '۶۴': '64',
    '128': '128',
    '۱۲۸': '128',
    '256': '256',
    '۲۵۶': '256',
    '512': '512',
    '۵۱۲': '512',
}


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


def extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, value):
    memory_ram = value.split(' ')
    memory_ram_1 = ''
    memory_ram_0 = ''
    if len(memory_ram) < 2:
        # print("Invalid format for memory value:", memory_ram)
        return 'ندارد'
    
    print('memory_ram', memory_ram)
    memory_ram_1 = memory_ram[1].replace('،', '').replace('\n', '').strip()
    memory_ram_0 = memory_ram[0].replace('،', '').replace('\n', '').strip()
    try:
        for key, value in kilo_mega_giga_tra.items():
            if memory_ram and key == memory_ram_1:
                # print('kilo_mega_giga_tra')
                memory_ram[1] = value
            elif memory_ram and key == memory_ram_0:
                memory_ram[0] = value
                # print('kilo_mega_giga_tra')

        for key, value in letter_to_digit_obj.items():
            if memory_ram and key == memory_ram[0]:
                # print('#' * 80)
                # print("letter_to_digit_obj1111")
                # print(memory_ram)
                # print('#' * 80)
                memory_ram[0] = value
                memory_ram = ''.join(memory_ram[:2])
            elif memory_ram and key == memory_ram[1]:
                # print('#' * 80)
                # print('letter_to_digit_obj')
                # print(memory_ram)
                # print('#' * 80)
                memory_ram[1] = value
                memory_ram = ''.join(memory_ram[:2])
    except Exception as e:
        error_message = str(traceback.format_exc())
        print(f"Error {error_message}")
        update_code_execution_state("Tecnolife", False, error_message)
    return memory_ram


def set_other_obj_data(other_data_obj, mobile_obj,url):
    en_title = mobile_obj['product_info']['model'].split(' ')
    fa_title = mobile_obj['product_info']['title']
    other_data_obj['title'] = fa_title
    other_data_obj['vietnam'] = True if 'Vietnam' in en_title else False
    brand = en_title[0]
    other_data_obj['brand'] = 'xiaomi' if brand in ['poco', 'Poco'] else brand
    # print(other_data_obj['brand'])
    other_data_obj['model'] = extract_model_form_title_en(en_title)
    other_data_obj['active'] = True
    other_data_obj['site'] = 'Tecnolife'
    other_data_obj['dual_sim'] = True
    other_data_obj['url'] = url
    other_data_obj['max_price'] = 1
    # other_data_obj['not_active'] = True if 'Not Active' in en_title else False
    is_not_active = any([any([True if txt in " ".join(en_title) else False for txt in not_active_texts ]), 
                         any([True if txt in fa_title else False for txt in not_active_texts ])])  
    other_data_obj['not_active'] = is_not_active
    print(" ".join(en_title), is_not_active)

# url = 'https://www.technolife.ir/product-2545'

@shared_task(bind=True, max_retries=0)
def kassa_crawler(self):
    try:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = 'Kasrapars',
            status = True,
            mobile = True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        
        brands_key = { 
            "شیائومی": "xiaomi",
            "سامسونگ": "samsung",
            "اپل": "apple",
            "پوکو": "poco",
            "آنر": "honor",
            "نوکیا": "nokia",
        }

        SITE = "Kasrapars"
        SELLER = "Kasrapars"

        all_mobile_objects = []
        for page_num in range(0, 6):
            response: ResponseType = retry_request(f"https://api.Kasrapars.ir/api/web/v10/product/index-brand?expand=letMeKnowOnAvailability%2Cvarieties%2CcartFeatures%2CcoworkerShortName%2CpromotionCoworker%2Cbrand&status_available=1&category_slug=mobilephone&page={page_num}&responseFields%5B0%5D=items", 'Kasrapars')
            # print(response.text)
            if not response:
                error_message = f"Response status code:  { response.status_code}"
                # print(url, error_message)
                update_code_execution_state('Kasrapars', False, error_message)
                continue

            # print(json.loads(response.text))
            print('---------------------------------------Kasrapars')
                
            
            for item in json.loads(response.text)['items']['items']:
                mobile_object: dict = {}
                brand = item['brand']['brand_name']
                if brand not in brands_key:
                    continue

                
                en_title = item['product_name_en']
                fa_title = item['product_name']
                slug = item['slug']
                model_pattern = r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T|gb)?|^(samsung|xiaomi|apple|nokia|honor|huawei|nothing\sphone)\s*|\s*vietnam\s*"
                model = re.sub(model_pattern, "", en_title.lower())
                if not model:
                    model = re.search(r"(?<=مدل\s)[\w\s]*\s*(?=ظرفیت)", fa_title)
                    if model:
                        model = model.group().strip()

                print(fa_title)
                print(en_title)
                
                for varieties in item['varieties']:
                    guarantee = varieties['guarantee']['guranty_name']

                
                    ram = re.search(
                        r"\s*رم\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?",
                        fa_title,
                    )
                    if ram:
                        ram = ram.group()
                        ram = re.sub(r"\s*گیگابایت\s*|\s*گگیابایت\s*", "GB", ram)
                        ram = re.sub(r"\s*رم\s*", "", ram)

                    else:
                        ram = re.search(r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T)?", en_title)
                        if ram:
                            ram = ram.group()
                            ram = re.sub(r"\s*(GB|TB|T)\s*", "", ram)
                            ram = len(ram.split("/")) >= 2 and ram.split("/")[1]
                            ram = ram + "GB"
                        else:
                            ram = "ندارد"

                    memory = re.search(
                        r"\s*ظرفیت\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?",
                        fa_title,
                    )
                    if memory:
                        memory = memory.group()
                        memory = re.sub(r"\s*گیگابایت\s*|\s*گگیابایت\s*", "GB", memory)
                        memory = re.sub(r"\s*ترابایت\s*", "TB", memory)
                        memory = re.sub(r"\s*ظرفیت\s*", "", memory)

                    else:
                        memory = re.search(r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T)?", en_title)
                        if memory:
                            memory = memory.group()
                            memory = re.sub(r"\s*(GB|TB|T)\s*", "", memory)
                            memory = (
                                len(memory.split("/")) >= 1 and memory.split("/")[0].strip()
                            )

                        else:
                            memory = "ندارد"

                    print(model)
                    print(memory)
                    print(ram)
                    vietnam = False
                    if varieties['pack'] is not None:
                        if 'VIT' in varieties['pack']['en_name']:
                            vietnam = True


                    mobile_object["model"] = model
                    mobile_object["memory"] = memory
                    mobile_object["ram"] = ram
                    mobile_object["brand"] = brands_key.get(brand, brand)
                    # mobile_object['title_en'] = en_title
                    mobile_object["title"] = fa_title
                    mobile_object["url"] = f"https://plus.Kasrapars.ir/product/{slug}"
                    mobile_object["site"] = 'Kasrapars'
                    mobile_object["seller"] = varieties['company']['company_name']
                    mobile_object["guarantee"] = guarantee
                    mobile_object["max_price"] = 1
                    mobile_object["mobile_digi_id"] = ""
                    mobile_object["dual_sim"] = True
                    mobile_object["active"] = True
                    mobile_object["mobile"] = True
                    mobile_object["vietnam"] = vietnam
                    
                    print(vietnam)
                    
                    mobile_object["not_active"] = (
                        True
                        if "نات اکتیو" in fa_title or "not active" in en_title.lower()
                        else False
                    )
                    mobile_object["color_name"] = varieties['color']['color_name']
                    mobile_object["color_hex"] = varieties['color']['hexcode']
                    mobile_object["min_price"] = varieties['price_off']
                    all_mobile_objects.append(mobile_object.copy())



        
        
        
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict)

        update_code_execution_state('Kasrapars', True)

    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state('Kasrapars', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)
