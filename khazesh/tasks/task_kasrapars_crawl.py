import re
import time
import traceback
from typing import List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, element
from celery import shared_task
from fake_useragent import UserAgent
from requests import Response
from requests.exceptions import ConnectionError, RequestException

from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj

ResponseType = Optional[Response]
OptionalList = Optional[List]


def retry_request(
    url: str,
    site: str,
    max_retries: int = 2,
    retry_delay: int = 0,
) -> ResponseType:
    ua = UserAgent()
    HEADERS = {
        "User-Agent": ua["google"],
        "From": "behnammohammadi148@gmail.com",
    }
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS)
            # response.raise_for_status()
            print("Connection successful")
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+0}: {ce}"
            # save_error_to_log(url, error_message)
            print(url, error_message)
            if i < max_retries - 0:
                print("Retrying...")
                time.sleep(retry_delay)
        except RequestException as re:
            error_message = f"Other request error: {re}"
            # print(url, error_message)
            update_code_execution_state(site, False, error_message)
            return None
    return None


@shared_task(bind=True, max_retrie=2)
def kasrapars_crawler(self):
    # try:
        brands_key = {
            "شیائومی": "xiaomi",
            "سامسونگ": "samsung",
            "اپل": "apple",
            "پوکو": "poco",
            "آنر": "honor",
            "نوکیا": "nokia",
        }

        SITE = "KasraPars"
        SELLER = "KasraPars"

        all_mobile_objects = []

        break_outer_for = False
        for page_num in range(0, 6):
            # response:  Optional[Response] = retry_request('https://www.mobile139.com/group/apple-mobiles')

            if break_outer_for:
                break

            # try:
            #     response: ResponseType = retry_request(
            #         f"https://plus.kasrapars.ir/products/category-products/TLC-01?page={page_num}",
            #         SITE,
            #     )
            #     # print(response.text)
            #     if response.status_code != 200:
            #         error_message = f"Response status code:  { response.status_code}"
            #         # print(url, error_message)
            #         update_code_execution_state(SITE, False, error_message)
            #         continue

            # except Exception as e:
            #     error_message = f"Error message:  {e}"
            #     # print(url, error_message)
            #     update_code_execution_state(SITE, False, error_message)
            #     continue
                    
            
            response: ResponseType = retry_request(
                f"https://plus.kasrapars.ir/products/category-products/TLC-01?page={page_num}",
                SITE,
            )
            # print(response.text)
            if response.status_code != 200:
                error_message = f"Response status code:  { response.status_code}"
                # print(url, error_message)
                update_code_execution_state(SITE, False, error_message)
                continue

                
                
            soup = BeautifulSoup(response.text, "html.parser")
            mobiles_div = soup.find("div", class_="row mb-3 mx-0 px-res-0").find_all(
                "div",
                class_="col-lg-3 col-md-4 col-sm-6 col-12 px-10 mb-1 px-res-0 category-product-div",
            )
            for mobile in mobiles_div:
                mobile_object: dict = {}
                mobile_card_body = mobile.find("div", class_="product-card-body")
                product_price_div = mobile_card_body.find(
                    "div", class_="product-prices-div"
                )
                prodcut_price = (
                    product_price_div.find("span", class_="product-price")
                    .text.replace("تومان", "")
                    .strip()
                )
                if prodcut_price == "ناموجود":
                    break_outer_for = True
                    print("prodcut_price", prodcut_price)
                    break

                prodcut_a_tag = mobile_card_body.find(
                    "h5", class_="product-title"
                ).find("a")
                fa_title = prodcut_a_tag.text.strip()
                mobile_link = prodcut_a_tag.attrs["href"]

                single_product_page_res: ResponseType = retry_request(mobile_link, SITE)

                if not single_product_page_res:
                    continue

                single_product_page: BeautifulSoup = BeautifulSoup(
                    single_product_page_res.text, "html.parser"
                )

                # Title and model
                product_info_box = single_product_page.find("div", "product-info dt-sl")
                brand = (
                    product_info_box.find("div", class_="row pt-2")
                    .find("div", class_="col-md-7 col-lg-7")
                    .find("div", class_="d-block mb-2")
                    .find("a")
                    .text.strip()
                )
                print(f"Procceing {brand}")
                if brand not in brands_key:
                    continue

                fa_title_box = product_info_box.find("h1")
                en_title = fa_title_box.find_next_sibling().text.strip()
                en_title = en_title if "TLP" not in en_title else ""
                fa_title = fa_title_box.text.strip()
                model_pattern = r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T|gb)?|^(samsung|xiaomi|apple|nokia|honor|huawei|nothing\sphone)\s*|\s*vietnam\s*"
                model = re.sub(model_pattern, "", en_title.lower())
                if not model:
                    model = re.search(r"(?<=مدل\s)[\w\s]*\s*(?=ظرفیت)", fa_title)
                    if model:
                        model = model.group().strip()

                print(fa_title)
                print(en_title)

                mobile_variants = single_product_page.find(
                    "div", class_="card box-card px-3 pb-3 pt-0"
                )

                # guarantee
                guarantee_variant = mobile_variants.find(
                    "div", class_="product-variant dt-sl"
                )
                guarantee = ""
                guarantee_code = ""
                if guarantee_variant:
                    guarantee_variant.find(
                        "ul", class_="product-variants float-right ml-3"
                    ).find_all("li", class_="ui-variant product-attribute")[0]
                    guarantee = guarantee_variant.find("span").text.strip()
                    guarantee_code = guarantee_variant.find("input").attrs["value"]
                # ram memroy

                ram = re.search(
                    r"\s*رم\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?",
                    fa_title,
                )
                if ram:
                    ram = ram.group()
                    ram = re.sub(r"\s*گیگابایت\s*|\s*گگیابایت\s*", "GB", ram)
                    ram = re.sub(r"\s*رم\s*", "", ram)

                else:
                    ram = re.search(r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T)?", en_title)
                    if ram:
                        ram = ram.group()
                        ram = re.sub(r"\s*(GB|TB|T)\s*", "", ram)
                        ram = len(ram.split("/")) >= 2 and ram.split("/")[1]
                        ram = ram + "GB"
                    else:
                        ram = "ندارد"

                memory = re.search(
                    r"\s*ظرفیت\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?",
                    fa_title,
                )
                if memory:
                    memory = memory.group()
                    memory = re.sub(r"\s*گیگابایت\s*|\s*گگیابایت\s*", "GB", memory)
                    memory = re.sub(r"\s*ترابایت\s*", "TB", memory)
                    memory = re.sub(r"\s*ظرفیت\s*", "", memory)

                else:
                    memory = re.search(r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T)?", en_title)
                    if memory:
                        memory = memory.group()
                        memory = re.sub(r"\s*(GB|TB|T)\s*", "", memory)
                        memory = (
                            len(memory.split("/")) >= 1 and memory.split("/")[0].strip()
                        )

                    else:
                        memory = "ندارد"

                print(model)
                print(memory)
                print(ram)
                mobile_object["model"] = model
                mobile_object["memory"] = memory
                mobile_object["ram"] = ram
                mobile_object["brand"] = brands_key.get(brand, brand)
                # mobile_object['title_en'] = en_title
                mobile_object["title"] = fa_title
                mobile_object["url"] = mobile_link
                mobile_object["site"] = SITE
                mobile_object["seller"] = SELLER
                mobile_object["guarantee"] = guarantee
                mobile_object["max_price"] = 1
                mobile_object["mobile_digi_id"] = ""
                mobile_object["dual_sim"] = True
                mobile_object["active"] = True
                mobile_object["vietnam"] = (
                    True
                    if "ویتنام" in fa_title or "vietnam" in en_title.lower()
                    else False
                )
                mobile_object["not_active"] = (
                    True
                    if "نات اکتیو" in fa_title or "not active" in en_title.lower()
                    else False
                )

                # clolors
                m_variants = mobile_variants.find(
                    "div", class_="product-variant dt-sl product-variant-color"
                )
                if not m_variants:
                    continue
                color_variants_lis = m_variants.find_all(
                    "li", class_="ui-variant product-attribute"
                )

                color_name = ""
                if len(color_variants_lis) == 1:
                    color_li_tag = color_variants_lis[0]
                    color_span = color_li_tag.find("span", class_="ui-variant-shape")
                    color_name = color_span.attrs["data-name"].strip()
                    background_style = color_span.get("style")
                    color_hex = color_hex = re.search(
                        r"#[a-zA-z0-9]{3,}", background_style
                    ).group()
                    mobile_price = (
                        mobile_variants.find(
                            "div", class_="dt-sl box-Price-number box-margin"
                        )
                        .find("span", class_="price text-danger")
                        .text.replace(",", "")
                        .strip()
                    )
                    mobile_object["color_name"] = color_name
                    mobile_object["color_hex"] = color_hex
                    mobile_object["min_price"] = int(mobile_price) * 10
                    all_mobile_objects.append(mobile_object.copy())
                    continue

                for color_li in color_variants_lis:
                    color_input = color_li.find("input", class_="variant-selector")
                    color_span = color_li.find("span", class_="ui-variant-shape")
                    color_name = color_span.attrs["data-name"].strip()
                    background_style = color_span.get("style")
                    color_hex = color_hex = re.search(
                        r"#[a-zA-z0-9]{3,}", background_style
                    ).group()
                    if "checked" in color_input.attrs.keys():
                        mobile_price = (
                            mobile_variants.find(
                                "div", class_="dt-sl box-Price-number box-margin"
                            )
                            .find("span", class_="price text-danger")
                            .text.replace(",", "")
                            .strip()
                        )
                        mobile_object["color_name"] = color_name
                        mobile_object["color_hex"] = color_hex
                        mobile_object["min_price"] = int(mobile_price) * 10
                        all_mobile_objects.append(mobile_object.copy())
                        continue
                    else:
                        color_code = color_input.attrs.get("value", 0)
                        uurl = f'https://plus.kasrapars.ir/product/{mobile_link.split("/")[-1]}/prices?groups%5B%5D={color_code}&groups%5B%5D={guarantee_code}'
                        color_res = retry_request(uurl, SITE)
                        color_soup = BeautifulSoup(color_res.text, "html.parser")
                        mobile_price = (
                            color_soup.find(
                                "div", class_="dt-sl box-Price-number box-margin"
                            )
                            .find("span", class_="price text-danger")
                            .text.replace(",", "")
                            .strip()
                        )
                        mobile_object["color_name"] = color_name
                        mobile_object["color_hex"] = color_hex
                        mobile_object["min_price"] = int(mobile_price) * 10
                        all_mobile_objects.append(mobile_object.copy())

        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict)

        update_code_execution_state(SITE, True)

    # except Exception as e:
    #     error_message = str(traceback.format_exc())
    #     update_code_execution_state(SITE, False, error_message)
    #     print(f"Error {error_message}")
    #     raise self.retry(exc=e, countdown=30)
