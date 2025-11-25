from datetime import datetime
import traceback
import pytz
import time
import requests
from celery import group, chord, shared_task

from .save_crawler_status import update_code_execution_state
from .save_accessories_crawler_status import accessories_update_code_execution_state
from .save_laptop_crawler_status import laptop_update_code_execution_state


# -------------------------
# تنظیمات پایه
# -------------------------
local_tz = pytz.timezone("Asia/Tehran")

# -------------------------
# Error handlers
# -------------------------
@shared_task
def error_handler(request, exc, tb_str, site_name):
    """
    هندل خطا برای موبایل، تبلت 
    """
    error_message = f"{type(exc).__name__}: {str(exc)}"
    update_code_execution_state(site_name, False, error_message)
    print(f"❌ [{site_name}] Error: {error_message}")

@shared_task
def accessories_error_handler(request, exc, tb_str, site_name, category):
    error_message = f"{type(exc).__name__}: {str(exc)}"
    accessories_update_code_execution_state(site_name, category, False, error_message)
    print(f"❌ [{site_name} - {category}] Error: {error_message}")


@shared_task
def laptop_error_handler(request, exc, tb_str, site_name):
    """
    هندل خطا برای کرول‌های لپ‌تاپ
    """
    error_message = f"{type(exc).__name__}: {str(exc)}"
    laptop_update_code_execution_state(site_name, False, error_message)
    print(f"❌ [Laptop - {site_name}] Error: {error_message}")

# -------------------------
# Notify Task
# -------------------------
@shared_task
def notify_bartar_digital(results=None):
    url = "https://bartardigital.com/wp-json/bdap/v1/update-prices"
    params = {"key": "NYb2RdV2RauMJosg1", "_ts": int(time.time())}
    try:
        res = requests.get(url, params=params, timeout=300)
        res.raise_for_status()
        print("✅ Notify sent to BartarDigital:", res.text)
        return res.text or ""
    except Exception as e:
        print("❌ Notify failed:", e)
        return str(e)


# -------------------------
# Helper برای chord
# -------------------------
def run_group_with_notify(tasks, queue_name):
    crawler_group = group([t.set(queue=queue_name) for t in tasks])
    chord(crawler_group)(notify_bartar_digital.s().set(queue=queue_name))
    return f"✅ group started: [{queue_name}]"


# -------------------------
# Mobile
# -------------------------
from .task_mobomin_crawl import mobomin_crawler
from .task_digikala_crawl import digikala_crawler
from .task_hamrahtel_graphql_crawl import hamrahtel_crawler
from .task_kassa_crawl import kassa_crawler
from .task_mobile140_crawl import mobile140_crawler
from .task_saymandigital_crawl import saymandigital_crawler
from .task_tecnolife_crawl import tecnolife_crawler
from .task_tellstar_crawl import tellstar_crawler

@shared_task
def start_mobile_crawlers(*args, **kwargs):
    tasks = [
        hamrahtel_crawler.si(),
        mobile140_crawler.si(),
        kassa_crawler.si(),
        saymandigital_crawler.si(),
        digikala_crawler.si(),
        tecnolife_crawler.si(),
        tellstar_crawler.si(),
        mobomin_crawler.si(),
    ]
    return run_group_with_notify(tasks, "mobile_crawler_queue")


# -------------------------
# Laptop
# -------------------------
from .task_laptop_tecnolife_crawl import laptop_tecnolife_crawler
from .task_laptop_hamrahtel_crawl import laptop_hamrahtel_crawler
from .task_laptop_digikala_crawl import laptop_digikala_crawler
from .task_laptop_etminantel_ceawl import laptop_etminantel_crawler

@shared_task
def start_laptop_crawlers(*args, **kwargs):
    tasks = [
        laptop_tecnolife_crawler.si().on_error(laptop_error_handler.s("Tecnolife")),
        laptop_hamrahtel_crawler.si().on_error(laptop_error_handler.s("Hamrahtel")),
        laptop_digikala_crawler.si().on_error(laptop_error_handler.s("Digikala")),
        laptop_etminantel_crawler.si().on_error(laptop_error_handler.s("Etminantel")),
    ]
    return run_group_with_notify(tasks, "laptop_crawler_queue")


