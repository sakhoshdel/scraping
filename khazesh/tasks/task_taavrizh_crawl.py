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
import urllib.parse
from celery import shared_task
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback

from khazesh.models import Mobile
from django.utils import timezone


HEADERS = {
    'From': 'behnammohammadi149@gmail.com', 
    }




SITE = 'Taavrizh'
GUARANTEE = '18 ماه گارانتی شرکتی'
SELLER = 'Taavrizh'

# crowled_mobile_brands: List[str] = ['t-apple',]
crowled_mobile_brands: List[str] = ['اپل', 'سامسونگ', 'شیائومی', 'ریلمی', "نوکیا", "هواوی", ] 
brand_dict_key = {
    'سامسونگ': 'samsung',
    'شیائومی': 'xiaomi',
    'نوکیا': 'nokia',
    'اپل': 'apple',
    'ریلمی': 'realme',
    'هواوی':'huawei'
    
}

ResponseType = Optional[Response]
Bs4Element = Optional[element.Tag]
Bs4ElementList = Optional[List[element.Tag]]

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
            # update_code_execution_state('Taavrizh', False, error_message)
            return None
    return None

def extract_details(en_title: str,) -> Tuple[Optional[str]]:
    # Define patterns
    en_model_pattern  = r'.*?(?=\b\d{1,3}(GB|MB|TB|G|M|T)\b)'

    # Extract model from English title
    model = re.search(en_model_pattern, en_title)
    if model:
        model = model.group(0).strip()
    else:
        model =  en_title
    
    
    brand = en_title.split(' ')[0]
    
    vietnam = True if 'Vietnam' in en_title else False

    not_active = True if 'non active' in en_title else False

    
    return model, brand, not_active, vietnam

