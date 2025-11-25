import re
import time
import traceback
from typing import Dict, List, Optional, Tuple
import requests
from celery import shared_task
from django.utils import timezone

from khazesh.models import ProductLaptop, BrandLaptop
from khazesh.tasks.save_laptop_crawler_status import laptop_update_code_execution_state
from khazesh.tasks.save_laptop_object_to_database import save_laptop_obj


# --------------------------- Helper functions ---------------------------
def fa_to_en_digits(s: str) -> str:
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if s else s


def extract_capacity(value: str) -> Optional[str]:
    if not value:
        return None
    v = fa_to_en_digits(value).replace("٫", ".").replace(",", ".")
    v = (v.replace("گیگابایت", "GB")
           .replace("مگابایت", "MB")
           .replace("ترابایت", "TB")
           .replace("کیلوبایت", "KB"))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB|MB|KB)", v, re.IGNORECASE)
    return f"{m.group(1)}{m.group(2).upper()}" if m else None


def cpu_from_title(text: str) -> Optional[str]:
    t = fa_to_en_digits(text or "")
    patterns = [
        (r"\b(i[3579])\b", lambda m: f"Intel Core {m.group(1).upper()}"),
        (r"(Ultra\s*[579])", lambda m: f"Intel Core {m.group(1).title()}"),
        (r"(Ryzen\s*[3579])", lambda m: f"AMD {m.group(1).title()}"),
        (r"\bR([3579])\b", lambda m: f"AMD Ryzen {m.group(1)}"),
        (r"\bM([1234])\s*(Pro|Max)?\b", lambda m: f"Apple M{m.group(1)} {(m.group(2) or '').strip()}"),
        (r"(Celeron|Pentium)", lambda m: m.group(1).title()),
    ]
    for pattern, builder in patterns:
        m = re.search(pattern, t, re.IGNORECASE)
        if m:
            return builder(m)
    return None


def clean_display_size(value: str) -> Optional[str]:
    if not value:
        return None
    v = fa_to_en_digits(value).replace("٫", ".").replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:اینچ|inch)", v, re.IGNORECASE)
    return m.group(1) if m else None


def safe_request(url: str, headers: Dict, cookies: Dict) -> Optional[requests.Response]:
    """Safe GET request with timeout, retries and logging"""
    for i in range(2):
        try:
            res = requests.get(url, headers=headers, cookies=cookies, timeout=15)
            res.raise_for_status()
            return res
        except requests.RequestException as e:
            print(f"⚠️ Request failed ({i+1}/2): {url} → {e}")
            laptop_update_code_execution_state("Digikala", False, str(e))
            time.sleep(1)
    return None


# --------------------------- STATICS ---------------------------
def STATICS() -> Tuple[List[str], Dict]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Connection": "keep-alive",
        "User-Agent": "Mozilla/5.0",
    }

    brand_urls = [
        "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/brands/apple/search/?camCode=2174&has_selling_stock=1&sort=7&page={page}",
        "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/brands/hp/search/?camCode=2174&has_selling_stock=1&sort=7&page={page}",
        "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/brands/msi/search/?camCode=2174&has_selling_stock=1&sort=4&page={page}",
        "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/brands/acer/search/?camCode=2174&has_selling_stock=1&sort=7&page={page}",
        "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/brands/asus/search/?camCode=2174&has_selling_stock=1&sort=7&page={page}",
        "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/brands/lenovo/search/?camCode=2174&has_selling_stock=1&sort=7&page={page}",
        "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/brands/microsoft/search/?camCode=2174&has_selling_stock=1&sort=7&page={page}",
    ]
    return brand_urls, headers


# --------------------------- Extraction functions ---------------------------
def extract_laptop_ids(url: str, headers: Dict, cookies: Dict) -> Optional[List[str]]:
    try:
        res = safe_request(url, headers, cookies)
        if not res:
            return None
        data = res.json()
        if data.get("status") != 200:
            return None

        urls = [
            f"https://api.digikala.com/v2/product/{p['id']}/"
            for p in data["data"].get("products", [])
            if p.get("status") == "marketable"
        ]
        return urls
    except Exception:
        laptop_update_code_execution_state("Digikala", False, traceback.format_exc())
        return None


