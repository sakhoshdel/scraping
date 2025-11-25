import json
import re
import time
import traceback
from typing import Dict, List, Optional, Tuple, Union
import requests
from celery import shared_task
from requests.exceptions import ConnectionError, RequestException, Timeout
from khazesh.tasks.save_object_to_database import save_obj
from khazesh.tasks.save_crawler_status import update_code_execution_state
import uuid
from khazesh.models import Mobile
from django.utils import timezone

ResponseType = Optional[requests.Response]


# ------------------ Safe request with retry ------------------
def retry_request(url: str, site: str, max_retries: int = 2, retry_delay: int = 1) -> ResponseType:
    HEADERS = {"From": "behnammohammadi149@gmail.com"}
    for i in range(max_retries):
        try:
            res = requests.get(url, headers=HEADERS, timeout=20)
            res.raise_for_status()
            return res
        except (ConnectionError, Timeout) as e:
            print(f"⚠️ [{site}] Connection error ({i+1}/{max_retries}): {e}")
            update_code_execution_state(site, False, str(e))
            time.sleep(retry_delay)
        except RequestException as e:
            print(f"⚠️ [{site}] Request failed: {e}")
            update_code_execution_state(site, False, str(e))
            return None
        except Exception:
            update_code_execution_state(site, False, traceback.format_exc())
            return None
    return None


# ------------------ Main crawler ------------------
@shared_task(bind=True, max_retries=1)
def tablet_kassa_crawler(self):
    SITE = "Kasrapars"
    SELLER = "Kasrapars"
    all_tablet_objects = []
    brands_key = {"شیائومی": "xiaomi", "سامسونگ": "samsung", "اپل": "apple"}

    try:
        batch_id = f"Kasrapars-{uuid.uuid4().hex[:12]}"
        print("🟢 شروع کرول تبلت‌های کسراپارس")

        for page_num in range(0, 6):
            url = f"https://api.kasrapars.ir/api/web/v10/product/index-brand?page={page_num}&responseFields%5B0%5D=items&status_available=1&expand=letMeKnowOnAvailability%2Cvarieties%2CcartFeatures%2CcoworkerShortName%2CpromotionCoworker%2Cbrand&category_slug=tablet&brand_slug[]=samsung"
            res = retry_request(url, SITE)
            if not res:
                continue

            try:
                data = res.json()
            except Exception:
                update_code_execution_state(f"{SITE}-tablet", False, f"Invalid JSON on page {page_num}")
                continue

            items = data.get("items", {}).get("items", [])
            if not items:
                continue

            for item in items:
                try:
                    tablet_object = {}
                    brand = item.get("brand", {}).get("brand_name", "")
                    if brand not in brands_key:
                        continue

                    en_title = item.get("product_name_en", "")
                    fa_title = item.get("product_name", "")
                    slug = item.get("slug", "")
                    model_pattern = r"\s*[\d]{1,3}/[\d]{1,2}\s*(GB|MB|T|gb)?|^(samsung|xiaomi|apple|nokia|honor|huawei|nothing\sphone)\s*|\s*vietnam\s*"
                    model = re.sub(model_pattern, "", en_title.lower()) or fa_title
                    if not model:
                        match = re.search(r"(?<=مدل\s)[\w\s]*\s*(?=ظرفیت)", fa_title)
                        model = match.group().strip() if match else en_title

                    for var in item.get("varieties", []):
                        try:
                            guarantee = var.get("guarantee", {}).get("guranty_name", "ذکر نشده")

                            # استخراج رم
                            ram = "ندارد"
                            match_ram_fa = re.search(r"\s*رم\s*[\d]{1,3}\s*(گیگابایت|ترابایت)?", fa_title)
                            if match_ram_fa:
                                ram = re.sub(r"\D", "", match_ram_fa.group()) + "GB"
                            else:
                                match_ram_en = re.search(r"[\d]{1,3}/[\d]{1,2}", en_title)
                                if match_ram_en:
                                    parts = match_ram_en.group().split("/")
                                    ram = parts[1] + "GB" if len(parts) > 1 else "ندارد"

                            # استخراج حافظه
                            memory = "ندارد"
                            match_mem_fa = re.search(r"\s*ظرفیت\s*[\d]{1,3}\s*(گیگابایت|ترابایت)?", fa_title)
                            if match_mem_fa:
                                memory = re.sub(r"\D", "", match_mem_fa.group()) + "GB"
                            else:
                                match_mem_en = re.search(r"[\d]{1,3}/[\d]{1,2}", en_title)
                                if match_mem_en:
                                    memory = match_mem_en.group().split("/")[0] + "GB"

                            vietnam = False
                            if var.get("pack") and "VIT" in var["pack"].get("en_name", ""):
                                vietnam = True

                            tablet_object.update({
                                "model": model,
                                "memory": memory,
                                "ram": ram,
                                "brand": brands_key.get(brand, brand),
                                "title": fa_title,
                                "url": f"https://plus.kasrapars.ir/product/{slug}",
                                "site": SITE,
                                "seller": var.get("company", {}).get("company_name", SELLER),
                                "guarantee": guarantee,
                                "max_price": 1,
                                "mobile_digi_id": "",
                                "dual_sim": True,
                                "active": True,
                                "mobile": False,
                                "vietnam": vietnam,
                                "not_active": "نات اکتیو" in fa_title or "not active" in en_title.lower(),
                                "color_name": var.get("color", {}).get("color_name", "نامشخص"),
                                "color_hex": var.get("color", {}).get("hexcode", ""),
                                "min_price": var.get("price_off", 0),
                            })
                            all_tablet_objects.append(tablet_object.copy())
                        except Exception:
                            update_code_execution_state(f"{SITE}-tablet", False, traceback.format_exc())
                            continue
                except Exception:
                    update_code_execution_state(f"{SITE}-tablet", False, traceback.format_exc())
                    continue

        # ذخیره در دیتابیس
        for t in all_tablet_objects:
            save_obj(t, batch_id=batch_id)

        Mobile.objects.filter(site=SITE, mobile=False).exclude(last_batch_id=batch_id).update(status=False)
        update_code_execution_state(f"{SITE}-tablet", bool(all_tablet_objects), "هیچ تبلتی ذخیره نشد." if not all_tablet_objects else "")

    except Exception:
        err = traceback.format_exc()
        update_code_execution_state(f"{SITE}-tablet", False, err)
        print(f"❌ Error: {err}")
        raise self.retry(exc=Exception(err), countdown=30)

    finally:
        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        Mobile.objects.filter(site=SITE, status=True, mobile=False, updated_at__lt=ten_min_ago).update(status=False)