# -------------------------
# Tablet
# -------------------------
from .task_tablet_hamrahtel_graphql_crawl import tablet_hamrahtel_crawler
from .task_tablet_mobile140_crawl import tablet_mobile140_crawler
from .task_tablet_kassa_crawl import tablet_kassa_crawler
from .task_tablet_digikala_crawl import tablet_digikala_crawler
from .task_tablet_tecnolife_crawl import tablet_tecnolife_crawler
from .task_tablet_darsoo_crawl import tablet_darsoo_crawler
from .task_tablet_etminantel_crawl import tablet_etminantel_crawler


@shared_task
def start_tablet_crawlers(*args, **kwargs):
    tasks = [
        tablet_hamrahtel_crawler.si().on_error(error_handler.s("Hamrahtel-tablet")),
        tablet_mobile140_crawler.si().on_error(error_handler.s("Mobile140-tablet")),
        tablet_kassa_crawler.si().on_error(error_handler.s("Kasrapars-tablet")),
        tablet_digikala_crawler.si().on_error(error_handler.s("Digikala-tablet")),
        tablet_tecnolife_crawler.si().on_error(error_handler.s("Tecnolife-tablet")),
        tablet_darsoo_crawler.si().on_error(error_handler.s("Darsoo-tablet")),
        tablet_etminantel_crawler.si().on_error(error_handler.s("Etminantel-tablet")),
        
    ]
    return run_group_with_notify(tasks, "tablet_crawler_queue")


# -------------------------
# Watch
# -------------------------
from .task_accessories_watchs_kasra_crawl import accessories_watchs_kasra_crawler
from .task_accessories_watchs_mobile140_crawl import accessories_watchs_mobile140_crawler
from .task_accessories_watchs_tecnolife_crawl import accessories_watchs_tecnolife_crawler
from .task_accessories_watchs_hamrahtel_crawl import accessories_watchs_hamrahtel_crawler
from .task_accessories_watchs_digikala_crawl import accessories_watchs_digikala_crawler

@shared_task
def start_watch_crawlers(*args, **kwargs):
    tasks = [
        accessories_watchs_kasra_crawler.si().on_error(accessories_error_handler.s("Kasrapars", "watchs")),
        accessories_watchs_mobile140_crawler.si().on_error(accessories_error_handler.s("Mobile140", "watchs")),
        accessories_watchs_tecnolife_crawler.si().on_error(accessories_error_handler.s("Tecnolife", "watchs")),
        accessories_watchs_hamrahtel_crawler.si().on_error(accessories_error_handler.s("Hamrahtel", "watchs")),
        accessories_watchs_digikala_crawler.si().on_error(accessories_error_handler.s("Digikala", "watchs")),
    ]
    return run_group_with_notify(tasks, "watch_crawler_queue")


# -------------------------
# Handsfree
# -------------------------
from .task_accessories_handsfree_kasra_crawl import accessories_handsfree_kasra_crawler
from .task_accessories_handsfree_mobile140_crawl import accessories_handsfree_mobile140_crawler
from .task_accessories_handsfree_tecnolife_crawl import accessories_handsfree_tecnolife_crawler
from .task_accessories_handsfree_hamrahtel_crawl import accessories_handsfree_hamrahtel_crawler
from .task_accessories_handsfree_digikala_crawl import accessories_handsfree_digikala_crawler

@shared_task
def start_handsfree_crawlers(*args, **kwargs):
    tasks = [
        accessories_handsfree_kasra_crawler.si().on_error(accessories_error_handler.s("Kasrapars", "handsfree")),
        accessories_handsfree_mobile140_crawler.si().on_error(accessories_error_handler.s("Mobile140", "handsfree")),
        accessories_handsfree_tecnolife_crawler.si().on_error(accessories_error_handler.s("Tecnolife", "handsfree")),
        accessories_handsfree_hamrahtel_crawler.si().on_error(accessories_error_handler.s("Hamrahtel", "handsfree")),
        accessories_handsfree_digikala_crawler.si().on_error(accessories_error_handler.s("Digikala", "handsfree")),
    ]
    return run_group_with_notify(tasks, "handsfree_crawler_queue")


