import json
import time
import traceback
import requests
from bs4 import BeautifulSoup
from celery import shared_task
from requests.exceptions import ConnectionError, RequestException, Timeout
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
from khazesh.models import Mobile
from django.utils import timezone
import uuid

# ------------------ تنظیمات عمومی ------------------
HEADERS = {"From": "behnammohammadi149@gmail.com"}
SITE = "Tecnolife-tablet"

not_active_texts = [
    "Not Active", "Not Activate", "Not Activated", "not active",
    "not-active", "Not_Active", "NOT_ACTIVE", "Not-Active",
    "NOT-ACTIVE", "ٔNOT ACTIVE", "نات اکتیو", "نات-اکتیو"
]

kilo_mega_giga_tra = {"کیلوبایت": "KB", "مگابایت": "MB", "گيگابايت": "GB", "گیگابایت": "GB", "ترابایت": "TB"}

letter_to_digit_obj = {
    "۱": "1", "2": "2", "۳": "3", "4": "4", "۶": "6", "۸": "8",
    "۱۲": "12", "۱۶": "16", "۳۲": "32", "۶۴": "64", "۱۲۸": "128", "۲۵۶": "256", "۵۱۲": "512",
}


# ------------------ توابع کمکی ------------------
def retry_request(url, headers=None, max_retries=2, retry_delay=1):
    for i in range(max_retries):
        try:
            res = requests.get(url, headers=headers, timeout=20)
            res.raise_for_status()
            return res
        except (ConnectionError, Timeout) as e:
            print(f"⚠️ Connection error on attempt {i+1}: {e}")
            if i < max_retries - 1:
                time.sleep(retry_delay)
        except RequestException as e:
            print(f"⚠️ Request error: {e}")
            update_code_execution_state(SITE, False, str(e))
            return None
    return None


def extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, value):
    try:
        parts = value.split(" ")
        if len(parts) < 2:
            return "ندارد"
        num = parts[0].strip()
        unit = parts[1].strip()

        # جایگزینی واحد
        if unit in kilo_mega_giga_tra:
            unit = kilo_mega_giga_tra[unit]

        # جایگزینی عدد فارسی
        if num in letter_to_digit_obj:
            num = letter_to_digit_obj[num]

        return f"{num}{unit}"
    except Exception:
        update_code_execution_state(SITE, False, traceback.format_exc())
        return "ندارد"


def set_other_obj_data(other_data_obj, tablet_obj, url):
    try:
        en_title = tablet_obj.get("product_info", {}).get("model", "").split(" ")
        fa_title = tablet_obj.get("product_info", {}).get("title", "")
        other_data_obj["title"] = fa_title
        other_data_obj["vietnam"] = "Vietnam" in " ".join(en_title)
        brand = en_title[0] if en_title else "Unknown"
        other_data_obj["brand"] = "xiaomi" if brand.lower() == "poco" else brand
        other_data_obj["model"] = " ".join(en_title[1:]).strip()
        other_data_obj["active"] = True
        other_data_obj["mobile"] = False
        other_data_obj["site"] = "Tecnolife"
        other_data_obj["dual_sim"] = True
        other_data_obj["url"] = url
        other_data_obj["max_price"] = 1
        other_data_obj["not_active"] = any(
            txt in fa_title or txt in " ".join(en_title) for txt in not_active_texts
        )
    except Exception:
        update_code_execution_state(SITE, False, traceback.format_exc())


