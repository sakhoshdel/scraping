import json
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
import time
import traceback
from khazesh.models import Mobile
from django.utils import timezone

def retry_request(url: str, headers, max_retries: int = 1, retry_delay: int = 1):
    for i in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
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

HEADERS = {
    'From': 'behnammohammadi149@gmail.com', }


def get_tablet_info(headers, url):
    try:
        res = retry_request(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        tenco_page_obj = json.loads(soup.find('script', id='__NEXT_DATA__').string.encode().decode())
        
        tecno_queries =tenco_page_obj.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        tablet_lists_obj = tecno_queries[5]
        
        tablets = tablet_lists_obj.get('state', {}).get('data').get('results', [])
        tablet_urls = []
        
        # available_tablets = list(filter(lambda tablet: tablet.get('available', 0), tablets))
        page_number_flag = False
        
        for tablet in tablets:
            if not tablet.get('available'):
                page_number_flag = True
                break
            tablet_title = tablet.get('name')
            tablet_code = tablet.get('code', '').split('-')[1]
            tablet_url = f"https://www.technolife.ir/product-{tablet_code}/{tablet_title.replace(' ','-').strip()}"
            tablet_urls.append(tablet_url)
            
        

        return tablet_urls, page_number_flag
    except Exception as e:
        print(f"Error in scraping {url}: {str(e)}")
        print('Error come from get_tablet_info (function)')
        return [], True

def main():
    phone_model_list = ['27_550_227/تمام-تبلت-ها?manufacturer_id=15_20_26_81&only_available=true']
    # phone_model_list = [ '69_70_80/nokia', ]


    tablet_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):

            url = f'https://www.technolife.ir/product/list/{phone_model}&page={i + 1}'
            tablet_urls, tablet_page_flag = get_tablet_info(HEADERS, url)
            tablet_all_urls.extend(tablet_urls)
            if tablet_page_flag:
                break
     
    print(tablet_all_urls)
    print(len(tablet_all_urls))
    return tablet_all_urls


def retry_main(max_retries=3, delay=5):
    retries = 0
    all_tablet_urls = main()
    while len(all_tablet_urls) == 0 and retries < max_retries:
        print(f"Retrying... attempt {retries + 1}")
        time.sleep(delay)
        all_tablet_urls = main()
        retries += 1

    if len(all_tablet_urls) == 0:
        raise Exception("No tablet URLs found after maximum retries")
    
    return all_tablet_urls

not_active_texts = ['Not Active','Not Activate','Not Activated',  'not active', 'not-active', "Not_Active", 'NOT_ACTIVE', 'Not-Active', 'NOT-ACTIVE', 'ٔNOT ACTIVE', 'نات اکتیو', 'نات-اکتیو'] 

kilo_mega_giga_tra = {
    'کیلوبایت': 'KB',
    'مگابایت': 'MB',
    'گيگابايت': 'GB',
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
    '16': '16',
    '۱۶': '16',
    '32': '32',
    '۳۲': '32',
    '48': '48',
    '۴۸': '48',
    '64': '64',
    '۶۴': '64',
    '128': '128',
    '۱۲۸': '128',
    '256': '256',
    '۲۵۶': '256',
    '512': '512',
    '۵۱۲': '512',
}


def extract_model_form_title_en(title_en):
    title_en_list = title_en

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


def extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, value):
    memory_ram = value.split(' ')
    memory_ram_1 = ''
    memory_ram_0 = ''
    if len(memory_ram) < 2:
        # print("Invalid format for memory value:", memory_ram)
        return 'ندارد'
    
    print('memory_ram', memory_ram)
    memory_ram_1 = memory_ram[1].replace('،', '').replace('\n', '').strip()
    memory_ram_0 = memory_ram[0].replace('،', '').replace('\n', '').strip()
    try:
        for key, value in kilo_mega_giga_tra.items():
            if memory_ram and key == memory_ram_1:
                # print('kilo_mega_giga_tra')
                memory_ram[1] = value
            elif memory_ram and key == memory_ram_0:
                memory_ram[0] = value
                # print('kilo_mega_giga_tra')

        for key, value in letter_to_digit_obj.items():
            if memory_ram and key == memory_ram[0]:
                # print('#' * 80)
                # print("letter_to_digit_obj1111")
                # print(memory_ram)
                # print('#' * 80)
                memory_ram[0] = value
                memory_ram = ''.join(memory_ram[:2])
            elif memory_ram and key == memory_ram[1]:
                # print('#' * 80)
                # print('letter_to_digit_obj')
                # print(memory_ram)
                # print('#' * 80)
                memory_ram[1] = value
                memory_ram = ''.join(memory_ram[:2])
    except Exception as e:
        error_message = str(traceback.format_exc())
        print(f"Error {error_message}")
        update_code_execution_state("Tecnolife-tablet", False, error_message)
    return memory_ram


