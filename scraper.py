import re
import json
from urllib.parse import urljoin
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import requests
from bs4 import BeautifulSoup
from PIL import Image
from config import (
    _SESSION, APPS_SCRIPT_URL, USE_APPS_SCRIPT_BACKEND, 
    _CAT_MAPPING, _AUTH_SELLERS
)
from image_utils import _run_image_checks_parallel

def parse_warranty_text(raw_text: str, product_name: str) -> dict:
    data = {"has_warranty": "NO", "warranty_duration": "N/A", "warranty_source": "None"}
    patterns = [
        r"(\d+)\s*(?:months?|month|mnths?|mths?)\s*(?:warranty|wrty|wrnty)",
        r"(\d+)\s*(?:year|yr|years|yrs)\s*(?:warranty|wrty|wrnty)",
        r"warranty[:\s]*(\d+)\s*(?:months?|years?)",
    ]
    combined = f"{raw_text} {product_name}"
    for p in patterns:
        m = re.search(p, combined, re.I)
        if m:
            unit = "months" if "month" in m.group(0).lower() else "years"
            data.update({
                "has_warranty":"YES", 
                "warranty_duration": f"{m.group(1)} {unit}", 
                "warranty_source": "Text Scanner"
            })
            return data
    return data

def detect_refurbished_status(product_name: str, description_text: str) -> dict:
    data = {"is_refurbished":"NO", "refurb_indicators":[]}
    kws = ["refurbished","renewed","refurb","recon","reconditioned","ex-uk","ex uk","pre-owned","certified","restored"]
    combined = f"{product_name} {description_text}".lower()
    for kw in kws:
        if kw in combined:
            data["is_refurbished"] = "YES"
            data["refurb_indicators"].append(f"Keyword: {kw}")
    return data

def extract_category(url: str) -> str:
    """
    Extracts the product category breadcrumb directly from the Jumia product page.
    Fallback for when the Apps Script payload misses it.
    """
    if not url or "http" not in url:
        return "N/A"
    try:
        # Added extended headers to bypass basic bot-protection blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1"
        }
        r = _SESSION.get(url, timeout=15, headers=headers)
        if r.ok:
            soup = BeautifulSoup(r.content, "html.parser")
            
            # Method 1: Try JSON-LD schema (Very reliable, SEO standard)
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "BreadcrumbList":
                        items = data.get("itemListElement", [])
                        items = sorted(items, key=lambda x: x.get("position", 0))
                        cat_list = [item.get("name") for item in items if item.get("name") and item.get("name").lower() != "home"]
                        if cat_list:
                            return " > ".join(cat_list)
                except Exception:
                    continue
            
            # Method 2: Try Jumia tracking attributes (Highly reliable)
            cat_el = soup.find(attrs={"data-category": True})
            if cat_el and cat_el.get("data-category"):
                cat_path = cat_el.get("data-category")
                parts = [p.strip() for p in cat_path.split("/") if p.strip() and p.strip().lower() != "home"]
                if parts:
                    return " > ".join(parts)

            # Method 3: Native CSS selectors (.brcbs a.cbs)
            category_links = soup.select(".brcbs a.cbs, a.cbs")
            if category_links:
                cat_list = [
                    a.get_text(strip=True) 
                    for a in category_links 
                    if a.get_text(strip=True) and a.get_text(strip=True).lower() != "home"
                ]
                if cat_list:
                    return " > ".join(cat_list)
    except Exception:
        pass
    return "N/A"

def apps_script_payload_to_original_data(payload: dict, target: dict, country_code: str = "KE") -> dict:
    name = payload.get("name") or payload.get("title") or "N/A"
    sku = str(payload.get("sku") or target.get("original_sku") or "N/A").upper()
    
    desc_blob = " ".join(payload.get("key_features", []) + payload.get("whats_in_the_box", []))
    rs = detect_refurbished_status(name, desc_blob)
    wi = parse_warranty_text(desc_blob, name)

    data = {
        "Input Source": target.get("original_sku", target.get("value", "")),
        "Product Name": name,
        "Brand": payload.get("brand") or (name.split()[0] if name != "N/A" else "N/A"),
        "Seller Name": payload.get("seller") or "N/A",
        "Category": payload.get("category") or "N/A",
        "SKU": sku,
        "Product URL": payload.get("url") or target.get("value", "N/A"),
        "Primary Image URL": (payload.get("images") or ["N/A"])[0],
        "Image URLs": payload.get("images", []),
        "Total Product Images": len(payload.get("images", [])),
        "Price": payload.get("price") or "N/A",
        "Product Rating": payload.get("rating") or "N/A",
        "Title has Refurbished": rs["is_refurbished"],
        "Refurbished Indicators": ", ".join(rs["refurb_indicators"]),
        "Has Warranty": wi["has_warranty"],
        "Warranty Duration": wi["warranty_duration"],
        "Warranty Source": wi["warranty_source"],
        "Seller authorized": "NO",
        "_desc_img_urls": payload.get("images", [])
    }
    
    norm_cat = data["Category"].replace(" > ", ">").replace(" ", "").lower()
    prod_type = _CAT_MAPPING.get(norm_cat)
    seller_lower = data["Seller Name"].lower()
    auth_list = _AUTH_SELLERS.get(country_code, {}).get(prod_type, set()) if prod_type else set()
    if any(a in seller_lower for a in auth_list if a):
        data["Seller authorized"] = "YES"

    return data

