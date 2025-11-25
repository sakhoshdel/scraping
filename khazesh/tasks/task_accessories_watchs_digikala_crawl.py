import re
import traceback
from typing import Dict, List, Tuple, Optional
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
    try:
        status = obj["data"]["product"]["status"]
        if status != "marketable":
            return None

        variants = obj["data"]["product"]["variants"]

        # فقط واریانت‌هایی که color دارند
        valid_variants = [v for v in variants if "color" in v]

        if not valid_variants:
            return None  # هیچ واریانت رنگ‌دار نیست

        # استخراج رنگ‌ها
        colors_obj_list = [v["color"] for v in valid_variants if v.get("color")]
        colors_obj_list = [obj for n, obj in enumerate(colors_obj_list) if obj not in colors_obj_list[n + 1:]]

        colors = [(c["hex_code"], c["title"]) for c in colors_obj_list]

        variant_objects = []

        for hex_code, color_title in colors:
            variant_obj = {"color_name": color_title, "color_hex": hex_code, "variants": []}

            prices = []
            for variant in valid_variants:
                if variant["color"]["hex_code"] == hex_code:
                    price = variant["price"]["selling_price"]
                    prices.append(price)
                    variant_obj["variants"].append(variant)

            if not prices:
                continue

            variant_obj["min_price"] = min(prices)
            variant_obj["max_price"] = max(prices)

            min_price_variant = min(
                variant_obj["variants"],
                key=lambda x: x["price"]["selling_price"]
            )

            variant_obj["seller"] = min_price_variant["seller"]["title"]
            variant_obj["guarantee"] = min_price_variant["warranty"]["title_fa"]

            variant_obj.pop("variants")
            variant_objects.append(variant_obj)

        return variant_objects

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'watchs', False, error_message)
        print(error_message)
        return None


def extract_url(obj):
    try:
        uri = obj["data"]["product"]["url"]["uri"].split("/")[1:-1]
        return f"https://digikala.com/{'/'.join(uri)}"
    except Exception:
        return "https://digikala.com"


def extract_mobile_ids(url, cookies, headers):
    try:
        obj = requests.get(url, headers=headers, cookies=cookies)
        if obj.status_code != 200:
            error_message = f"HTTP {obj.status_code} while fetching product IDs from {url}"
            accessories_update_code_execution_state('Digikala', 'watchs', False, error_message)
            print(error_message)
            return None

        obj = obj.json()
        http_status_code = obj.get("status")
        mobile_urls = []

        if http_status_code == 200:
            for product in obj["data"]["products"]:
                if product.get("status") == "marketable":
                    pid = product["id"]
                    mobile_urls.append(f"https://api.digikala.com/v2/product/{pid}/")
        else:
            print(f"http_status_code from get_mobile_ids: {http_status_code}")

        return mobile_urls

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'watchs', False, error_message)
        print(f"Error {error_message}")
        return None


def extract_mobile_data(url, cookies, headers, category):
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        if response.status_code != 200:
            error_message = f"HTTP {response.status_code} while fetching {url}"
            accessories_update_code_execution_state('Digikala', 'watchs', False, error_message)
            print(error_message)
            return None

        obj = response.json()
        http_status_code = obj.get("status")
        if http_status_code != 200:
            return None

        product = obj["data"]["product"]
        if product.get("status") != "marketable":
            return None

        title_en_list = product["title_en"].strip().split(" ")
        title_fa = product["title_fa"]

        brand_title = product["brand"]["title_en"]
        brand = BrandAccessories.objects.filter(name_en=brand_title).first()
        if not brand:
            brand = BrandAccessories.objects.create(name_fa=brand_title, name_en=brand_title)

        base_obj = {
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
                v.update(base_obj)
            return variants
        base_obj["stock"] = False
        base_obj["min_price"] = 0
        base_obj["max_price"] = 0
        return [base_obj]

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'watchs', False, error_message)
        print(f"Error {error_message}")
        return None


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
        service = Service(executable_path="/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(URL)
        time.sleep(5)
        cookies = {cookie["name"]: cookie["value"] for cookie in driver.get_cookies()}
        return cookies
    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'watchs', False, error_message)
        print(f"Error {error_message}")
        return None
    finally:
        if driver:
            driver.quit()


@shared_task(bind=True, max_retries=1)
def accessories_watchs_digikala_crawler(self):
    url_list = []
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = get_cookie()

    try:
        if not cookies:
            accessories_update_code_execution_state('Digikala', 'watchs', False, "Failed to get cookies.")
            return

        category = CategoryAccessories.objects.filter(name_en='watchs').first()
        url_digi = (
            "https://api.digikala.com/v1/categories/wearable-gadget/search/"
            "?brands%5B0%5D=21761&brands%5B1%5D=14944&brands%5B2%5D=14347"
            "&brands%5B3%5D=10&brands%5B4%5D=18&brands%5B5%5D=2497&brands%5B6%5D=31732"
            "&brands%5B7%5D=1662&brands%5B8%5D=39851&brands%5B9%5D=82&has_selling_stock=1&page=1"
        )

        response = requests.get(url_digi, headers=headers)
        if response.status_code != 200:
            accessories_update_code_execution_state('Digikala', 'watchs', False, f"HTTP {response.status_code} on initial request.")
            return

        data = response.json()
        total_pages = data["data"]["pager"]["total_pages"]

        if total_pages <= 0:
            accessories_update_code_execution_state('Digikala', 'watchs', False, "No pages found for Digikala watchs.")
            return

        for i in range(total_pages):
            link = f"https://api.digikala.com/v1/categories/wearable-gadget/search/?brands%5B0%5D=21761&brands%5B1%5D=14944&brands%5B2%5D=14347&brands%5B3%5D=10&brands%5B4%5D=18&brands%5B5%5D=2497&brands%5B6%5D=31732&brands%5B7%5D=1662&brands%5B8%5D=39851&brands%5B9%5D=82&has_selling_stock=1&page={i+1}"
            url_list.append(link)

        all_mobile_urls = []
        for url in url_list:
            ids = extract_mobile_ids(url, cookies, headers)
            if ids:
                all_mobile_urls.extend(ids)

        if not all_mobile_urls:
            accessories_update_code_execution_state('Digikala', 'watchs', False, "No product URLs found.")
            return

        mobile_datas_list = []
        for url in all_mobile_urls:
            data = extract_mobile_data(url, cookies, headers, category)
            if data:
                mobile_datas_list.extend(data)

        if not mobile_datas_list:
            accessories_update_code_execution_state('Digikala', 'watchs', False, "No product data found.")
            return

        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        ProductAccessories.objects.filter(
            site='Digikala',
            status=True,
            updated_at__lt=ten_min_ago,
            category__name_en='watchs'
        ).update(status=False)

        for mobile_dict in mobile_datas_list:
            save_obj(mobile_dict)

        accessories_update_code_execution_state('Digikala', 'watchs', True)

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Digikala', 'watchs', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)

