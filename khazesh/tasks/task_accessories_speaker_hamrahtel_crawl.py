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
        "جی بی ال": "JBL",
        "هارمن کاردن": "harman kardon",
        "انکر": "anker",
        "شیائومی": "xiaomi",
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
                        "values": ["jy-by-l", "hrmn-khrdn", "nkhr", "shyywmy"]
                    }
                ],
                "isAvailable": True,
                "stockAvailability": "IN_STOCK",
                "price": {"range": {"gte": 0}},
                "category": {"eq": "Q2F0ZWdvcnk6OA=="},
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
    """
    Retry a GET or POST request with a specified number of retries and delay.

    Args:
        url (str): The URL to make the request to.
        site (str): Site identifier for logging or state tracking.
        post_data (Optional[Dict]): Data to send in a POST request.
        max_retries (int): Maximum number of retry attempts. Default is 3.
        retry_delay (int): Delay in seconds between retries. Default is 1.
        req_type (str): Request type ('get' or 'post'). Default is 'get'.

    Returns:
        ResponseType: Response object if successful, None otherwise.
    """

    HEADERS = {
        "From": "behnammohammadi149@gmail.com",
        "Content-Type": "application/json",
    }

    for i in range(max_retries):
        try:
            if req_type.lower() == "get":
                response = requests.get(url, headers=HEADERS)
                response.raise_for_status()  # Ensure HTTP errors raise exceptions
                print("Connection successful")
                return response

            elif req_type.lower() == "post":
                response = requests.post(url, json=post_data, headers=HEADERS)
                response.raise_for_status()  # Ensure HTTP errors raise exceptions
                print("POST request successful")
                return response

            else:
                raise ValueError(f"Invalid request type: {req_type}")

        except ConnectionError as ce:
            print(f"Connection error on attempt {i + 1}: {ce}")
            accessories_update_code_execution_state(site, 'speaker', False, str(ce))

            if i < max_retries - 1:
                print("Retrying...")
                time.sleep(retry_delay)

        except RequestException as re:
            print(f"Request error on attempt {i + 1}: {re}")
            accessories_update_code_execution_state(site, 'speaker', False, str(re))

            if i < max_retries - 1:
                print("Retrying...")
                time.sleep(retry_delay)
            else:
                raise re  # Re-raise the exception on the last attempt

    print(f"Failed to fetch data from {url} after {max_retries} attempts.")
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
    res: ResponseType = retry_request(
        url, site=site, post_data=body_for_all_mobiles, req_type="post"
    )

    if res.status_code != 200:
        accessories_update_code_execution_state('Hamrahtel', 'speaker', False, f"HTTP {res.status_code} in get_all_mobiles_id")
        return all_mobiles_id, res.status_code


    res = res.json()

    if res.get("errors", {}):
        accessories_update_code_execution_state('Hamrahtel', 'speaker', False, str(res.get("errors")))
        return all_mobiles_id, res.get("errors")


    all_data = res.get("data", {}).get("publicProducts", {})

    for mobile in all_data.get("edges", []):
        all_mobiles_id.append(mobile.get("node", {}).get("slug", 0))

    has_next_page = all_data.get("pageInfo", {}).get("hasNextPage", False)

    counter = 0
    end_cursor = ""
    while has_next_page:
        counter += 1
        end_cursor = all_data.get("pageInfo", {}).get("endCursor", "")
        body_for_all_mobiles = {
            **body_for_all_mobiles,
            "variables": {
                **body_for_all_mobiles.get("variables", {}),
                "after": end_cursor,
                # "first": body_for_all_mobiles["variables"]["first"] + 20,
            },
        }

        res: ResponseType = retry_request(
            url, site=site, post_data=body_for_all_mobiles, req_type="post"
        )
        if res.status_code != 200:
            break

        res = res.json()

        all_data = res.get("data", {}).get("publicProducts", {})
        for mobile in all_data.get("edges", []):
            all_mobiles_id.append(mobile.get("node", {}).get("slug", 0))
        # print("New End Cursor:", all_data.get("pageInfo", {}).get("endCursor", ""))
        # print(
        #     "New End First:", body_for_all_mobiles["variables"]['first']
        # )
        has_next_page = all_data.get("pageInfo", {}).get("hasNextPage", False)
        # print(counter)
        # print(end_cursor)
        # print(has_next_page)

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

    (
        site,
        guarantee,
        url,
        seller,
        brand_keyes,
        _,
        body_for_single_mobile_data,
    ) = generate_statics()

    category = CategoryAccessories.objects.filter(name_en='speaker').first()
    mobile_object = {}
    body_for_single_mobile_data = {
        **body_for_single_mobile_data,
        "variables": {
            **body_for_single_mobile_data["variables"],
            "slug": mobile_id,  # This should be changed when reqeust
        },
    }

    res: ResponseType = retry_request(
        url, site=site, post_data=body_for_single_mobile_data, req_type="post"
    )

    if res.status_code != 200:
        return (res.status_code,)

    res = res.json()

    if res.get("errors", {}):
        return res.get("errors")

    mobile_detail = res.get("data").get("publicProduct", {})
    en_title = mobile_detail.get("name", "")
    attributes = mobile_detail.get("attributes", [])
    # print(attributes)
    brand_slug = None
    for attr in attributes:
        if attr.get("attribute", {}).get("name", "").strip() == "برند":
            values = attr.get("values", [])
            if values:
                brand_slug = values[0].get("name", "").strip()
            break

    if not brand_slug:
        accessories_update_code_execution_state('Hamrahtel', 'speaker', False, f"No brand found for {mobile_id}")
        return []

    if brand_slug not in brand_keyes:
        return

    brand_en = brand_keyes[brand_slug]

    

    brand = BrandAccessories.objects.filter(name_en=brand_en).first()
    if not brand:
        brand = BrandAccessories.objects.create(name_fa=brand_slug, name_en=brand_en)
                       


    mobile_object["url"] = f"https://hamrahtel.com/products/{mobile_id}"
    mobile_object["title"] = en_title
    mobile_object["model"] = en_title
    mobile_object["brand"] = brand
    mobile_object["category"] = category
    mobile_object["max_price"] = 1
    mobile_object["site"] = site
    mobile_object["seller"] = seller
    mobile_object["guarantee"] = guarantee
    mobile_object["stock"] = True
    mobile_object["fake"] = False
    mobile_object["description"] = ''

    moblie_variants = filter(
        lambda variant: (
            variant.get("quantityAvailable", 0) and variant.get("pricing", {})
        ),
        mobile_detail.get("variants", []),
    )

    for variant in moblie_variants:
        variant_attirbute = variant.get("attributes")

        color_variant_attribute = next(
            (attr for attr in variant.get("attributes", [])
            if attr.get("attribute", {}).get("name", "").strip() == "رنگ"),
            None
        )
        if not color_variant_attribute or not color_variant_attribute.get("values"):
            continue

        color_name = color_variant_attribute.get("values", [])[0].get("name", "")
        color_hex = color_variant_attribute.get("values", [])[0].get("value", "")

        variant_price = variant.get("pricing", {}).get("price", {}).get("gross", {}).get("amount", 0)
        if not variant_price:
            continue
        variant_price = int(variant_price) * 10


        mobile_obj_variants.append(
            {
                "color_name": color_name,
                "color_hex": color_hex,
                "min_price": variant_price,
                **mobile_object,
            }
        )
        print(color_name, color_hex, variant_price)

    print(len(mobile_obj_variants))
    # print((mobile_obj_variants))
    print("#" * 90)

    return mobile_obj_variants


