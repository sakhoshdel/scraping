from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
import urllib.parse
from requests import Response
import requests
import logging
import time 
from typing import List,Dict, Tuple, Optional
import re
import csv

ResponseType = Optional[Response]

def retry_request(url: str, max_retries: int = 1, retry_delay: int = 1, headers='') -> ResponseType:
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

def extract_details(en_title: str,) -> Tuple[Optional[str]]:
    # Define patterns
    en_model_pattern  = r'.*?(?=\b\d{1,3}(GB|MB|TB|G|M|T)\b)'
    memory_ram_pattern = r'(\d+GB)(?:\sRAM\s(\d+GB))?'
    ram = 'ندارد'
    memory = 'ندارد'
    
    match = re.search(memory_ram_pattern, en_title)
    if match:
        memory = match.group(1)
        ram = match.group(2)

    # Extract model from English title
    model = re.search(en_model_pattern, en_title)
    if model:
        model = model.group(0).strip()
    else:
        model =  en_title
    
    
    
    
    vietnam_keys = ['Vietnam', 'Vietna', 'Viet', 'vietnam', 'viet', 'vietna']
    vietnam = any([True if vietnam_key in en_title else False for vietnam_key in vietnam_keys])
    not_active_keywords = ['non Active', 'Non Active', 'NON ACTIV']
    not_active =any([True if not_active_key in en_title else False for not_active_key in not_active_keywords])

    
    return model, not_active, vietnam, ram, memory

def fetch_bearer_token(url, email):
    try:
        # Initialize UserAgent and ChromeOptions
        chrome_options = webdriver.ChromeOptions()
        chrome_options.set_capability('browserless:token', 'seP9QYgrex2JLu96TTW')
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('window-size=1920x1080')
        chrome_options.add_argument('--disable-gpu')  # Disable GPU acceleration in headless mode
        chrome_options.add_experimental_option("detach", True)  # Keep the browser open after script ends

        driver = webdriver.Remote(
            command_executor='https://chrome-bartardigital.liara.run/webdriver',
            options=chrome_options
        )

        # Open the target website
        driver.get(url)
        
        # Extract cookies and find the LUNA_AUTH token
        cookies = driver.get_cookies()
        encoded_token = next((cookie['value'] for cookie in cookies if cookie['name'] == 'LUNA_AUTH'), None)
        
        # Close the browser
        driver.quit()
        
        # If token is found, decode it
        if encoded_token:
            bearer_token = urllib.parse.unquote(encoded_token)
            print(f"Decoded Bearer Token: {bearer_token}")
            return bearer_token
        else:
            print("Bearer token not found.")
            return None

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return None

bearer_token = fetch_bearer_token('https://hamrahtel.com/', 'behnammohammadi149@gmail.com')

if not bearer_token:
    print("Failed to fetch bearer token. Exiting...")
    exit()  # Exit the script if the token was not found

SITE = 'Hamrahtel'
GUARANTEE = 'ذکر نشده'
SELLER = 'Hamrahtel'

HEADERS = {
    'From': 'behnammohammadi149@gmail.com', 
    'Authorization': bearer_token
    }

# HEADERS = {
#     'From': 'behnammohammadi149@gmail.com', 
#     'Authorization': "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuYmYiOiIxNzI1ODQyMTkwIiwiZXhwIjoiMTcyNjcwNjE5MCIsImh0dHA6Ly9zY2hlbWFzLnhtbHNvYXAub3JnL3dzLzIwMDUvMDUvaWRlbnRpdHkvY2xhaW1zL2VtYWlsYWRkcmVzcyI6IjliY2ZmOTUxLWE0ZTAtNDNlOC05ZDVhLWU0OWVjZWEyZmZmNiIsImh0dHA6Ly9zY2hlbWFzLnhtbHNvYXAub3JnL3dzLzIwMDUvMDUvaWRlbnRpdHkvY2xhaW1zL25hbWVpZGVudGlmaWVyIjoiOWJjZmY5NTEtYTRlMC00M2U4LTlkNWEtZTQ5ZWNlYTJmZmY2IiwiaHR0cDovL3NjaGVtYXMueG1sc29hcC5vcmcvd3MvMjAwNS8wNS9pZGVudGl0eS9jbGFpbXMvbmFtZSI6IjliY2ZmOTUxLWE0ZTAtNDNlOC05ZDVhLWU0OWVjZWEyZmZmNiIsIkN1c3RvbWVySWQiOiI3NTkwMzQ0NSJ9.FLvYZ3Y_fSFuzs4bzDlBBUJnxHEIXONM-TUFyb9xVEw"
#     }

