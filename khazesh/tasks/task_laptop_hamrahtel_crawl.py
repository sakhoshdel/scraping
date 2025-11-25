import re
import time
import json
import traceback
import requests
import logging
from typing import Dict, List, Optional
from celery import shared_task
from django.utils import timezone

from khazesh.models import BrandLaptop, ProductLaptop
from khazesh.tasks.save_laptop_object_to_database import save_laptop_obj
from khazesh.tasks.save_laptop_crawler_status import laptop_update_code_execution_state

# ---------------------- تنظیمات ثابت ----------------------
GRAPHQL_URL = "https://core-api.hamrahtel.com/graphql/"
HEADERS = {
    "From": "behnammohammadi149@gmail.com",
    "Content-Type": "application/json",
}


# ---------------------- درخواست امن ----------------------
def safe_request(url: str, post_data: dict, retries=2, delay=2):
    for i in range(retries):
        try:
            res = requests.post(url, json=post_data, headers=HEADERS, timeout=25)
            if res.status_code == 200:
                return res
            logging.warning(f"⚠️ Status code {res.status_code} on {url}")
        except requests.RequestException as e:
            logging.error(f"❌ Request error (try {i+1}/{retries}): {e}")
        time.sleep(delay)
    return None


# ---------------------- GraphQL Query Builders ----------------------
def body_all_laptops(after: Optional[str] = None):
    variables = {
        "first": 50,
        "channel": "customer",
        "where": {
            "isAvailable": True,
            "stockAvailability": "IN_STOCK",
            "price": {"range": {"gte": 0}},
            "category": {"eq": "Q2F0ZWdvcnk6NA=="},
        },
        "sortBy": {"channel": "customer", "direction": "ASC", "field": "PUBLICATION_DATE"},
    }
    if after:
        variables["after"] = after
    return {
        "operationName": "HomeProductList",
        "variables": variables,
        "query": """
        query HomeProductList($first: Int, $channel: String, $where: ProductWhereInput, $sortBy: PublicProductOrder, $after: String) {
          publicProducts(first: $first, after: $after, channel: $channel, where: $where, sortBy: $sortBy) {
            totalCount
            pageInfo { hasNextPage endCursor }
            edges { node { id name slug } }
          }
        }""",
    }


def body_single_laptop(slug: str):
    return {
        "operationName": "ProductDetail",
        "variables": {"channel": "customer", "slug": slug},
        "query": """
        query ProductDetail($slug: String!, $channel: String) {
          publicProduct(slug: $slug, channel: $channel) {
            id
            name
            description
            seoDescription
            slug
            isAvailable
            attributes {
              attribute { name slug }
              values { name value }
            }
            variants {
              id
              name
              quantityAvailable
              attributes { attribute { name slug } values { name value } }
              pricing {
                price { gross { amount } }
                priceUndiscounted { gross { amount } }
              }
            }
          }
        }""",
    }


# ---------------------- ابزارهای کمکی ----------------------
def fa_to_en_digits(s: str) -> str:
    return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")) if s else s


def extract_capacity(value: str) -> Optional[str]:
    if not value:
        return None
    v = fa_to_en_digits(value).replace("٫", ".").replace(",", ".")
    if re.search(r"Hz|هرتز", v):
        return None
    v = re.sub(r"گیگابایت", "GB", v)
    v = re.sub(r"مگابایت", "MB", v)
    v = re.sub(r"ترابایت", "TB", v)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB|MB|KB)", v, re.IGNORECASE)
    return f"{m.group(1)}{m.group(2).upper()}" if m else None


def cpu_from_title(text: str) -> Optional[str]:
    if not text:
        return None
    t = fa_to_en_digits(text)
    for pat, label in [
        (r"\bi[3579]\b", "Core "),
        (r"Ultra\s*[579]", "Core "),
        (r"Ryzen\s*[3579]", ""),
        (r"\bR([3579])\b", "Ryzen "),
        (r"(Celeron|Pentium)", ""),
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            return label + m.group(0).title()
    return None


def clean_display_size(value: str) -> Optional[str]:
    if not value:
        return None
    v = fa_to_en_digits(value).replace("٫", ".").replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:اینچ|inch)", v)
    return m.group(1) if m else None


def gpu_from_title(title: str) -> Optional[str]:
    if not title:
        return None
    t = fa_to_en_digits(title)
    m = re.search(r"(RTX|GTX)\s*([0-9]{3,4}Ti?)", t, re.IGNORECASE)
    if m:
        return f"NVIDIA GeForce {m.group(1).upper()} {m.group(2)}"
    if "iris" in t.lower():
        return "Intel Iris Xe"
    if "uhd" in t.lower():
        return "Intel UHD Graphics"
    if "radeon" in t.lower():
        return "AMD Radeon"
    return None


