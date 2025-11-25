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

import csv

HEADERS = {
    'From': 'behnammohammadi149@gmail.com', 
    }


SITE = 'Taavrizh'
GUARANTEE = '18 ماه گارانتی شرکتی'
SELLER = 'Taavrizh'

# crowled_mobile_brands: List[str] = ['t-apple',]
crowled_mobile_brands: List[str] = ['t-samsung', 't-apple', 't-xiaomi', 't-nokia']
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


all_mobile_objects:List[Dict]= []
for brand in crowled_mobile_brands:

    
    break_page_num_for  = False
    print(f"Processing {brand}...")
    for page_num in range(1, 4):  # Crawling first 3 pages

        if break_page_num_for: 
            break
            
        response:  ResponseType = retry_request(f'https://taavrizh.com/t-brands/{brand}/page/{page_num}')

        if not response:
            print(f"Response for {brand} is None ")
            continue
            
        soup: BeautifulSoup = BeautifulSoup(response.text, 'html.parser')
        all_mobile_products_ul: Bs4Element = soup.find('ul', class_='products columns-4 columns-1200-5 columns-992-4 columns-768-3 columns-576-2 columns-320-2')

        if not all_mobile_products_ul:
            print('There is no such div with class products columns-4 columns-1200-5 columns-992-4 columns-768-3 columns-576-2 columns-320-2')
            continue
            
        all_mobile_products = all_mobile_products_ul.find_all('li')

        mobile_object: Dict = {}

        
        print(len(all_mobile_products))
        for product in all_mobile_products:
            product: Bs4Element
            
            mobile_fa_title = product.find('h2', class_='woocommerce-loop-product__title').text.strip()
            if mobile_fa_title.split(' ')[0] != 'گوشی':
                continue
            
            
            mobile_price_div = product.find('span', class_="price")
            mobile_price = mobile_price_div.text.replace('تومان', '').strip().replace(',', '') if mobile_price_div else mobile_price_div
            
            if mobile_price == 'ناموجود':
                break_page_num_for = True
                break
            
            print(mobile_price)
            print(mobile_fa_title)

            mobile_link = product.find('a')['href']
            single_product_page_res: ResponseType = retry_request(mobile_link)
            if not single_product_page_res:
                # break_page_num_for = True
                continue
            
            single_product_page: BeautifulSoup = BeautifulSoup(single_product_page_res.text, 'html.parser')
            
            attributes_div = single_product_page.find('div',class_='short-attributes').find('div', class_='attributes')
            attributes = attributes_div.find_all('div', class_='attribute')
            
            not_active = True if 'Not Active' in mobile_fa_title else False
            vietnam = True if 'ویتنام' in mobile_fa_title else False
        
            model = ''
            ram = 'ندارد'
            memory = 'ندارد'
            
            for attribute in attributes:
                attr = attribute.find('span', class_='label')
                if attr and attr.text.strip() == 'مدل:':
                    model = attribute.find('span', class_='value').text.strip().replace('-', ' ')
                    
                    print('model', model)

                if attr and attr.text.strip() == 'حافظه داخلی:':
                    memory = ''.join(attribute.find('span', class_='value').text.replace('گیگابایت', 'GB').replace('ترابایت', 'T').strip().split())
                    print('memory', memory)
                    
                if attr and attr.text.strip() == 'مقدار RAM:':
                    ram = ''.join(attribute.find('span', class_='value').text.replace('گیگابایت', 'GB').strip().split())
                    print('ram', ram)
                    
            # print('brand', brand.split('-')[1].capitalize())
            mobile_object['model'] = model
            mobile_object['memory'] = memory
            mobile_object['ram'] = ram
            mobile_object['brand'] = brand.split('-')[1].capitalize()
           
            
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
            
            variant_colors_json_data = single_product_page.find('form', class_='variations_form cart').attrs['data-product_variations']
      
            if not variant_colors_json_data:
                continue
            else:
                variant_colors_json_data = json.loads(variant_colors_json_data)
            # print(variant_colors_json_data)
            
            for item in variant_colors_json_data:
                is_in_stock = item.get('is_in_stock', '')
                if not is_in_stock : continue
                
                attributes = item.get('attributes', {})
                if brand == 't-samsung':
                    mobile_object['vietnam'] = vietnam or attributes.get('attribute_pa_pack', '') == 'vietnam' or attributes.get('attribute_%d8%a7%d9%86%d8%aa%d8%ae%d8%a7%d8%a8-%d9%be%da%a9', '') == 'ویتنام'
                    print("attribute_%d8%a7%d9%86%d8%aa%d8%ae%d8%a7%d8%a8-%d9%be%da%a9)", attributes.get('attribute_%d8%a7%d9%86%d8%aa%d8%ae%d8%a7%d8%a8-%d9%be%da%a9', ''))
                else:
                    mobile_object['vietnam'] = False

                if brand == 't-apple':
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
                
                
with open('taavrizh.csv', 'w', newline='') as f:
    writer = csv.writer(f)

    # get one of the object from list and extract keys
    writer.writerow(list(all_mobile_objects[0].keys()))
    for mobie_obj in all_mobile_objects:
        writer.writerow(list(mobie_obj.values()))
