import re
import time
import traceback
from typing import Dict, List, Optional, Tuple, Union

import requests
from celery import shared_task
from requests.exceptions import ConnectionError, RequestException

from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj

from khazesh.models import Mobile
from django.utils import timezone
import uuid

ResponseType = Union[requests.Response, None]


def generate_statics() -> Tuple:
    site = "Hamrahtel"
    guarantee = "ذکر نشده"
    seller = "Hamrahtel"
    brand_keyes = {
        "اپل": "apple",
        "سامسونگ": "samsung",
        "نوکیا": "nokia",
        "شیائومی": "xiaomi",
        "ریلمی": "realme",
        "موتورولا": "motorola",
        "ناتینگ فون": "nothing",
        "آنر": "honor",
        "هواوی": "huawei",
    }

    graphql_url = "https://core-api.hamrahtel.com/graphql/"

    body_for_all_mobiles = {
        "operationName": "HomeProductList",
        "variables": {
            "first": 100,
            "channel": "customer",
            "where": {
                "isAvailable": True,
                "stockAvailability": "IN_STOCK",
                "price": {"range": {"gte": 0}},
                "category": {"eq": "Q2F0ZWdvcnk6Mg=="},
            },
            "sortBy": {
                "channel": "customer",
                "direction": "ASC",
                "field": "PUBLICATION_DATE",
            },
            "search": None,
        },
        "query": 'query HomeProductList($first: Int = 100, $channel: String = "customer", $where: ProductWhereInput, $sortBy: PublicProductOrder, $after: String, $search: String, $filter: ProductFilterInput) {\n  publicProducts(\n    first: $first\n    after: $after\n    channel: $channel\n    where: $where\n    sortBy: $sortBy\n    search: $search\n    filter: $filter\n  ) {\n    totalCount\n    pageInfo {\n      hasNextPage\n      endCursor\n      __typename\n    }\n    edges {\n      node {\n        ...ProductListFragment\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ProductListFragment on Product {\n  id\n  name\n  isAvailable\n  isAvailableForPurchase\n  slug\n  variants {\n    id\n    name\n    quantityAvailable\n    attributes {\n      attribute {\n        name\n        slug\n        __typename\n      }\n      values {\n        name\n        value\n        file {\n          url\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  pricing {\n    discount {\n      gross {\n        amount\n        __typename\n      }\n      __typename\n    }\n    priceRangeUndiscounted {\n      start {\n        gross {\n          amount\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    priceRange {\n      start {\n        gross {\n          amount\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  mainImage {\n    url\n    __typename\n  }\n  category {\n    name\n    id\n    __typename\n  }\n  __typename\n}',
    }

    body_for_single_mobile_data = {
        "operationName": "ProductDetail",
        "variables": {
            "channel": "customer",
            "slug": "ID_OF_MOBILE",
        },
        "query": 'query ProductDetail($slug: String!, $channel: String = "customer") {\n  publicProduct(slug: $slug, channel: $channel) {\n    id\n    name\n    isAvailable\n    slug\n    seoDescription\n    description\n    isAvailableForPurchase\n    attributes {\n      attribute {\n        id\n        name\n        slug\n        type\n        __typename\n      }\n      values {\n        id\n        name\n        value\n        file {\n          url\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    variants {\n      id\n      name\n      quantityAvailable\n      isOfoghSubjected\n      quantityLimitPerCustomer\n      quantityLimitPerCustomerPerDay\n      metafields(keys: ["order"])\n      attributes {\n        attribute {\n          name\n          slug\n          __typename\n        }\n        values {\n          name\n          value\n          file {\n            url\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      pricing {\n        ...ProductPricingFragment\n        __typename\n      }\n      __typename\n    }\n    category {\n      name\n      id\n      slug\n      parent {\n        name\n        id\n        slug\n        __typename\n      }\n      __typename\n    }\n    media {\n      id\n      alt\n      uri {\n        url\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ProductPricingFragment on VariantPricingInfo {\n  discount {\n    gross {\n      amount\n      __typename\n    }\n    __typename\n  }\n  price {\n    gross {\n      amount\n      __typename\n    }\n    __typename\n  }\n  priceUndiscounted {\n    gross {\n      amount\n      __typename\n    }\n    __typename\n  }\n  __typename\n}',
    }

    return (
        site,
        guarantee,
        graphql_url,
        seller,
        brand_keyes,
        body_for_all_mobiles,
        body_for_single_mobile_data,
    )


def retry_request(url: str, site: str, post_data: Optional[Dict] = None, max_retries: int = 1, retry_delay: int = 1, req_type: str = "get") -> ResponseType:
    HEADERS = {
        "From": "behnammohammadi149@gmail.com",
        "Content-Type": "application/json",
    }

    for i in range(max_retries):
        try:
            if req_type.lower() == "get":
                response = requests.get(url, headers=HEADERS)
            elif req_type.lower() == "post":
                response = requests.post(url, json=post_data, headers=HEADERS)
            else:
                raise ValueError(f"Invalid request type: {req_type}")

            response.raise_for_status()
            return response
        except (ConnectionError, RequestException) as e:
            print(f"⚠️ {type(e).__name__} on attempt {i + 1}: {e}")
            if i < max_retries - 1:
                print("Retrying...")
                time.sleep(retry_delay)
            else:
                update_code_execution_state(site, False, str(e))
                return None
        except Exception:
            error_message = traceback.format_exc()
            update_code_execution_state(site, False, error_message)
            print(error_message)
            return None
    return None


