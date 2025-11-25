from datetime import datetime, time
import traceback
# from django.utils import timezone
import pytz

from celery import chain, group, shared_task, chord
import requests
from requests.exceptions import RequestException, ConnectionError
from requests import Response
from .save_crawler_status import update_code_execution_state
from .save_accessories_crawler_status import accessories_update_code_execution_state

# Crawlers
# Kasra
from .task_accessories_watchs_kasra_crawl import accessories_watchs_kasra_crawler
from .task_accessories_handsfree_kasra_crawl import accessories_handsfree_kasra_crawler
from .task_accessories_powerbank_kasra_crawl import accessories_powerbank_kasra_crawler
from .task_accessories_charger_kasra_crawl import accessories_charger_kasra_crawler
from .task_accessories_speaker_kasra_crawl import accessories_speaker_kasra_crawler

# Mobile 140
from .task_accessories_watchs_mobile140_crawl import accessories_watchs_mobile140_crawler
from .task_accessories_handsfree_mobile140_crawl import accessories_handsfree_mobile140_crawler
from .task_accessories_powerbank_mobile140_crawl import accessories_powerbank_mobile140_crawler
from .task_accessories_charger_mobile140_crawl import accessories_charger_mobile140_crawler
from .task_accessories_speaker_mobile140_crawl import accessories_speaker_mobile140_crawler

# Tecnolife
from .task_accessories_watchs_tecnolife_crawl import accessories_watchs_tecnolife_crawler
from .task_accessories_handsfree_tecnolife_crawl import accessories_handsfree_tecnolife_crawler
from .task_accessories_powerbank_tecnolife_crawl import accessories_powerbank_tecnolife_crawler
from .task_accessories_charger_tecnolife_crawl import accessories_charger_tecnolife_crawler
from .task_accessories_speaker_tecnolife_crawl import accessories_speaker_tecnolife_crawler

# Hamrahtel
from .task_accessories_watchs_hamrahtel_crawl import accessories_watchs_hamrahtel_crawler
from .task_accessories_handsfree_hamrahtel_crawl import accessories_handsfree_hamrahtel_crawler
from .task_accessories_powerbank_hamrahtel_crawl import accessories_powerbank_hamrahtel_crawler
from .task_accessories_charger_hamrahtel_crawl import accessories_charger_hamrahtel_crawler
from .task_accessories_speaker_hamrahtel_crawl import accessories_speaker_hamrahtel_crawler

# Digikala
from .task_accessories_watchs_digikala_crawl import accessories_watchs_digikala_crawler
from .task_accessories_handsfree_digikala_crawl import accessories_handsfree_digikala_crawler
from .task_accessories_powerbank_digikala_crawl import accessories_powerbank_digikala_crawler
from .task_accessories_speaker_digikala_crawl import accessories_speaker_digikala_crawler
from .task_accessories_charger_digikala_crawl import accessories_charger_digikala_crawler


# Mobile
from .task_mobomin_crawl import mobomin_crawler
from .task_digikala_crawl import digikala_crawler
from .task_hamrahtel_graphql_crawl import hamrahtel_crawler
from .task_kassa_crawl import kassa_crawler
from .task_mobile140_crawl import mobile140_crawler
from .task_saymandigital_crawl import saymandigital_crawler
from .task_taavrizh_crawl import taavrizh_crawler
from .task_tecnolife_crawl import tecnolife_crawler
from .task_tellstar_crawl import tellstar_crawler


# Tablet 
from .task_tablet_hamrahtel_graphql_crawl import tablet_hamrahtel_crawler
from .task_tablet_mobile140_crawl import tablet_mobile140_crawler
from .task_tablet_kassa_crawl import tablet_kassa_crawler
from .task_tablet_digikala_crawl import tablet_digikala_crawler
from .task_tablet_tecnolife_crawl import tablet_tecnolife_crawler
from .task_tablet_darsoo_crawl import tablet_darsoo_crawler




local_tz = pytz.timezone("Asia/Tehran")



@shared_task
def error_handler(task_id, exc, traceback, site_name):

    error_message = str(traceback.format_exc())
    update_code_execution_state(site_name, False, error_message)
    print(f"Error {error_message}")

@shared_task
def accessories_error_handler(task_id, exc, traceback, site_name, category):

    error_message = 'error'
    accessories_update_code_execution_state(site_name, category, False, error_message)
    print(f"Error {error_message}")
    
    
