import json
import re
import time
import traceback
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from celery import shared_task
from django.utils import timezone

from khazesh.models import ProductLaptop, BrandLaptop
from khazesh.tasks.save_laptop_object_to_database import save_laptop_obj
from khazesh.tasks.save_laptop_crawler_status import laptop_update_code_execution_state


# ------------------------------------------------------------
# Helper
# ------------------------------------------------------------
def fa_to_en_digits(s: str) -> str:
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if s else s


def extract_capacity(value: str) -> Optional[str]:
    if not value:
        return None
    v = fa_to_en_digits(value).replace("٫", ".").replace(",", ".")
    v = (
        v.replace("گیگابایت", "GB")
         .replace("مگابایت", "MB")
         .replace("ترابایت", "TB")
         .replace("کیلوبایت", "KB")
    )
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


def toman_to_rial(amount: int) -> int:
    return int(amount) * 10


def safe_request(url: str, headers: Dict, cookies: Dict,
                 retries: int = 2, timeout: int = 15) -> Optional[requests.Response]:
    for i in range(retries):
        try:
            res = requests.get(url, headers=headers, cookies=cookies, timeout=timeout)
            res.raise_for_status()
            return res
        except requests.RequestException as e:
            print(f"⚠️ Request failed ({i+1}/{retries}): {url} -> {e}")
            laptop_update_code_execution_state("Etminantel", False, str(e))
            time.sleep(1)
    return None


# ------------------------------------------------------------
# Page + Product List
# ------------------------------------------------------------
def get_list_pages(start_url: str, headers: Dict, cookies: Dict) -> List[str]:
    pages = [start_url]
    base = start_url.split("?")[0]

    for i in range(2, 10):
        test_url = f"{base}page/{i}/"
        if "?" in start_url:
            test_url += "?" + start_url.split("?", 1)[1]

        res = safe_request(test_url, headers, cookies)
        if not res or res.status_code == 404:
            break

        pages.append(test_url)

    return pages


def extract_product_urls(list_url: str, headers: Dict, cookies: Dict) -> List[str]:
    res = safe_request(list_url, headers, cookies)
    if not res:
        return []
    soup = BeautifulSoup(res.text, "html.parser")
    urls = []
    for a in soup.select("a.woocommerce-LoopProduct-link"):
        href = a.get("href")
        if href:
            urls.append(href.split("#")[0])
    return urls


# ------------------------------------------------------------
# Schema Extraction
# ------------------------------------------------------------
def parse_schema_product(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[Dict]]:
    scripts = soup.find_all("script", {"type": "application/ld+json"})
    product_node = None

    for script in scripts:
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue

        graph = data.get("@graph")
        if isinstance(graph, list):
            for node in graph:
                t = node.get("@type")
                if t == "ProductGroup":
                    return "group", node
                if t == "Product":
                    product_node = node

    if product_node:
        return "product", product_node

    return None, None


def extract_brand(soup: BeautifulSoup) -> str:
    meta = soup.select_one(".product_meta")
    if not meta:
        return "نامشخص"
    text = meta.get_text(" ", strip=True)
    m = re.search(r"برند ها:\s*(.+)", text)
    if not m:
        return "نامشخص"
    brand = re.split(r"[،,]", m.group(1))[0].strip()
    return brand or "نامشخص"


