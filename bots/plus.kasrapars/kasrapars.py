import requests
import json
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from requests import Response
import time 
from itertools import chain
import re
from typing import List , Optional
ResponseType = Optional[Response]
OptionalList = Optional[List]

SITE = 'Kasrapars'
SELLER = 'Kasrapars'
HEADERS = {
    'From': 'behnammohammadi149@gmail.com', 
    }

all_mobile_objects = []

def retry_request(url: str, max_retries:int=1, retry_delay:int=1) -> ResponseType:
    for i in range(max_retries):
        try:
            response = requests.get(url)
            # response.raise_for_status()
            print("Connection successful")
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            # save_error_to_log(url, error_message)
            print(url, error_message)
            if i < max_retries - 1:
                print("Retrying...")
                time.sleep(retry_delay)
        except RequestException as re:
            error_message = f"Other request error: {re}"
            print(url, error_message)
            return None
    return None

all_existing_products_url: List[List] = []

kilo_mega_giga_tra = {
    'کیلوبایت': 'KB',

    'مگابایت': 'MB',
    'گیگابایت': 'GB',
    'ترابایت': 'TB'
}
brands_key = {'شیائومی': 'xiaomi',
              'سامسونگ':'samsung',
              'اپل':'apple',
              'پوکو':'poco',
              'آنر': 'honor',
              'نوکیا':'nokia'}

break_outer_for =False

for page_num in range(0, 6):       
            
            response: ResponseType = retry_request(f"https://api.Kasrapars.ir/api/web/v10/product/index-brand?expand=letMeKnowOnAvailability%2Cvarieties%2CcartFeatures%2CcoworkerShortName%2CpromotionCoworker%2Cbrand&status_available=1&category_slug=mobilephone&page={page_num}&responseFields%5B0%5D=items",)
            # print(response.text)
            if not response:
                error_message = f"Response status code:  { response.status_code}"
                # print(url, error_message)
                continue


                 
            print(json.loads(response.text))
            print('---------------------------------------Kasrapars')
                
            
            for item in json.loads(response.text)['items']['items']:
                mobile_object: dict = {}
                brand = item['brand']['brand_name']
                if brand not in brands_key:
                    continue

                
                en_title = item['product_name_en']
                fa_title = item['product_name']
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
                    if 'VIT' in varieties['pack']['en_name']:
                        vietnam = True


                    mobile_object["model"] = model
                    mobile_object["memory"] = memory
                    mobile_object["ram"] = ram
                    mobile_object["brand"] = brands_key.get(brand, brand)
                    # mobile_object['title_en'] = en_title
                    mobile_object["title"] = fa_title
                    mobile_object["url"] = '#'
                    mobile_object["site"] = SITE
                    mobile_object["seller"] = varieties['company']['company_name']
                    mobile_object["guarantee"] = guarantee
                    mobile_object["max_price"] = 1
                    mobile_object["mobile_digi_id"] = ""
                    mobile_object["dual_sim"] = True
                    mobile_object["active"] = True
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

            