def set_other_obj_data(other_data_obj, tablet_obj,url):
    en_title = tablet_obj['product_info']['model'].split(' ')
    fa_title = tablet_obj['product_info']['title']
    other_data_obj['title'] = fa_title
    other_data_obj['vietnam'] = True if 'Vietnam' in en_title else False
    brand = en_title[0]
    other_data_obj['brand'] = 'xiaomi' if brand in ['poco', 'Poco'] else brand
    # print(other_data_obj['brand'])
    other_data_obj['model'] = extract_model_form_title_en(en_title)
    other_data_obj['active'] = True
    other_data_obj['mobile'] = False
    other_data_obj['site'] = 'Tecnolife'
    other_data_obj['dual_sim'] = True
    other_data_obj['url'] = url
    other_data_obj['max_price'] = 1
    # other_data_obj['not_active'] = True if 'Not Active' in en_title else False
    is_not_active = any([any([True if txt in " ".join(en_title) else False for txt in not_active_texts ]), 
                         any([True if txt in fa_title else False for txt in not_active_texts ])])  
    other_data_obj['not_active'] = is_not_active
    print(" ".join(en_title), is_not_active)

# url = 'https://www.technolife.ir/product-2545'

@shared_task(bind=True, max_retries=1)
def tablet_tecnolife_crawler(self):
    all_tablet_urls = retry_main()
    try:  
        all_tablets_objects = []
        for url in all_tablet_urls:
            # try:
            res = retry_request(url, headers=HEADERS)
            soup = BeautifulSoup(res.text, 'html.parser')

            obj = soup.find('script', {'id': '__NEXT_DATA__'}).get_text()
            obj = json.loads(obj)
            # print(type(obj))
            tablet_obj = obj['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']
            # print(seller_items)

            all_color_bojects = []
            same_color_seller_obj = []
            # find same collor tablets and select min price
            for obj in tablet_obj['seller_items_component']:
                color_name = obj['color']['value']
                color_hex = obj['color']['code']

                # sellers for each color
                seller_items = obj['seller_items']

                for seller in seller_items:
                    seller_available = seller['available']

                    if seller_available:

                        same_color_seller_obj.append({
                            'color_name': color_name,
                            'color_hex': color_hex,
                            "seller": seller['seller'],
                            'guarantee': seller['guarantee'],
                            'mobile_digi_id': seller['_id'],
                            'min_price': seller['discounted_price'] * 10

                        })
                all_color_bojects.append(same_color_seller_obj)
                same_color_seller_obj = []

            all_color_bojects = list(filter(lambda x: bool(x), all_color_bojects))

            last_mobil_objests = []
            for same_color_tablets in all_color_bojects:
                min_price_obj = min(same_color_tablets, key=lambda x: x['min_price'])

                last_mobil_objests.append(min_price_obj)

            other_data_obj = {}
            for obj in tablet_obj['configurations_component']:
                if obj['title'] == 'حافظه':
                    for info_obj in obj['info']:
                        item = info_obj['item']
                        if item == 'حافظه داخلی':
                            value = info_obj['value']
                            other_data_obj['memory'] = extract_ram_or_memory(
                                kilo_mega_giga_tra, letter_to_digit_obj, value)
                            print('memory', other_data_obj['memory'])

                        if item == 'حافظه RAM':
                            value = info_obj['value']
                            other_data_obj['ram'] = extract_ram_or_memory(
                                kilo_mega_giga_tra, letter_to_digit_obj, value)
                            print('ram', other_data_obj['ram'])

                    if not other_data_obj.get('ram'):
                        other_data_obj['ram'] = 'ندارد'
                    if not other_data_obj.get('memory'):
                        other_data_obj['memory'] = 'ندارد'
            set_other_obj_data(other_data_obj, tablet_obj, url)
            print(url)
            for tablet in last_mobil_objests:
                tablet.update(other_data_obj)

            all_tablets_objects.extend(last_mobil_objests)
            
        
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = 'Tecnolife',
            status = True,
            mobile = False,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        
        
        for tablet_dict in all_tablets_objects:
            save_obj(tablet_dict)
            
        update_code_execution_state("Tecnolife-tablet", True)


    except Exception as e:
        error_message = str(traceback.format_exc())
        print(f"Error {error_message}")
        update_code_execution_state("Tecnolife-tablet", False, error_message)
        raise self.retry(exc=e, countdown=30)
