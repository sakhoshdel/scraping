import json
import re
import traceback
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging
from khazesh.models import BrandAccessories, CategoryAccessories
from khazesh.tasks.save_accessories_object_to_database import save_obj
from khazesh.tasks.save_accessories_crawler_status import accessories_update_code_execution_state
from requests.exceptions import ConnectionError, RequestException
import time
import traceback
from typing import List, Optional, Tuple
from requests import Response
from khazesh.models import ProductAccessories
from django.utils import timezone

ResponseType = Optional[Response]
OptionalList = Optional[List]
def retry_request(
    url: str,
    site: str,
    category: str,
    max_retries: int = 1,
    retry_delay: int = 0,
) -> ResponseType:
    HEADERS = {
        "From": "ali.taravati.hamid@gmail.com",
    }
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS)
            # response.raise_for_status()
            
            print("Connection successful Accessories Kasra")
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
            accessories_update_code_execution_state(site, category, False, error_message)
            return None
    return None

HEADERS = {
    'From': 'ali.taravati.hamid@gmail.com', }





@shared_task(bind=True, max_retries=1)
def accessories_charger_kasra_crawler(self):
    try:
        

        all_mobile_objects = []
        category = CategoryAccessories.objects.filter(name_en='charger').first()
        for page_num in range(0, 3):
            response: ResponseType = retry_request(f"https://api.Kasrapars.ir/api/web/v10/product/index-brand?expand=varieties.minOrderCount%2CletMeKnowOnAvailability%2Cvarieties%2CcartFeatures%2CcoworkerShortName%2Csrc%2CisInWishList%2CpromotionCoworker%2Cdescription%2Cbrand&page={page_num}&responseFields%5B0%5D=items&category_slug=mobile-charger&status_available=1&brand_slug[]=samsung", 'Kasrapars', 'charger')
            # print(response.text)
            if not response:
                error_message = f"Response status code:  { response.status_code}"
                # print(url, error_message)
                accessories_update_code_execution_state('Kasrapars', 'charger', False, error_message)
                continue

            # print(json.loads(response.text))
            print('Accessories charger Kasrapars')
                
            
            for item in json.loads(response.text)['items']['items']:
                mobile_object: dict = {}
                
                brand = BrandAccessories.objects.filter(name_en=item['brand']['slug']).first()
                if not brand:
                    brand = BrandAccessories.objects.create(name_fa=item['brand']['brand_name'], name_en=item['brand']['slug'])

                
                en_title = item['product_name_en']
                fa_title = item['product_name']
                slug = item['slug']
                model = item['short_name']
                fake = item['fake']

                
                
                for varieties in item['varieties']:
                    description = ''
                    for stocks in varieties['stocks']:
                        '<b>{stocks["count"]}</b>'
                        description = description + f'در انبار <b>{stocks["store"]["name"]}</b> شهر  <b>{stocks["city"]["name"]}</b> تعداد موجودی این شارژر <b>{stocks["count"]}</b> می باشد. <hr>'
                    guarantee = varieties['guarantee']['guranty_name']

                
                    
                    mobile_object["model"] = model
                    mobile_object["brand"] = brand
                    mobile_object["category"] = category
                    mobile_object["title"] = fa_title
                    mobile_object["url"] = f"https://plus.Kasrapars.ir/product/{slug}"
                    mobile_object["site"] = 'Kasrapars'
                    mobile_object["seller"] = varieties['company']['company_name']
                    mobile_object["guarantee"] = guarantee
                    mobile_object["max_price"] = 1
                    mobile_object["stock"] = varieties['status']['can_buy']
                    mobile_object["fake"] = fake
                    mobile_object["color_name"] = varieties['color']['color_name']
                    mobile_object["color_hex"] = varieties['color']['hexcode']
                    mobile_object["min_price"] = varieties['price_off']
                    mobile_object["description"] = description
                    all_mobile_objects.append(mobile_object.copy())

        
        
        # ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        # ProductAccessories.objects.filter(
        #     site = 'Kasrapars',
        #     status = True,
        #     updated_at__lt=ten_min_ago,
        #     category__name_en='charger'
        # ).update(status=False)
        
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict)

        accessories_update_code_execution_state('Kasrapars', 'charger', True)

    except Exception as e:
        error_message = str(traceback.format_exc())
        accessories_update_code_execution_state('Kasrapars', 'charger', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)