@shared_task(bind=True, max_retries=1)
def accessories_speaker_hamrahtel_crawler(self):

    all_mobiles: List[Dict] = []

    try:

        all_mobile_ids = run_get_all_mobiles_id()
        if not isinstance(all_mobile_ids, list) or not all_mobile_ids:
            accessories_update_code_execution_state('Hamrahtel', 'speaker', False, f"Invalid or empty mobile IDs: {all_mobile_ids}")
            return


        for mobile_id in all_mobile_ids:

            varinat_mobiles = get_mobile_data(mobile_id)

            if not varinat_mobiles:
                continue
            all_mobiles += varinat_mobiles


        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        ProductAccessories.objects.filter(
            site = 'Hamrahtel',
            status = True,
            updated_at__lt=ten_min_ago,
            category__name_en='speaker'
        ).update(status=False)
        
        for mobile_dict in all_mobiles:
            save_obj(mobile_dict)

        if all_mobiles:
            accessories_update_code_execution_state('Hamrahtel', 'speaker', True)
        else:
            accessories_update_code_execution_state('Hamrahtel', 'speaker', False, "No speaker products found.")

    except Exception as e:
        error_message = traceback.format_exc()
        accessories_update_code_execution_state('Hamrahtel', 'speaker', False, error_message)
        raise self.retry(exc=e, countdown=30)

    print("len(all_mobiles)", len(all_mobiles))