HAMRAHTEL_BRAND_IDES = {
    '65': 'xiaomi',
    '48': 'samsung',
    '66': 'apple',
    '69': 'nokia',
    '111':'honor',
    '115': 'realme',
    '133': 'nothing-phone',
    
}
crowled_mobile_brands_ides: List[str] = ['66', '48', '65', '69', '111','115', '133']


all_mobile_ides :List[str]= []
for brand_id in crowled_mobile_brands_ides:
    url =  f'https://app.hamrahtel.com/api/categories/{brand_id}/products/?'
    response = retry_request(url, headers=HEADERS)
    
    if not response:
            print(f"Response for {HAMRAHTEL_BRAND_IDES[brand_id]} is None ")
            continue
        
    mobiles = response.json().get('products')
    for mobile in mobiles:
        if not mobile.get('in_stock', ''):
            continue
        
        all_mobile_ides.append((mobile.get('id', ''), HAMRAHTEL_BRAND_IDES[brand_id]))

     
all_mobile_objects: List[Dict] = []


for mobile_id, brand in all_mobile_ides:
    res = retry_request(f'https://app.hamrahtel.com/api/products/{mobile_id}', headers=HEADERS)

    if not res:
        print(f"Response for {brand} is None ")
        continue
    
    mobile_details_obj = res.json().get('products')
    if not mobile_details_obj:
        print(f"There is no mobile_details for {mobile_id}")
        continue
    
    mobile_details_obj = mobile_details_obj[0]
    # print(mobile_details_obj)
    
    
    mobile_object: Dict = {}
    
    en_title = mobile_details_obj.get('name')
    if not en_title:
        # print(mobile_details_obj)
        continue
    model, not_active, vietnam, ram, memory = extract_details(en_title)
    
    if brand == 'apple':
        encoded_short_description = mobile_details_obj.get('short_description', '')
        # short_description = encoded_short_description.encode().decode('unicode_escape')
        short_description = encoded_short_description.encode().decode()
        print("short_description", short_description)
        ram_pattern = r'(\d+)\s*گیگابایت\s*رم'
        ram_match = re.search(ram_pattern, short_description)
        if ram_match:
            ram = ram_match.group(1) + 'GB'  # Group 1 captures the number
            print(f"Extracted RAM number: {ram}")
            
        print("rammmmmmm", ram)
        
    mobile_object['model'] = model
    mobile_object['memory'] = memory
    mobile_object['ram'] = ram
    mobile_object['brand'] = brand.capitalize()
    mobile_object['vietnam'] = vietnam
    mobile_object['not_active'] = not_active
    # mobile_object['title_en'] = en_title
    mobile_object['title'] = en_title
    uurl = f"https://hamrahtel.com/product/lpd-{mobile_id}/{en_title.replace(' ', '-').replace('/', '-').lower()}/"
    mobile_object['url'] = uurl
    mobile_object['site'] = SITE
    mobile_object['seller'] = SELLER
    mobile_object['guarantee'] = GUARANTEE
    mobile_object['max_price'] = 1
    mobile_object['mobile_digi_id'] = ''
    mobile_object['dual_sim'] = True
    mobile_object['active'] = True            
           
    # print(en_title)
    # print(uurl)
    # print(mobile_details_obj.get('attributes', []))
    # print('$' * 100)
    single_mobile_attributes = mobile_details_obj.get('attributes', [])
    if not single_mobile_attributes:
        continue
    attributes: List[Dict]= single_mobile_attributes[0].get('attribute_values', [])
    if not attributes:
        continue
    
    for attribute in attributes:
        if not attribute.get('in_stock'):
            continue
        
        print(model,memory, ram, vietnam, not_active, attribute.get('name'),
              int(attribute.get('final_price_value', 0)) * 10, sep='#', end='\n')
        all_mobile_objects.append({
            'color_name': attribute.get('name'),
            'color_hex': attribute.get('color_squares_rgb'),
            'min_price': int(attribute.get('final_price_value', 0)) * 10,
            **mobile_object
        })

        
with open('hamrahtel.csv', 'w', newline='') as f:
    writer = csv.writer(f)

    # get one of the object from list and extract keys
    writer.writerow(list(all_mobile_objects[0].keys()))
    for mobie_obj in all_mobile_objects:
        writer.writerow(list(mobie_obj.values()))
