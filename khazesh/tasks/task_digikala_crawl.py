import re
import traceback
from typing import Dict, List, Tuple, Optional

import requests
from celery import shared_task

from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
from khazesh.models import Mobile
from django.utils import timezone
import uuid
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time


def STATICS() -> Optional[Tuple[Dict]]:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "2222222222",
    }

    brands = [
        ("apple", 5),
        ("samsung", 7),
        ("xiaomi", 7),
        ("nokia", 5),
        ("huawei", 7),
        ("honor", 3),
        ("motorola", 3),
        ("nothing", 2),
        ("realme", 2),
    ]

    not_active_texts = [
        "Not Active",
        "Not Activate",
        "Not Activated",
        "not active",
        "not-active",
        "Not_Active",
        "NOT_ACTIVE",
        "Not-Active",
        "NOT-ACTIVE",
        "ٔNOT ACTIVE",
        "نات اکتیو",
        "نات-اکتیو",
    ]

    return brands, headers, not_active_texts


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
        if status == "marketable":
            variants = obj["data"]["product"]["variants"]
            colors_obj_list = [variant["color"] for variant in variants]
            colors_obj_list = [
                obj for n, obj in enumerate(colors_obj_list) if obj not in colors_obj_list[n + 1 :]
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
                variant_obj["min_price"] = min(prices, default="EMPTY")
                variant_obj["max_price"] = max(prices, default="EMPTY")

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
        return None
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Digikala", False, error_message)
        print(f"Error in extract_same_color_variants:\n{error_message}")
        return None


def extract_ram_and_memory(obj):
    try:
        title_en = obj["data"]["product"]["title_en"]
        pattern = r"(\d+GB) | (\d+TB)"
        matches = re.findall(pattern, title_en)
        if matches and len(matches) == 2:
            memory = list(filter(lambda x: x != "", matches[0]))
            ram = list(filter(lambda x: x != "", matches[1]))
            matches = sum([memory, ram], [])
            return matches

        attribiutes_list = obj["data"]["product"]["specifications"][0]["attributes"]
        kilo_mega_giga_tra = {
            "کیلوبایت": "KB",
            "مگابایت": "MB",
            "گیگابایت": "GB",
            "ترابایت": "TB",
        }

        letter_to_digit_obj = {
            "یک": "1",
            "دو": "2",
            "سه": "3",
            "چهار": "4",
            "پنج": "5",
            "شش": "6",
            "هشت": "8",
            "12": "12",
            "16": "16",
            "32": "32",
            "64": "64",
            "128": "128",
            "256": "256",
            "512": "512",
        }

        ram = [obj["values"][0] for obj in attribiutes_list if obj["title"] == "مقدار RAM"]
        if ram:
            ram = ram[0].split(" ")
        memory = [obj["values"][0] for obj in attribiutes_list if obj["title"] == "حافظه داخلی"]
        if memory:
            memory = memory[0].split(" ")

        for key, value in kilo_mega_giga_tra.items():
            if key in ram and ram:
                ram[1] = value
            if key in memory and memory:
                memory[1] = value

        for key, value in letter_to_digit_obj.items():
            if key in ram and ram:
                ram[0] = value
                ram = "".join(ram)
            if key in memory and memory:
                memory[0] = value
                memory = "".join(memory)

        if not ram:
            ram = None
        if not memory:
            memory = None

        return [memory, ram]
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Digikala", False, error_message)
        print(f"Error in extract_ram_and_memory:\n{error_message}")
        return [None, None]


def extract_url(obj):
    try:
        uri = obj["data"]["product"]["url"]["uri"].split("/")[1:-1]
        return f"https://digikala.com/{'/'.join(uri)}"
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Digikala", False, error_message)
        print(f"Error in extract_url:\n{error_message}")
        return ""


def extract_mobile_ids(url, cookies, headers):
    try:
        obj = requests.get(url, headers=headers, cookies=cookies)
        if obj.status_code != 200:
            print(f"{url} - HTTP {obj.status_code}")
            return None

        obj = obj.json()
        http_status_code = obj.get("status", 0)
        mobile_urls = []

        if http_status_code == 200:
            for product in obj["data"]["products"]:
                if product["status"] == "marketable":
                    id = product["id"]
                    mobile_urls.append(f"https://api.digikala.com/v2/product/{id}/")
        else:
            print(f"Unexpected status in response: {http_status_code}")

        return mobile_urls
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Digikala", False, error_message)
        print(f"Error in extract_mobile_ids:\n{error_message}")
        return None


def extract_mobile_data(url, cookies, headers, not_active_texts):
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        if response.status_code != 200:
            print(f"Error: Received non-{response.status_code} status code.")
            return None

        obj = response.json()
        http_status_code = obj["status"]
        marketable = obj["data"]["product"].get("status")
        if http_status_code != 200 or marketable != "marketable":
            return None

        title_en_list = obj["data"]["product"]["title_en"].strip().split(" ")
        title_fa = obj["data"]["product"]["title_fa"]
        memory, ram = extract_ram_and_memory(obj)

        my_obj = {
            "mobile_digi_id": obj["data"]["product"]["id"],
            "title": title_fa,
            "brand": obj["data"]["product"]["brand"]["title_en"],
            "model": extract_model_form_title(title_en_list),
            "ram": ram,
            "memory": memory,
            "vietnam": "Vietnam" in title_en_list,
            "active": True,
            "mobile": True,
            "not_active": any(txt in " ".join(title_en_list) for txt in not_active_texts),
            "site": "DigiKala",
            "dual_sim": all(x in title_en_list for x in ["Dual", "Sim"]),
            "url": extract_url(obj),
        }

        same_color_variants = extract_same_color_variants(obj)
        if same_color_variants:
            for mobile in same_color_variants:
                mobile.update(my_obj)
            return same_color_variants

        my_obj["active"] = False
        return [my_obj]
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Digikala", False, error_message)
        print(f"Error in extract_mobile_data:\n{error_message}")
        return None


def get_cookie() -> Optional[dict]:
    URL = "https://digikala.com"
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
        cook = {cookie["name"]: cookie["value"] for cookie in cookies}
        return cook
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Digikala", False, error_message)
        print(f"Error in get_cookie:\n{error_message}")
        return None
    finally:
        try:
            driver.quit()
        except Exception:
            pass


@shared_task(bind=True, max_retries=1)
def digikala_crawler(self):
    url_list = []
    brands, headers, not_active_texts = STATICS()
    cookies = get_cookie()

    try:
        batch_id = f"Digikala-{uuid.uuid4().hex[:12]}"
        for brand, page in brands:
            for i in range(page):
                link = f"https://api.digikala.com/v1/categories/mobile-phone/brands/{brand}/search/?seo_url=&page={i+1}"
                url_list.append(link)

        all_mobile_urls = list(map(lambda url: extract_mobile_ids(url, cookies, headers), url_list))
        all_mobile_urls = sum(list(filter(None, all_mobile_urls)), [])

        mobile_datas_list = list(
            map(lambda url: extract_mobile_data(url, cookies, headers, not_active_texts), all_mobile_urls)
        )
        mobile_datas_list = sum(list(filter(None, mobile_datas_list)), [])

        for mobile_dict in mobile_datas_list:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site="Digikala", mobile=True).exclude(last_batch_id=batch_id).update(status=False)

        update_code_execution_state(
            "Digikala",
            bool(mobile_datas_list),
            "هیچ محصولی پیدا نشد." if not mobile_datas_list else "",
        )

    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Digikala", False, error_message)
        print(f"Error in digikala_crawler:\n{error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site="Digikala", status=True, mobile=True, updated_at__lt=ten_min_ago
        ).update(status=False)
