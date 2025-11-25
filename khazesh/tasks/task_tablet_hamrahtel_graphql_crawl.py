import re
import time
import traceback
from typing import Dict, List, Optional, Tuple, Union
import requests
from celery import shared_task
from requests.exceptions import ConnectionError, RequestException, Timeout
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import uuid
from khazesh.models import Mobile
from django.utils import timezone
import gzip, io

ResponseType = Optional[requests.Response]


# ------------------ Static Config ------------------
def generate_statics() -> Tuple:
    site = "Hamrahtel"
    guarantee = "ذکر نشده"
    seller = "Hamrahtel"
    brand_keyes = {"سامسونگ": "samsung", "شیائومی": "xiaomi"}
    graphql_url = "https://core-api.hamrahtel.com/graphql/"

    body_for_all_tablets = {
        "operationName": "HomeProductList",
        "variables": {
            "first": 100,
            "channel": "customer",
            "where": {
                "isAvailable": True,
                "stockAvailability": "IN_STOCK",
                "price": {"range": {"gte": 0}},
                "category": {"eq": "Q2F0ZWdvcnk6NQ=="},
                "attributes": [{"slug": "brand", "values": ["smswng", "shyywmy"]}]
            },
            "sortBy": {
                "channel": "customer",
                "direction": "ASC",
                "field": "PUBLICATION_DATE"
            }
        },
        "query": """
query HomeProductList($first: Int = 20, $channel: String = "customer", $where: ProductWhereInput, $sortBy: PublicProductOrder) {
  publicProducts(first: $first, channel: $channel, where: $where, sortBy: $sortBy) {
    totalCount
    edges {
      node {
        name
        slug
        isAvailable
        category { name }
      }
    }
  }
}
"""

    }


    body_for_single_tablet_data = {
        "operationName": "ProductDetail",
        "variables": {
            "channel": "customer",
            "slug": "ID_OF_TABLET"
        },
        "query": """query ProductDetail($slug: String!, $channel: String = "customer") {
            publicProduct(slug: $slug, channel: $channel) {
                id
                name
                isAvailable
                slug
                seoDescription
                description
                isAvailableForPurchase
                badgeMeta: metafields(
                keys: ["badge-title", "badge-description", "badge-link", "badge-icon"]
                )
                attributes {
                attribute {
                    id
                    name
                    slug
                    type
                    __typename
                }
                values {
                    id
                    name
                    value
                    file {
                    url
                    __typename
                    }
                    __typename
                }
                __typename
                }
                variants {
                id
                name
                quantityAvailable
                isOfoghSubjected
                quantityLimitPerCustomer
                quantityLimitPerCustomerPerDay
                metafields(keys: ["order"])
                attributes {
                    attribute {
                    name
                    slug
                    __typename
                    }
                    values {
                    name
                    value
                    file {
                        url
                        __typename
                    }
                    __typename
                    }
                    __typename
                }
                pricing {
                    ...ProductPricingFragment
                    __typename
                }
                __typename
                }
                category {
                name
                id
                slug
                parent {
                    name
                    id
                    slug
                    __typename
                }
                __typename
                }
                media {
                id
                alt
                uri {
                    url
                    __typename
                }
                __typename
                }
                __typename
            }
            }

            fragment ProductPricingFragment on VariantPricingInfo {
            discount {
                gross {
                amount
                __typename
                }
                __typename
            }
            price {
                gross {
                amount
                __typename
                }
                __typename
            }
            priceUndiscounted {
                gross {
                amount
                __typename
                }
                __typename
            }
            __typename
        }"""
    }


    return site, guarantee, graphql_url, seller, brand_keyes, body_for_all_tablets, body_for_single_tablet_data


