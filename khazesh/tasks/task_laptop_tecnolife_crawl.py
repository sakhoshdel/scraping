import json
import requests
from celery import shared_task
from bs4 import BeautifulSoup
import logging
import time
import traceback
from django.utils import timezone
import re
from khazesh.models import BrandLaptop, ProductLaptop
from khazesh.tasks.save_laptop_object_to_database import save_laptop_obj
from khazesh.tasks.save_laptop_crawler_status import laptop_update_code_execution_state

HEADERS = {"From": "behnammohammadi149@gmail.com"}
SITE = "Tecnolife"

# ------------------ درخواست امن ------------------
def safe_request(url, headers, retries=2, delay=2):
    for i in range(retries):
        try:
            res = requests.get(url, headers=headers, timeout=20)
            res.raise_for_status()
            return res
        except requests.RequestException as e:
            logging.warning(f"⚠️ Request failed ({i+1}/{retries}) → {e}")
            time.sleep(delay)
    return None


# ------------------ ابزارهای کمکی ------------------
def normalize_capacity(value: str):
    if not value:
        return None
    return (
        value.replace("گیگابایت", "GB")
        .replace("مگابایت", "MB")
        .replace("ترابایت", "TB")
        .replace("کیلوبایت", "KB")
        .replace(" ", "")
        .strip()
    )


def clean_display_size(value: str):
    if not value:
        return None
    v = value.replace("٫", ".").replace(",", ".")
    v = v.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:اینچ|inch)", v, re.IGNORECASE)
    if m:
        return m.group(1)
    for num in re.findall(r"\d+(?:\.\d+)?", v):
        try:
            if 10 <= float(num) <= 20:
                return num
        except ValueError:
            continue
    return None


# ------------------ استخراج آدرس محصولات ------------------
def get_laptop_info(headers, url):
    try:
        res = safe_request(url, headers)
        if not res:
            return [], True

        soup = BeautifulSoup(res.text, "html.parser")
        script_tag = soup.find("script", id="__NEXT_DATA__")
        if not script_tag:
            return [], True

        page_obj = json.loads(script_tag.string)
        queries = page_obj.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])

        # پیدا کردن query صحیح (به جای queries[5])
        laptop_lists_obj = None
        for q in queries:
            if "results" in str(q):
                laptop_lists_obj = q
                break
        if not laptop_lists_obj:
            return [], True

        laptops = laptop_lists_obj.get("state", {}).get("data", {}).get("results", [])
        laptop_urls = []
        page_number_flag = False

        for laptop in laptops:
            if not laptop.get("available"):
                page_number_flag = True
                break
            name = laptop.get("name", "")
            code = laptop.get("code", "").split("-")[-1]
            if not name or not code:
                continue
            laptop_urls.append(f"https://www.technolife.ir/product-{code}/{name.replace(' ', '-')}")
        return laptop_urls, page_number_flag
    except Exception:
        laptop_update_code_execution_state(SITE, False, traceback.format_exc())
        return [], True


