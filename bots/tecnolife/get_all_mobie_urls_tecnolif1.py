import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from lxml import etree
import logging
import time
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait 
from selenium.webdriver.support import expected_conditions as EC 
logging.basicConfig(filename='error.log', level=logging.ERROR)


def retry_request(url: str, headers, max_retries: int = 3, retry_delay: int = 1):
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

# service = Service(ChromeDriverManager().install())
# service = Service(executable_path='/usr/bin/chromedriver')
# options = ChromeOptions()

# options.add_argument('--disable-notifications')
# options.add_argument('window-size=1920x1080')
# # options.add_argument('--headless')  # Optional: Comment this if you need a visible browser
# # options.add_argument('--disable-gpu')  # Disable GPU acceleration in headless mode
# options.add_experimental_option("detach", True)  # Keep the browser open after script ends


def get_mobile_info(url):
    ua = UserAgent()
    # options.add_argument(f'user-agent={ua["google"]}')  # Set a proper user-agent string
    # driver = Chrome(service=service, options=options)
    
    try:
        # driver.get(url)
        #         # Wait until the specific CSS file is loaded
        # css_file_url = "https://www.technolife.ir/_next/static/css/bb0e1b340ba5f383.css"  # Replace with your target CSS file URL
        # WebDriverWait(driver, 30).until(
        #     lambda driver: driver.execute_script(
        #         f'return [...document.styleSheets].some(sheet => sheet.href === "{css_file_url}");'
        #     )
        # )
        
        
        # # Increase timeout and use a more specific wait condition if needed
        # WebDriverWait(driver, 30).until(
        #     EC.presence_of_element_located((By.CSS_SELECTOR, 'article'))
        # )
        # Debugging: Print page source to check if content is loaded
        # print(driver.page_source)

        # soup = BeautifulSoup(driver.page_source, 'html.parser')
        # soup = BeautifulSoup(driver.page_source, 'html.parser')
        # mobiles_box = soup.find('article')
        
        if mobiles_box:
            mobiles = mobiles_box.find_all('section')
            mobile_urls = []
            print('len(mobiles)', len(mobiles))
            if mobiles:
                mobile_section = mobiles[0]
                print(len(mobile_section.find_all('div', recursive=False)))
                
                with open('div.html', 'a') as f:
                    f.write(str(mobile_section.find_all('div', recursive=False)))
                    f.write('#' * 30)
                
                return mobile_urls, False

        return [], False

    except Exception as e:
        logging.error(f"Error in scraping {url}: {str(e)}")
        return [], False
    finally:
        driver.quit()

    # except Exception as e:
    #     print(f"Error in scraping {url}: {str(e)}")
    #     print('Error come from get_mobile_info (function)')
    #     return []

# mobile_urls, outer_for_break = get_mobile_info("https://www.technolife.ir/69_70_73/apple/")
def main():
    phone_model_list = ['69_70_73/apple/', '69_70_77/samsung',
                        '69_70_79/xiaomi', '69_70_799/poco',
                        '69_70_80/nokia', '69_70_780/motorola',
                        '69_70_798/huawei', '69_70_74/honor',
                        '69_70_804/گوشی-موبایل-ریلمی-realme',
                        '69_70_85/nothing-phone']
    # phone_model_list = ['69_70_80/nokia', ]

    mobile_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):

            url = f'https://www.technolife.ir/product/list/{phone_model}?page={i + 1}'
            print('phome_model', phone_model)
            mobile_urls, outer_for_flag = get_mobile_info(url)
            if outer_for_flag:
                break

            mobile_all_urls.extend(mobile_urls)
    # print(mobile_all_urls)
    print("len(mobile_all_urls)", len(mobile_all_urls))
    return mobile_all_urls


if __name__ == "__main__":
    main()
