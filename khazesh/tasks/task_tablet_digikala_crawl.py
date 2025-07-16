import re
import traceback
from typing import Dict, List, Tuple,Optional

import requests
from celery import shared_task

from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
from khazesh.models import Mobile
from django.utils import timezone

def STATICS() -> Optional[Tuple[Dict]]:
    
    # [(brand_name, page_number)]
    # these are from seo_url?=1 form
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
        "Not Active",
        "Not Active",
        "Not Activate",
        "Not Activated",
        "not active",
        "not-active",
        "Not_Active",
        "NOT_ACTIVE",
        "Not-Active",
        "NOT-ACTIVE",
        "ٔNOT ACTIVE",
        "نات اکتیو",
        "نات-اکتیو",
    ]

    return brands, not_active_texts


def extract_model_form_title(title_en_list):
    model = ""
    for word in title_en_list[1:]:
        if "GB" in word:
            break
        if word in ["Dual", "Single"]:
            break
        model += word + " "
        if word == "Mini":
            break
    return model.strip()


def extract_same_color_variants(obj):
    status = obj["data"]["product"]["status"]
    if status == "marketable":
        # colors_obj_list = obj['data']['product']['colors']
        variants = obj["data"]["product"]["variants"]

        # get colors from variants
        colors_obj_list = [variant["color"] for variant in variants]

        # remove duplicated colors
        colors_obj_list = [
            obj
            for n, obj in enumerate(colors_obj_list)
            if obj not in colors_obj_list[n + 1 :]
        ]
        colors = list(map(lambda x: (x["hex_code"], x["title"]), colors_obj_list))
        variant_objects = []
        for hex, color in colors:
            variant_obj = {"color_name": color, "color_hex": hex, "variants": []}
            prices = []
            for variant in variants:
                if variant["color"]["hex_code"] == hex:
                    price = variant["price"]["selling_price"]
                    prices.append(price)
                    variant_obj["variants"].append(variant)
            # print(prices)
            variant_obj["min_price"] = min(prices, default="EMPTY")
            variant_obj["max_price"] = max(prices, default="EMPTY")

            # finding lowest price of seller in the one color tablet
            min_price_variant = min(
                variant_obj["variants"],
                key=lambda x: x["price"]["selling_price"],
                default="EMPTY",
            )
            if min_price_variant != "EMPTY":
                variant_obj["seller"] = min_price_variant["seller"]["title"]
                variant_obj["guarantee"] = min_price_variant["warranty"]["title_fa"]
                variant_obj.pop("variants")

            variant_objects.append(variant_obj)

        return variant_objects
    # print(f'tablet phone is {status}__(extract_same_color_variants function)')
    return None


def extract_ram_and_memory(obj):
    title_en = obj["data"]["product"]["title_en"]
    pattern = r"(\d+GB) | (\d+TB)"
    # pattern1 = r'(\d+TB)'
    matches = re.findall(pattern, title_en)

    # print('matches2', matches)
    if matches and len(matches) == 2:

        memory = list(filter(lambda x: x != "", matches[0]))
        ram = list(filter(lambda x: x != "", matches[1]))
        matches = sum([memory, ram], [])
        # print(matches)
        return matches

    attribiutes_list = obj["data"]["product"]["specifications"][0]["attributes"]

    kilo_mega_giga_tra = {
        "کیلوبایت": "KB",
        "مگابایت": "MB",
        "گیگابایت": "GB",
        "ترابایت": "TB",
    }

    letter_to_digit_obj = {
        "یک": "1",
        "دو": "2",
        "سه": "3",
        "چهار": "4",
        "پنج": "5",
        "شش": "6",
        "هشت": "8",
        "12": "12",
        "16": "16",
        "32": "32",
        "64": "64",
        "128": "128",
        "256": "256",
        "512": "512",
    }
    # print(attribiutes_list)
    ram = [obj["values"][0] for obj in attribiutes_list if obj["title"] == "مقدار RAM"]
    if ram:
        ram = ram[0].split(" ")

    memory = [
        obj["values"][0] for obj in attribiutes_list if obj["title"] == "حافظه داخلی"
    ]
    if memory:
        memory = memory[0].split(" ")
    for key, value in kilo_mega_giga_tra.items():
        if key in ram and ram:
            ram[1] = value

        if key in memory and memory:
            memory[1] = value

    for key, value in letter_to_digit_obj.items():
        if key in ram and ram:
            ram[0] = value
            ram = "".join(ram)

        if key in memory and memory:
            memory[0] = value
            memory = "".join(memory)

    if not ram:
        ram = None

    if not memory:
        memory = None

    # print(memory, ram)
    return [memory, ram]