def extract_laptop_data(url: str, headers: Dict, cookies: Dict) -> Optional[List[Dict]]:
    try:
        res = safe_request(url, headers, cookies)
        if not res:
            return None
        data = res.json()
        if data.get("status") != 200:
            return None

        product = data["data"]["product"]
        if product.get("status") != "marketable":
            return None

        title_fa = product.get("title_fa", "")
        title_en = product.get("title_en", "")
        brand_name = product.get("brand", {}).get("title_en", "نامشخص")
        brand, _ = BrandLaptop.objects.get_or_create(name_fa=brand_name, name_en=brand_name)

        specs = {
            "ram": "نامشخص",
            "storage": "نامشخص",
            "cpu": "نامشخص",
            "gpu": "نامشخص",
            "display_size": "نامشخص",
            "display_resolution": "نامشخص",
            "battery": "نامشخص",
            "os": "نامشخص",
            "weight": "نامشخص",
        }

        for group in product.get("specifications", []):
            for attr in group.get("attributes", []):
                title = attr.get("title", "").strip()
                val = next(iter(attr.get("values", [])), None)
                if not val:
                    continue

                if "RAM" in title or "رم" in title:
                    specs["ram"] = extract_capacity(val) or specs["ram"]
                elif "حافظه داخلی" in title or "Storage" in title:
                    specs["storage"] = extract_capacity(val) or specs["storage"]
                elif "پردازنده" in title and "گرافیکی" not in title:
                    specs["cpu"] = cpu_from_title(val) or specs["cpu"]
                elif "گرافیکی" in title or "GPU" in title:
                    specs["gpu"] = val
                elif "اندازه صفحه" in title or "سایز" in title:
                    specs["display_size"] = clean_display_size(val) or specs["display_size"]
                elif "رزولوشن" in title:
                    specs["display_resolution"] = val
                elif "سیستم عامل" in title:
                    specs["os"] = val
                elif "باتری" in title:
                    specs["battery"] = val
                elif "وزن" in title:
                    specs["weight"] = val

        # fallback
        specs["cpu"] = specs["cpu"] if specs["cpu"] != "نامشخص" else cpu_from_title(title_en) or "نامشخص"
        specs["ram"] = specs["ram"] if specs["ram"] != "نامشخص" else extract_capacity(title_en) or "نامشخص"
        specs["storage"] = specs["storage"] if specs["storage"] != "نامشخص" else extract_capacity(title_en) or "نامشخص"
        specs["display_size"] = specs["display_size"] if specs["display_size"] != "نامشخص" else clean_display_size(title_fa) or "نامشخص"

        base_info = {
            "title": title_fa,
            "model": title_en,
            "brand": brand,
            "site": "Digikala",
            "url": f"https://www.digikala.com/product/dkp-{product['id']}/",
            "stock": True,
            **specs,
        }

        variants = []
        for v in product.get("variants", []):
            try:
                price_info = v.get("price", {})
                color_info = v.get("color", {})
                warranty_info = v.get("warranty", {})

                variants.append({
                    **base_info,
                    "color_name": color_info.get("title", "نامشخص"),
                    "color_hex": color_info.get("hex_code", ""),
                    "guarantee": warranty_info.get("title_fa", "نامشخص"),
                    "min_price": price_info.get("selling_price", 0),
                    "max_price": price_info.get("rrp_price", 0),
                })
            except Exception:
                continue

        return variants
    except Exception:
        laptop_update_code_execution_state("Digikala", False, traceback.format_exc())
        return None


# --------------------------- Main Task ---------------------------
@shared_task(bind=True, max_retries=1)
def laptop_digikala_crawler(self):
    try:
        brand_urls, headers = STATICS()
        cookies = {}
        all_urls = []

        # مرحله اول: دریافت ID لپ‌تاپ‌ها
        for url_template in brand_urls:
            for page in range(1, 4):
                ids = extract_laptop_ids(url_template.format(page=page), headers, cookies)
                if ids:
                    all_urls.extend(ids)
                time.sleep(0.3)

        # مرحله دوم: دریافت داده هر لپ‌تاپ
        all_laptops = []
        for url in all_urls:
            items = extract_laptop_data(url, headers, cookies)
            if items:
                all_laptops.extend(items)
            time.sleep(0.3)

        # غیرفعال‌سازی لپ‌تاپ‌های قدیمی
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        ProductLaptop.objects.filter(
            site="Digikala", status=True, updated_at__lt=ten_min_ago
        ).update(status=False)

        # ذخیره در دیتابیس
        for laptop in all_laptops:
            save_laptop_obj(laptop)

        laptop_update_code_execution_state("Digikala", True)
        print(f"✅ Crawled {len(all_laptops)} laptops successfully.")

    except Exception:
        err = traceback.format_exc()
        laptop_update_code_execution_state("Digikala", False, err)
        print(f"❌ Error: {err}")
        raise self.retry(exc=Exception(err), countdown=30)
