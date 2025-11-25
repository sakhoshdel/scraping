import requests
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from requests import Response
import logging
import time 
import re
from urllib.parse import quote
from typing import List,Dict, Tuple, Optional
import json
from celery import shared_task
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback

from khazesh.models import Mobile
from django.utils import timezone

HEADERS = {
    'From': 'behnammohammadi149@gmail.com', 
}


SITE = 'Tellstar'
GUARANTEE = 'گارانتی 18 ماهه - رجیستر شده'
SELLER = 'Tellstar'


kilo_mega_giga_tra = {
    'کیلوبایت': 'KB',

    'مگابایت': 'MB',
    'گیگابایت': 'GB',
    'ترابایت': 'TB'
}

persion_diti_to_english = {
    '۰': '0',
    '۱': '1',
    '۲': '2',
    '۳': '3',
    '۴': '4',
    '۵': '5',
    '۶': '6',
    '۷': '7',
    '۸': '8',
    '۹': '9'
    
}

crowled_mobile_brands: List[str] = ['APPLE', 'SAMSUNG', 'XIAOMI', 'Nothing-Phone', 'HONOR','HUAWEI', 'MOTOROLA', 'Realme']
# crowled_mobile_brands: List[str] = ['HONOR',]
ResponseType = Optional[Response]
Bs4Element = Optional[element.Tag]
Bs4ElementList = Optional[List[element.Tag]]

# logging.basicConfig(filename='error.log', level=logging.ERROR)

def retry_request(url: str, max_retries: int = 1, retry_delay: int = 1) -> ResponseType:
    for i in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            logging.info("Connection successful")
            return response
        except ConnectionError as ce:
            error_message = f"Connection error on attempt {i+1}: {ce}"
            logging.error(f"{url} - {error_message}")
            print(f"{url} - {error_message}")
            if i < max_retries - 1:
                logging.info("Retrying...")
                time.sleep(retry_delay)
        except requests.RequestException as re:
            error_message = f"Request error: {re}"
            logging.error(f"{url} - {error_message}")
            print(f"{url} - {error_message}")
            update_code_execution_state(SITE, False, error_message)
            return None
    return None


remove_pattern = r'^\s*product\(\s*|,\s*[\d]+\s*\)$'

# SITE_MOBILE_ATTRIBUTE_KEYS = {'70':'وضعیت گارانتی',
#                               '71': 'رنگ بندی',
#                               '129': 'دیگر ویژگی ها',
#                               '137':'سفارش'}
SITE_MOBILE_ATTRIBUTE_KEYS = {'وضعیت گارانتی': 'guarantee',
                              'رنگ بندی': 'color',
                              'دیگر ویژگی ها': 'not_active',
                              'سفارش': 'which_country',
                              'پک': 'pack'}

SITE_MOBILE_ATTRIBUTE_CODE = {'70': 'guarantee',
                              '71': 'color',
                              '129': 'not_active',
                              '137': 'which_country',
                              '162': 'pack'}


