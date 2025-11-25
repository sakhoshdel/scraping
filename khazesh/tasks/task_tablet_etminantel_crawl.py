import re
import traceback
from typing import Dict, List, Optional, Tuple
import requests
import time
import uuid

from bs4 import BeautifulSoup
from celery import shared_task
from django.utils import timezone

from khazesh.models import Mobile
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj


# --------------------------------------------------------
# Helpers
# --------------------------------------------------------

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


def toman_to_rial(amount: int):
    return int(amount) * 10


def safe_request(url: str, headers: Dict, cookies: Dict, retries: int = 2, timeout: int = 20):
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, cookies=cookies, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            msg = f"Request failed ({i+1}/{retries}): {url} -> {e}"
            print(msg)
            update_code_execution_state("Etminantel-tablet", False, msg)
            time.sleep(1)
    return None


def get_list_pages(start_url: str, headers: Dict, cookies: Dict):
    pages = [start_url]
    base = start_url.split("?", 1)[0]

    for i in range(2, 10):
        test_url = f"{base}page/{i}/"
        if "?" in start_url:
            test_url += "?" + start_url.split("?", 1)[1]

        r = safe_request(test_url, headers, cookies)
        if not r or r.status_code == 404:
            break

        pages.append(test_url)

    return pages


def extract_product_urls(list_url: str, headers: Dict, cookies: Dict):
    r = safe_request(list_url, headers, cookies)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    urls = []
    for a in soup.select("a.woocommerce-LoopProduct-link"):
        href = a.get("href")
        if href:
            urls.append(href.split("#")[0])
    return urls


def extract_brand(soup: BeautifulSoup):
    meta = soup.select_one(".product_meta")
    if not meta:
        return "نامشخص"
    text = meta.get_text(" ", strip=True)
    m = re.search(r"برند ها:\s*(.+)", text)
    if not m:
        return "نامشخص"
    brand = m.group(1).split("،")[0].split(",")[0].strip()
    return brand or "نامشخص"


def find_color_hex_for_name(soup: BeautifulSoup, color_name: str):
    if not color_name:
        return ""
    color_name = color_name.strip()

    for div in soup.select("div.jcaa_obj_color"):
        title = (div.get("title") or "").strip()
        style = div.get("style") or ""

        m = re.search(r"background:\s*(#[0-9A-Fa-f]{3,6})", style)
        if not m:
            continue

        hex_code = m.group(1)

        if title and (title == color_name or title in color_name or color_name in title):
            return hex_code

    return ""


# --------------------------------------------------------
# Model extractor (مثل دیجیکالا)
# --------------------------------------------------------

def extract_clean_model(full_title: str):
    """
    ورودی:
    تبلت سامسونگ A9 X110 wifi | حافظه 64 رم 4 گیگابایت   Samsung Galaxy Tab A9 ...

    خروجی:
    تبلت سامسونگ A9 X110 wifi
    """

    if "|" in full_title:
        return full_title.split("|")[0].strip()

    # حذف بخش حافظه
    title = re.split(r"حافظه|RAM|رم|گیگ|GB", full_title)[0].strip()

    # حذف اعداد ظرفیت
    title = re.sub(r"\d+\s*GB", "", title, flags=re.IGNORECASE)

    # اگر مدل شامل کلمات انگلیسی پشت سر هم باشد → برگردان
    m = re.findall(r"[A-Za-z0-9]+\s?[A-Za-z0-9]*", title)
    if m:
        return title.strip()

    return title.strip()


# --------------------------------------------------------
# Schema parsers
# --------------------------------------------------------

def parse_schema_product(soup: BeautifulSoup):
    scripts = soup.find_all("script", {"type": "application/ld+json"})
    product_node = None

    for s in scripts:
        try:
            raw = s.string or ""
            if not raw.strip():
                continue

            raw = re.sub(r"//.*?\n", "", raw)
            obj = __import__("json").loads(raw)

        except:
            continue

        graph = obj.get("@graph")
        if not isinstance(graph, list):
            continue

        for node in graph:
            t = node.get("@type")

            if t == "ProductGroup":
                return "group", node

            if t == "Product":
                product_node = node

    if product_node:
        return "product", product_node

    return None, None


def parse_specs_from_schema(node: Dict):
    specs = {"ram": "نامشخص", "storage": "نامشخص"}
    guarantee = None
    extra = {}

    for p in node.get("additionalProperty", []):
        name = p.get("name", "")
        value = (p.get("value") or "").strip()
        if not value:
            continue

        if name == "pa_ram":
            specs["ram"] = extract_capacity(value) or specs["ram"]

        elif name == "pa_memory":
            specs["storage"] = extract_capacity(value) or specs["storage"]

        elif name == "pa_guarantee":
            guarantee = value

        else:
            extra[name] = value

    return specs, extra, guarantee


