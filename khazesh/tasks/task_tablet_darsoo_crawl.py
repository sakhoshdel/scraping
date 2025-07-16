import json
import re
import traceback
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
from requests.exceptions import ConnectionError, RequestException
import time
import traceback
from typing import List, Optional, Tuple
from requests import Response

from khazesh.models import Mobile
from django.utils import timezone
from urllib.parse import urljoin


urls = [
    "https://darsoo.com/categories/%D8%AA%D8%A8%D9%84%D8%AA/%D8%AA%D8%A8%D9%84%D8%AA-%D8%B4%DB%8C%D8%A7%D8%A6%D9%88%D9%85%DB%8C/",
    "https://darsoo.com/categories/%D8%AA%D8%A8%D9%84%D8%AA/%D8%AA%D8%A8%D9%84%D8%AA-%D8%B3%D8%A7%D9%85%D8%B3%D9%88%D9%86%DA%AF/",
    "https://darsoo.com/categories/%D8%AA%D8%A8%D9%84%D8%AA/%D8%AA%D8%A8%D9%84%D8%AA-%D8%A7%D9%BE%D9%84/"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

session = requests.Session()
session.headers.update(HEADERS)


def get_products_from_page(soup, base_url):
    product_blocks = soup.select("ul.listing-items > li")
    product_list = []
    for product_card in product_blocks:
        price = product_card.select_one(".price-value-wrapper")
        if price:
            tablet_price = price.text.replace('تومان', '').strip().replace(',', '')
        else:
            tablet_price = None

        box_title = product_card.select_one(".product-box-title")
        if tablet_price is not None and box_title and ("موجود" in box_title.text or "available" in box_title.text.lower()):
            link_tag = product_card.select_one(".product-box-title > a")
            if link_tag and link_tag.get("href"):
                full_link = urljoin(base_url, link_tag["href"])
                title_text = box_title.text.strip()
                product_list.append({"title": title_text, "price": tablet_price, 'link': full_link})
    return product_list


def get_all_pagination_links(soup, base_url):
    pagination_links = []
    pagination_ul = soup.find("ul", class_="pagination")
    if pagination_ul:
        for li in pagination_ul.find_all("li"):
            a_tag = li.find("a")
            if a_tag and "href" in a_tag.attrs:
                link = a_tag["href"].strip()
                if link:
                    full_link = urljoin(base_url, link)
                    if full_link not in pagination_links:
                        pagination_links.append(full_link)
    return pagination_links


def crawl_all_pages(base_url):
    response = session.get(base_url)
    soup = BeautifulSoup(response.content, "html.parser")

    pagination_links = get_all_pagination_links(soup, base_url)
    if not pagination_links:
        pagination_links = [base_url]

    all_products = []
    for page_url in pagination_links:
        print(f"در حال کرول: {page_url}")
        try:
            response = session.get(page_url)
            if response.status_code != 200:
                print(f"خطا در دریافت صفحه: {response.status_code}")
                update_code_execution_state('Darsoo-tablet', False, f"خطا در دریافت صفحه: {response.status_code}")
                continue
            page_soup = BeautifulSoup(response.content, "html.parser")
            products = get_products_from_page(page_soup, page_url)
            all_products.extend(products)
            time.sleep(1)  # تأخیر ثابت
        except Exception as e:
            update_code_execution_state('Darsoo-tablet', False, f"خطا در کرول صفحه {page_url}: {e}")
            print(f"خطا در کرول صفحه {page_url}: {e}")
    return all_products


def get_full_product_title(soup):
    div = soup.find("div", class_="defaulta mb-3")
    if div:
        h1 = div.find("h1")
        if h1:
            return h1.text.strip()
    return "نامشخص"


def get_product_colors(product_url):
    try:
        response = session.get(product_url)
        if response.status_code != 200:
            print(f"خطا در دریافت اطلاعات رنگ‌ها برای {product_url}: {response.status_code}")
            
            update_code_execution_state('Darsoo-tablet', False, f"خطا در دریافت اطلاعات رنگ‌ها برای {product_url}: {response.status_code}")
            return []
        soup = BeautifulSoup(response.content, "html.parser")

        guarantee_meta = soup.find("meta", attrs={"name": "guarantee"})
        meta_guarantee = guarantee_meta["content"].strip() if guarantee_meta else None

        color_container = soup.find("div", id="showAttrBaseG1")
        warranty_container = soup.find("div", id="showAttrBaseG2")

        color_list = []

        if color_container:
            color_divs = color_container.find_all("div", class_="d-flex ml-1 py-1 px-2")
            for idx, color_div in enumerate(color_divs, 1):
                color_id_input = color_div.find("input", id=lambda x: x and x.startswith("cid_id_"))
                color_id = color_id_input["value"] if color_id_input else "نامشخص"

                color_code_div = color_div.find("div", id=lambda x: x and x.startswith("colorCode_"))
                style = color_code_div["style"] if color_code_div else ""
                color_code = "نامشخص"
                if "background-color:" in style:
                    color_code = style.split("background-color:")[1].split(";")[0].strip()

                color_name_div = color_div.find("div", id=lambda x: x and x.startswith("colorSelectName_"))
                color_name = color_name_div.text.strip() if color_name_div else "نامشخص"

                price_input = soup.find("input", id=f"attrprice_{idx}")
                price = price_input["value"] if price_input else "نامشخص"

                warranty_text = "نامشخص"
                if warranty_container:
                    attr_box = warranty_container.find("div", id=f"attrBaseBox_{idx}")
                    if attr_box and "display: none" not in attr_box.get("style", ""):
                        label = attr_box.find("label")
                        if label:
                            warranty_text = label.get_text(separator=" ", strip=True)
                            warranty_text = re.sub(r'\s+', ' ', warranty_text)

                if meta_guarantee:
                    warranty_text = meta_guarantee

                color_list.append({
                    "color_id": color_id,
                    "color_code": color_code,
                    "color_name": color_name,
                    "price": (int(price)*10),
                    "warranty": warranty_text
                })

        else:
            price_tag = soup.find("span", class_="price")
            price = price_tag.text.strip() if price_tag else "نامشخص"
            warranty_text = "نامشخص"
            if meta_guarantee:
                warranty_text = meta_guarantee
            color_list.append({
                "color_id": "نامشخص",
                "color_code": "نامشخص",
                "color_name": "پیش‌فرض",
                "price": (int(price)*10),
                "warranty": warranty_text
            })

        return color_list
    except Exception as e:
        print(f"خطا در دریافت رنگ‌ها از {product_url}: {e}")
        update_code_execution_state('Darsoo-tablet', False, f"خطا در دریافت رنگ‌ها از {product_url}: {e}")

        return []


def get_brand_name_english(product_url):
    try:
        response = session.get(product_url)
        if response.status_code != 200:
            print(f"خطا در دریافت برند برای {product_url}: {response.status_code}")
            
            return "نامشخص"
        soup = BeautifulSoup(response.content, "html.parser")

        brand_name = "نامشخص"
        div = soup.find("div", class_="product-directory default")
        if div:
            ul = div.find("ul", class_="mr-1")
            if ul:
                for li in ul.find_all("li"):
                    span = li.find("span")
                    if span and "برند" in span.text:
                        a_tag = li.find("a")
                        if a_tag:
                            text = a_tag.text.strip()
                            if " - " in text:
                                brand_name = text.split(" - ")[1].strip()
                            else:
                                brand_name = text
                        break
        return brand_name
    except Exception as e:
        print(f"خطا در دریافت برند از {product_url}: {e}")
        return "نامشخص"


def normalize_gb(text):
    # فقط عدد رو جدا کن و دوباره با "GB" ترکیب کن
    match = re.search(r'(\d+)', text)
    if match:
        return f"{match.group(1)}GB"
    return text



def parse_title_info(title, brand_english):
    full_title = title.strip()

    # تشخیص مدل
    if brand_english == "نامشخص":
        model = "نامشخص"
    else:
        pattern = re.compile(rf"({re.escape(brand_english)}.*?)(?:با حافظه|رم|$)", re.IGNORECASE)
        match = pattern.search(full_title)
        if match:
            model = match.group(1).strip()
        else:
            model = full_title

    # تشخیص حافظه
    memory_match = re.search(r'(\d+\s*(?:گیگابایت|گیگ|GB|G))\s*(?:حافظه|ذخیره‌سازی|Storage)?', full_title, re.IGNORECASE)
    memory = normalize_gb(memory_match.group(1)) if memory_match else "نامشخص"

    # تشخیص رم
    ram_match = re.search(
        r'(?:رم\s*(\d+\s*(?:گیگابایت|گیگ|GB|G))|(\d+\s*(?:گیگابایت|گیگ|GB|G))\s*رم|(\d+\s*GB)\s*RAM)',
        full_title, re.IGNORECASE)
    if ram_match:
        ram_raw = next(group for group in ram_match.groups() if group is not None)
        ram = normalize_gb(ram_raw)
    else:
        ram = "نامشخص"

    # تشخیص نات اکتیو
    is_not_active = "نات اکتیو" in full_title.lower() or "not active" in full_title.lower()

    return {
        "full_title": full_title,
        "model": model,
        "memory": memory,
        "ram": ram,
        "is_not_active": is_not_active
    }







def get_product_details(product_url):
    try:
        response = session.get(product_url)
        if response.status_code != 200:
            print(f"خطا در دریافت اطلاعات محصول {product_url}: {response.status_code}")
            update_code_execution_state('Darsoo-tablet', False, f"خطا در دریافت اطلاعات محصول {product_url}: {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, "html.parser")

        full_title = get_full_product_title(soup)
        colors = get_product_colors(product_url)

        return {
            "full_title": full_title,
            "colors": colors,
            "soup": soup,
        }
    except Exception as e:
        print(f"خطا در دریافت جزئیات محصول {product_url}: {e}")
        
        update_code_execution_state('Darsoo-tablet', False, f"خطا در دریافت جزئیات محصول {product_url}: {e}")
        return None


def clean_model(text):
    # حذف بخش‌هایی مثل ظرفیت 512 گیگابایت، رم 8 گیگابایت و کلمات اضافی
    patterns_to_remove = [
        r'ظرفیت\s*\d+\s*(?:گیگابایت|گیگ|GB|G)',  # حذف ظرفیت با مقدار و واحد
        r'رم\s*\d+\s*(?:گیگابایت|گیگ|GB|G)',      # حذف رم با مقدار و واحد
        r'\d+\s*(?:گیگابایت|گیگ|GB|G)\s*رم',      # حذف رم با مقدار و واحد به شکل معکوس
        r'(?:حافظه|ذخیره‌سازی|Storage)',             # حذف کلمات حافظه و ذخیره سازی
        r'(\d+\s*GB)',                              # حذف هر عدد + GB
    ]

    cleaned_text = text
    for pattern in patterns_to_remove:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)

    # حذف فاصله‌های اضافی
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    return cleaned_text


@shared_task(bind=True, max_retries=1)
def tablet_darsoo_crawler(self):
    try:
        
        all_tablet_objects = []


        for url in urls:
            print(f"🟡 شروع کرول همه صفحات: {url}")
            products = crawl_all_pages(url)

            all_items = []

            for p in products:
                tablet_object: dict = {}
                product_url = p["link"]
                details = get_product_details(product_url)
                if not details:
                    continue

                full_title = details["full_title"]
                colors = details["colors"]

                brand_name_en = get_brand_name_english(product_url)

                title_info = parse_title_info(full_title, brand_name_en)

                for color_info in colors:
                    
                    tablet_object["model"] = clean_model(full_title)
                    tablet_object["memory"] = title_info["memory"]
                    tablet_object["ram"] = title_info["ram"]
                    tablet_object["brand"] = brand_name_en
                    tablet_object["title"] = full_title
                    tablet_object["url"] = product_url
                    tablet_object["site"] = 'Darsoo'
                    tablet_object["seller"] = 'Darsoo'
                    tablet_object["guarantee"] = color_info.get("warranty", "نامشخص")
                    tablet_object["max_price"] = 1
                    tablet_object["mobile_digi_id"] = ""
                    tablet_object["dual_sim"] = True
                    tablet_object["active"] = True
                    tablet_object["mobile"] = False
                    tablet_object["vietnam"] = False                    
                    tablet_object["not_active"] = title_info["is_not_active"]
                    tablet_object["color_name"] = color_info["color_name"]
                    tablet_object["color_hex"] = color_info["color_code"]
                    tablet_object["min_price"] = color_info["price"]
                    
                    
                    all_tablet_objects.append(tablet_object.copy())
                    

        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = 'Darsoo',
            status = True,
            mobile = False,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        
        
        for tablet_dict in all_tablet_objects:
            save_obj(tablet_dict)

        update_code_execution_state('Darsoo-tablet', True)

    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state('Darsoo-tablet', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)
