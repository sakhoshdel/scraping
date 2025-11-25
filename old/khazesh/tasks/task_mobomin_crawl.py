import requests
from bs4 import BeautifulSoup, element
from requests.exceptions import RequestException, ConnectionError
from celery import shared_task

from requests import Response
import logging
import time 
import re
from urllib.parse import quote
from typing import List,Dict, Tuple, Optional
from .save_crawler_status import update_code_execution_state
from .save_object_to_database import save_obj
import traceback
# import copy
# import csv
from khazesh.models import Mobile
from django.utils import timezone


crowled_mobile_brands: List[str] = ['اپل', 'سامسونگ', 'شیائومی', 'ریلمی', 'نوکیا','ناتینگ-فون','honor']
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
            if i < max_retries - 1:
                logging.info("Retrying...")
                time.sleep(retry_delay)
        except requests.RequestException as re:
            error_message = f"Request error: {re}"
            logging.error(f"{url} - {error_message}")
            print(f"{url} - {error_message}")
            update_code_execution_state('Mobomin', False, error_message)

            
            return None
    return None

def extract_details(en_title: str,) -> Tuple[Optional[str]]:
    # Define patterns
    en_model_pattern  = r'.*?(?=\b\d{1,3}(GB|MB|TB)\b)'
    # words_to_replace = ["Xiaomi", "iPhone", "Samsung", "Nokia", "HONOR"]
    # Extract model from English title
    model = re.search(en_model_pattern, en_title)
    if model:
        model = model.group(0).strip()

    else:
        model =  en_title

    brand = 'apple' if 'iPhone' in en_title.split(' ')[0] else en_title.split(' ')[0].strip()

    vietnam = True if 'Vietnam' in en_title else False

    not_active = True if 'non active' in en_title else False

    return model, brand, not_active, vietnam


