import re
import traceback
from typing import Dict, List, Tuple,Optional

import requests
from celery import shared_task

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time

from khazesh.models import BrandAccessories, CategoryAccessories
from khazesh.models import ProductAccessories
from khazesh.tasks.save_accessories_object_to_database import save_obj
from khazesh.tasks.save_accessories_crawler_status import accessories_update_code_execution_state
from django.utils import timezone

def STATICS() -> Optional[Tuple[Dict]]:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "2222222222",
        # You can add more headers if necessary, such as Referer or Authorization headers
    }
   

    

    return headers


def extract_model_form_title(title_en_list):
    model = ""
    for word in title_en_list[1:]:
        if "GB" in word:
            break
        if word in ["Dual", "Single"]:
            break
        model += word + " "
        if word == "Mini":
            break
    return model.strip()


def extract_same_color_variants(obj):
    status = obj["data"]["product"]["status"]
    if status == "marketable":
        # colors_obj_list = obj['data']['product']['colors']
        variants = obj["data"]["product"]["variants"]

        # get colors from variants
        colors_obj_list = [variant["color"] for variant in variants]

        # remove duplicated colors
        colors_obj_list = [
            obj
            for n, obj in enumerate(colors_obj_list)
            if obj not in colors_obj_list[n + 1 :]
        ]
        colors = list(map(lambda x: (x["hex_code"], x["title"]), colors_obj_list))
        variant_objects = []
        for hex, color in colors:
            variant_obj = {"color_name": color, "color_hex": hex, "variants": []}
            prices = []
            for variant in variants:
                if variant["color"]["hex_code"] == hex:
                    price = variant["price"]["selling_price"]
                    prices.append(price)
                    variant_obj["variants"].append(variant)
            # print(prices)
            variant_obj["min_price"] = min(prices, default="EMPTY")
            variant_obj["max_price"] = max(prices, default="EMPTY")

            # finding lowest price of seller in the one color mobile
            min_price_variant = min(
                variant_obj["variants"],
                key=lambda x: x["price"]["selling_price"],
                default="EMPTY",
            )
            if min_price_variant != "EMPTY":
                variant_obj["seller"] = min_price_variant["seller"]["title"]
                variant_obj["guarantee"] = min_price_variant["warranty"]["title_fa"]
                variant_obj.pop("variants")

            variant_objects.append(variant_obj)

        return variant_objects
    # print(f'mobile phone is {status}__(extract_same_color_variants function)')
    return None


def extract_url(obj):
    uri = obj["data"]["product"]["url"]["uri"].split("/")[1:-1]
    return f"https://digikala.com/{'/'.join(uri)}"


def extract_mobile_ids(url, cookies, headers):
    try:
        obj = requests.get(url, headers=headers, cookies=cookies)
        if obj.status_code != 200:
            error_message = f"Bad status code {obj.status_code} for URL: {url}"
            accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
            print(error_message)
            return None

        data = obj.json()
        if data.get("status") != 200:
            error_message = f"Invalid API response (status={data.get('status')}) for URL: {url}"
            accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
            return None

        mobile_urls = []
        for product in data.get("data", {}).get("products", []):
            if product.get("status") == "marketable":
                pid = product.get("id")
                mobile_urls.append(f"https://api.digikala.com/v2/product/{pid}/")
        return mobile_urls

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
        print(f"❌ extract_mobile_ids failed:\n{error_message}")
        return None

def extract_mobile_data(url, cookies, headers, category):
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        if response.status_code != 200:
            error_message = f"Bad status code {response.status_code} for {url}"
            accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
            print(error_message)
            return None

        obj = response.json()
        if not obj or "data" not in obj or "product" not in obj["data"]:
            error_message = f"Unexpected JSON structure for {url}"
            accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
            print(error_message)
            return None

        product = obj["data"]["product"]
        if product.get("status") != "marketable":
            return None

        title_fa = product.get("title_fa", "")
        title_en_list = (product.get("title_en", "") or "").strip().split(" ")

        brand_title_en = product.get("brand", {}).get("title_en", "Unknown")
        brand = BrandAccessories.objects.filter(name_en=brand_title_en).first()
        if not brand:
            brand = BrandAccessories.objects.create(name_fa=brand_title_en, name_en=brand_title_en)

        my_obj = {
            "title": title_fa,
            "brand": brand,
            "category": category,
            "model": extract_model_form_title(title_en_list),
            "stock": True,
            "site": "Digikala",
            "url": extract_url(obj),
            "fake": False,
            "description": ''
        }

        variants = extract_same_color_variants(obj)
        if variants:
            for v in variants:
                v.update(my_obj)
            return variants

        my_obj["stock"] = False
        return [my_obj]

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
        print(f"❌ extract_mobile_data failed:\n{error_message}")
        return None