def extract_details(en_title: str) -> Tuple[Optional[str]]:
    try:
        memory_ram_pattern = r"(\d+GB)(?:\sRAM\s(\d+GB))?"
        ram = "ندارد"
        memory = "ندارد"

        match = re.search(memory_ram_pattern, en_title)
        if match:
            memory = match.group(1)
            ram = match.group(2)

        vietnam = any(v in en_title for v in ["Vietnam", "Vietna", "viet"])
        not_active = any(x in en_title for x in ["non Active", "Non Active", "NON ACTIV"])
        return en_title, not_active, vietnam, ram, memory
    except Exception:
        print("Error in extract_details")
        return en_title, False, False, "ندارد", "ندارد"


def get_all_mobiles_id():
    all_mobiles_id: List = []
    site, _, url, _, _, body_for_all_mobiles, _ = generate_statics()
    res = retry_request(url, site, post_data=body_for_all_mobiles, req_type="post")
    if not res or res.status_code != 200:
        return all_mobiles_id, getattr(res, "status_code", "RequestFailed")

    res = res.json()
    all_data = res.get("data", {}).get("publicProducts", {})

    for mobile in all_data.get("edges", []):
        all_mobiles_id.append(mobile.get("node", {}).get("slug", 0))

    has_next_page = all_data.get("pageInfo", {}).get("hasNextPage", False)
    counter = 0
    while has_next_page:
        counter += 1
        end_cursor = all_data.get("pageInfo", {}).get("endCursor", "")
        body_for_all_mobiles["variables"]["after"] = end_cursor
        res = retry_request(url, site, post_data=body_for_all_mobiles, req_type="post")
        if not res or res.status_code != 200:
            break
        res = res.json()
        all_data = res.get("data", {}).get("publicProducts", {})
        for mobile in all_data.get("edges", []):
            all_mobiles_id.append(mobile.get("node", {}).get("slug", 0))
        has_next_page = all_data.get("pageInfo", {}).get("hasNextPage", False)
    return all_mobiles_id, counter


def run_get_all_mobiles_id() -> Union[List, int, Dict]:
    try:
        all_mobiles_id, counter = get_all_mobiles_id()
        if not all_mobiles_id:
            print(f"No mobiles retrieved. {counter}")
            return counter
        print(f"Retrieved {len(all_mobiles_id)} mobile IDs in {counter} iterations.")
        return all_mobiles_id
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Hamrahtel", False, error_message)
        print(error_message)
        return 0


def get_mobile_data(mobile_id: Union[int, str]) -> Dict:
    try:
        mobile_obj_variants: List[Dict] = []
        site, guarantee, url, seller, brand_keyes, _, body_for_single_mobile_data = generate_statics()

        body_for_single_mobile_data["variables"]["slug"] = mobile_id
        res = retry_request(url, site, post_data=body_for_single_mobile_data, req_type="post")
        if not res or res.status_code != 200:
            return []

        res = res.json()
        mobile_detail = res.get("data", {}).get("publicProduct", {})
        en_title = mobile_detail.get("name", "")
        brand = next(
            (v["name"].strip() for a in mobile_detail.get("attributes", [])
             if a.get("attribute", {}).get("name") == "برند"
             for v in a.get("values", [])), None)
        if not brand or brand not in brand_keyes:
            return []

        brand = brand_keyes[brand]
        en_title, not_active, vietnam, ram, memory = extract_details(en_title)

        base_obj = {
            "url": f"https://hamrahtel.com/products/{mobile_id}",
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
            "mobile": True,
            "max_price": 1,
            "site": site,
            "seller": seller,
            "guarantee": guarantee,
        }

        for variant in mobile_detail.get("variants", []):
            if not (variant.get("quantityAvailable") and variant.get("pricing")):
                continue
            color_attr = next(
                (a for a in variant.get("attributes", [])
                 if a.get("attribute", {}).get("name") == "رنگ"),
                None)
            if not color_attr:
                continue
            val = color_attr["values"][0]
            color_name, color_hex = val.get("name", ""), val.get("value", "")
            price = int(variant.get("pricing", {}).get("price", {}).get("gross", {}).get("amount", 0)) * 10
            mobile_obj_variants.append({
                **base_obj,
                "color_name": color_name,
                "color_hex": color_hex,
                "min_price": price
            })

        return mobile_obj_variants
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Hamrahtel", False, error_message)
        print(f"Error in get_mobile_data:\n{error_message}")
        return []


@shared_task(bind=True, max_retries=1)
def hamrahtel_crawler(self):
    all_mobiles: List[Dict] = []
    try:
        batch_id = f"Hamrahtel-{uuid.uuid4().hex[:12]}"
        all_mobile_ids = run_get_all_mobiles_id()
        if not isinstance(all_mobile_ids, list):
            update_code_execution_state("Hamrahtel", False, str(all_mobile_ids))
            return

        for mobile_id in all_mobile_ids:
            variants = get_mobile_data(mobile_id)
            if variants:
                all_mobiles.extend(variants)

        for mobile_dict in all_mobiles:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site="Hamrahtel", mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state("Hamrahtel", bool(all_mobiles), "هیچ محصولی پیدا نشد." if not all_mobiles else "")
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state("Hamrahtel", False, error_message)
        print(f"Error in hamrahtel_crawler:\n{error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)
    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site="Hamrahtel", status=True, mobile=True, updated_at__lt=ten_min_ago).update(status=False)