# ------------------ Safe Request ------------------
def retry_request(url: str, site: str, post_data: Optional[Dict] = None, max_retries: int = 2, retry_delay: int = 1, req_type: str = "get") -> ResponseType:
    HEADERS = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "Origin": "https://hamrahtel.com",
        "Referer": "https://hamrahtel.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    }



    for i in range(max_retries):
        try:
            if req_type.lower() == "post":
                r = requests.post(url, json=post_data, headers=HEADERS, timeout=25)
                print(f"Status Code: {r.status_code}")
                try:
                    # اگر پاسخ فشرده است، حتماً بازش کن
                    raw = r.content
                    try:
                        raw = gzip.decompress(raw)
                    except:
                        pass


                    # چند حالت مختلف برای دیکد کردن تست می‌کنیم
                    for enc in ["utf-8", "utf-8-sig", "latin-1"]:
                        try:
                            text = raw.decode(enc)
                            print("✅ Decoded using:", enc)
                            print(text[:1500])
                            break
                        except Exception:
                            continue
                    else:
                        print("❌ هیچ‌کدام از انکدینگ‌ها کار نکرد.")

                except Exception as e:
                    print("⚠️ Decode error:", e)

            else:
                r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            return r
        except (ConnectionError, Timeout) as e:
            print(f"⚠️ [{site}] connection error ({i+1}/{max_retries}): {e}")
            update_code_execution_state(f"{site}-tablet", False, str(e))
            if i < max_retries - 1:
                time.sleep(retry_delay)
        except RequestException as e:
            print(f"⚠️ [{site}] request exception: {e}")
            update_code_execution_state(f"{site}-tablet", False, str(e))
            return None
        except Exception:
            update_code_execution_state(f"{site}-tablet", False, traceback.format_exc())
            return None
    return None


# ------------------ Extraction helpers ------------------
def extract_details(en_title: str) -> Tuple[str, bool, bool, str, str]:
    memory_ram_pattern = r"(\d+GB)(?:\sRAM\s(\d+GB))?"
    ram = "ندارد"
    memory = "ندارد"
    match = re.search(memory_ram_pattern, en_title)
    if match:
        memory = match.group(1)
        ram = match.group(2) or "ندارد"

    vietnam = any(k in en_title for k in ["Vietnam", "Vietna", "Viet", "vietnam", "viet"])
    not_active = any(k in en_title for k in ["non Active", "Non Active", "NON ACTIV"])
    return en_title, not_active, vietnam, ram, memory


# ------------------ Data Fetchers ------------------
def get_all_tablets_id() -> Tuple[List[str], int]:
    all_tablets_id = []
    site, _, url, _, _, body_all, _ = generate_statics()
    res = retry_request(url, site=site, post_data=body_all, req_type="post")

    if not res:
        return [], 0

    try:
        data = res.json()
    except Exception:
        update_code_execution_state(f"{site}-tablet", False, "Invalid JSON response from GraphQL")
        return [], 0

    all_data = data.get("data", {}).get("publicProducts", {})
    for t in all_data.get("edges", []):
        slug = t.get("node", {}).get("slug")
        if slug:
            all_tablets_id.append(slug)

    has_next = all_data.get("pageInfo", {}).get("hasNextPage", False)
    counter = 0
    while has_next:
        counter += 1
        cursor = all_data.get("pageInfo", {}).get("endCursor")
        body_all["variables"]["after"] = cursor
        res = retry_request(url, site=site, post_data=body_all, req_type="post")
        if not res:
            break
        try:
            data = res.json()
        except Exception:
            break
        all_data = data.get("data", {}).get("publicProducts", {})
        for t in all_data.get("edges", []):
            slug = t.get("node", {}).get("slug")
            if slug:
                all_tablets_id.append(slug)
        has_next = all_data.get("pageInfo", {}).get("hasNextPage", False)
    return all_tablets_id, counter