# ---------------------- استخراج داده‌ها ----------------------
def get_all_laptops_id() -> List[str]:
    all_slugs, after = [], None
    try:
        while True:
            res = safe_request(GRAPHQL_URL, body_all_laptops(after))
            if not res:
                break
            data = res.json().get("data", {}).get("publicProducts", {})
            for edge in data.get("edges", []):
                slug = edge.get("node", {}).get("slug")
                if slug:
                    all_slugs.append(slug)

            page_info = data.get("pageInfo", {})
            if page_info.get("hasNextPage"):
                after = page_info.get("endCursor")
                time.sleep(0.5)
            else:
                break
    except Exception:
        laptop_update_code_execution_state("Hamrahtel", False, traceback.format_exc())
    return all_slugs


def parse_specs_from_text(desc: str, title: str, seo: str) -> dict:
    specs = {"ram": "نامشخص", "storage": "نامشخص", "cpu": "نامشخص", "gpu": "نامشخص", "display_size": "نامشخص"}
    full_txt = f"{desc} {seo}".replace("\n", " ")
    try:
        if "رم" in full_txt or "RAM" in full_txt:
            specs["ram"] = extract_capacity(full_txt) or specs["ram"]
        if "حافظه" in full_txt or "Storage" in full_txt:
            specs["storage"] = extract_capacity(full_txt) or specs["storage"]
        if specs["cpu"] == "نامشخص":
            specs["cpu"] = cpu_from_title(title) or "نامشخص"
        if specs["gpu"] == "نامشخص":
            specs["gpu"] = gpu_from_title(title) or "نامشخص"
    except Exception:
        laptop_update_code_execution_state("Hamrahtel", False, traceback.format_exc())
    return specs


def get_laptop_data(slug: str) -> List[Dict]:
    try:
        res = safe_request(GRAPHQL_URL, body_single_laptop(slug))
        if not res:
            return []
        data = res.json().get("data", {}).get("publicProduct", {})
        if not data:
            return []

        brand_name = "نامشخص"
        for attr in data.get("attributes", []):
            if attr.get("attribute", {}).get("slug") == "brand" and attr.get("values"):
                brand_name = attr["values"][0].get("name", "نامشخص")

        brand, _ = BrandLaptop.objects.get_or_create(name_fa=brand_name, name_en=brand_name)
        specs = parse_specs_from_text(data.get("description", ""), data.get("name", ""), data.get("seoDescription", ""))

        base = {
            "title": data.get("name", ""),
            "model": data.get("name", ""),
            "brand": brand,
            "site": "Hamrahtel",
            "url": f"https://hamrahtel.com/products/{slug}",
            "stock": data.get("isAvailable", True),
            "seller": "Hamrahtel",
            **specs,
        }

        variants = []
        for v in data.get("variants", []) or []:
            try:
                pricing = v.get("pricing", {})
                min_price = int(pricing.get("price", {}).get("gross", {}).get("amount", 0)) * 10
                max_price = int(pricing.get("priceUndiscounted", {}).get("gross", {}).get("amount", 0)) * 10

                color_name = None
                warranty = None
                for attr in v.get("attributes", []):
                    slug = attr.get("attribute", {}).get("slug")
                    vals = attr.get("values", [])
                    if slug == "color" and vals:
                        color_name = vals[0].get("name")
                    if slug == "warranty" and vals:
                        warranty = vals[0].get("name")

                variants.append({
                    **base,
                    "color_name": color_name or "",
                    "guarantee": warranty or "نامشخص",
                    "min_price": min_price,
                    "max_price": max_price,
                })
            except Exception:
                continue

        return variants
    except Exception:
        laptop_update_code_execution_state("Hamrahtel", False, traceback.format_exc())
        return []


# ---------------------- Celery Task ----------------------
@shared_task(bind=True, max_retries=1)
def laptop_hamrahtel_crawler(self):
    try:
        slugs = get_all_laptops_id()
        all_laptops = []

        for slug in slugs:
            laptops = get_laptop_data(slug)
            if laptops:
                all_laptops.extend(laptops)
            time.sleep(0.5)

        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        ProductLaptop.objects.filter(site="Hamrahtel", status=True, updated_at__lt=ten_min_ago).update(status=False)

        for laptop in all_laptops:
            save_laptop_obj(laptop)

        laptop_update_code_execution_state("Hamrahtel", True)
        print(f"✅ {len(all_laptops)} laptops crawled successfully.")

    except Exception:
        err = traceback.format_exc()
        laptop_update_code_execution_state("Hamrahtel", False, err)
        raise self.retry(exc=Exception(err), countdown=30)