def build_variation_attribute_maps(soup: BeautifulSoup):
    result = {}
    form = soup.find("form", class_="variations_form")
    if not form:
        return result

    for sel in form.select('select[name^="attribute_"]'):
        name = sel.get("name")
        if not name:
            continue

        options = {}
        for opt in sel.find_all("option"):
            slug = opt.get("value")
            text = opt.text.strip()
            if slug:
                options[slug] = text

        if options:
            result[name] = options

    return result


# --------------------------------------------------------
# Extract tablet variants from product page
# --------------------------------------------------------

def extract_etminantel_tablet_variants(url: str, headers: Dict, cookies: Dict):
    r = safe_request(url, headers, cookies)
    if not r:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    product_type, schema_node = parse_schema_product(soup)
    if product_type != "group" or not schema_node:
        return None

    brand_name = extract_brand(soup)
    title = schema_node.get("name", "").strip() or soup.select_one("h1.product_title").text.strip()
    model = extract_clean_model(title)

    specs_base, extra_attrs, guarantee_base = parse_specs_from_schema(schema_node)

    form = soup.find("form", class_="variations_form")
    if not form:
        return None

    try:
        variations = __import__("json").loads(form.get("data-product_variations") or "[]")
    except:
        variations = []

    attr_maps = build_variation_attribute_maps(soup)

    output = []

    for var in variations:

        display_price = var.get("display_price")
        in_stock = var.get("is_in_stock", True)

        if not in_stock:
            continue
        if not display_price or int(display_price) == 0:
            continue

        price_rial = toman_to_rial(int(display_price))

        # --- extract ALL attributes ---
        variant_attrs = {}
        ram = specs_base.get("ram", "نامشخص")
        memory = specs_base.get("storage", "نامشخص")
        guarantee = guarantee_base
        color_name = ""

        for attr_name, slug in var.get("attributes", {}).items():

            if not slug:
                continue

            text = attr_maps.get(attr_name, {}).get(slug, slug)
            variant_attrs[attr_name] = text   # ذخیره همه متغیرها

            if "ram" in attr_name.lower():
                ram = extract_capacity(text) or ram

            elif "memory" in attr_name.lower():
                memory = extract_capacity(text) or memory

            elif "guarantee" in attr_name.lower():
                guarantee = text

            elif "color" in attr_name.lower():
                color_name = text

        color_hex = find_color_hex_for_name(soup, color_name)

        item = {
            "mobile_digi_id": None,
            "title": title,
            "brand": brand_name,
            "model": model,
            "ram": ram,
            "memory": memory,
            "vietnam": False,
            "active": True,
            "mobile": False,
            "not_active": False,
            "site": "Etminantel",
            "dual_sim": False,
            "url": url,
            "color_name": color_name or "نامشخص",
            "color_hex": color_hex,
            "min_price": price_rial,
            "max_price": price_rial,
            "seller": "Etminantel",
            "guarantee": guarantee or "نامشخص",
            "extra_attributes": variant_attrs,   # ← تمام متغیرها را ذخیره کن
        }

        output.append(item)

    return output or None

# --------------------------------------------------------
# Crawl category pages
# --------------------------------------------------------

def crawl_etminantel_tablets(start_url: str):
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = {}

    pages = get_list_pages(start_url, headers, cookies)
    print("Pages:", pages)

    product_urls = []
    seen = set()

    for p in pages:
        urls = extract_product_urls(p, headers, cookies)
        for u in urls:
            if u not in seen:
                seen.add(u)
                product_urls.append(u)

    print(f"Found {len(product_urls)} tablet URLs")

    results = []
    for idx, u in enumerate(product_urls, 1):
        print(f"[{idx}/{len(product_urls)}] {u}")
        items = extract_etminantel_tablet_variants(u, headers, cookies)
        if items:
            results.extend(items)
        time.sleep(0.3)

    return results


# --------------------------------------------------------
# Celery task
# --------------------------------------------------------

@shared_task(bind=True, max_retries=1)
def tablet_etminantel_crawler(self):
    try:
        batch_id = f"Etminantel-{uuid.uuid4().hex[:12]}"
        start_url = "https://etminantel.com/product-category/tablet/?min_price=1&max_price=999999900000"

        all_data = crawl_etminantel_tablets(start_url)
        print(f"Extracted total: {len(all_data)} records")

        for obj in all_data:
            save_obj(obj, batch_id=batch_id)

        Mobile.objects.filter(site="Etminantel", mobile=False).exclude(last_batch_id=batch_id).update(status=False)

        update_code_execution_state("Etminantel-tablet", bool(all_data))

    except Exception:
        err = traceback.format_exc()
        update_code_execution_state("Etminantel-tablet", False, err)
        raise self.retry(exc=Exception(err), countdown=20)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site="Etminantel", mobile=False, status=True, updated_at__lt=ten_min_ago).update(status=False)
