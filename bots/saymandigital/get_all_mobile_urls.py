import requests
from bs4 import BeautifulSoup


HEADERS = {
    'From': 'behnammohammadi149@gmail.com', }
def get_mobile_info(headers,url):
    try:
        res = requests.get(url=url, headers=headers).text
        content = BeautifulSoup(res, 'html.parser')
        mobiles_box = content.find('div', {'id': "type-card-products"})
        mobiles = mobiles_box.select('div.col-6.col-lg-4.col-xl-4.col-xxl-3')
        mobile_urls = []

        for mobile in mobiles:

            mobile_price = mobile.find(
                'div', class_="product-price").find('span', class_='total-price').get_text()

            if 'نا‌موجود' in mobile_price:
                break

            mobile_url = mobile.find('a')['href']
            mobile_urls.append((mobile_url, mobile_price.strip()))

        return mobile_urls
    except Exception as e:
        print(f"Error in scraping {url}: {str(e)}")
        print('Error come from get_mobile_info (function)')
        return []


def main():
    phone_model_list = ['اپل', 'سامسونگ', 'شیائومی',
    'هواوی', 'نوکیا', 'honor', 'realme','motorola', 'گوشی-ناتینگ-فون', ]

    mobile_all_urls = []
    for phone_model in phone_model_list:
        for i in range(4):

            url = f'https://saymandigital.com/محصولات/{phone_model}/?page={i + 1}'
            mobile_urls = get_mobile_info(HEADERS, url)

            mobile_all_urls.extend(mobile_urls)
    print(mobile_all_urls)
    print(len(mobile_all_urls))
    return mobile_all_urls


if __name__ == "__main__":
    main()
