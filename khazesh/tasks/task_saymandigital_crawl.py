
import requests 
from bs4 import BeautifulSoup
from unidecode import unidecode
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote

from celery import shared_task
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback

from khazesh.models import Mobile
from django.utils import timezone


HEADERS = {
    'From': 'behnammohammadi149@gmail.com', }

def get_mobile_info(headers,url):
    try:
        res = requests.get(url=url, headers=headers).text
        content = BeautifulSoup(res, 'html.parser')
        mobiles_box = content.find('div', {'id': "type-card-products"})
        mobiles = mobiles_box.select('div.col-6.col-lg-4.col-xl-4.col-xxl-3')
        mobile_urls = []

        for mobile in mobiles:

            mobile_price = mobile.find(
                'div', class_="product-price").find('span', class_='total-price').get_text()

            if 'نا‌موجود' in mobile_price:
                break

            mobile_url = mobile.find('a')['href']
            mobile_urls.append((mobile_url, mobile_price.strip()))

        return mobile_urls
    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state('Saymandigital', False, error_message)
        print(f"Error {error_message}")
        print('Error come from get_mobile_info (function)')
        return []


def main():
    phone_model_list = ['اپل', 'سامسونگ', 'شیائومی', 'هواوی', 'نوکیا', 'honor', 'realme', 'گوشی-ناتینگ-فون', 'motorola']

    mobile_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):

            url = f'https://saymandigital.com/محصولات/{phone_model}/?page={i + 1}'
            mobile_urls = get_mobile_info(HEADERS, url)

            mobile_all_urls.extend(mobile_urls)
    print(mobile_all_urls)
    print(len(mobile_all_urls))
    return mobile_all_urls



def extract_color_hex(colorName_coloerhex_gaurantee):
    color_hex_div = colorName_coloerhex_gaurantee.find(
        'div', {'class': ['color-range', 'd-inline-block']})
    color_hex = color_hex_div.find('span')['style']
    color_hex = color_hex.strip().split(':')
    color_hex = color_hex[1].strip(
    )[:-1] if 'background' in color_hex and len(color_hex) == 2 else None
    return color_hex


def extract_color_name(colorName_coloerhex_gaurantee):
    color_name_span = colorName_coloerhex_gaurantee.find(
        'span', {'class': ['d-inline-block', 'text', 'xml-2']})
    return color_name_span.get_text().strip()


def extract_guarantee(colorName_coloerhex_gaurantee):
    gaurantee_div = colorName_coloerhex_gaurantee.find('div', class_='supply')
    gaurantee_span = gaurantee_div.find('span', class_='supply-text')
    guarantee = gaurantee_span.get_text().strip()
    print(type(guarantee))
    return guarantee


def extract_price(seller_box_responsive):
    price_div = seller_box_responsive.find('div', class_='total-price')
    price_span = price_div.find('span')
    price = price_span.get_text().split(' ')[0].replace(',', '')
    return int(unidecode(price)) * 10


def extract_name_seller(seller_box_responsive):
    seller_name_div = seller_box_responsive.find('div', class_='name-seller')
    seller_name_span = seller_name_div.find('span', class_='name')
    return seller_name_span.get_text().strip()


def extract_model_form_title_en(title_en):
    title_en_list = title_en.split(' ')

    model = ''
    for word in title_en_list[1:]:
        if 'GB' in word:
            break
        if word in ['Dual', 'Single', 'DualSIM']:
            break
        model += word + ' '
        if word == 'Mini':
            break
    return model.strip()


def extract_ram_and_memory(soup, title_en):
    memory_ram = ''
    for i, word in enumerate(title_en):
        if word in ["SIM", 'Sim', 'sim']:
            try:
                memory_ram = title_en[i + 1]
            except Exception as e:
                memory_ram = None
                print(f"error from (extract_ram_and_memory) function == {e}")
    memory = None
    ram = None
    print(memory_ram)
    if memory_ram and ('TB' in memory_ram or 'GB' in memory_ram or 'MB' in memory_ram or "KB" in memory_ram):
        memory, ram = memory_ram.split('/')

        if 'TB' not in memory and 'GB' not in memory and 'MB' not in memory:
            memory = memory + ram[-2:]

    print('memory and ram', memory, ram)
    if memory and ram:
        return memory, ram

    memory_ram_dive = soup.find('div', {'id': 'panels-stay-open-collapse-22'})
    memory_ram_ul = memory_ram_dive.find('ul', class_='list-unstyled')
    memory_ram_lis = memory_ram_ul.find_all('li')
    memory = None
    ram = None
    for li in memory_ram_lis:
        key_div_text = li.find('div', class_='key-info').get_text().strip()
        value_div_text = li.find('div', class_='value-info').get_text().strip()
        if key_div_text == 'حافظه داخلی':
            memory = value_div_text.split(' ')
            if len(memory) == 1:
                pattern = r'\d+|\D+'
                memory = re.findall(pattern, memory[0])

        if key_div_text in ['مقدار RAM', 'رم']:
            ram = value_div_text.split(' ')
            if len(ram) == 1:
                pattern = r'\d+|\D+'
                ram = re.findall(pattern, ram[0])

    kilo_mega_giga_tra = {
        'کیلوبایت': 'KB',
  
        'مگابایت': 'MB',
        'گیگابایت': 'GB',
        'ترابایت': 'TB'
    }

    letter_to_digit_obj = {
        '1': '1',
        '۱': '1',
        'یک': '1',
        '2': '2',
        '۲': '2',
        'دو': '2',
        '3': '3',
        '۳': '3',
        'سه': '3',
        '4': '4',
        '۴': '4',
        'چهار': '4',
        '6': '6',
        '۶': '6',
        'شش': '6',
        '8': '8',
        '۸': '8',
        'هشت': '8',
        '12': '12',
        '۱۲': '12',
        '۱۶': '16',
        '32': '32',
        '۳۲': '32',
        '48': '48',
        '۶۴': '64',
        '128': '128',
        '۱۲۸': '128',
        '256': '256',
        '۲۵۶': '256',
        '512': '512',
        '۵۱۲': '512',
    }

    for key, value in kilo_mega_giga_tra.items():
        if ram and key == ram[1]:
            ram[1] = value
        elif ram and key == ram[0]:
             ram[0] = value
        if memory and key == memory[1]:
            memory[1] = value
        elif memory and key == memory[0]:
             memory[0] = value


    for key, value in letter_to_digit_obj.items():
        if ram and key == ram[0]:
            print('#' * 80)
            print(ram)
            print('#' * 80)
            ram[0] = value
            ram = ''.join(ram)
        elif ram and key == ram[1]:
            print('#' * 80)
            print(ram)
            print('#' * 80)
            ram[1] = value
            ram = ''.join(ram)

        if memory and key == memory[0]:
            print('#' * 80)
            print(memory)
            print('#' * 80)
            memory[0] = value
            memory = ''.join(memory)
        elif memory and key == memory[1]:
            print('#' * 80)
            print(memory)
            print('#' * 80)
            memory[1] = value
            memory = ''.join(memory)

        # if memory and key in memory:
        #     memory[0] = value
        #     memory = ''.join(memory)
    print(memory, ram)
    return memory, ram