def scrape_item(target, timeout=60, country_code="KE", do_check=True):
    try:
        sku = target.get("original_sku", "") if target.get("type") == "sku" else ""
        params = {"sku": sku} if sku else {"url": target["value"]}
        r = requests.get(APPS_SCRIPT_URL, params=params, timeout=timeout)
        payload = r.json()
        
        # --- FIX: Direct HTML parsing fallback for category ---
        cat = payload.get("category")
        if not cat or cat == "N/A" or cat.strip() == "":
            prod_url = payload.get("url") or target.get("value")
            if prod_url:
                payload["category"] = extract_category(prod_url)
                
        data = apps_script_payload_to_original_data(payload, target, country_code)
        if do_check: data = _run_image_checks_parallel(data)
        return data
    except Exception as e:
        return {"Product Name": "ERROR", "Error": str(e)}

def extract_category_links(category_url: str, max_pages: int = 1) -> list:
    base_url = re.sub(r"[?&]page=\d+", "", category_url).rstrip("?&")
    sep = "&" if "?" in base_url else "?"
    extracted = []
    for page in range(1, max_pages + 1):
        current_url = f"{base_url}{sep}page={page}" if page > 1 else base_url
        try:
            r = _SESSION.get(current_url, timeout=20)
            if r.ok:
                soup = BeautifulSoup(r.content, "html.parser")
                for a in soup.select("article.prd a.core"):
                    href = a.get("href")
                    if href and ".html" in href:
                        extracted.append(urljoin(current_url, href))
        except Exception:
            pass
    return list(dict.fromkeys(extracted))

def extract_category_images(category_url: str, max_pages: int = 1) -> list:
    base_url = re.sub(r"[?&]page=\d+", "", category_url).rstrip("?&")
    sep = "&" if "?" in base_url else "?"
    extracted = []
    seen = set()
    for page in range(1, max_pages + 1):
        current_url = f"{base_url}{sep}page={page}" if page > 1 else base_url
        try:
            r = _SESSION.get(current_url, timeout=20)
            if r.ok:
                soup = BeautifulSoup(r.content, "html.parser")
                for article in soup.find_all("article", class_="prd"):
                    img_tag = article.find("img", class_="img") or article.find("img")
                    if img_tag:
                        img_url = img_tag.get("data-src") or img_tag.get("src")
                        if img_url and "data:image" not in img_url and img_url not in seen:
                            seen.add(img_url)
                            img_url = re.sub(r"fit-in/\d+x\d+/", "fit-in/500x500/", img_url)
                            
                            name = "product"
                            a_tag = article.find("a", class_="core")
                            if a_tag:
                                name = a_tag.get("data-id") or a_tag.get("data-name") or "product"
                                name = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")[:30]
                            extracted.append({"url": img_url, "name": f"{name}_{len(extracted)}"})
        except Exception:
            pass
    return extracted

def process_inputs(text_in, file_in, d):
    raw = set()
    if text_in: raw.update(i.strip() for i in re.split(r"[\n,]", text_in) if i.strip())
    if file_in:
        df = pd.read_excel(file_in, header=None) if file_in.name.endswith(".xlsx") else pd.read_csv(file_in, header=None)
        raw.update(str(c).strip() for c in df.values.flatten() if str(c).strip() and str(c).lower() != "nan")
    return [{"type":"sku" if len(v)<30 and "http" not in v else "url", "value":v if "http" in v else f"https://www.{d}/catalog/?q={v}", "original_sku":v if "http" not in v else ""} for v in raw]

def fetch_image_from_sku_via_apps_script(sku: str, active_country: str | None = None):
    call = requests.get(APPS_SCRIPT_URL, params={"sku": sku.strip().upper()}, timeout=60)
    if not call.ok or not call.json().get("found"): return None, None
    images = call.json().get("images") or []
    if not images: return None, None
    try:
        r = _SESSION.get(images[0], timeout=20)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA"), active_country
    except Exception: return None, None

def fetch_image_from_product_url_via_apps_script(url: str, active_country: str | None = None):
    call = requests.get(APPS_SCRIPT_URL, params={"url": url.strip()}, timeout=60)
    if not call.ok or not call.json().get("found"): return None, None
    images = call.json().get("images") or []
    if not images: return None, None
    try:
        r = _SESSION.get(images[0], timeout=20)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA"), active_country
    except Exception: return None, None
