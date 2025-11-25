import re
import traceback
from typing import Dict, List, Tuple, Optional
import requests
import time
import uuid
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from celery import shared_task
from khazesh.models import Mobile
from django.utils import timezone
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj


# ------------------ Static Config ------------------
def STATICS() -> Optional[Tuple[Dict]]:
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
        "Not Active", "Not Activate", "Not Activated", "not active",
        "not-active", "Not_Active", "NOT_ACTIVE", "Not-Active", "NOT-ACTIVE",
        "ٔNOT ACTIVE", "نات اکتیو", "نات-اکتیو",
    ]
    return brands, not_active_texts


# ------------------ Extractors ------------------
def extract_model_form_title(title_en_list):
    model = ""
    for word in title_en_list[1:]:
        if "GB" in word or word in ["Dual", "Single"]:
            break
        model += word + " "
        if word == "Mini":
            break
    return model.strip()


def extract_same_color_variants(obj):
    try:
        if obj["data"]["product"].get("status") != "marketable":
            return None
        variants = obj["data"]["product"]["variants"]
        colors_obj_list = [v["color"] for v in variants]
        colors_obj_list = [c for i, c in enumerate(colors_obj_list) if c not in colors_obj_list[i + 1:]]
        colors = [(c["hex_code"], c["title"]) for c in colors_obj_list]

        variant_objects = []
        for hex_code, color in colors:
            variant_obj = {"color_name": color, "color_hex": hex_code, "variants": []}
            prices = []
            for variant in variants:
                if variant["color"]["hex_code"] == hex_code:
                    price = variant["price"]["selling_price"]
                    prices.append(price)
                    variant_obj["variants"].append(variant)

            if not prices:
                continue

            variant_obj["min_price"] = min(prices)
            variant_obj["max_price"] = max(prices)
            min_variant = min(variant_obj["variants"], key=lambda x: x["price"]["selling_price"])
            variant_obj["seller"] = min_variant["seller"]["title"]
            variant_obj["guarantee"] = min_variant["warranty"]["title_fa"]
            variant_obj.pop("variants")
            variant_objects.append(variant_obj)
        return variant_objects
    except Exception:
        update_code_execution_state("Digikala-tablet", False, traceback.format_exc())
        return None


def extract_ram_and_memory(obj):
    try:
        title_en = obj["data"]["product"].get("title_en", "")
        matches = re.findall(r"(\d+GB|\d+TB)", title_en)
        if len(matches) >= 2:
            return [matches[0], matches[1]]

        attrs = obj["data"]["product"]["specifications"][0].get("attributes", [])
        ram = next((a["values"][0] for a in attrs if a["title"] == "مقدار RAM"), "None")
        memory = next((a["values"][0] for a in attrs if a["title"] == "حافظه داخلی"), "None")
        return [memory, ram]
    except Exception:
        update_code_execution_state("Digikala-tablet", False, traceback.format_exc())
        return [None, None]


def extract_url(obj):
    try:
        uri = obj["data"]["product"]["url"]["uri"].split("/")[1:-1]
        return f"https://digikala.com/{'/'.join(uri)}"
    except Exception:
        return "نامشخص"


