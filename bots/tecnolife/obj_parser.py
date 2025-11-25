from get_all_mobie_urls_tecnolif import HEADERS, main, BeautifulSoup, retry_request
import json
import csv
import time


def retry_main(max_retries=3, delay=5):
    retries = 0
    all_mobile_urls = main()
    while len(all_mobile_urls) == 0 and retries < max_retries:
        print(f"Retrying... attempt {retries + 1}")
        time.sleep(delay)
        all_mobile_urls = main()
        retries += 1

    if len(all_mobile_urls) == 0:
        raise Exception("No mobile URLs found after maximum retries")
    
    return all_mobile_urls


all_mobile_urls = retry_main()

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
        print("Invalid format for memory value:", memory_ram)
        return 'ندارد'
    
    print('memory_ram', memory_ram)
    memory_ram_1 = memory_ram[1].replace('،', '').replace('\n', '').strip()
    memory_ram_0 = memory_ram[0].replace('،', '').replace('\n', '').strip()
    
    for key, value in kilo_mega_giga_tra.items():
        if memory_ram and key == memory_ram_1:
            print('kilo_mega_giga_tra')
            memory_ram[1] = value
        elif memory_ram and key == memory_ram_0:
            memory_ram[0] = value
            print('kilo_mega_giga_tra')

    for key, value in letter_to_digit_obj.items():
        if memory_ram and key == memory_ram[0]:
            print('#' * 80)
            print("letter_to_digit_obj1111")
            print(memory_ram)
            print('#' * 80)
            memory_ram[0] = value
            memory_ram = ''.join(memory_ram[:2])
        elif memory_ram and key == memory_ram[1]:
            print('#' * 80)
            print('letter_to_digit_obj')
            print(memory_ram)
            print('#' * 80)
            memory_ram[1] = value
            memory_ram = ''.join(memory_ram[:2])

    return memory_ram


def set_other_obj_data(other_data_obj):
    en_title = mobile_obj['product_info']['model'].split(' ')
    fa_title = mobile_obj['product_info']['title']
    other_data_obj['title'] = fa_title
    other_data_obj['vietnam'] = True if 'Vietnam' in en_title else False
    brand = en_title[0]
    other_data_obj['brand'] = 'xiaomi' if brand in ['poco', 'Poco'] else brand
    # print(other_data_obj['brand'])
    other_data_obj['model'] = extract_model_form_title_en(en_title)
    other_data_obj['active'] = True
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
all_mobiles_objects = []
# try:
for url in all_mobile_urls:
    # try:
    res = retry_request(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')

    obj = soup.find('script', {'id': '__NEXT_DATA__'}).get_text()
    obj = json.loads(obj)
    print(type(obj))
    mobile_obj = obj['props']['pageProps']['dehydratedState']['queries'][0]['state']['data']
    # print(seller_items)

    all_color_bojects = []
    same_color_seller_obj = []
    # find same collor mobiles and select min price
    for obj in mobile_obj['seller_items_component']:
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
    for same_color_mobiles in all_color_bojects:
        min_price_obj = min(same_color_mobiles, key=lambda x: x['min_price'])

        last_mobil_objests.append(min_price_obj)

    other_data_obj = {}
    for obj in mobile_obj['configurations_component']:
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
    set_other_obj_data(other_data_obj)

    for mobile in last_mobil_objests:
        mobile.update(other_data_obj)

    all_mobiles_objects.extend(last_mobil_objests)

# except Exception as e:
#     print(f'error {e}')
        # update_code_execution_state('Tecnolife', False, str(e))

# update_code_execution_state('Tecnolife', True)



# print(all_mobiles_objects)

# try:
with open('tecnolife_.csv', 'w', newline='') as f:
    writer = csv.writer(f)

    # get one of the object from list and extract keys
    writer.writerow(list(all_mobiles_objects[0].keys()))
    for mobie_obj in all_mobiles_objects:
        writer.writerow(list(mobie_obj.values()))
    
# except Exception as e:
    # update_code_execution_state('Tecnolife', False, str(e))
        
# except Exception as e:
#     print(f'Critical error: {e}')
#     # update_code_execution_state('Tecnolife', False, str(e)) 