@shared_task(bind=True, max_retries=0)
def taavrizh_crawler(self):
    try:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = 'Taavrizh',
            status = True,
            mobile = True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        
        
        
        all_mobile_objects:List[Dict]= []
        for brand in crowled_mobile_brands:

            
            break_page_num_for  = False
            print(f"Processing {brand}...")
            for page_num in range(1, 4):  # Crawling first 3 pages

                if break_page_num_for: 
                    break
                    
                response:  ResponseType = retry_request(f'https://taavrizh.com/product-category/product-rands/{brand}/page/{page_num}')

                if not response:
                    print(f"Response for {brand_dict_key[brand]} is None ")
                    continue
                    
                soup: BeautifulSoup = BeautifulSoup(response.text, 'html.parser')
                all_mobile_products_ul: Bs4Element = soup.find('ul', class_='products columns-4')

                if not all_mobile_products_ul:
                    print('There is no such div with class products  columns-4')
                    continue
                    
                all_mobile_products = all_mobile_products_ul.find_all('li')

                mobile_object: Dict = {}

                
                # print(len(all_mobile_products))
                for product in all_mobile_products:
                    product: Bs4Element
          
                    mobile_info = product.find('div', class_='info-product')
                    if not mobile_info:
                        continue
                     
                    mobile_inner_product_info = mobile_info.find('div', class_="products__item-info")
                    if not mobile_inner_product_info:
                        continue
                    
                    mobile_items_p_tag = mobile_inner_product_info.find('p', class_="products__item-fatitle force-rtl")
                    mobile_items_a_tag = mobile_items_p_tag.find('a')
                    mobile_fa_title = mobile_items_a_tag.attrs['title']
                    mobile_link = mobile_items_a_tag.attrs['href']
                    
                    if mobile_fa_title.split(' ')[0] != 'گوشی':
                        continue
                    
                    mobile_price = mobile_inner_product_info.find('span', class_ = 'products__item-price')\
                        .text.strip().replace('تومان', '')

                    
                    # print(mobile_fa_title)
                    # print(mobile_price)
                    
                    # mobile_price_div = product.find('span', class_="price")
                    # mobile_price = mobile_price_div.text.replace('تومان', '').strip().replace(',', '') if mobile_price_div else mobile_price_div
                    
                    if mobile_price == 'ناموجود':
                        break_page_num_for = True
                        break


                    single_product_page_res: ResponseType = retry_request(mobile_link)
                    if not single_product_page_res:
                        continue
                    
                    single_product_page: BeautifulSoup = BeautifulSoup(single_product_page_res.text, 'html.parser')
                    
                    mobile_short_attributes_li = single_product_page.find('ul',class_='bakala-product-specifications-list').find_all('li', class_='bakala-product-specification-item')
                    
                    not_active = True if 'Not Active' in mobile_fa_title else False
                    vietnam = True if 'ویتنام' in mobile_fa_title else False
                
                    model = ''
                    ram = 'ندارد'
                    memory = 'ندارد'
                    en_title = ''
                  
                    
                    for attribute_li in mobile_short_attributes_li:
                        attribute_p_tags = attribute_li.find('div', class_='bakala-product-specification-item-wrap')
                        
                        attribute_lable = attribute_p_tags.find('p', class_='bakala-product-specification-item-label')  
                        if attribute_lable and attribute_lable.text.strip() == 'مدل':
                            en_title  =  attribute_p_tags.find('p', class_='bakala-product-specification-item-value')\
                                .text.strip().replace('-', ' ').lower()
                            model = en_title.replace(brand_dict_key[brand], '')
                            
                            print('model', model)

                        if attribute_lable and attribute_lable.text.strip() == 'حافظه داخلی':
                            memory = ''.join( attribute_p_tags.find('p', class_='bakala-product-specification-item-value')\
                                .text.replace('گیگابایت', 'GB').replace('ترابایت', 'T').strip().split())
                            # print('memory', memory)
                            
                        if attribute_lable and attribute_lable.text.strip() == 'مقدار RAM':
                            ram = ''.join(attribute_p_tags.find('p', class_='bakala-product-specification-item-value')\
                                .text.replace('گیگابایت', 'GB').strip().split())
                            # print('ram', ram)
                            
                    if ram == 'ندارد' or memory == 'ندارد':
                        all_specification_div = single_product_page.find( id='tab-additional_information')
                        all_ul = all_specification_div.find_all('ul', class_="spec-list")
                        for ul in all_ul:
                            all_li = ul.find_all('li')  
                            for li in all_li:
                                mobile_info = li.find('span', class_='technicalspecs-title').text.strip()  
                                if mobile_info == 'مقدار RAM' and ram == 'ندارد':
                                    ram = ''.join(li.find('span', class_='technicalspecs-value')\
                                        .text.replace('گیگابایت', 'GB').strip().split())
                                    print('ram', ram)

                                if mobile_info == 'حافظه داخلی' and memory == 'ندارد':
                                    memory = ''.join(li.find('span', class_='technicalspecs-value')\
                                        .text.replace('گیگابایت', 'GB').replace('ترابایت', 'T').strip().split())
                                    print('memory', memory)
                    
                    print( type(mobile_object))
                    mobile_object['model'] = model
                    mobile_object['memory'] = memory
                    mobile_object['ram'] = ram
                    mobile_object['brand'] = brand_dict_key[brand]
                
                    
                    # mobile_object['title_en'] = en_title
                    mobile_object['title'] = mobile_fa_title
                    mobile_object['url'] = mobile_link
                    mobile_object['site'] = SITE
                    mobile_object['seller'] = SELLER
                    mobile_object['guarantee'] = GUARANTEE
                    mobile_object['max_price'] = 1
                    mobile_object['mobile_digi_id'] = ''
                    mobile_object['dual_sim'] = True
                    mobile_object['active'] = True 
                    mobile_object['mobile'] = True     
                    
                    product_obj = product.find('form', class_="variations_form wpcvs_archive")
                    mobile_obj_form_json = product_obj.attrs["data-product_variations"]
        #             variant_colors_json_data = single_product_page.find('form', class_='variations_form cart').attrs['data-product_variations']
            
                    if not mobile_obj_form_json:
                        continue
                    else:
                        mobile_obj_form_json = json.loads(mobile_obj_form_json)
                    # print(mobile_obj_form_json)
                    
                    for item in mobile_obj_form_json:
                        is_in_stock = item.get('is_in_stock', '')
                        if not is_in_stock : continue
                        
                        attributes = item.get('attributes', {})
                        if brand == 't-samsung':
                            mobile_object['vietnam'] = vietnam or attributes.get('attribute_pa_pack', '') == 'vietnam' or attributes.get('attribute_%d8%a7%d9%86%d8%aa%d8%ae%d8%a7%d8%a8-%d9%be%da%a9', '') == 'ویتنام'
                            print("attribute_%d8%a7%d9%86%d8%aa%d8%ae%d8%a7%d8%a8-%d9%be%da%a9)", attributes.get('attribute_%d8%a7%d9%86%d8%aa%d8%ae%d8%a7%d8%a8-%d9%be%da%a9', ''))
                        else:
                            mobile_object['vietnam'] = False

                        if brand == 'اپل':
                            mobile_object['not_active'] = not_active or attributes.get('attribute_%d9%86%d9%88%d8%b9', '') == 'Not Active'
                        else:
                            mobile_object['not_active'] = False
                        
                        
                        color_key = next(iter(attributes))  # Get the color attribute key
                        color_value = attributes[color_key]  # Get the URL-encoded color value
                        decoded_color = urllib.parse.unquote(color_value).split('-')[0]

                        display_price = int(item.get('display_price', 0)) * 10 # Get the price
                        
                     
                        all_mobile_objects.append({'min_price':display_price, 
                                    'color_name':decoded_color,
                                    'color_hex':'', **mobile_object})
                        
                        print(f"Color: {decoded_color}, Price: {display_price}")
                        
        
       
        
        
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict)
        
        update_code_execution_state('Taavrizh', True)

        
    except Exception as e:
        error_message = str(traceback.format_exc())
        update_code_execution_state('Taavrizh', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)



# taavrizh_crawler()
