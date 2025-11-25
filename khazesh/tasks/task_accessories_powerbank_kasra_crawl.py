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
    HEADERS = {"From": "ali.taravati.hamid@gmail.com"}
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                print(f"✅ Connection successful [{site}] - page {i+1}")
                return response
            else:
                error_message = f"Unexpected status code {response.status_code} for {url}"
                print(error_message)
                accessories_update_code_execution_state(site, category, False, error_message)
                return None
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            print(error_message)
            if i < max_retries - 1:
                print("Retrying...")
                time.sleep(retry_delay)
            else:
                accessories_update_code_execution_state(site, category, False, error_message)
                return None
        except RequestException as re:
            error_message = f"Request error: {re}"
            print(error_message)
            accessories_update_code_execution_state(site, category, False, error_message)
            return None
        except Exception:
            error_message = traceback.format_exc()
            accessories_update_code_execution_state(site, category, False, error_message)
            print(f"❌ retry_request unexpected error:\n{error_message}")
            return None
    return None
HEADERS = {
    'From': 'ali.taravati.hamid@gmail.com', }





@shared_task(bind=True, max_retries=1)
def accessories_powerbank_kasra_crawler(self):
    try:
        

        all_mobile_objects = []
        category = CategoryAccessories.objects.filter(name_en='powerbank').first()
        for page_num in range(0, 3):
            response: ResponseType = retry_request(f"https://api.Kasrapars.ir/api/web/v10/product/index-brand?expand=varieties.minOrderCount%2CletMeKnowOnAvailability%2Cvarieties%2CcartFeatures%2CcoworkerShortName%2Csrc%2CisInWishList%2CpromotionCoworker%2Cdescription%2Cbrand&page={page_num}&responseFields%5B0%5D=items&category_slug=powerbank&status_available=1&brand_slug[]=xiaomi&brand_slug[]=anker", 'Kasrapars', 'powerbank')
            # print(response.text)
            if not response:
                accessories_update_code_execution_state('Kasrapars', 'powerbank', False, "Response is None or failed to fetch data.")
                continue

            # print(json.loads(response.text))
            print('Accessories powerbank Kasrapars')
                
            
            try:
                data = json.loads(response.text)
                items_list = data.get('items', {}).get('items', [])
            except Exception:
                error_message = f"Invalid JSON structure on page {page_num}"
                accessories_update_code_execution_state('Kasrapars', 'powerbank', False, error_message)
                continue

            for item in items_list:
                try:
                    brand_slug = item.get('brand', {}).get('slug', 'unknown')
                    brand_name = item.get('brand', {}).get('brand_name', 'نامشخص')
                    brand = BrandAccessories.objects.filter(name_en=brand_slug).first()
                    if not brand:
                        brand = BrandAccessories.objects.create(name_fa=brand_name, name_en=brand_slug)

                    fa_title = item.get('product_name', '')
                    slug = item.get('slug', '')
                    model = item.get('short_name', '')
                    fake = item.get('fake', False)

                    for varieties in item.get('varieties', []):
                        description = ''
                        for stocks in varieties.get('stocks', []):
                            description += (
                                f'در انبار <b>{stocks["store"]["name"]}</b> شهر '
                                f'<b>{stocks["city"]["name"]}</b> تعداد موجودی این پاوربانک '
                                f'<b>{stocks["count"]}</b> می‌باشد. <hr>'
                            )
                        guarantee = varieties.get('guarantee', {}).get('guranty_name', 'ندارد')

                        mobile_object = {
                            "model": model,
                            "brand": brand,
                            "category": category,
                            "title": fa_title,
                            "url": f"https://plus.Kasrapars.ir/product/{slug}",
                            "site": 'Kasrapars',
                            "seller": varieties.get('company', {}).get('company_name', 'Kasrapars'),
                            "guarantee": guarantee,
                            "max_price": 1,
                            "stock": varieties.get('status', {}).get('can_buy', False),
                            "fake": fake,
                            "color_name": varieties.get('color', {}).get('color_name', 'نامشخص'),
                            "color_hex": varieties.get('color', {}).get('hexcode', '#FFFFFF'),
                            "min_price": varieties.get('price_off', 0),
                            "description": description
                        }
                        all_mobile_objects.append(mobile_object.copy())

                except Exception:
                    error_message = traceback.format_exc()
                    accessories_update_code_execution_state('Kasrapars', 'powerbank', False, error_message)
                    print(f"❌ Error parsing product item:\n{error_message}")
                    continue
        
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        ProductAccessories.objects.filter(
            site = 'Kasrapars',
            status = True,
            updated_at__lt=ten_min_ago,
            category__name_en='powerbank'
        ).update(status=False)
        
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict)

        if all_mobile_objects:
            accessories_update_code_execution_state('Kasrapars', 'powerbank', True)
        else:
            accessories_update_code_execution_state('Kasrapars', 'powerbank', False, "No powerbank products found on Kasrapars.")


    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Kasrapars', 'powerbank', False, error_message)
        print(f"❌ [Kasrapars - Powerbank] Crawler failed:\n{error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)