def get_tablet_info(headers, url):
    try:
        res = retry_request(url, headers=headers)
        if not res:
            return [], True

        soup = BeautifulSoup(res.text, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            return [], True

        data = json.loads(script_tag.get_text())
        queries = data.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
        if not queries:
            return [], True

        # پیدا کردن query مناسب به صورت ایمن
        tablet_lists_obj = None
        for q in queries:
            if "results" in str(q):
                tablet_lists_obj = q
                break

        if not tablet_lists_obj:
            return [], True

        tablets = tablet_lists_obj.get("state", {}).get("data", {}).get("results", [])
        urls = []
        stop_flag = False

        for t in tablets:
            if not t.get("available"):
                stop_flag = True
                break
            name = t.get("name", "")
            code = t.get("code", "").split("-")[-1]
            urls.append(f"https://www.technolife.ir/product-{code}/{name.replace(' ', '-')}")
        return urls, stop_flag
    except Exception:
        update_code_execution_state(SITE, False, traceback.format_exc())
        return [], True


def main():
    models = ["27_550_227/تمام-تبلت-ها?manufacturer_id=15_20_26_81&only_available=true"]
    all_urls = []
    for model in models:
        for i in range(4):
            url = f"https://www.technolife.ir/product/list/{model}&page={i+1}"
            urls, stop = get_tablet_info(HEADERS, url)
            all_urls.extend(urls)
            if stop:
                break
    return all_urls


def retry_main(max_retries=3, delay=5):
    for i in range(max_retries):
        urls = main()
        if urls:
            return urls
        print(f"Retrying ({i+1}/{max_retries})...")
        time.sleep(delay)
    raise Exception("No tablet URLs found after maximum retries")


# ------------------ تسک اصلی ------------------
@shared_task(bind=True, max_retries=1)
def tablet_tecnolife_crawler(self):
    try:
        batch_id = f"Tecnolife-{uuid.uuid4().hex[:12]}"
        all_tablets = []
        urls = retry_main()

        for url in urls:
            try:
                res = retry_request(url, headers=HEADERS)
                if not res:
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                script = soup.find("script", {"id": "__NEXT_DATA__"})
                if not script:
                    continue

                data = json.loads(script.get_text())
                queries = data.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
                tablet_data = None
                for q in queries:
                    if "seller_items_component" in str(q):
                        tablet_data = q.get("state", {}).get("data", {})
                        break

                if not tablet_data:
                    continue

                # جمع‌آوری sellerها بر اساس رنگ
                all_colors = []
                for color_obj in tablet_data.get("seller_items_component", []):
                    sellers = [
                        {
                            "color_name": color_obj["color"]["value"],
                            "color_hex": color_obj["color"]["code"],
                            "seller": s["seller"],
                            "guarantee": s["guarantee"],
                            "mobile_digi_id": s["_id"],
                            "min_price": s["discounted_price"] * 10,
                        }
                        for s in color_obj.get("seller_items", [])
                        if s.get("available")
                    ]
                    if sellers:
                        all_colors.append(sellers)

                if not all_colors:
                    continue

                # کمترین قیمت در هر رنگ
                min_price_items = [min(c, key=lambda x: x["min_price"]) for c in all_colors]

                # مشخصات فنی (RAM و Memory)
                other_data = {}
                for cfg in tablet_data.get("configurations_component", []):
                    if cfg.get("title") == "حافظه":
                        for info in cfg.get("info", []):
                            item, val = info.get("item"), info.get("value")
                            if item == "حافظه داخلی":
                                other_data["memory"] = extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, val)
                            elif item == "حافظه RAM":
                                other_data["ram"] = extract_ram_or_memory(kilo_mega_giga_tra, letter_to_digit_obj, val)

                other_data.setdefault("ram", "ندارد")
                other_data.setdefault("memory", "ندارد")
                set_other_obj_data(other_data, tablet_data, url)

                for t in min_price_items:
                    t.update(other_data)
                all_tablets.extend(min_price_items)

            except Exception:
                update_code_execution_state(SITE, False, traceback.format_exc())
                continue

        for t in all_tablets:
            save_obj(t, batch_id=batch_id)

        Mobile.objects.filter(site="Tecnolife", mobile=False).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state("Tecnolife-tablet", bool(all_tablets))

    except Exception:
        err = traceback.format_exc()
        update_code_execution_state("Tecnolife-tablet", False, err)
        print(err)
        raise self.retry(exc=Exception(err), countdown=30)
    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site="Tecnolife", status=True, mobile=False, updated_at__lt=ten_min_ago).update(status=False)
