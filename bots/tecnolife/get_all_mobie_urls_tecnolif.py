import requests
from bs4 import BeautifulSoup
from lxml import etree
import json
import logging
import time


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


def get_mobile_info(headers, url):
    try:
        res = retry_request(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        tenco_page_obj = json.loads(soup.find('script', id='__NEXT_DATA__').string.encode().decode())
        tecno_queries =tenco_page_obj.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        mobile_lists_obj = tecno_queries[4]
        
        mobiles = mobile_lists_obj.get('state', {}).get('data').get('results', [])
        mobile_urls = []
        # available_mobiles = list(filter(lambda mobile: mobile.get('available', 0), mobiles))
        page_number_flag = False
        for mobile in mobiles:
            if not mobile.get('available'):
                page_number_flag = True
                break
            mobile_title = mobile.get('name')
            mobile_code = mobile.get('code', '').split('-')[1]
            mobile_url = f"https://www.technolife.ir/product-{mobile_code}/{mobile_title.replace(' ','-').strip()}"
            mobile_urls.append(mobile_url)
            

        return mobile_urls, page_number_flag
    except Exception as e:
        print(f"Error in scraping {url}: {str(e)}")
        print('Error come from get_mobile_info (function)')
        return [], True

def main():
    phone_model_list = ['69_70_73/apple/',
                        '69_70_77/samsung',
                        '69_70_79/xiaomi',
                        '69_70_799/poco',
                        '69_70_80/nokia',
                        '69_70_780/motorola',
                        '69_70_798/huawei',
                        '69_70_74/honor',
                        '69_70_804/گوشی-موبایل-ریلمی-realme/',
                        '69_70_85/nothing-phone/']
    # phone_model_list = [ '69_70_80/nokia', ]


    mobile_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):

            url = f'https://www.technolife.ir/product/list/{phone_model}?page={i + 1}'
            mobile_urls, mobile_page_flag = get_mobile_info(HEADERS, url)
            mobile_all_urls.extend(mobile_urls)
            if mobile_page_flag:
                break
     
    print(mobile_all_urls)
    print(len(mobile_all_urls))
    return mobile_all_urls


if __name__ == "__main__":
    main()
