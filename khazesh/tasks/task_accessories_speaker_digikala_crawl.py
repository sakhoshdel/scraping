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
        if obj.status_code == 200:
            obj = obj.json()

        else:
            print(url)
            print("obj.status_code", obj.status_code)
            obj = {}
            return None

        # sleep(3)

        http_status_code = obj["status"]
        # print('http_status_code', http_status_code)
        mobile_urls = []
        if http_status_code == 200:
            # sleep(3)
            for i in range(len(obj["data"]["products"])):
                # print(i)
                # get each product of status
                status = obj["data"]["products"][i]["status"]
                # if status != 'comming_soon' and status != 'stop_production':
                if status == "marketable":
                    id = obj["data"]["products"][i]["id"]
                    mobile_urls.append(
                        # f'https://api.digikala.com/v1/product/{id}/')
                        f"https://api.digikala.com/v2/product/{id}/"
                    )

                    # print('len(mobile_urls)', len(mobile_urls))

        else:
            print(f"http_status_code from get_mobile_ids: {http_status_code}")

        return mobile_urls
    except Exception:
        error_message = traceback.format_exc()
        print(f"❌ [extract_mobile_ids] error:\n{error_message}")
        accessories_update_code_execution_state('Digikala', 'speaker', False, error_message)
        return []



def extract_mobile_data(url, cookies, headers, category):
    try:
        response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        if response.status_code != 200:
            accessories_update_code_execution_state('Digikala', 'speaker', False, f"Non-200 ({response.status_code}) for {url}")
            return None

        obj = response.json()
        http_status_code = obj.get("status", None)
        if http_status_code != 200:
            print(f"⚠️ Unexpected status in response ({http_status_code}) for {url}")
            return None

        product = obj.get("data", {}).get("product", {})
        if not product:
            print(f"⚠️ No product data in {url}")
            return None

        if product.get("status") != "marketable":
            return None

        title_en_list = product.get("title_en", "").strip().split(" ")
        title_fa = product.get("title_fa", "بدون عنوان")

        brand_title = product.get("brand", {}).get("title_en", "Unknown")
        brand = BrandAccessories.objects.filter(name_en=brand_title).first()
        if not brand:
            brand = BrandAccessories.objects.create(name_fa=brand_title, name_en=brand_title)

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

        same_color_variants = extract_same_color_variants(obj)
        if same_color_variants:
            for mobile in same_color_variants:
                mobile.update(my_obj)
            return same_color_variants

        my_obj["stock"] = False
        return [my_obj]

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'speaker', False, error_message)
        print(f"❌ [extract_mobile_data] error:\n{error_message}")
        return None


#
def get_cookie() -> Optional[dict]:
    """Return cookie from site"""
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

        service = Service(executable_path="/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)

        driver.get(URL)
        time.sleep(5)

        cookies = {cookie["name"]: cookie["value"] for cookie in driver.get_cookies()}
        return cookies

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'speaker', False, error_message)
        print(f"❌ [get_cookie] error:\n{error_message}")
        return None
    finally:
        if driver:
            driver.quit()


@shared_task(bind=True, max_retries=1)
def accessories_speaker_digikala_crawler(self):
    # brands = [('nothing', 2)]
    url_list = []
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    cookies = get_cookie()
    if not cookies:
        accessories_update_code_execution_state('Digikala', 'speaker', False, "Failed to retrieve cookies from site.")
        return



    try:
        category = CategoryAccessories.objects.filter(name_en='speaker').first()
        url_digi = "https://api.digikala.com/v1/categories/speaker/search/?brands%5B0%5D=1096&brands%5B1%5D=1095&brands%5B2%5D=1742&brands%5B3%5D=1662&has_selling_stock=1&page=1"
        response = requests.get(url_digi, headers=headers)
        if response.status_code == 200:
            data = response.json()
            total_pages = data["data"]["pager"]["total_pages"]

            
            if True:
                if total_pages > 0:
                    if True:
                        for i in range(total_pages):
                            link = f"https://api.digikala.com/v1/categories/speaker/search/?brands%5B0%5D=1096&brands%5B1%5D=1095&brands%5B2%5D=1742&brands%5B3%5D=1662&has_selling_stock=1&page={i+1}"
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
                        category__name_en='speaker'
                    ).update(status=False)
                    
                    
                    # save crowled objects to database
                    for mobile_dict in mobile_datas_list:
                        save_obj(mobile_dict)

                    if mobile_datas_list:
                        accessories_update_code_execution_state('Digikala', 'speaker', True)
                    else:
                        accessories_update_code_execution_state('Digikala', 'speaker', False, "No speaker products found.")


    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'speaker', False, error_message)
        print(f"❌ [accessories_speaker_digikala_crawler] crashed:\n{error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)


