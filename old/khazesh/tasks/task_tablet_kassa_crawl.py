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






@shared_task(bind=True, max_retries=0)
def tablet_kassa_crawler(self):
    try:
        brands_key = { 
            "شیائومی": "xiaomi",
            "سامسونگ": "samsung",
            "اپل": "apple",
        }

        SITE = "Kasrapars"
        SELLER = "Kasrapars"

        all_tablet_objects = []
        for page_num in range(0, 6):
            response: ResponseType = retry_request(f"https://api.Kasrapars.ir/api/web/v10/product/index-brand?page={page_num}&responseFields%5B0%5D=items&status_available=1&expand=letMeKnowOnAvailability%2Cvarieties%2CcartFeatures%2CcoworkerShortName%2CpromotionCoworker%2Cbrand&category_slug=tablet&brand_slug[]=samsung", 'Kasrapars')
            # print(response.text)
            if not response:
                error_message = f"Response status code:  { response.status_code}"
                # print(url, error_message)
                update_code_execution_state('Kasrapars-tablet', False, error_message)
                continue

            # print(json.loads(response.text))
            print('---------------------------------------Kasrapars')
                
            
            for item in json.loads(response.text)['items']['items']:
                tablet_object: dict = {}
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


                    tablet_object["model"] = model
                    tablet_object["memory"] = memory
                    tablet_object["ram"] = ram
                    tablet_object["brand"] = brands_key.get(brand, brand)
                    # tablet_object['title_en'] = en_title
                    tablet_object["title"] = fa_title
                    tablet_object["url"] = f"https://plus.Kasrapars.ir/product/{slug}"
                    tablet_object["site"] = 'Kasrapars'
                    tablet_object["seller"] = varieties['company']['company_name']
                    tablet_object["guarantee"] = guarantee
                    tablet_object["max_price"] = 1
                    tablet_object["mobile_digi_id"] = ""
                    tablet_object["dual_sim"] = True
                    tablet_object["active"] = True
                    tablet_object["mobile"] = False
                    tablet_object["vietnam"] = vietnam
                    
                    print(vietnam)
                    
                    tablet_object["not_active"] = (
                        True
                        if "نات اکتیو" in fa_title or "not active" in en_title.lower()
                        else False
                    )
                    tablet_object["color_name"] = varieties['color']['color_name']
                    tablet_object["color_hex"] = varieties['color']['hexcode']
                    tablet_object["min_price"] = varieties['price_off']
                    all_tablet_objects.append(tablet_object.copy())



        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = 'Kasrapars',
            status = True,
            mobile = False,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        
        
        for tablet_dict in all_tablet_objects:
            save_obj(tablet_dict)

        update_code_execution_state('Kasrapars-tablet', True)

    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state('Kasrapars-tablet', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)