def get_tablet_data(tablet_id: str) -> List[Dict]:
    site, guarantee, url, seller, brand_keyes, _, body_single = generate_statics()
    body_single["variables"]["slug"] = tablet_id

    res = retry_request(url, site=site, post_data=body_single, req_type="post")
    if not res:
        return []

    try:
        data = res.json()
    except Exception:
        update_code_execution_state(f"{site}-tablet", False, f"Invalid JSON for {tablet_id}")
        return []

    product = data.get("data", {}).get("publicProduct", {})
    if not product:
        return []

    en_title = product.get("name", "")

    # -----------------------------
    # 🔥 brand detection (مشکل اصلی)
    # -----------------------------
    attrs = product.get("attributes", [])
    brand_attr = next(
        (a for a in attrs if "برند" in a.get("attribute", {}).get("name", "")),
        None
    )

    if not brand_attr:
        return []

    brand_name = None
    values = brand_attr.get("values") or []
    if values:
        brand_name = values[0].get("name", "").strip()

    if not brand_name:
        return []

    brand = brand_keyes.get(brand_name)
    if not brand:
        # اگر برند جدید بود، حذفش نکن → آن را ذخیره کن
        brand = brand_name.lower()

    # -----------------------------
    # RAM / Memory extraction
    # -----------------------------
    en_title, not_active, vietnam, ram, memory = extract_details(en_title)

    # Base shared fields
    tablet_base = {
        "url": f"https://hamrahtel.com/products/{tablet_id}",
        "title": en_title,
        "model": en_title,
        "memory": memory,
        "ram": ram,
        "brand": brand.capitalize(),
        "vietnam": vietnam,
        "not_active": not_active,
        "mobile_digi_id": "",
        "dual_sim": True,
        "active": True,
        "mobile": False,
        "max_price": 1,
        "site": site,
        "seller": seller,
        "guarantee": guarantee,
    }

    # -----------------------------
    # 🔥 variant parsing (بدون حذف اشتباه)
    # -----------------------------
    variants = product.get("variants", [])
    tablet_variants = []

    for v in variants:
        try:
            # 1) رنگ
            color_attr = next(
                (a for a in v.get("attributes", []) if a.get("attribute", {}).get("name") == "رنگ"),
                None
            )
            if not color_attr:
                continue

            color_val = color_attr["values"][0]
            color_name = color_val.get("name", "").strip()
            color_hex = color_val.get("value", "")

            # 2) قیمت → کاملاً امن و بدون خطا
            pricing = v.get("pricing") or {}
            price_info = pricing.get("price") or {}
            gross = price_info.get("gross") or {}
            amount = gross.get("amount")

            if not amount:
                # اگر قیمت نبود اما quantity > 0 بود → حذف نکن
                if v.get("quantityAvailable", 0) > 0:
                    price = 0
                else:
                    continue
            else:
                price = int(amount) * 10

            # 3) ساخت نهایی variant
            variant_obj = {
                **tablet_base,
                "color_name": color_name,
                "color_hex": color_hex,
                "min_price": price,
            }

            tablet_variants.append(variant_obj)

        except Exception as e:
            update_code_execution_state(f"{site}-tablet", False, f"Error parsing variant for {tablet_id}: {str(e)}")
            continue

    return tablet_variants

# ------------------ Main Task ------------------
@shared_task(bind=True, max_retries=1)
def tablet_hamrahtel_crawler(self):
    all_tablets = []
    site = "Hamrahtel"

    try:
        batch_id = f"Hamrahtel-{uuid.uuid4().hex[:12]}"
        ids, _ = get_all_tablets_id()
        if not ids:
            update_code_execution_state(f"{site}-tablet", False, "هیچ محصولی یافت نشد.")
            return

        for tablet_id in ids:
            try:
                variants = get_tablet_data(tablet_id)
                if variants:
                    all_tablets.extend(variants)
            except Exception:
                update_code_execution_state(f"{site}-tablet", False, traceback.format_exc())
                continue

        for t in all_tablets:
            save_obj(t, batch_id=batch_id)

        Mobile.objects.filter(site=site, mobile=False).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(f"{site}-tablet", bool(all_tablets), "هیچ تبلتی ثبت نشد." if not all_tablets else "")

    except Exception:
        error = traceback.format_exc()
        update_code_execution_state(f"{site}-tablet", False, error)
        print(error)
        raise self.retry(exc=Exception(error), countdown=30)
    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site=site, status=True, mobile=False, updated_at__lt=ten_min_ago).update(status=False)