@shared_task(bind=True, max_retries=0)
def mobomin_crawler(self):
    try:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = 'Mobomin',
            status = True,
            mobile = True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        HEADERS = {
            'From': 'behnammohammadi149@gmail.com', 
            }

        SITE = 'Mobomin'
        GUARANTEE = 'ذکر نشده'
        SELLER = 'Mobomin'

        all_mobile_objects:List[Dict]= []
        for brand_fa in crowled_mobile_brands:
            break_page_num_for  = False
            print(f"Processing {brand_fa}...")
            for page_num in range(1, 4):  # Crawling first 3 pages

                if break_page_num_for: 
                    break

                category_url =f"https://mobomin.com/search/{brand_fa}?page={page_num}"
                print(category_url)
                response: ResponseType = retry_request(category_url)

                if not response:
                    print(f"Response for {brand_fa} is None ")
                    continue

                soup: BeautifulSoup = BeautifulSoup(response.text, 'html.parser')
                all_mobile_products_div: Bs4Element = soup.find(class_='row row-list-item')

                if not all_mobile_products_div:
                    print('There is no such div with class row row-list-item')
                    continue

                all_mobile_products = all_mobile_products_div.find_all('div', class_='col-12 col-md-4 col-lg-3 item-category pl-2 pr-2')

                mobile_object: Dict = {}

                print(len(all_mobile_products))
                for product in all_mobile_products:
                    product: Bs4Element
                    mobile_price_div = product.find(class_="c-price__value-wrapper")
                    mobile_price = mobile_price_div.text.replace('تومان', '').strip().replace(',', '') if mobile_price_div else mobile_price_div

                    if mobile_price == 'ناموجود':
                        break_page_num_for = True
                        break

                    mobile_link = product.find('a')['href']

                    single_product_page_res: ResponseType = retry_request(mobile_link)

                    if not single_product_page_res:
                        break_page_num_for = True
                        break

                    single_product_page: BeautifulSoup = BeautifulSoup(single_product_page_res.text, 'html.parser')

                    memory_ram_tag = single_product_page.find('ul', class_="product-detail")
                    ram = ''
                    memory = ''
                    if memory_ram_tag:
                        # استخراج memory_span از تگ‌هایی که شامل 'حافظه' هستند
                        memory_text = [li.find('span').text for li in memory_ram_tag.find_all('li')if li.find('b') and 'حافظه' in li.find('b').text][0]
                        ram_text = [li.find('span').text for li in memory_ram_tag.find_all('li') if li.find('b') and 'رم' in li.find('b').text][0]
                        # print("memory_text",memory_text)
                        # print("ram_text",ram_text)

                        memory =''.join(memory_text.replace('گیگ', 'GB')\
                            .replace('ترابایت', 'T')\
                            .split(' ')).strip()
                        ram = ''.join(ram_text.replace('گیگ', '').strip().split()) + 'GB'
                        # memory =''.join(re.sub(r'(رم|حافظه)\s*:? ?', '', memory_ram_tag.find_all('li')[0].text).strip().replace('گیگ', 'GB')\
                        #     .replace('ترابایت', 'T')\
                        #     .replace('حافظه :', '')\
                        #     .replace('حافظه : ', '')\
                        #     .split(' ')).strip()
                        # ram = re.sub(r'رم\s*:? ?', '',memory_ram_tag.find_all('li')[1].text).strip() + 'GB'
                    else:
                        ram = 'ندارد'
                        memory = 'ندارد'

                    # print(memory,'#', ram)
                    title: Bs4Element = single_product_page.find('h1', class_='c-product__title')
                    en_title = title.text.strip() if title else 'تایتل وجود ندارد'
                    fa_title = 'خالی'
                    model, brand, not_active, vietnam =  extract_details(en_title)

                    # print(en_title)
                    # print(mobile_price)
                    # print(extract_details(en_title))

                    mobile_object['model'] = model
                    mobile_object['memory'] = memory
                    mobile_object['ram'] = ram
                    mobile_object['brand'] = brand
                    mobile_object['vietnam'] = vietnam
                    mobile_object['not_active'] = not_active
                    # mobile_object['title_en'] = en_title
                    mobile_object['title'] = en_title
                    mobile_object['url'] = mobile_link
                    mobile_object['site'] = SITE
                    mobile_object['seller'] = SELLER
                    mobile_object['guarantee'] = GUARANTEE
                    mobile_object['max_price'] = 1
                    mobile_object['mobile_digi_id'] = ''
                    mobile_object['dual_sim'] = True
                    mobile_object['active'] = True  
                    mobile_object['mobile'] = True            

                    mobile_color_tag = single_product_page.find('div', class_="col-lg-7 col-md-7 col-12")
                    mobile_colors_div = mobile_color_tag.find_all('div', 'row mt-3')
                    if not mobile_colors_div:
                        continue

                    for mobile_color_div in mobile_colors_div:
                        mobile_color = " ".join(mobile_color_div.find('h5').text.strip().split(' ')[1:])
                        mobile_specific_color_price = mobile_color_div.find('h6').find('span').text.strip().split(' ')[0].replace(',', '')
                        print(mobile_color, mobile_specific_color_price)
                        all_mobile_objects.append({'min_price':int(mobile_specific_color_price.strip()) * 10, 
                                                'color_name':mobile_color,
                                                'color_hex':'', **mobile_object})


        
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict)

        update_code_execution_state('Mobomin', True)

    except Exception as e:
        error_message =  str(traceback.format_exc())
        update_code_execution_state('Mobomin', False, error_message)
        print(f"Error {error_message}")
        raise self.retry(exc=e, countdown=30)


# with open('Mobomin.csv', 'w', newline='') as f:
#     writer = csv.writer(f)

#     # get one of the object from list and extract keys
#     writer.writerow(list(all_mobile_objects[0].keys()))
#     for mobie_obj in all_mobile_objects:
#         writer.writerow(list(mobie_obj.values()))
