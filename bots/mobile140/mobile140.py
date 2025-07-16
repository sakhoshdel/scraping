import requests
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from requests import Response
import logging
import time 
import re
from urllib.parse import quote
from typing import List,Dict, Tuple, Optional
import copy
import csv

HEADERS = {
'From': 'behnammohammadi149@gmail.cm', 
    }


SITE = 'Mobile140'
GUARANTEE = 'گارانتی 18 ماهه - رجیستر شده'
SELLER = 'mobile140'


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

crowled_mobile_brands: List[str] = ['apple', 'samsung', 'xiaomi', 'nokia', 'realme','huawei', 'honor']

# def save_error_to_log(url, error_message):
#     error_log = ConnectionErrorLog(url=url, error_message=error_message)
#     error_log.save()
    
# ResponseType: TypeAlias = Optional[Response]
# Bs4Element: TypeAlias = Optional[element.Tag]
# Bs4ElementList: TypeAlias = Optional[List[element.Tag]]
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
            return None
    return None



def color_data_extractor(color_li_tag: Bs4Element) -> dict:
    input_tag_attrs: Bs4Element = color_li_tag.find('input').attrs
    color_name: str = input_tag_attrs['data-title']
    # This is required because for requesting new color information
    color_value: str = input_tag_attrs['data-val']
    
    # Html Bold Tag
    b_tag: Bs4Element = color_li_tag.find('b')
    
    # This is required for extracting color hex
    span_tag_style: str = b_tag.find('span')['style']
    
    # print(re.findall(r'(?<=(background-color:\s))(#[0-9a-zA-Z]+)', span_tag_style ))
    color_hex: str = re.search(r'background-color:\s*([#0-9a-zA-Z]+)', span_tag_style ).group(1)
    # print(re.findall(r'#[0-9a-zA-Z]+$', span_tag_style ))
    
    color_checked = True if 'checked' in input_tag_attrs else False
    
    
    
    
    
    
    return {'color_hex': color_hex, 'color_name': color_name,
            'color_value': color_value, 'color_checked': color_checked
            }
    


def extract_details(en_title: str, fa_title: str) -> Tuple[Optional[str]]:
    # Define patterns
    en_model_pattern = r'(([^A-Za-z]+\s*).*?\s)(?=[0-9]{1,3}(GB|MB|T))'
    fa_model_pattern = r'مدل\s+([^\s]+(?:\s+[^\s(]+)*)'
    memory_pattern = r'(\d+\s*GB|\d+\s*MB|\d+\s*TB)'
    ram_pattern = r'Ram\s+(\d+\s*GB|\d+\s*MB|\d+\s*TB)'

    # Extract model from English title
    model = re.search(en_model_pattern, en_title)
    # If no model found in English title, try Persian title
    if not model:
        model = re.search(fa_model_pattern, fa_title)
    # Get the model name if found
    model_name = model.group(1).strip() if model else None

    # Extract memory and RAM from English title
    memory_match = re.search(memory_pattern, en_title)
    ram_match = re.search(ram_pattern, en_title)
    
    memory = memory_match.group(1) if memory_match else None
    ram = ram_match.group(1) if ram_match else None

    # Extract brand from English title
    brand = en_title.split(' ')[0]
    
    # Extract vietnam and not_active from fa
    vietnam = True if 'ویتنام' in fa_title else False
    not_active = True if 'نان اکتیو' in fa_title else False
    
    return model_name, memory, ram, brand, vietnam, not_active

all_mobile_objects: List[Dict] = []