@shared_task
def notify_after_crawl(results):
    valid_results = [r for r in results if r and isinstance(r, dict)]

    if not valid_results:
        print(":no_entry: هیچ نتیجه موفقی وجود ندارد.")
        return 'No valid results'

    # ارسال نتایج به API خارجی
    payload = {'results': valid_results}
    try:
        res = requests.get("https://bartardigital.com/wp-json/bdap/v1/update-prices?key=NYb2RdV2RauMJosg1", json=payload, timeout=1000)
        print(f":white_check_mark: اطلاع‌رسانی انجام شد: {res.status_code}")
        return res.status_code
    except Exception as e:
        print(f":x: خطا در ارسال به API خارجی: {e}")
        return 'Notify failed'


@shared_task
def start_main_crawlers(*args, **kwargs):
    REST_TIME = 60

    # ساختن لیست crawler تسک‌ها
    main_group = group(
        hamrahtel_crawler.si().set(countdown=REST_TIME),
        mobile140_crawler.si().set(countdown=REST_TIME),
        kassa_crawler.si().set(countdown=REST_TIME),
        saymandigital_crawler.si().set(countdown=REST_TIME),
        digikala_crawler.si().set(countdown=REST_TIME),
        tecnolife_crawler.si().set(countdown=REST_TIME),
        taavrizh_crawler.si().set(countdown=REST_TIME),
        tellstar_crawler.si().set(countdown=REST_TIME),
        mobomin_crawler.si().set(countdown=REST_TIME),
    )

    main_group.apply_async(queue='main_crawler_queue')

    return "✅ chains started: [main]"



    


@shared_task
def start_secondary_crawlers(*args, **kwargs):
    REST_TIME = 1 * 60  # secends
    
    
    # -----------------------
    # ✅ CHAIN 2 - سایت‌های فرعی
    # -----------------------
    secondary_group = group(
        # Tablet
        tablet_hamrahtel_crawler.si().set(countdown=REST_TIME).on_error(error_handler.s("Hamrahtel-tablet")),
        tablet_mobile140_crawler.si().set(countdown=REST_TIME).on_error(error_handler.s("Mobile140-tablet")),
        tablet_kassa_crawler.si().set(countdown=REST_TIME).on_error(error_handler.s("Kasrapars-tablet")),
        tablet_digikala_crawler.si().set(countdown=REST_TIME).on_error(error_handler.s("Digikala-tablet")),
        tablet_tecnolife_crawler.si().set(countdown=REST_TIME).on_error(error_handler.s("Tecnolife-tablet")),
        tablet_darsoo_crawler.si().set(countdown=REST_TIME).on_error(error_handler.s("Darsoo-tablet")),

        # Kasra
        accessories_watchs_kasra_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Kasrapars', 'watchs')),
        accessories_handsfree_kasra_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Kasrapars', 'handsfree')),
        accessories_powerbank_kasra_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Kasrapars', 'powerbank')),
        accessories_charger_kasra_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Kasrapars', 'charger')),
        accessories_speaker_kasra_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Kasrapars', 'speaker')),
        
        # Mobile 140
        accessories_watchs_mobile140_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Mobile140', 'watchs')),
        accessories_handsfree_mobile140_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Mobile140', 'handsfree')),
        accessories_powerbank_mobile140_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Mobile140', 'powerbank')),
        accessories_charger_mobile140_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Mobile140', 'charger')),
        accessories_speaker_mobile140_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Mobile140', 'speaker')),
    
        # Tecnolife
        accessories_watchs_tecnolife_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Tecnolife', 'watchs')),
        accessories_handsfree_tecnolife_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Tecnolife', 'handsfree')),
        accessories_powerbank_tecnolife_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Tecnolife', 'powerbank')),
        accessories_charger_tecnolife_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Tecnolife', 'charger')),
        accessories_speaker_tecnolife_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Tecnolife', 'speaker')),

        # Hamrahtel
        accessories_watchs_hamrahtel_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Hamrahtel', 'watchs')),
        accessories_handsfree_hamrahtel_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Hamrahtel', 'handsfree')),
        accessories_powerbank_hamrahtel_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Hamrahtel', 'powerbank')),
        accessories_charger_hamrahtel_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Hamrahtel', 'charger')),
        accessories_speaker_hamrahtel_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Hamrahtel', 'speaker')),
    
        # Digikala
        accessories_watchs_digikala_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Digikala', 'watchs')),
        accessories_handsfree_digikala_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Digikala', 'handsfree')),
        accessories_powerbank_digikala_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Digikala', 'powerbank')),
        accessories_charger_digikala_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Digikala', 'charger')),
        accessories_speaker_digikala_crawler.si().set(countdown=REST_TIME).on_error(accessories_error_handler.s('Digikala', 'speaker')),    

    )


    
    secondary_group.apply_async(queue='secondary_crawler_queue')

    return "✅ chains started: [secondary]"
    