# ------------------ Cookie via Selenium ------------------
def get_cookie() -> Optional[dict]:
    """Extract cookies safely using headless Chrome"""
    URL = "https://digikala.com"
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("window-size=1920x1080")
        service = Service(executable_path="/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(URL)
        time.sleep(5)
        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
        return cookies
    except Exception:
        update_code_execution_state("Digikala-tablet", False, traceback.format_exc())
        return None
    finally:
        if driver:
            driver.quit()


# ------------------ API Handlers ------------------
def extract_tablet_ids(url, cookies, headers):
    try:
        r = requests.get(url, headers=headers, cookies=cookies, timeout=20)
        if r.status_code != 200:
            update_code_execution_state("Digikala-tablet", False, f"Bad status {r.status_code} for {url}")
            return None
        obj = r.json()
        if obj.get("status") != 200:
            return None
        tablets = []
        for product in obj["data"].get("products", []):
            if product.get("status") == "marketable":
                tablets.append(f"https://api.digikala.com/v2/product/{product['id']}/")
        return tablets
    except Exception:
        update_code_execution_state("Digikala-tablet", False, traceback.format_exc())
        return None


def extract_tablet_data(url, cookies, headers, not_active_texts):
    try:
        r = requests.get(url, headers=headers, cookies=cookies, timeout=20)
        if r.status_code != 200:
            update_code_execution_state("Digikala-tablet", False, f"Bad status {r.status_code} for {url}")
            return None
        obj = r.json()
        if obj.get("status") != 200:
            return None

        product = obj["data"]["product"]
        if product.get("status") != "marketable":
            return None

        title_en_list = product.get("title_en", "").split(" ")
        title_fa = product.get("title_fa", "")
        memory, ram = extract_ram_and_memory(obj)

        base_obj = {
            "mobile_digi_id": product["id"],
            "title": title_fa,
            "brand": product["brand"]["title_en"],
            "model": extract_model_form_title(title_en_list),
            "ram": ram,
            "memory": memory,
            "vietnam": "Vietnam" in title_en_list,
            "active": True,
            "mobile": False,
            "not_active": any(txt in " ".join(title_en_list) for txt in not_active_texts),
            "site": "Digikala",
            "dual_sim": all(x in title_en_list for x in ["Dual", "Sim"]),
            "url": extract_url(obj),
        }

        variants = extract_same_color_variants(obj)
        if variants:
            for v in variants:
                v.update(base_obj)
            return variants
        else:
            base_obj["active"] = False
            return [base_obj]
    except Exception:
        update_code_execution_state("Digikala-tablet", False, traceback.format_exc())
        return None


# ------------------ Main Task ------------------
@shared_task(bind=True, max_retries=1)
def tablet_digikala_crawler(self):
    cookies = get_cookie()
    headers = {"User-Agent": "Mozilla/5.0"}
    brands, not_active_texts = STATICS()
    url_list = []

    try:
        batch_id = f"Digikala-{uuid.uuid4().hex[:12]}"
        main_url = "https://api.digikala.com/v1/categories/tablet/search/?brands%5B0%5D=10&brands%5B1%5D=18&brands%5B2%5D=1662&has_selling_stock=1&page=1"
        res = requests.get(main_url, headers=headers)
        if res.status_code != 200:
            update_code_execution_state("Digikala-tablet", False, f"Main URL error: {res.status_code}")
            return
        data = res.json()
        total_pages = data["data"]["pager"]["total_pages"]
        print(f"📦 Total pages: {total_pages}")

        for i in range(total_pages):
            url_list.append(f"https://api.digikala.com/v1/categories/tablet/search/?brands%5B0%5D=10&brands%5B1%5D=18&brands%5B2%5D=1662&has_selling_stock=1&page={i+1}")

        all_ids = sum(filter(None, [extract_tablet_ids(u, cookies, headers) for u in url_list]), [])
        print(f"🟢 Found {len(all_ids)} product IDs")

        all_data = sum(filter(None, [extract_tablet_data(u, cookies, headers, not_active_texts) for u in all_ids]), [])
        print(f"🟢 Extracted {len(all_data)} tablet records")

        for tablet_dict in all_data:
            save_obj(tablet_dict, batch_id=batch_id)

        Mobile.objects.filter(site="Digikala", mobile=False).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state("Digikala-tablet", bool(all_data), "هیچ محصولی پیدا نشد." if not all_data else "")
    except Exception:
        err = traceback.format_exc()
        update_code_execution_state("Digikala-tablet", False, err)
        print(f"Error {err}")
        raise self.retry(exc=Exception(err), countdown=30)
    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site="Digikala", status=True, mobile=False, updated_at__lt=ten_min_ago).update(status=False)