def extract_url(obj):
    uri = obj["data"]["product"]["url"]["uri"].split("/")[1:-1]
    return f"https://digikala.com/{'/'.join(uri)}"


def extract_tablet_ids(url, cookies, headers):
    try:
        obj = requests.get(url, headers=headers, cookies=cookies)
        if obj.status_code == 200:
            obj = obj.json()

        else:
            print(url)
            print("obj.status_code", obj.status_code)
            obj = {}
            return None

        # sleep(3)

        http_status_code = obj["status"]
        # print('http_status_code', http_status_code)
        tablet_urls = []
        if http_status_code == 200:
            # sleep(3)
            for i in range(len(obj["data"]["products"])):
                # print(i)
                # get each product of status
                status = obj["data"]["products"][i]["status"]
                # if status != 'comming_soon' and status != 'stop_production':
                if status == "marketable":
                    id = obj["data"]["products"][i]["id"]
                    tablet_urls.append(
                        # f'https://api.digikala.com/v1/product/{id}/')
                        f"https://api.digikala.com/v2/product/{id}/"
                    )

                    # print('len(tablet_urls)', len(tablet_urls))

        else:
            print(f"http_status_code from get_tablet_ids: {http_status_code}")

        return tablet_urls
    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state("Digikala-tablet", False, error_message)
        print(f"Error {error_message}")
        return None


def extract_tablet_data(url, cookies, headers, not_active_texts):
    try:
        response = requests.get(url, headers=headers, cookies=cookies)
        if response.status_code == 200:
            obj = response.json()  # Only try to parse JSON if the status code is 200.
        else:
            # Handle non-200 responses accordingly
            print(f"Error: Received non-{response.status_code} status code.")
        # print(url)
        # sleep(2)
        http_status_code = obj["status"]
        print(obj)
        marketable = obj["data"]["product"].get("status")
        if not http_status_code == 200:
            print(
                f"http_status_code from (get_tablet_data) function: {http_status_code}"
            )
            return None

        if marketable == "marketable":

            title_en_list = obj["data"]["product"]["title_en"].strip().split(" ")
            title_fa = obj["data"]["product"]["title_fa"]

            # print(extract_ram_and_memory(obj))
            memory, ram = extract_ram_and_memory(obj)
            # print(obj['data']['product']['brand']['title_en'])
            print(
                " ".join(title_en_list),
                any(
                    [True for txt in not_active_texts if txt in " ".join(title_en_list)]
                ),
            )

            my_obj = {
                "mobile_digi_id": obj["data"]["product"]["id"],
                "title": title_fa,
                "brand": obj["data"]["product"]["brand"]["title_en"],
                "model": extract_model_form_title(title_en_list),
                "ram": ram,
                "memory": memory,
                "vietnam": "Vietnam" in title_en_list,
                "active": True,
                "mobile": False,
                "not_active": any(
                    [
                        True if txt in " ".join(title_en_list) else False
                        for txt in not_active_texts
                    ]
                ),
                "site": "DigiKala",
                "dual_sim": all([x in title_en_list for x in ["Dual", "Sim"]]),
                "url": extract_url(obj),
            }
            same_color_variants = extract_same_color_variants(obj)
            if same_color_variants:
                for tablet in same_color_variants:
                    tablet.update(my_obj)

                # print('same_color_variants', same_color_variants)
                return same_color_variants

            # print('come to my object')
            my_obj["active"] = False
            return [my_obj]

    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state("Digikala-tablet", False, error_message)
        print(f"Error {error_message}")
        return None


