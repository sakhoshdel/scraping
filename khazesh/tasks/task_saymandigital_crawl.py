import requests
from bs4 import BeautifulSoup
from unidecode import unidecode
import re
from urllib.parse import unquote
from celery import shared_task
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback
import uuid
from khazesh.models import Mobile
from django.utils import timezone
import collections


HEADERS = {'From': 'behnammohammadi149@gmail.com'}


# ----------------------------- گرفتن لیست موبایل‌ها -----------------------------
def get_mobile_info(headers, url):
    try:
        res = requests.get(url=url, headers=headers, timeout=20)
        res.raise_for_status()
        content = BeautifulSoup(res.text, 'html.parser')
        mobiles_box = content.find('div', {'id': "type-card-products"})
        if not mobiles_box:
            raise Exception("div with id='type-card-products' not found")

        mobiles = mobiles_box.select('div.col-6.col-lg-4.col-xl-4.col-xxl-3')
        mobile_urls = []

        for mobile in mobiles:
            try:
                mobile_price = mobile.find('div', class_="product-price").find('span', class_='total-price').get_text()
                if 'نا‌موجود' in mobile_price:
                    break
                mobile_url = mobile.find('a')['href']
                mobile_urls.append((mobile_url, mobile_price.strip()))
            except Exception:
                print("⚠️ Error parsing one product in get_mobile_info")
                continue

        return mobile_urls

    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state('Saymandigital', False, error_message)
        print(f"Error {error_message}")
        print('Error in get_mobile_info()')
        return []


# ----------------------------- گرفتن صفحات محصولات -----------------------------
def main():
    phone_model_list = ['اپل', 'سامسونگ', 'شیائومی', 'هواوی', 'نوکیا', 'honor', 'realme', 'گوشی-ناتینگ-فون', 'motorola']
    mobile_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):
            url = f'https://saymandigital.com/محصولات/{phone_model}/?page={i + 1}'
            urls = get_mobile_info(HEADERS, url)
            mobile_all_urls.extend(urls)
    print(f"Collected {len(mobile_all_urls)} URLs.")
    return mobile_all_urls


# ----------------------------- استخراج رنگ و مشخصات -----------------------------
def extract_color_hex(colorName_coloerhex_gaurantee):
    try:
        color_hex_div = colorName_coloerhex_gaurantee.find('div', {'class': ['color-range', 'd-inline-block']})
        span = color_hex_div.find('span') if color_hex_div else None
        if not span or 'style' not in span.attrs:
            return None
        color_hex = span['style'].split(':')[-1].strip().rstrip(';')
        return color_hex
    except Exception:
        return None


def extract_color_name(colorName_coloerhex_gaurantee):
    try:
        color_name_span = colorName_coloerhex_gaurantee.find('span', {'class': ['d-inline-block', 'text', 'xml-2']})
        return color_name_span.get_text().strip() if color_name_span else 'نامشخص'
    except Exception:
        return 'نامشخص'


def extract_guarantee(colorName_coloerhex_gaurantee):
    try:
        gaurantee_div = colorName_coloerhex_gaurantee.find('div', class_='supply')
        if not gaurantee_div:
            return 'نامشخص'
        gaurantee_span = gaurantee_div.find('span', class_='supply-text')
        return gaurantee_span.get_text().strip() if gaurantee_span else 'نامشخص'
    except Exception:
        return 'نامشخص'


def extract_price(seller_box_responsive):
    try:
        price_div = seller_box_responsive.find('div', class_='total-price')
        price_span = price_div.find('span') if price_div else None
        if not price_span:
            return 0
        price = price_span.get_text().split(' ')[0].replace(',', '')
        return int(unidecode(price)) * 10
    except Exception:
        return 0


def extract_name_seller(seller_box_responsive):
    try:
        seller_name_div = seller_box_responsive.find('div', class_='name-seller')
        seller_name_span = seller_name_div.find('span', class_='name') if seller_name_div else None
        return seller_name_span.get_text().strip() if seller_name_span else 'نامشخص'
    except Exception:
        return 'نامشخص'


def extract_model_form_title_en(title_en):
    title_en_list = title_en.split(' ')
    model = ''
    for word in title_en_list[1:]:
        if 'GB' in word or word in ['Dual', 'Single', 'DualSIM']:
            break
        model += word + ' '
        if word == 'Mini':
            break
    return model.strip()


# ----------------------------- حافظه و رم -----------------------------
def extract_ram_and_memory(soup, title_en):
    try:
        memory_ram = ''
        for i, word in enumerate(title_en):
            if word in ["SIM", 'Sim', 'sim']:
                memory_ram = title_en[i + 1] if i + 1 < len(title_en) else ''
        memory, ram = None, None
        if '/' in memory_ram:
            memory, ram = memory_ram.split('/')
            if not any(x in memory for x in ['GB', 'TB', 'MB']):
                memory += ram[-2:]
        if memory and ram:
            return memory, ram
    except Exception:
        pass

    # Try to extract from specs
    try:
        memory_ram_dive = soup.find('div', {'id': 'panels-stay-open-collapse-22'})
        if not memory_ram_dive:
            return 'نامشخص', 'نامشخص'
        memory_ram_ul = memory_ram_dive.find('ul', class_='list-unstyled')
        memory_ram_lis = memory_ram_ul.find_all('li') if memory_ram_ul else []
        memory, ram = 'نامشخص', 'نامشخص'
        for li in memory_ram_lis:
            key_text = li.find('div', class_='key-info').get_text().strip()
            value_text = li.find('div', class_='value-info').get_text().strip()
            if 'حافظه' in key_text:
                memory = value_text
            elif 'رم' in key_text:
                ram = value_text
        return memory, ram
    except Exception:
        return 'نامشخص', 'نامشخص'