# ------------------ استخراج اطلاعات فنی لپ‌تاپ ------------------
def set_laptop_obj_data(other_data_obj, laptop_obj, url):
    try:
        fa_title = laptop_obj.get("product_info", {}).get("title", "")
        other_data_obj["title"] = fa_title

        # برند و مدل
        model_str = laptop_obj.get("product_info", {}).get("model", "") or fa_title
        brand_slug = model_str.split(" ")[0] if model_str else "نامشخص"
        brand, _ = BrandLaptop.objects.get_or_create(name_fa=brand_slug, name_en=brand_slug)

        other_data_obj.update({
            "brand": brand,
            "model": model_str,
            "stock": True,
            "site": SITE,
            "url": url,
            "max_price": 1,
            "description": "",
        })

        # ویژگی‌ها
        flat_attrs = {}
        for block in laptop_obj.get("configurations_component", []) or []:
            for iv in block.get("info") or []:
                k, v = (iv.get("item") or "").strip(), (iv.get("value") or "").strip()
                if k and v:
                    flat_attrs[k] = v

        def pick(keys):
            for k in flat_attrs.keys():
                if any(key.lower() in k.lower() for key in keys):
                    return flat_attrs[k]
            return None

        other_data_obj["ram"] = normalize_capacity(pick(["RAM", "حافظه RAM"]))
        other_data_obj["storage"] = normalize_capacity(pick(["SSD", "HDD", "ظرفیت حافظه داخلی"]))
        cpu_series = pick(["سری پردازنده"])
        cpu_model = pick(["مدل پردازنده"])
        other_data_obj["cpu"] = " ".join(x for x in [cpu_series, cpu_model] if x)
        gpu_series = pick(["سازنده پردازنده گرافیکی"])
        gpu_model = pick(["مدل پردازنده گرافیکی"])
        other_data_obj["gpu"] = " ".join(x for x in [gpu_series, gpu_model] if x)
        other_data_obj["display_size"] = clean_display_size(
            pick(["اندازه صفحه", "Display", "Screen Size"])
        )
        other_data_obj["display_resolution"] = pick(["رزولوشن", "وضوح تصویر"])
        other_data_obj["weight"] = pick(["وزن"])
        other_data_obj["battery"] = pick(["باتری"])
        other_data_obj["os"] = pick(["سیستم عامل", "OS"])
    except Exception:
        laptop_update_code_execution_state(SITE, False, traceback.format_exc())


# ------------------ مرحله دریافت لیست URLها ------------------
def main():
    laptop_model_list = [
        "164_163_130/تمامی-کامپیوترها-و-لپ-تاپ-ها?manufacturer_id=78_89_77_71_55_20_19_16&only_available=true"
    ]
    all_urls = []
    for model in laptop_model_list:
        for i in range(4):
            url = f"https://www.technolife.ir/product/list/{model}&page={i + 1}"
            urls, stop = get_laptop_info(HEADERS, url)
            all_urls.extend(urls)
            if stop:
                break
    return all_urls


def retry_main(max_retries=3, delay=5):
    for i in range(max_retries):
        urls = main()
        if urls:
            return urls
        time.sleep(delay)
    raise Exception("No laptop URLs found after retries")


# ------------------ تسک اصلی ------------------
@shared_task(bind=True, max_retries=1)
def laptop_tecnolife_crawler(self):
    try:
        all_laptops = []
        all_urls = retry_main()

        for url in all_urls:
            try:
                res = safe_request(url, HEADERS)
                if not res:
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
                script = soup.find("script", {"id": "__NEXT_DATA__"})
                if not script:
                    continue
                data = json.loads(script.get_text())
                laptop_obj = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]

                all_colors = []
                for color_obj in laptop_obj.get("seller_items_component", []) or []:
                    color_name = color_obj.get("color", {}).get("value", "")
                    color_hex = color_obj.get("color", {}).get("code", "")
                    sellers = color_obj.get("seller_items", [])
                    same_color = []
                    for s in sellers:
                        if s.get("available"):
                            same_color.append({
                                "color_name": color_name,
                                "color_hex": color_hex,
                                "seller": s.get("seller"),
                                "guarantee": s.get("guarantee"),
                                "min_price": s.get("discounted_price", 0) * 10,
                            })
                    if same_color:
                        all_colors.append(same_color)

                if not all_colors:
                    continue

                min_price_per_color = [min(c, key=lambda x: x["min_price"]) for c in all_colors]
                base_data = {}
                set_laptop_obj_data(base_data, laptop_obj, url)
                for item in min_price_per_color:
                    item.update(base_data)
                    all_laptops.append(item)
                time.sleep(0.5)

            except Exception:
                laptop_update_code_execution_state(SITE, False, traceback.format_exc())
                continue

        ten_min_ago = timezone.now() - timezone.timedelta(minutes=10)
        ProductLaptop.objects.filter(site=SITE, status=True, updated_at__lt=ten_min_ago).update(status=False)

        for laptop in all_laptops:
            save_laptop_obj(laptop)

        laptop_update_code_execution_state(SITE, True)
        print(f"✅ {len(all_laptops)} laptops crawled successfully from Technolife.")

    except Exception:
        err = traceback.format_exc()
        laptop_update_code_execution_state(SITE, False, err)
        raise self.retry(exc=Exception(err), countdown=30)
