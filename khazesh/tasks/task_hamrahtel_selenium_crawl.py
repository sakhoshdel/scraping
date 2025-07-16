from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
import re
from .save_object_to_database import save_obj
from .save_crawler_status import update_code_execution_state
from celery import shared_task
from requests import Response
import traceback
from typing import Optional, Tuple, List, Dict
import time

from khazesh.models import Mobile
from django.utils import timezone

ResponseType = Optional[Response]


def extract_linear_gradient(css_text:str):  
    pattern = r"background:\s*(linear-gradient.*[^;])"

    match = re.search(pattern, css_text)  
    if match:  
        return match.group(1)  
    else:  
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
    
    vietnam_keys = ['Vietnam', 'Vietna', 'Viet', 'vietnam', 'viet', 'vietna']
    vietnam = any([True if vietnam_key in en_title else False for vietnam_key in vietnam_keys])
    not_active_keywords = ['non Active', 'Non Active', 'NON ACTIV']
    not_active =any([True if not_active_key in en_title else False for not_active_key in not_active_keywords])

    
    return en_title, not_active, vietnam, ram, memory

# #@shared_task(bind=True, max_retries=3)
def hamrahtel_crawler(self):
    try:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)

        Mobile.objects.filter(
            site = SITE,
            status = True,
            updated_at__lt=ten_min_ago,
        ).update(status=False)
        IGONRED_EXCEPTIONS = (NoSuchElementException, StaleElementReferenceException)
        SITE = 'Hamrahtel'
        GUARANTEE = 'ذکر نشده'
        SELLER = 'Hamrahtel'
        XPATH = '//div[2]/div[2]/main/div/div/div[2]/div/div/div/div[1]'

        URL = "https://hamrahtel.com/categories?category=mwbyl"


        BRANDS_KEYS = {
            'اپل': 'apple',
            'سامسونگ': 'samsung',
            'نوکیا': 'nokia',
            'شیائومی': 'xiaomi',
            'ریلمی': 'realme',
            'موتورولا': 'motorola',
            'ناتینگ فون': 'nothing',
            'آنر': 'honor',
            'هواوی': 'huawei'
        }
        # Initialize UserAgent and ChromeOptions
        chrome_options = webdriver.ChromeOptions()
        chrome_options.set_capability('browserless:token', 'seP9QYgrex2JLu96TTW')
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--headless")
        
        # Chrome options
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('window-size=2000x1080')
        chrome_options.add_argument('--headless')  # Optional: Comment this if you need a visible browser
        chrome_options.add_argument('--disable-gpu')  # Disable GPU acceleration in headless mode
        chrome_options.add_experimental_option("detach", True)  # Keep the browser open after script ends
        
        # Start WebDriver
        driver = webdriver.Remote(
            command_executor='https://chrome-bartardigital.liara.run/webdriver',
            options=chrome_options
        )
        driver.get(URL)
        
        time.sleep(4)
        
        # Scroll down the page until the end  
        last_height = driver.execute_script("return document.body.scrollHeight")  
        while True: 
            # Scroll down to the bottom of the page  
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")  

            # Wait for the page to load  
            time.sleep(2)  

            # Calculate the new scroll height and compare with the last scroll height  
            new_height = driver.execute_script("return document.body.scrollHeight")  
            if new_height == last_height:  
                break  
            last_height = new_height  
    
        
                
                
        box_element = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-sentry-component='ProductListContent']"))
    )
        
        #‌Todo This class name (mantine-1avyp1d) are can chnage potentially 
        elements = box_element.find_elements(By.CLASS_NAME, 'mantine-1avyp1d')
        each_product_page_url = []
        for element in elements:  
            a_tags = element.find_elements(By.TAG_NAME, 'a')  
            for a_tag in a_tags:  
                each_product_page_url.append(a_tag.get_attribute('href'))
        
        
        all_mobile_objects: List[Dict] = []
        for product_url in each_product_page_url:
            print(product_url)
            driver.get(product_url)
            driver.maximize_window()
            time.sleep(3.0)
            # driver.maximize_window()

        #‌Todo This class name (mantine-1bzvmv9) are can chnage potentially 

            try:  
                product_content = WebDriverWait(driver, 120, ignored_exceptions=IGONRED_EXCEPTIONS).until(  
                EC.visibility_of_element_located((By.CLASS_NAME, 'mantine-1bzvmv9'))  )
                time.sleep(3)  # Adjust the time as needed to ensure the content is fully loaded

                product_details = product_content.find_element(By.CLASS_NAME, 'mantine-11qe9uy')
                product_variants = product_content.find_element(By.CSS_SELECTOR, "[data-sentry-component='ProductVariants']")
                
                
            except StaleElementReferenceException:  
            # Handle the stale element exception, e.g., navigate back and re-find the element  
                driver.back()  
                product_content = WebDriverWait(driver, 120, ignored_exceptions=IGONRED_EXCEPTIONS).until(  
                    EC.visibility_of_element_located((By.CLASS_NAME, 'mantine-1bzvmv9'))  
                )  
                product_details = product_content.find_element(By.CLASS_NAME, 'mantine-11qe9uy')

                product_variants = product_content.find_element(By.CSS_SELECTOR, "[data-sentry-component='ProductVariants']")            
            
            
            mobile_object: Dict = {}
            
            
            en_title = product_details.find_element(By.TAG_NAME, 'h1').text
            _,  not_active, vietnam, ram, memory = extract_details(en_title)
            # print(en_title, not_active, vietnam, ram, memory, sep='\n')
            
            # find brand of mobile
            product_summery_info_lis = product_details\
                .find_element(By.CSS_SELECTOR,"[data-sentry-component='ProductSummeryInfo']")\
                    .find_elements(By.TAG_NAME, 'li')
                    
            brand = ''
            brand_el_txt = product_summery_info_lis[0].text.strip()
            for brand_key in BRANDS_KEYS:
                if brand_key in brand_el_txt:
                    brand = BRANDS_KEYS[brand_key]
    
                
            if not brand:
                print(f'This brand not supported => {brand_el_txt}')
                continue
            
            mobile_object['url'] = product_url
            mobile_object['title'] = en_title
            mobile_object['model'] = en_title
            mobile_object['memory'] = memory
            mobile_object['ram'] = ram
            mobile_object['brand'] = brand.capitalize()
            mobile_object['vietnam'] = vietnam
            mobile_object['not_active'] = not_active
            mobile_object['mobile_digi_id'] = ''
            mobile_object['dual_sim'] = True
            mobile_object['active'] = True     
            mobile_object['max_price'] = 1
            mobile_object['site'] = SITE
            mobile_object['seller'] = SELLER
            mobile_object['guarantee'] = GUARANTEE
                
            # print(mobile_object)
            
                        
            #‌ Producc varinast 
            product_price_variants = product_variants.find_elements(By.CLASS_NAME, 'mantine-1avyp1d')
            for p in product_price_variants:
                if brand == 'nokia':
                    print(p.text)
                    print( 'تومان' in p.text)
            product_price_variants = filter(lambda price_el: 'تومان' in price_el.text  ,product_price_variants)
            
            # print(list (product_price_variants))
            color_hex = ''
            color_name = ''
            min_price = ''
            for price_el in product_price_variants:
                color_name = price_el.find_element(By.CLASS_NAME, 'mantine-rj9ps7').text.strip()
                color_hex = price_el.find_element(By.CLASS_NAME, "mantine-1avyp1d").get_attribute('style')
                color_hex = extract_linear_gradient(color_hex)
                # print('color_hex: ', color_hex)
                # print('color_name: ', color_name)
                min_price = price_el.find_element(By.CLASS_NAME, 'mantine-1n96e1r').text.strip().replace('٬', '')
                
                
                    # print('min_price: ', min_price)
                all_mobile_objects.append({
                        'color_name': color_name,
                        'color_hex': color_hex,
                        'min_price': int(min_price) * 10,
                        **mobile_object
                    }) 
            # time.sleep(2) 
            # soup = BeautifulSoup(product_content.text,'html.parser' )
            # print('*' * 50)
            # product_content.screenshot('screeeee.png')
            # print(product_content.text)
            
        
        # print(all_mobile_objects)
        print('len(all_mobile_objects)', len(all_mobile_objects))
        
        
        
        
        
        for mobile_dict in all_mobile_objects:
            save_obj(mobile_dict)
        
        
        update_code_execution_state(SITE, success=True)
        
        
        driver.quit()
        
        
        
    except Exception as e:
        error_message = str(traceback.format_exc())
        print(f"Error {error_message}")
        update_code_execution_state(SITE, False, error_message)