# ----------------------------- ساخت مدل هر محصول -----------------------------
def create_mobiel_list_object_for_url(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'lxml')
        content_sellers_boxe = soup.find('div', class_="content-sellers-responsive")
        if not content_sellers_boxe:
            raise Exception("content-sellers-responsive div not found")

        boxes = content_sellers_boxe.find_all('div', class_='seller-box-responsive')
        en_title_tag = soup.find('h2', class_='title-small')
        title_fa_tag = soup.find('h1', class_='title-big')
        title_fa = title_fa_tag.get_text().strip() if title_fa_tag else 'بدون عنوان'
        title_en = en_title_tag.get_text().strip() if en_title_tag else 'unknown'
        print(f"Processing: {title_fa}")

        memory, ram = extract_ram_and_memory(soup, title_en.split(' '))
        site = 'Saymandigital'
        brand = title_en.split(' ')[0]
        model = extract_model_form_title_en(title_en)

        mobile_obj = {
            'mobile_digi_id': 1,
            'title': title_fa,
            'brand': brand,
            'model': model,
            'ram': ram,
            'memory': memory,
            'active': True,
            'mobile': True,
            'site': site,
            'dual_sim': True,
            'url': url,
            'max_price': 1,
        }

        seller_mobiles_list = []
        for seller in boxes:
            try:
                color_box = seller.find('div', {'class': ['d-flex', 'flex-wrap', 'xmt-4']})
                if not color_box:
                    continue
                guarantee = extract_guarantee(color_box)
                seller_box_obj = {
                    'color_hex': extract_color_hex(color_box),
                    'color_name': extract_color_name(color_box),
                    'guarantee': guarantee,
                    'vietnam': 'ساخت ویتنام' in guarantee,
                    'not_active': 'نات اکتیو' in guarantee,
                    'min_price': extract_price(seller),
                    'seller': extract_name_seller(seller),
                }
                seller_mobiles_list.append({**mobile_obj, **seller_box_obj})
            except Exception:
                continue

        return seller_mobiles_list
    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state('Saymandigital', False, error_message)
        print(f"Error {error_message}")
        print('Error in create_mobiel_list_object_for_url()')
        return []


def extract_min_price_of_same_color_objecs(seller_mobiles_list_func, url):
    seller_mobiles_list = seller_mobiles_list_func(url)
    if not seller_mobiles_list:
        return []

    values = [(obj['color_name'], obj['vietnam']) for obj in seller_mobiles_list]
    dupplicate_mobiles_color = [item for item, count in collections.Counter(values).items() if count > 1]

    list_of_same_color_obj_list = []
    for color, vietnam in dupplicate_mobiles_color:
        dupplicate_mobiles_obj = list(filter(lambda x: (x['color_name'] == color and x['vietnam'] == vietnam), seller_mobiles_list))
        list_of_same_color_obj_list.append(dupplicate_mobiles_obj)

    seller_mobiles_list = [obj for obj in seller_mobiles_list if obj not in sum(list_of_same_color_obj_list, [])]
    min_price_objects = [min(obj_list, key=lambda x: x['min_price']) for obj_list in list_of_same_color_obj_list]
    seller_mobiles_list.extend(min_price_objects)
    return seller_mobiles_list


# ----------------------------- تسک اصلی -----------------------------
@shared_task(bind=True, max_retries=1)
def saymandigital_crawler(self):
    try:
        batch_id = f"Saymandigital-{uuid.uuid4().hex[:12]}"
        all_mobile_urls = main()
        all_saymandigital_mobile_obj = []

        for url, _ in all_mobile_urls:
            try:
                url = unquote(url)
                result = extract_min_price_of_same_color_objecs(create_mobiel_list_object_for_url, url)
                all_saymandigital_mobile_obj.extend(result)
            except Exception:
                err = traceback.format_exc()
                update_code_execution_state('Saymandigital', False, f"Error in product {url}: {err}")
                continue

        for mobile_dict in all_saymandigital_mobile_obj:
            save_obj(mobile_dict, batch_id=batch_id)

        Mobile.objects.filter(site="Saymandigital", mobile=True).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(
            'Saymandigital',
            bool(all_saymandigital_mobile_obj),
            'هیچ محصولی پیدا نشد.' if not all_saymandigital_mobile_obj else ''
        )

    except Exception:
        error_message = traceback.format_exc()
        update_code_execution_state('Saymandigital', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=Exception(error_message), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(
            site='Saymandigital',
            status=True,
            mobile=True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