#
def get_cookie() -> Optional[dict]:
    URL = "https://digikala.com"
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("window-size=2000x1080")
        chrome_options.add_experimental_option("detach", True)

        CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
        service = Service(executable_path=CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(URL)
        time.sleep(5)

        cookies = driver.get_cookies()
        cook = {c["name"]: c["value"] for c in cookies}
        return cook
    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
        print(f"❌ get_cookie failed:\n{error_message}")
        return None
    finally:
        if driver:
            driver.quit()

@shared_task(bind=True, max_retries=1)
def accessories_powerbank_digikala_crawler(self):
    # brands = [('nothing', 2)]
    url_list = []
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    cookies = get_cookie()
    if not cookies:
        accessories_update_code_execution_state('Digikala', 'powerbank', False, "Failed to retrieve cookies from Digikala.")
        return
    try:
        category = CategoryAccessories.objects.filter(name_en='powerbank').first()
        url_digi = "https://api.digikala.com/v1/categories/power-bank/search/?brands%5B0%5D=704&brands%5B1%5D=68&brands%5B2%5D=1742&brands%5B3%5D=1662&brands%5B4%5D=6113&brands%5B5%5D=9054&has_selling_stock=1&page=1"
        response = requests.get(url_digi, headers=headers)
        if response.status_code != 200:
            accessories_update_code_execution_state('Digikala', 'powerbank', False, f"Failed initial API request (status={response.status_code})")
            return

        try:
            data = response.json()
            total_pages = data.get("data", {}).get("pager", {}).get("total_pages", 0)
        except Exception:
            error_message = traceback.format_exc()
            accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
            return

        if response.status_code == 200:
            data = response.json()
            total_pages = data["data"]["pager"]["total_pages"]

            
            if True:
                if total_pages > 0:
                    if True:
                        for i in range(total_pages):
                            link = f"https://api.digikala.com/v1/categories/power-bank/search/?brands%5B0%5D=704&brands%5B1%5D=68&brands%5B2%5D=1742&brands%5B3%5D=1662&brands%5B4%5D=6113&brands%5B5%5D=9054&has_selling_stock=1&page={i+1}"
                            # print('link', link)
                            url_list.append(link)

                    # print('url_list', url_list)s
                    # get Ids of mobiles
                    # all mobiles brand ids in digikala

                    all_mobile_urls = list(
                        map(lambda url: extract_mobile_ids(url, cookies, headers), url_list)
                    )
                    all_mobile_urls = sum(list(filter(None, all_mobile_urls)), [])

                    mobile_datas_list = list(
                        map(
                            lambda url: extract_mobile_data(
                                url, cookies, headers, category
                            ),
                            all_mobile_urls,
                        )
                    )
                    mobile_datas_list = sum(list(filter(None, mobile_datas_list)), [])

                    ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

                  
                    ProductAccessories.objects.filter(
                        site = 'Digikala',
                        status = True,
                        updated_at__lt=ten_min_ago,
                        category__name_en='powerbank'
                    ).update(status=False)
                    
                    
                    # save crowled objects to database
                    for mobile_dict in mobile_datas_list:
                        save_obj(mobile_dict)

                    if mobile_datas_list:
                        accessories_update_code_execution_state('Digikala', 'powerbank', True)
                    else:
                        accessories_update_code_execution_state('Digikala', 'powerbank', False, "No powerbank products found in Digikala crawl.")


    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'powerbank', False, error_message)
        print(f"❌ [Digikala - Powerbank] Crawler failed:\n{error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)