@shared_task(bind=True, max_retries=0)
def tellstar_crawler(self):
    try:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = SITE,
            status = True,
            mobile = True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        all_mobile_objects:List[Dict]= []
        for brand in crowled_mobile_brands:
            
            break_page_num_for  = False
            print(f"Processing {brand}...")
            
            for page_num in range(1, 5):  
                if break_page_num_for: 
                    break
                    
                response:  ResponseType = retry_request(f'https://tellstar.ir/search/product_{brand}/?page={page_num}')
                if not response:
                    print(f"Response for {brand} is None ")
                    continue
                
                soup: BeautifulSoup = BeautifulSoup(response.text, 'html.parser')
                all_mobile_products_box: Bs4Element = soup.find(id='category-items').find('div', class_='row g-3')
                all_mobile_divs = all_mobile_products_box.find_all('div', class_='col-lg-3')
                
                
                for mobile in all_mobile_divs:
                    mobile_object: Dict = {}    
                    mobile_attributer_dict = {'guarantee': [],
                                            'not_active': [],
                                            'color': [],
                                            'which_country': [],
                                            'pack': []}
                    
                    mobile: Bs4Element
                    mobile_title_box = mobile.find('div', class_='product-title')
                    mobil_title_a_tag = mobile_title_box.find('div', class_='title').find('a', class_='text-overflow-1')
                    mobile_fa_title = mobil_title_a_tag.text.strip()
                    mobile_link = mobil_title_a_tag.attrs['href']
                    
                    if not 'گوشی' in mobile_fa_title:
                        continue

                
                    mobile_price_a_tag = mobile.find('a', class_='product-action')
                    mobile_price = mobile_price_a_tag.find('p', class_='new-price').text\
                        .replace('تومان','').strip()
                    
                    # print('mobile_fa_title', mobile_fa_title)
                    # print('mobile_price', mobile_price)
                    # در این سایت ناموجود را به اشتباه (نا موجود نوشتن)
                    if mobile_price == 'نا موجود':
                        break_page_num_for = True
                        break
                    # print(mobile_link)
                    single_product_page_res: ResponseType = retry_request(f'https://tellstar.ir/{mobile_link}')
                    if not single_product_page_res:
                        # break_page_num_for = True
                        continue

                    single_product_page: BeautifulSoup = BeautifulSoup(single_product_page_res.text, 'html.parser')
                    
                    single_mobile_div = single_product_page.find(lambda tag: tag.name == 'div' and tag.has_attr('x-data') and 'product(' in tag['x-data'])

                    single_product_variations = single_mobile_div.attrs['x-data']
                    # single_product_variations_safe= json.loads(re.sub(regex_pattern, '', single_product_variations))
                    normalize_to_json_obj = '[' + re.sub(remove_pattern, '', single_product_variations) + ']'
                    
                    # print(normalize_to_json_obj)
                    mobile_variatoins = json.loads(normalize_to_json_obj)
                    #‌[1] is product that show when product page loads 
                    mobile_variants_all =  mobile_variatoins[0]
                    moible_varients_in_stock = list(filter(lambda mobile: mobile.get('in_stock', '') , mobile_variants_all.values()))    

                    single_page_mobile_variant_data_from_html = single_mobile_div.find(id='content-box')\
                        .find('div', class_="product-meta-feature")\
                            .find_next_sibling().find_all('div', class_='product-meta-color')
                            
                    for item in single_page_mobile_variant_data_from_html:
                        attribute_type = item.find('h5', class_='font-16').text.strip()
                        attribute_items = item.find('div', class_='product-meta-color-items').find_all('label', class_='btn')
                        # print('attribute_items', attribute_items)
                        # print('attribute_type',attribute_type)
                        
                        attribute_key = SITE_MOBILE_ATTRIBUTE_KEYS.get(attribute_type, '')
                        for attribute in attribute_items:
                            attribute_code = attribute.attrs['for'].replace('attribute-', '')
                            attribute_name = attribute.text.strip()
                            color_hex = ''
                            # print('attribute_name', attribute_name)
                            # print('attribute_code', attribute_code)
                            if attribute_key == 'color':
                                color_hex = attribute.find('span').get('style')
                                match = re.search(r'#[a-zA-Z0-9]{3,}', color_hex)
                                if match:
                                    color_hex = match.group()
                                    mobile_attributer_dict[attribute_key].append({
                                        'code':attribute_code,
                                        'name':attribute_name,
                                        'color_hex':color_hex
                                        
                                    })
                                    continue
                            
                            mobile_attributer_dict[attribute_key].append({
                                    'code':attribute_code,
                                    'name':attribute_name,                            
                                })
                    
                    # print('mobile_attributer_dict', mobile_attributer_dict)
                    

                    ram = re.search(r'\s*رم\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?', mobile_fa_title)
                    if ram:
                        ram = ram.group()
                        ram =  re.sub(r'\s*گیگابایت\s*|\s*گگیابایت\s*', 'GB', ram)
                        ram = re.sub(r'\s*رم\s*', '', ram)
                                                       
                    else:
                        ram =  re.search(r'\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T)?', mobile_fa_title)
                        if ram:
                            ram = ram.group()
                            ram = re.sub(r'\s*(GB|TB|T)\s*', '', ram)
                            ram = len(ram.split('/')) >=2 and ram.split('/')[1]
                            ram = ram.strip() + 'GB'
                        else:
                            ram = 'ندارد'
                        
                    mobile_object['ram'] = ram
                        
                    memory = re.search(r'\s*حافظه\s*[\d]{1,3}\s*(گیگابایت|ترابایت|مگابایت|گگیابایت)?', mobile_fa_title)
                    if memory:
                        memory = memory.group()
                        memory = re.sub(r'\s*گیگابایت\s*|\s*گگیابایت\s*', 'GB', memory)
                        memory = re.sub(r'\s*ترابایت\s*', 'TB', memory)
                        memory =  re.sub(r'\s*حافظه\s*', '', memory)
                                
                    else:
                        memory =  re.search(r'\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T)?', mobile_fa_title)
                        if memory:
                            memory = memory.group()
                            memory = re.sub(r'\s*(GB|TB|T)\s*', '', memory)
                            memory = len(memory.split('/')) >=1 and memory.split('/')[0].strip()
                            
                        else:
                            memory = 'ندارد'
                        
                    mobile_object['memory'] = memory
                    
                    model = re.search(r'[\w\s]*\s*', mobile_fa_title)
                    if model:
                        model = model.group()
                        model = re.sub(r'^\s*(samsung|xiaomi|apple|nokia|honor|huawei|nothing\sphone)\s*', '', model.lower())
                    
                    mobile_object['brand'] = brand.lower()
                    mobile_object['url'] = f'https://tellstar.ir{mobile_link}'
                    mobile_object['title'] = mobile_fa_title
                    mobile_object['vietnam'] = any([True if vietnam_key in mobile_fa_title else False for vietnam_key in ['VIT', 'ویتنام']])
                    
                    mobile_object['model'] = model
                    # # mobile_object['title_en'] = en_title
                    mobile_object['site'] = SITE
                    mobile_object['seller'] = SELLER
                    mobile_object['max_price'] = 1
                    mobile_object['mobile_digi_id'] = ''
                    mobile_object['dual_sim'] = True
                    mobile_object['active'] = True
                    mobile_object['mobile'] = True
                    
                    mobile_guarantee = mobile_attributer_dict.get('guarantee', [])[0]
                    mobile_colores = mobile_attributer_dict.get('color',[])
                    mobile_not_active = mobile_attributer_dict.get('not_active',[])
                    
                    for mobile_in_stock in moible_varients_in_stock:
                        
                        off_price = mobile_in_stock.get('off_price', 0)
                        
                        # mobile_object['min_price'] =  int(mobile_in_stock.get('off_price', 0)) * 10
                        mobile_object['min_price'] =  int(off_price) * 10 if off_price != None else int(mobile_in_stock.get('price', 0)) * 10
                        color_object = {}
                        not_active_object = {}

                        attribute_values = mobile_in_stock.get('attribute_values', {})
                        for idd, value in attribute_values.items():
                            key = SITE_MOBILE_ATTRIBUTE_CODE.get(idd)
                            if key == 'guarantee':
                                mobile_object[key] = mobile_guarantee.get('name', '')
                            if key == 'color':
                                color_object = [color_obj for color_obj in  mobile_colores if color_obj['code'] == f'{idd}-{value}'][0]
                                mobile_object['color_name'] = color_object.get('name', '')
                                mobile_object['color_hex'] = color_object.get('color_hex', '')
                                
                            if key == 'not_active':
                                    not_active_object = [not_active_obj for not_active_obj in  mobile_not_active if not_active_obj['code'] == f'{idd}-{value}']
                                    mobile_object['not_active'] = True if (not_active_object and 'غیرفعال' in not_active_object[0].get('name', '')) else False
                        # print('color_object', color_object)
                        # print(not_active_object)
                        # print( mobile_guarantee)
                        # print(mobile_object)
                        # print('#' * 80)
                        
                        all_mobile_objects.append(mobile_object.copy())
                    # print('*' * 80)
                    # print(all_mobile_objects)               
                    # print('len(all_mobile_objects)',len(all_mobile_objects))
                    # print('$' * 100)
                    
                    
        
        
        
        for mobile_dict in all_mobile_objects:
            # print('mobile_from_main', mobile_dict)
            save_obj(mobile_dict)

        update_code_execution_state(SITE, True)

    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state(SITE, False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)
        

            