#
def get_cookie() -> Optional[dict] :
    """Return cookie from site"""

    URL = "https://digikala.com"
    try:
        import time

        from selenium import webdriver
        
        chrome_options = webdriver.ChromeOptions()
        chrome_options.set_capability('browserless:token', 'seP9QYgrex2JLu96TTW')
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")

        # Chrome options
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("window-size=2000x1080")
        chrome_options.add_argument(
            "--headless"
        )  # Optional: Comment this if you need a visible browser
        chrome_options.add_argument(
            "--disable-gpu"
        )  # Disable GPU acceleration in headless mode
        chrome_options.add_experimental_option(
            "detach", True
        )  # Keep the browser open after script ends

        # Start WebDriver
        driver = webdriver.Remote(
            command_executor='https://chrome-bartardigital.liara.run/webdriver',
            options=chrome_options
        )
        driver.get(URL)

        time.sleep(5)

        cookies = driver.get_cookies()
        # cookies = {cookie["name"]: cookie["value"] for cookie in cookies}
        # cook = {}
        # for cookie in cookies:
        #     # print(f"{cookie['name']}:\t{cookie['value']}")
        #     cook.update({cookie["name"]: cookie["value"]})
        cook = {cookie["name"]: cookie["value"] for cookie in cookies} 

        # print(cookies)
        # print(driver.co)
        return cook
    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state("Digikala-tablet", False, error_message)
        print(f"Error {error_message}")
        return None
    finally:
        driver.quit()

    # print(json.dumps(re.text))


@shared_task(bind=True, max_retries=1)
def tablet_digikala_crawler(self):
    # brands = [('nothing', 2)]
    url_list = []
    brands, not_active_texts = STATICS()
    cookies = get_cookie()
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        url_digi = "https://api.digikala.com/v1/categories/tablet/search/?brands%5B0%5D=10&brands%5B1%5D=18&brands%5B2%5D=1662&has_selling_stock=1&page=1"
        response = requests.get(url_digi, headers=headers)
        if response.status_code == 200:
            data = response.json()
            total_pages = data["data"]["pager"]["total_pages"]

            
            if True:
                if total_pages > 0:
                    if True:
                        for i in range(total_pages):
                            link = f"https://api.digikala.com/v1/categories/tablet/search/?brands%5B0%5D=10&brands%5B1%5D=18&brands%5B2%5D=1662&has_selling_stock=1&page={i+1}"
                            # print('link', link)
                            url_list.append(link)

                    # print('url_list', url_list)s
                    # get Ids of tablets
                    # all tablets brand ids in digikala

                    all_tablet_urls = list(
                        map(lambda url: extract_tablet_ids(url, cookies, headers), url_list)
                    )
                    all_tablet_urls = sum(list(filter(None, all_tablet_urls)), [])

                    tablet_datas_list = list(
                        map(
                            lambda url: extract_tablet_data(
                                url, cookies, headers, not_active_texts
                            ),
                            all_tablet_urls,
                        )
                    )
                    tablet_datas_list = sum(list(filter(None, tablet_datas_list)), [])

                    ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

                    Mobile.objects.filter(
                        site = 'Digikala',
                        status = True,
                        mobile = False,
                        updated_at__lt=ten_min_ago,
                    ).update(status=False)
                    
                    
                    # save crowled objects to database
                    for tablet_dict in tablet_datas_list:
                        save_obj(tablet_dict)

                    update_code_execution_state("Digikala-tablet", True)

    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state("Digikala-tablet", False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)