def parse_specs_from_schema(node: Dict) -> Tuple[Dict, Dict, Optional[str]]:
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
    extra_attrs = {}
    guarantee = None

    for prop in node.get("additionalProperty", []):
        name = prop.get("name", "")
        value = str(prop.get("value", "")).strip()
        if not value:
            continue

        if name == "pa_ram":
            specs["ram"] = extract_capacity(value) or specs["ram"]
        elif name == "pa_memory":
            specs["storage"] = extract_capacity(value) or specs["storage"]
        elif name == "pa_graphic-card":
            specs["gpu"] = value
        elif name == "pa_screen-size":
            specs["display_size"] = clean_display_size(value) or specs["display_size"]
        elif name == "pa_resolution":
            specs["display_resolution"] = value
        elif name == "pa_operating-system":
            specs["os"] = value
        elif name.startswith("pa_processor"):
            cpu_val = cpu_from_title(value)
            if cpu_val:
                specs["cpu"] = cpu_val
        elif name == "pa_guarantee":
            guarantee = value
        else:
            extra_attrs[name] = value

    w = node.get("weight")
    if isinstance(w, dict) and w.get("value"):
        specs["weight"] = fa_to_en_digits(str(w["value"]))

    if specs["cpu"] == "نامشخص":
        specs["cpu"] = cpu_from_title(node.get("name") or "") or "نامشخص"

    return specs, extra_attrs, guarantee


# ------------------------------------------------------------
# Color Extractor (HTML, not variation)
# ------------------------------------------------------------
def extract_color_from_html(soup: BeautifulSoup) -> Tuple[str, str]:
    color_name = "نامشخص"
    color_hex = ""

    color_li = soup.select_one(".jcaa_attr_select .jcaa_obj_color")
    if color_li:
        color_hex = color_li.get("style", "").replace("background:", "").strip()
        color_name = color_li.get("title", "").strip() or "نامشخص"

    return color_name, color_hex