for brand in crowled_mobile_brands:
    break_page_num_for  = 0
    print(f"Processing {brand}...")
    for page_num in range(1, 4):  # Crawling first 3 pages
        
        if break_page_num_for: 
            break
        response:  ResponseType = retry_request(f'https://www.mobile140.com/group/{brand}-mobiles?page={page_num}')

        if response:
            soup: BeautifulSoup = BeautifulSoup(response.text, 'html.parser')

            all_mobile_products: Bs4Element = soup.find(id='products')
            # print(all_mobile_products)
            product_wrapper: Bs4ElementList = all_mobile_products.find_all('div', class_='product__wrapper')
            # print("product_wrapper", type(product_wrapper))

            mobile_object: Dict = {}
            for product in product_wrapper:
                product: Bs4Element
                mobile_price_tag: Bs4Element = product.find(class_='product__price product__offer')
                
                mobile_price : Bs4Element = mobile_price_tag.find(class_='product__offer--new')
                # In first ended product loop is terminated 'تمام شد'
                if not mobile_price:
                    break_page_num_for = 1
                    break
                
                # mobile_link = product.find('a').attrs['href']
                mobile_link = product.find('a')['href']
                
                product_id = product.find_previous_sibling('div', class_="compareView").find('input')['value']
                # print('product_id', product_id)
                # print(mobile_link)
                # print(mobile_price)    
                # print("*" * 30)
                
                single_product_page_res: ResponseType = retry_request(mobile_link)
                
                if not single_product_page_res:
                    break_page_num_for = 1
                    break
                
                # Find mobile variant colors
                single_product_page: BeautifulSoup = BeautifulSoup(single_product_page_res.text, 'html.parser')

                title: Bs4Element = single_product_page.find('div', class_='single__product__headline').find('h1')

                # Get titles
                en_title: str = title.span.extract().text.strip()
                fa_title: str = title.text.strip()
                # print(f'{en_title = }')
                # print(f'{fa_title = }')

                # Get Model Memory Ram
                model: str
                memory: str
                ram: str
                brand: str
                vietnam: str
                not_active: str
                model, memory, ram, brand, vietnam, not_active = extract_details(en_title, fa_title)

                mobile_object['model'] = model
                mobile_object['memory'] = memory
                mobile_object['ram'] = ram
                mobile_object['brand'] = brand
                mobile_object['vietnam'] = vietnam
                mobile_object['not_active'] = not_active
                # mobile_object['title_en'] = en_title
                mobile_object['title'] = fa_title
                mobile_object['url'] = mobile_link
                mobile_object['site'] = SITE
                mobile_object['seller'] = SELLER
                mobile_object['guarantee'] = GUARANTEE
                mobile_object['max_price'] = 1
                mobile_object['mobile_digi_id'] = product_id
                mobile_object['dual_sim'] = True
                mobile_object['active'] = True
                
                
                # print("Model:", model)
                # print("Memory:", memory)
                # print("RAM:", ram)
                # print("brand:", brand)
                # print("vietnam:", vietnam)
                # print("not_active:", not_active)
                
                single_product_page_directory: Bs4Element = single_product_page.find(class_='single__product__directory')
                single_product_variant_color_tags: Bs4ElementList = single_product_page_directory.\
                    find_next('div', class_= "single__product__variants").\
                    find('ul', class_='list-unstyled').find_all('li')
                
                
                colors_of_single_mobile: List[Dict] = list(map(lambda li_tag: color_data_extractor(li_tag), single_product_variant_color_tags))
                
                checked_color = [color_obj for color_obj in colors_of_single_mobile if color_obj['color_checked']]
                # print(checked_color)
                mobile_price.span.extract()
                price: str = mobile_price.text.strip()
                mobile_object['min_price'] = ''.join([persion_diti_to_english[i] for i in price.replace(',', '')]) + '0'
                mobile_object['color_name'] = checked_color[0]['color_name']            
                mobile_object['color_hex'] = checked_color[0]['color_hex']
                all_mobile_objects.append(copy.deepcopy(mobile_object))    
                colors_of_single_mobile.remove(checked_color[0])
                # print(colors_of_single_mobile)
                
                if not colors_of_single_mobile: 
                    # print('hahahhahah')
                    continue
                for color in colors_of_single_mobile:
                    variant_mobile_object = copy.deepcopy(mobile_object)
                    variant_color_value = color['color_value']
                    encoded_title = quote(fa_title.replace(' ','-'), safe='')
                    variant_color_price_url = f'https://mobile140.com/fa/product/"%DA%AF%D9%88%D8%B4%DB%8C-%D9%85%D9%88%D8%A8%D8%A7%DB%8C%D9%84"/{product_id}-{encoded_title}.html&action=price_show&priceid=&colorid={variant_color_value}&productid={product_id}&ajax=ok'
                    
                    variant_color_price_res = retry_request(variant_color_price_url)
                    if variant_color_price_res:
                        different_color_mobile = BeautifulSoup(variant_color_price_res.text, 'html.parser')
                        price = different_color_mobile.find('span', class_="single__product__price--new").find('span').text
                        
                        variant_mobile_object['min_price'] = ''.join([persion_diti_to_english[i] for i in price.replace(',', '')]) + '0'
                        variant_mobile_object['color_name'] = color['color_name']            
                        variant_mobile_object['color_hex'] = color['color_hex']
                        all_mobile_objects.append(copy.deepcopy(variant_mobile_object))
                    

print(all_mobile_objects)
print(len(all_mobile_objects))

with open('mobile140.csv', 'w', newline='') as f:
    writer = csv.writer(f)

    # get one of the object from list and extract keys
    writer.writerow(list(all_mobile_objects[0].keys()))
    for mobie_obj in all_mobile_objects:
        writer.writerow(list(mobie_obj.values()))
