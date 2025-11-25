import re
import time
import traceback
from typing import Dict, List, Optional, Tuple, Union

import requests
from celery import shared_task
from requests.exceptions import ConnectionError, RequestException

from khazesh.models import BrandAccessories, CategoryAccessories
from khazesh.models import ProductAccessories
from khazesh.tasks.save_accessories_object_to_database import save_obj
from khazesh.tasks.save_accessories_crawler_status import accessories_update_code_execution_state
from django.utils import timezone

ResponseType = Union[requests.Response, None]


def generate_statics() -> Tuple:
    site = "Hamrahtel"
    guarantee = "ذکر نشده"
    seller = "Hamrahtel"
    brand_keyes = {
        "انرجایزر": "energizer",
        "انکر": "anker",
        "شیائومی": "xiaomi",
        "فیلیپس": "philips",
        "کلومن": "koluman",
    }

    graphql_url = "https://core-api.hamrahtel.com/graphql/"

    # body_for_all_mobiles = {
    #     "operationName": "HomeProductList",
    #     "variables": {
    #         "first": 100,
    #         "channel": "customer",
    #         "where": {
    #             "isAvailable": True,
    #             "stockAvailability": "IN_STOCK",
    #             "price": {"range": {"gte": 0}},
    #             "category": {"eq": "Q2F0ZWdvcnk6Mg=="},
    #         },
    #         "sortBy": {
    #             "channel": "customer",
    #             "direction": "ASC",
    #             "field": "PUBLICATION_DATE",
    #         },
    #         "search": None,
    #     },
    #     "query": 'query HomeProductList($first: Int = 100, $channel: String = "customer", $where: ProductWhereInput, $sortBy: ProductOrder, $after: String, $search: String, $filter: ProductFilterInput) {\n  publicProducts(\n    first: $first\n    after: $after\n    channel: $channel\n    where: $where\n    sortBy: $sortBy\n    search: $search\n    filter: $filter\n  ) {\n    totalCount\n    pageInfo {\n      hasNextPage\n      endCursor\n      __typename\n    }\n    edges {\n      node {\n        ...ProductListFragment\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment ProductListFragment on Product {\n  id\n  name\n  isAvailable\n  isAvailableForPurchase\n  slug\n  variants {\n    id\n    name\n    quantityAvailable\n    attributes {\n      attribute {\n        name\n        slug\n        __typename\n      }\n      values {\n        name\n        value\n        file {\n          url\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  pricing {\n    discount {\n      gross {\n        amount\n        __typename\n      }\n      __typename\n    }\n    priceRangeUndiscounted {\n      start {\n        gross {\n          amount\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    priceRange {\n      start {\n        gross {\n          amount\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  mainImage {\n    url\n    __typename\n  }\n  category {\n    name\n    id\n    __typename\n  }\n  __typename\n}',
    # }

    body_for_all_mobiles = {
        "operationName": "HomeProductList",
        "variables": {
            "first": 100,
            "channel": "customer",
            "where": {
                "attributes": [
                    {
                        "slug": "brand",
                        "values": ["nrjyzr", "fylyps", "nkhr", "shyywmy", "khlwmn"]
                    }
                ],
                "isAvailable": True,
                "stockAvailability": "IN_STOCK",
                "price": {"range": {"gte": 0}},
                "category": {"eq": "Q2F0ZWdvcnk6OQ=="},
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
            "slug": "ID_OF_MOBILE",  # This should be changed when reqeust
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


def retry_request(
    url: str,
    site: str,
    post_data: Optional[Dict] = None,
    max_retries: int = 1,
    retry_delay: int = 1,
    req_type: str = "get",
) -> ResponseType:
    HEADERS = {
        "From": "behnammohammadi149@gmail.com",
        "Content-Type": "application/json",
    }

    for i in range(max_retries):
        try:
            if req_type.lower() == "get":
                response = requests.get(url, headers=HEADERS, timeout=15)
            elif req_type.lower() == "post":
                response = requests.post(url, json=post_data, headers=HEADERS, timeout=15)
            else:
                raise ValueError(f"Invalid request type: {req_type}")

            response.raise_for_status()
            print(f"✅ {req_type.upper()} request successful on attempt {i+1}")
            return response

        except (ConnectionError, RequestException) as e:
            error_message = f"{type(e).__name__} on attempt {i+1}: {e}"
            print(f"⚠️ {url} - {error_message}")
            if i < max_retries - 1:
                time.sleep(retry_delay)
                continue
            accessories_update_code_execution_state(site, 'powerbank', False, error_message)
            return None

        except Exception:
            error_message = traceback.format_exc()
            accessories_update_code_execution_state(site, 'powerbank', False, error_message)
            print(f"❌ Unexpected error in retry_request:\n{error_message}")
            return None

def extract_details(
    en_title: str,
) -> Tuple[Optional[str]]:
    # Define patterns
    en_model_pattern = r".*?(?=\b\d{1,3}(GB|MB|TB|G|M|T)\b)"
    memory_ram_pattern = r"(\d+GB)(?:\sRAM\s(\d+GB))?"
    ram = "ندارد"
    memory = "ندارد"

    match = re.search(memory_ram_pattern, en_title)
    if match:
        memory = match.group(1)
        ram = match.group(2)

    vietnam_keys = ["Vietnam", "Vietna", "Viet", "vietnam", "viet", "vietna"]
    vietnam = any(
        [True if vietnam_key in en_title else False for vietnam_key in vietnam_keys]
    )
    not_active_keywords = ["non Active", "Non Active", "NON ACTIV"]
    not_active = any(
        [
            True if not_active_key in en_title else False
            for not_active_key in not_active_keywords
        ]
    )

    return en_title, not_active, vietnam, ram, memory


def get_all_mobiles_id():
    all_mobiles_id: List = []
    site, _, url, _, _, body_for_all_mobiles, _ = generate_statics()

    res: ResponseType = retry_request(url, site=site, post_data=body_for_all_mobiles, req_type="post")
    if not res or res.status_code != 200:
        accessories_update_code_execution_state(site, 'powerbank', False, f"Failed initial GraphQL request: {url}")
        return [], 0

    try:
        res = res.json()
    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state(site, 'powerbank', False, error_message)
        return [], 0

    if res.get("errors"):
        accessories_update_code_execution_state(site, 'powerbank', False, str(res["errors"]))
        return [], 0

    data = res.get("data", {}).get("publicProducts", {})
    for edge in data.get("edges", []):
        node = edge.get("node", {})
        if node:
            all_mobiles_id.append(node.get("slug", ""))

    has_next = data.get("pageInfo", {}).get("hasNextPage", False)
    cursor = ""
    counter = 0

    while has_next:
        counter += 1
        cursor = data.get("pageInfo", {}).get("endCursor", "")
        body_for_all_mobiles["variables"]["after"] = cursor
        res = retry_request(url, site=site, post_data=body_for_all_mobiles, req_type="post")
        if not res or res.status_code != 200:
            break
        res = res.json()
        data = res.get("data", {}).get("publicProducts", {})
        for edge in data.get("edges", []):
            node = edge.get("node", {})
            if node:
                all_mobiles_id.append(node.get("slug", ""))
        has_next = data.get("pageInfo", {}).get("hasNextPage", False)

    return all_mobiles_id, counter


def run_get_all_mobiles_id() -> Union[List, int, Dict]:
    try:
        all_mobiles_id, counter = get_all_mobiles_id()
        if not all_mobiles_id:  # Check if the list is empty
            print(f"No mobiles retrieved. {counter}")

            # if post request has error or status_code is be not 200 it return
            return counter
        else:
            print(
                f"Retrieved {len(all_mobiles_id)} mobile IDs in {counter} iterations."
            )
            return all_mobiles_id

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the request: {e}")
        return 0
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return 0


def get_mobile_data(mobile_id: Union[int, str]) -> Dict:
    mobile_obj_variants: List[Dict] = []

    site, guarantee, url, seller, brand_keyes, _, body_for_single_mobile_data = generate_statics()
    category = CategoryAccessories.objects.filter(name_en='powerbank').first()

    body_for_single_mobile_data["variables"]["slug"] = mobile_id
    res = retry_request(url, site=site, post_data=body_for_single_mobile_data, req_type="post")
    if not res or res.status_code != 200:
        accessories_update_code_execution_state(site, 'powerbank', False, f"Bad response for slug {mobile_id}")
        return []

    try:
        data = res.json()
        product = data.get("data", {}).get("publicProduct", {})
        if not product:
            return []

        attributes = product.get("attributes", [])
        brand_attr = next((a for a in attributes if a.get("attribute", {}).get("name") == "برند"), None)
        if not brand_attr:
            return []

        brand_slug = brand_attr.get("values", [{}])[0].get("name", "").strip()
        if brand_slug not in brand_keyes:
            return []

        brand_en = brand_keyes[brand_slug]
        brand = BrandAccessories.objects.filter(name_en=brand_en).first() or \
                BrandAccessories.objects.create(name_fa=brand_slug, name_en=brand_en)

        base_obj = {
            "url": f"https://hamrahtel.com/products/{mobile_id}",
            "title": product.get("name", ""),
            "model": product.get("name", ""),
            "brand": brand,
            "category": category,
            "max_price": 1,
            "site": site,
            "seller": seller,
            "guarantee": guarantee,
            "stock": True,
            "fake": False,
            "description": ''
        }

        for variant in product.get("variants", []):
            if not variant.get("pricing"):
                continue
            color_attr = next((a for a in variant.get("attributes", []) if a.get("attribute", {}).get("name") == "رنگ"), None)
            if not color_attr:
                continue
            color_val = color_attr.get("values", [{}])[0]
            color_name = color_val.get("name", "")
            color_hex = color_val.get("value", "")
            price = int(variant.get("pricing", {}).get("price", {}).get("gross", {}).get("amount", 0)) * 10

            mobile_obj_variants.append({
                "color_name": color_name,
                "color_hex": color_hex,
                "min_price": price,
                **base_obj
            })

        return mobile_obj_variants

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state(site, 'powerbank', False, error_message)
        print(f"❌ get_mobile_data failed for {mobile_id}:\n{error_message}")
        return []


@shared_task(bind=True, max_retries=1)
def accessories_powerbank_hamrahtel_crawler(self):
    all_mobiles: List[Dict] = []

    try:
        all_mobile_ids = run_get_all_mobiles_id()
        if not isinstance(all_mobile_ids, list) or not all_mobile_ids:
            accessories_update_code_execution_state('Hamrahtel', 'powerbank', False, "No powerbank IDs found.")
            return

        for mobile_id in all_mobile_ids:
            variants = get_mobile_data(mobile_id)
            if not variants:
                continue
            all_mobiles += variants

        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        ProductAccessories.objects.filter(
            site='Hamrahtel',
            status=True,
            updated_at__lt=ten_min_ago,
            category__name_en='powerbank'
        ).update(status=False)

        for mobile_dict in all_mobiles:
            save_obj(mobile_dict)

        if all_mobiles:
            accessories_update_code_execution_state('Hamrahtel', 'powerbank', True)
        else:
            accessories_update_code_execution_state('Hamrahtel', 'powerbank', False, "No powerbank products found.")

    except Exception:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Hamrahtel', 'powerbank', False, error_message)
        print(f"❌ [Hamrahtel - Powerbank] Crawler failed:\n{error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)

    print("len(all_mobiles)", len(all_mobiles))