def extract_model_from_title(title: str) -> str:

    if not title:
        return ""

    title = title.strip()

    # الگوی اصلی: مدل XXXXXX تا قبل از مشخصات
    pattern = r"مدل\s+(.+?)\s+(?:رنگ|رم|حافظه|ظرفیت|SSD|HDD|GB|گیگابایت|ترابایت|اینچی|M\d|CPU|GPU|پردازنده|با|و|$)"

    m = re.search(pattern, title, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # اگر الگو پیدا نشد، از بعد از کلمه "مدل" تا انتها
    if "مدل" in title:
        return title.split("مدل", 1)[1].strip()

    # fallback
    return title
# ------------------------------------------------------------
# Long Function: extract_product_variants
# ------------------------------------------------------------
def extract_product_variants(url: str, headers: Dict, cookies: Dict) -> List[Dict]:
    res = safe_request(url, headers, cookies)
    if not res:
        return []

    soup = BeautifulSoup(res.text, "html.parser")

    product_type, node = parse_schema_product(soup)
    if not node:
        print("Schema not found:", url)
        return []

    brand_name = extract_brand(soup)
    title = node.get("name", "").strip()
    description = node.get("description", "").strip()
    brand_obj, _ = BrandLaptop.objects.get_or_create(
        name_fa=brand_name,
        name_en=brand_name
    )
    specs, extra_attrs, guarantee = parse_specs_from_schema(node)
 
    base_info = {
        "title": title,
        "model": extract_model_from_title(title),
        "brand": brand_obj,
        "site": "Etminantel",
        "url": url,
        "stock": True,
        "description": description,
        "ram": specs["ram"],
        "storage": specs["storage"],
        "cpu": specs["cpu"],
        "gpu": specs["gpu"],
        "display_size": specs["display_size"],
        "display_resolution": specs["display_resolution"],
        "battery": specs["battery"],
        "os": specs["os"],
        "weight": specs["weight"],
    }

    # default color
    default_color_name, default_color_hex = extract_color_from_html(soup)

    variants = []

    # ----------------------------------
    # ProductGroup = variable
    # ----------------------------------
    if product_type == "group":
        form = soup.find("form", class_="variations_form")
        if not form:
            return []

        try:
            variations = json.loads(form.get("data-product_variations") or "[]")
        except:
            variations = []

        # attribute maps
        attr_maps = {}
        for sel in form.select('select[name^="attribute_"]'):
            name = sel.get("name")
            opts = {}
            for opt in sel.find_all("option"):
                if opt.get("value"):
                    opts[opt.get("value")] = opt.get_text(strip=True)
            if opts:
                attr_maps[name] = opts

        for var in variations:
            attrs = var.get("attributes", {})
            price = var.get("display_price")
            if price is None:
                continue

            price_rial = toman_to_rial(int(price))
            in_stock = bool(var.get("is_in_stock", True))

            variant_specs = dict(base_info)
            color_name = default_color_name
            color_hex = default_color_hex
            guarantee_v = guarantee
            extra = dict(extra_attrs)

            for attr_name, slug in attrs.items():
                if not slug:
                    continue
                text = attr_maps.get(attr_name, {}).get(slug, slug)

                if attr_name.endswith("pa_ram"):
                    variant_specs["ram"] = extract_capacity(text) or variant_specs["ram"]
                elif attr_name.endswith("pa_memory"):
                    variant_specs["storage"] = extract_capacity(text) or variant_specs["storage"]
                elif attr_name.endswith("pa_screen-size"):
                    variant_specs["display_size"] = clean_display_size(text) or variant_specs["display_size"]
                elif attr_name.endswith("pa_resolution"):
                    variant_specs["display_resolution"] = text
                elif attr_name.endswith("pa_guarantee"):
                    guarantee_v = text
                elif attr_name.endswith("pa_color"):
                    color_name = text
                else:
                    extra[attr_name] = text

            variants.append({
                **variant_specs,
                "color_name": color_name,
                "color_hex": color_hex,
                "guarantee": guarantee_v or "نامشخص",
                "min_price": price_rial,
                "max_price": price_rial,
                "stock": in_stock,
                "extra_attributes": extra,
            })

    else:
        # simple product
        offers = node.get("offers", {}) or {}
        price = offers.get("price")
        try:
            price_rial = int(price)
        except:
            price_rial = 0

        in_stock = "InStock" in (offers.get("availability") or "")

        variants.append({
            **base_info,
            "color_name": default_color_name,
            "color_hex": default_color_hex,
            "guarantee": guarantee or "نامشخص",
            "min_price": price_rial,
            "max_price": price_rial,
            "stock": in_stock,
            "extra_attributes": extra_attrs,
        })

    # فقط محصولات موجود
    variants = [v for v in variants if v["stock"]]

    return variants


# ------------------------------------------------------------
# Crawler Main
# ------------------------------------------------------------
def crawl_etminantel(start_url: str) -> List[Dict]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    }
    cookies = {}

    list_pages = get_list_pages(start_url, headers, cookies)
    print("List pages:", list_pages)

    product_urls = []
    seen = set()

    for page in list_pages:
        urls = extract_product_urls(page, headers, cookies)
        for u in urls:
            if u not in seen:
                seen.add(u)
                product_urls.append(u)

    print("Found", len(product_urls), "product urls")

    result = []
    for idx, url in enumerate(product_urls, 1):
        print(f"Processing {idx}/{len(product_urls)}:", url)
        items = extract_product_variants(url, headers, cookies)
        result.extend(items)
        time.sleep(0.3)

    return result


# ------------------------------------------------------------
# Celery Task
# ------------------------------------------------------------
@shared_task(bind=True, max_retries=1)
def laptop_etminantel_crawler(self):
    try:
        ts = int(time.time() * 1000)

        start_url = (
            f"https://etminantel.com/product-category/laptop/"
            f"?min_price=1&max_price=99999900000&product_brand=apple%2Chp%2Cmicrosoft&t={ts}"
        )

        all_laptops = crawl_etminantel(start_url)

        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        ProductLaptop.objects.filter(
            site="Etminantel", status=True, updated_at__lt=ten_min_ago
        ).update(status=False)

        # save all to DB
        for laptop in all_laptops:
            laptop.pop("extra_attributes", None)  

            save_laptop_obj(laptop)

        laptop_update_code_execution_state("Etminantel", True)
        print(f"✔️ Crawled {len(all_laptops)} laptops successfully.")

    except Exception:
        err = traceback.format_exc()
        laptop_update_code_execution_state("Etminantel", False, err)
        print("❌ Error:", err)
        raise self.retry(exc=Exception(err), countdown=30)