# -------------------------
# Powerbank
# -------------------------
from .task_accessories_powerbank_kasra_crawl import accessories_powerbank_kasra_crawler
from .task_accessories_powerbank_mobile140_crawl import accessories_powerbank_mobile140_crawler
from .task_accessories_powerbank_tecnolife_crawl import accessories_powerbank_tecnolife_crawler
from .task_accessories_powerbank_hamrahtel_crawl import accessories_powerbank_hamrahtel_crawler
from .task_accessories_powerbank_digikala_crawl import accessories_powerbank_digikala_crawler

@shared_task
def start_powerbank_crawlers(*args, **kwargs):
    tasks = [
        accessories_powerbank_kasra_crawler.si().on_error(accessories_error_handler.s("Kasrapars", "powerbank")),
        accessories_powerbank_mobile140_crawler.si().on_error(accessories_error_handler.s("Mobile140", "powerbank")),
        accessories_powerbank_tecnolife_crawler.si().on_error(accessories_error_handler.s("Tecnolife", "powerbank")),
        accessories_powerbank_hamrahtel_crawler.si().on_error(accessories_error_handler.s("Hamrahtel", "powerbank")),
        accessories_powerbank_digikala_crawler.si().on_error(accessories_error_handler.s("Digikala", "powerbank")),
    ]
    return run_group_with_notify(tasks, "powerbank_crawler_queue")


# -------------------------
# Charger
# -------------------------
from .task_accessories_charger_kasra_crawl import accessories_charger_kasra_crawler
from .task_accessories_charger_mobile140_crawl import accessories_charger_mobile140_crawler
from .task_accessories_charger_tecnolife_crawl import accessories_charger_tecnolife_crawler
from .task_accessories_charger_hamrahtel_crawl import accessories_charger_hamrahtel_crawler
from .task_accessories_charger_digikala_crawl import accessories_charger_digikala_crawler

@shared_task
def start_charger_crawlers(*args, **kwargs):
    tasks = [
        accessories_charger_kasra_crawler.si().on_error(accessories_error_handler.s("Kasrapars", "charger")),
        accessories_charger_mobile140_crawler.si().on_error(accessories_error_handler.s("Mobile140", "charger")),
        accessories_charger_tecnolife_crawler.si().on_error(accessories_error_handler.s("Tecnolife", "charger")),
        accessories_charger_hamrahtel_crawler.si().on_error(accessories_error_handler.s("Hamrahtel", "charger")),
        accessories_charger_digikala_crawler.si().on_error(accessories_error_handler.s("Digikala", "charger")),
    ]
    return run_group_with_notify(tasks, "charger_crawler_queue")


# -------------------------
# Speaker
# -------------------------
from .task_accessories_speaker_kasra_crawl import accessories_speaker_kasra_crawler
from .task_accessories_speaker_mobile140_crawl import accessories_speaker_mobile140_crawler
from .task_accessories_speaker_tecnolife_crawl import accessories_speaker_tecnolife_crawler
from .task_accessories_speaker_hamrahtel_crawl import accessories_speaker_hamrahtel_crawler
from .task_accessories_speaker_digikala_crawl import accessories_speaker_digikala_crawler

@shared_task
def start_speaker_crawlers(*args, **kwargs):
    tasks = [
        accessories_speaker_kasra_crawler.si().on_error(accessories_error_handler.s("Kasrapars", "speaker")),
        accessories_speaker_mobile140_crawler.si().on_error(accessories_error_handler.s("Mobile140", "speaker")),
        accessories_speaker_tecnolife_crawler.si().on_error(accessories_error_handler.s("Tecnolife", "speaker")),
        accessories_speaker_hamrahtel_crawler.si().on_error(accessories_error_handler.s("Hamrahtel", "speaker")),
        accessories_speaker_digikala_crawler.si().on_error(accessories_error_handler.s("Digikala", "speaker")),
    ]
    return run_group_with_notify(tasks, "speaker_crawler_queue")