def create_mobiel_list_object_for_url(url):
    try:
        res = requests.get(
            url, headers=HEADERS).text
        soup = BeautifulSoup(res, 'lxml')

        content_sellers_boxe = soup.find(
            'div', class_="content-sellers-responsive")
        boxes = content_sellers_boxe.find_all(
            'div', class_='seller-box-responsive')

        en_title = soup.find('h2', class_='title-small')
        title_fa = soup.find('h1', class_='title-big').get_text().strip()
        title_en = en_title.get_text().strip()
        print(title_fa)
        print(url)
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
            colorName_coloerhex_guarantee = seller.find(
                'div', {'class': ['d-flex', 'flex-wrap', 'xmt-4']})

            guarantee = extract_guarantee(colorName_coloerhex_guarantee)
            # print(type(guarantee))

            seller_box_obj = {
                'color_hex': extract_color_hex(colorName_coloerhex_guarantee),
                'color_name': extract_color_name(colorName_coloerhex_guarantee),
                'guarantee': guarantee,
                'vietnam': True if 'ساخت ویتنام' in guarantee else False,
                'not_active': True if 'نات اکتیو' in guarantee else False,
                'min_price': extract_price(seller),
                'seller': extract_name_seller(seller),
            }
            seller_mobiles_list.append(seller_box_obj)

        for obj in seller_mobiles_list:
            obj.update(mobile_obj)

        return seller_mobiles_list
    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state('Saymandigital', False, error_message)
        print(f"Error {error_message}")
        # print(f'error  {url} error: {e}')
        print('error come from (create_mobiel_list_object_for_url) function ')
        return []


def extract_min_price_of_same_color_objecs(seller_mobiles_list_func, url):
    seller_mobiles_list = seller_mobiles_list_func(url)

    # list of tuple of color and vietnam of mobile object
    values = [(obj['color_name'], obj['vietnam'])
              for obj in seller_mobiles_list]

    # list color of duplicated color and gaurantee
    import collections
    dupplicate_mobiles_color = [
        item for item, conunt in collections.Counter(values).items() if conunt > 1]

    # list of list duplicated mobile object
    # list_of_same_color_obj_list = [list(filter(
    #     lambda x: x['color_name'] == color, seller_mobiles_list)) for color in dupplicate_mobiles_color]
    list_of_same_color_obj_list = []
    for color, vietnam in dupplicate_mobiles_color:

        dupplicate_mobiles_obj = list(filter(lambda x: (
            x['color_name'] == color and x['vietnam'] == vietnam), seller_mobiles_list))
        list_of_same_color_obj_list.append(dupplicate_mobiles_obj)

        # print(dupplicate_mobiles_obj)

    # remove duplicated mobile objects from mobile list object
    seller_mobiles_list = [obj for obj in seller_mobiles_list if obj not in sum(
        list_of_same_color_obj_list, [])]

    # find min price of duplicated objects
    min_price_objects = [min(obj_list,  key=lambda x: x['min_price'])
                         for obj_list in list_of_same_color_obj_list]

    seller_mobiles_list.extend(min_price_objects)
    return seller_mobiles_list


@shared_task(bind=True, max_retries=0)
def saymandigital_crawler(self):
    try:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = 'Saymandigital',
            status = True,
            mobile = True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        
        
        all_mobile_urls = main()
        all_saymandigital_mobile_obj = []
        for url, _ in all_mobile_urls:
            url = unquote(url)
            print(url)
            last_list_mobil_obj = extract_min_price_of_same_color_objecs(
                create_mobiel_list_object_for_url, url)
            all_saymandigital_mobile_obj.extend(last_list_mobil_obj)
    
            
        
        
        
        for mobile_dict in all_saymandigital_mobile_obj:
            save_obj(mobile_dict)
            
        update_code_execution_state('Saymandigital', True)

    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state('Saymandigital', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)


# all_saymandigital_mobile_obj = []
# url = 'https://saymandigital.com/product/nokia-130-2017/'
# last_list_mobil_obj = extract_min_price_of_same_color_objecs(
#     create_mobiel_list_object_for_url, url)

