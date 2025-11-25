# /home/bartardigi/scraping/khazesh/tasks/task_tablet_darsoo_crawl.py

import json
import re
import traceback
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
from requests.exceptions import ConnectionError, RequestException, Timeout
import time
from typing import List, Optional
import uuid
from khazesh.models import Mobile
from django.utils import timezone
from urllib.parse import urljoin, unquote
from html import unescape

# ------------------ Config ------------------
urls = [
    "https://darsoo.com/categories/%D8%AA%D8%A8%D9%84%D8%AA/%D8%AA%D8%A8%D9%84%D8%AA-%D8%B4%DB%8C%D8%A7%D8%A6%D9%88%D9%85%DB%8C/",
    "https://darsoo.com/categories/%D8%AA%D8%A8%D9%84%D8%AA/%D8%AA%D8%A8%D9%84%D8%AA-%D8%B3%D8%A7%D9%85%D8%B3%D9%88%D9%86%DA%AF/",
    "https://darsoo.com/categories/%D8%AA%D8%A8%D9%84%D8%AA/%D8%AA%D8%A8%D9%84%D8%AA-%D8%A7%D9%BE%D9%84/"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

session = requests.Session()
session.headers.update(HEADERS)

SITE = 'Darsoo'
SELLER = 'Darsoo'


# ------------------ Safe request helper ------------------
def safe_get(url: str, retries: int = 2, delay: int = 1):
    """Safe HTTP GET with retries and error reporting"""
    for i in range(retries):
        try:
            response = session.get(url, timeout=20)
            response.raise_for_status()
            return response
        except (ConnectionError, Timeout) as ce:
            err = f"Connection error ({i+1}/{retries}): {ce}"
            print(f"⚠️ {url} - {err}")
            update_code_execution_state(f'{SITE}-tablet', False, err)
            time.sleep(delay)
        except RequestException as re:
            err = f"Request error: {re}"
            print(f"⚠️ {url} - {err}")
            update_code_execution_state(f'{SITE}-tablet', False, err)
            return None
        except Exception:
            err = traceback.format_exc()
            print(f"⚠️ {url} - {err}")
            update_code_execution_state(f'{SITE}-tablet', False, err)
            return None
    return None


# ------------------ Extract product info ------------------
def get_products_from_page(soup, base_url):
    """
    ساختار جدید لیست محصول‌ها روی دارسو:
      <div class="childprocatbox">
        <a class="product-card-2" href="PRODUCT_URL"> ... <h3>TITLE</h3> ... <span class="woocommerce-Price-amount"><bdi>PRICE تومان</bdi></span> ... </a>
    """
    product_cards = soup.select("div.childprocatbox a.product-card-2")
    product_list = []

    for card in product_cards:
        try:
            link = card.get("href")
            h3 = card.find("h3")
            title_text = h3.get_text(strip=True) if h3 else None

            # قیمت ممکنه "ناموجود" باشه
            price_bdi = card.select_one(".woocommerce-Price-amount bdi")
            if price_bdi:
                raw_price = price_bdi.get_text(strip=True)
                # تبدیل 23.386.000 → 23386000
                price_num = re.sub(r"[^\d]", "", raw_price)
            else:
                # اگر ناموجود بود، price رو None می‌گذاریم تا فیلتر فعلی حفظ شود
                unavailable = card.select_one(".pcb-price span[style*='#df2d2d']")
                price_num = None if unavailable else None

            if title_text and link and price_num:
                full_link = urljoin(base_url, link)
                product_list.append({
                    "title": title_text,
                    "price": price_num,  # (با سیاست فعلی، بعداً  *10 برای ریال)
                    "link": full_link
                })
        except Exception:
            continue

    print(f"📦 تعداد محصولات یافت‌شده در {base_url}: {len(product_list)}")
    return product_list


def get_all_pagination_links(soup, base_url):
    """
    اگر صفحه‌بندی وکامرس باشد معمولاً ul.page-numbers وجود دارد.
    در غیر این صورت فقط همان base_url برگردانده می‌شود.
    """
    pagination_links = []
    try:
        # تلاش 1: وکامرس
        for a in soup.select("ul.page-numbers li a"):
            href = a.get("href", "").strip()
            if href:
                full_link = urljoin(base_url, href)
                if full_link not in pagination_links:
                    pagination_links.append(full_link)

        # تلاش 2: هر نوع pagination دیگر
        if not pagination_links:
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
    except Exception:
        pass

    return pagination_links or [base_url]


def crawl_all_pages(base_url):
    response = safe_get(base_url)
    if not response:
        return []

    soup = BeautifulSoup(response.content, "html.parser")
    pagination_links = get_all_pagination_links(soup, base_url)
    all_products = []

    for page_url in pagination_links:
        print(f"📄 در حال کرول: {page_url}")
        response = safe_get(page_url)
        if not response:
            continue
        try:
            page_soup = BeautifulSoup(response.content, "html.parser")
            products = get_products_from_page(page_soup, page_url)
            all_products.extend(products)
            time.sleep(0.4)
        except Exception:
            update_code_execution_state(f'{SITE}-tablet', False, traceback.format_exc())
    return all_products


# ------------------ Product detail extraction ------------------
def get_full_product_title(soup):
    # ساختار جدید: h1.product-title
    try:
        h1 = soup.find("h1", class_="product-title")
        if h1:
            return h1.get_text(strip=True)
    except Exception:
        pass
    return "نامشخص"


def _extract_color_hex_map(soup):
    """
    تلاش برای یافتن رنگ‌ها و کد رنگ از UL گزینه‌های رنگ در صفحه محصول.
    اگر پیدا نشد، خالی برمی‌گردد.
    """
    color_hex_map = {}
    try:
        for li in soup.select("ul.color-variable-items-wrapper li.variable-item"):
            val = li.get("data-value", "").strip()  # ممکنه urlencoded یا انگلیسی مثل 'blue' باشه
            style_span = li.select_one(".variable-item-span-color")
            hex_code = None
            if style_span and style_span.has_attr("style"):
                m = re.search(r'background-color:\s*([^;]+)', style_span["style"])
                if m:
                    hex_code = m.group(1).strip()
            if val:
                color_hex_map[val] = hex_code or "نامشخص"
    except Exception:
        pass
    return color_hex_map


def get_product_colors(product_url):
    """
    ساختار جدید: فرم variations_form دارای data-product_variations است (JSON).
    از آن، قیمت، موجودی، رنگ (attribute_pa_color) و گارانتی (attribute_pa_guarantee) را می‌خوانیم.
    """
    try:
        response = safe_get(product_url)
        if not response:
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        form = soup.select_one("form.variations_form.cart")
        if not form:
            # fallback قدیمی
            price_tag = soup.find("span", class_="price")
            price = re.sub(r'\D', '', price_tag.text) if price_tag else "0"
            return [{
                "color_id": "نامشخص",
                "color_code": "نامشخص",
                "color_name": "پیش‌فرض",
                "price": int(price) * 10 if price else 0,
                "warranty": "نامشخص"
            }]

        raw = form.get("data-product_variations", "")
        if not raw:
            return []

        # data-product_variations داخل HTML escape شده ( &quot; )
        variations = json.loads(unescape(raw))

        # رنگ → کدرنگ از UL اگر موجود باشد
        color_hex_map = _extract_color_hex_map(soup)

        color_list = []
        for idx, var in enumerate(variations, 1):
            try:
                attrs = var.get("attributes", {})
                color_raw = attrs.get("attribute_pa_color", "")  # ممکنه urlencoded باشد
                guarantee_raw = attrs.get("attribute_pa_guarantee", "")

                color_name = unquote(color_raw) if color_raw else "نامشخص"
                guarantee = unquote(guarantee_raw) if guarantee_raw else "نامشخص"

                # قیمت تومانی در display_price؛ سیاست قبلی: *10 برای ریالی
                display_price = var.get("display_price")
                price_rial = int(display_price) * 10 if isinstance(display_price, (int, float)) else 0

                # کد رنگ از map (کلید map همان data-value در UL است؛ ممکن است urlencoded باشد)
                color_hex = None
                if color_raw in color_hex_map:
                    color_hex = color_hex_map[color_raw]
                elif color_name in color_hex_map:
                    color_hex = color_hex_map[color_name]
                else:
                    color_hex = "نامشخص"

                # وضعیت موجودی (اختیاری)
                in_stock = var.get("is_in_stock", False)

                color_list.append({
                    "color_id": str(var.get("variation_id") or idx),
                    "color_code": color_hex or "نامشخص",
                    "color_name": color_name or "نامشخص",
                    "price": price_rial,
                    "warranty": guarantee or "نامشخص",
                    "in_stock": bool(in_stock),
                })
            except Exception:
                continue

        return color_list

    except Exception:
        update_code_execution_state(f'{SITE}-tablet', False, traceback.format_exc())
        return []


def get_brand_name_english(product_url):
    """
    قبلاً از breadcrumb می‌خواند. اگر پیدا نشد، از عنوان لاتین داخل عنوان محصول استخراج می‌کنیم.
    """
    try:
        response = safe_get(product_url)
        if not response:
            return "نامشخص"
        soup = BeautifulSoup(response.content, "html.parser")

        # تلاش 1: ساختار قبلی
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
                                return text.split(" - ")[1].strip()
                            return text

        # تلاش 2: از عنوان
        title = get_full_product_title(soup)
        # چند برند رایج برای fallback
        brands = ["Xiaomi", "Samsung", "Apple", "Lenovo", "Huawei", "Honor", "Nokia", "Realme", "Oppo", "OnePlus"]
        for b in brands:
            if re.search(rf"\b{re.escape(b)}\b", title, flags=re.IGNORECASE):
                return b

        return "نامشخص"
    except Exception:
        return "نامشخص"


def normalize_gb(text):
    match = re.search(r'(\d+)', text)
    return f"{match.group(1)}GB" if match else text


def parse_title_info(title, brand_english):
    full_title = title.strip()
    try:
        if brand_english == "نامشخص":
            model = "نامشخص"
        else:
            pattern = re.compile(rf"({re.escape(brand_english)}.*?)(?:با حافظه|رم|$)", re.IGNORECASE)
            match = pattern.search(full_title)
            model = match.group(1).strip() if match else full_title

        memory_match = re.search(r'(\d+\s*(?:گیگابایت|گیگ|GB|G))', full_title)
        memory = normalize_gb(memory_match.group(1)) if memory_match else "نامشخص"

        ram_match = re.search(r'(\d+\s*(?:گیگابایت|GB|G))\s*(?:RAM|رم)?', full_title, re.IGNORECASE)
        ram = normalize_gb(ram_match.group(1)) if ram_match else "نامشخص"

        is_not_active = any(x in full_title.lower() for x in ["not active", "نات اکتیو"])

        return {"full_title": full_title, "model": model, "memory": memory, "ram": ram, "is_not_active": is_not_active}
    except Exception:
        return {"full_title": full_title, "model": full_title, "memory": "نامشخص", "ram": "نامشخص", "is_not_active": False}


def clean_model(text):
    patterns = [
        r'ظرفیت\s*\d+\s*(?:گیگابایت|گیگ|GB|G)',
        r'رم\s*\d+\s*(?:گیگابایت|گیگ|GB|G)',
        r'\d+\s*GB',
        r'(?:حافظه|ذخیره‌سازی|Storage)',
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', text).strip()


# ------------------ NEW: get_product_details (طبق ساختار فعلی)
def get_product_details(product_url):
    try:
        response = session.get(product_url)
        if response.status_code != 200:
            print(f"خطا در دریافت اطلاعات محصول {product_url}: {response.status_code}")
            update_code_execution_state('Darsoo-tablet', False, f"خطا در دریافت اطلاعات محصول {product_url}: {response.status_code}")
            return None

        soup = BeautifulSoup(response.content, "html.parser")
        full_title = get_full_product_title(soup)
        colors = get_product_colors(product_url)  # از JSON variations می‌خواند

        # ===== فقط برای تست: چاپ خروجی =====
        print(f"\n🧾 عنوان: {full_title}")
        for c in colors:
            print(f"   • رنگ: {c.get('color_name')}  | کدرنگ: {c.get('color_code')} | قیمت (ریال): {c.get('price')} | گارانتی: {c.get('warranty')} | موجودی: {c.get('in_stock')}")

        return {
            "full_title": full_title,
            "colors": colors,
            "soup": soup,
        }
    except Exception as e:
        print(f"خطا در دریافت جزئیات محصول {product_url}: {e}")
        update_code_execution_state('Darsoo-tablet', False, f"خطا در دریافت جزئیات محصول {product_url}: {e}")
        return None


# ------------------ Main Task ------------------
@shared_task(bind=True, max_retries=1)
def tablet_darsoo_crawler(self):
    try:
        batch_id = f"Darsoo-{uuid.uuid4().hex[:12]}"
        all_tablet_objects = []
        total_found = 0

        for url in urls:
            print(f"🟡 شروع کرول دسته: {url}")
            products = crawl_all_pages(url)

            for p in products:
                try:
                    product_url = p["link"]
                    details = get_product_details(product_url)
                    if not details:
                        continue

                    full_title = details["full_title"]
                    colors = details["colors"]
                    brand_name_en = get_brand_name_english(product_url)
                    title_info = parse_title_info(full_title, brand_name_en)

                    # فقط چاپ برای تست
                    print(f"🔗 {product_url}")
                    print(f"📌 مدل پاکسازی‌شده: {clean_model(full_title)} | برند: {brand_name_en} | حافظه: {title_info['memory']} | رم: {title_info['ram']}")

                    for color_info in colors:
                        # ساخت آبجکت مطابق ساختار فعلی (ذخیره هنوز فعاله)
                        tablet_object = {
                            "model": clean_model(full_title),
                            "memory": title_info["memory"],
                            "ram": title_info["ram"],
                            "brand": brand_name_en,
                            "title": full_title,
                            "url": product_url,
                            "site": SITE,
                            "seller": SELLER,
                            "guarantee": color_info.get("warranty", "نامشخص"),
                            "max_price": 1,
                            "mobile_digi_id": "",
                            "dual_sim": True,
                            "active": True,
                            "mobile": False,
                            "vietnam": False,
                            "not_active": title_info["is_not_active"],
                            "color_name": color_info.get("color_name"),
                            "color_hex": color_info.get("color_code"),
                            "min_price": color_info.get("price", 0),
                        }

                        all_tablet_objects.append(tablet_object)
                        total_found += 1

                except Exception:
                    update_code_execution_state(f'{SITE}-tablet', False, traceback.format_exc())
                    continue

        # ===== فقط چاپ جمع‌بندی تست =====
        print(f"\n✅ تعداد رکوردهای جمع‌آوری‌شده: {total_found}")

        # ذخیره مثل قبل (اگه نمی‌خوای الان ذخیره کنه، این دو بلاک رو کامنت کن)
        for tablet_dict in all_tablet_objects:
            save_obj(tablet_dict, batch_id=batch_id)

        Mobile.objects.filter(site=SITE, mobile=False).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(f'{SITE}-tablet', bool(all_tablet_objects), 'هیچ محصولی پیدا نشد.' if not all_tablet_objects else '')

    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state(f'{SITE}-tablet', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)
    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site=SITE, status=True, mobile=False, updated_at__lt=ten_min_ago).update(status=False)
