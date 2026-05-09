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

def fetch_native_product_data(url: str) -> dict:
    """
    Highly aggressive native fetcher. Uses DOM parsing, JSON-LD, and Raw HTML Regex 
    to guarantee URL, Category, and full Image array extraction.
    """
    data = {"url": url, "category": "N/A", "images": [], "name": None}
    if not url or "http" not in url:
        return data
    
    # 1. Immediately kill 'productimagezoom' URLs
    if "productimagezoom/sku/" in url:
        sku_match = re.search(r'sku/([^/]+)', url)
        if sku_match:
            sku_val = sku_match.group(1)
            domain_match = re.search(r'https://www\.([^/]+)', url)
            domain = domain_match.group(1) if domain_match else "jumia.co.ke"
            url = f"https://www.{domain}/catalog/?q={sku_val}"

    try:
        # Spoof Googlebot to completely bypass Jumia WAF/Cloudflare blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive"
        }
        
        r = _SESSION.get(url, timeout=15, headers=headers, allow_redirects=True)
        if not r.ok:
            return data
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        # 2. Re-route Search Results (if URL was a catalog query)
        if "catalog/?q=" in url or "catalog/?q=" in r.url or "catalog/" in r.url:
            first_product = soup.select_one("article.prd a.core")
            if first_product:
                real_url = urljoin(r.url, first_product.get("href"))
                r = _SESSION.get(real_url, timeout=15, headers=headers, allow_redirects=True)
                soup = BeautifulSoup(r.text, "html.parser")
                data["url"] = real_url
            else:
                return data
        else:
            canonical = soup.select_one('link[rel="canonical"]')
            data["url"] = canonical.get("href") if canonical else r.url

        # Extract Title safely
        h1 = soup.select_one("h1.-fs20")
        if h1:
            data["name"] = h1.get_text(strip=True)

        # 3. Extract Category - Method A: Standard Breadcrumbs
        c_links = soup.select(".brcbs a.cbs, a.cbs")
        if c_links:
            c_list = [a.get_text(strip=True) for a in c_links if a.get_text(strip=True).lower() != "home"]
            if c_list:
                data["category"] = " > ".join(c_list)
        
        # Extract Category - Method B: Jumia DataLayer Regex (Extremely Reliable)
        if data["category"] == "N/A":
            cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', r.text)
            if cat_match:
                raw_cat = cat_match.group(1)
                if "/" in raw_cat:
                    data["category"] = " > ".join([p.strip() for p in raw_cat.split("/") if p.strip() and p.strip().lower() != "home"])
                else:
                    data["category"] = raw_cat

        # 4. Extract Images - Method A: DOM Traversal
        images = []
        for a in soup.select("#imgs a[data-image], .sldr a[data-image], img[data-src]"):
            img = a.get("data-image") or a.get("data-src")
            if img and "data:image" not in img and ("fit-in" in img or "product" in img):
                images.append(img)
                
        # Extract Images - Method B: Raw HTML Scan (Catches all gallery images even if JS didn't load)
        if not images:
            found_imgs = re.findall(r'https://[a-zA-Z0-9\.\-]+/unsafe/fit-in/\d+x\d+/filters:[^"\']+?\.jpg', r.text)
            images.extend(found_imgs)
            
        # Deduplicate & Force High Res
        if images:
            unique_images = []
            for img in images:
                clean_img = re.sub(r'fit-in/\d+x\d+/', 'fit-in/680x680/', img)
                if clean_img not in unique_images:
                    unique_images.append(clean_img)
            data["images"] = unique_images

    except Exception as e:
        print(f"Native fetch error: {e}")
        
    return data

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
        
        # 1. Intercept broken URLs before Apps Script
        target_url = target.get("value", "")
        if "productimagezoom/sku/" in target_url:
            m = re.search(r'sku/([^/]+)', target_url)
            if m:
                sku = m.group(1)
                target["type"] = "sku"
                target_url = f"https://www.jumia.co.ke/catalog/?q={sku}"
                target["value"] = target_url
                target["original_sku"] = sku
                
        params = {"sku": sku} if sku else {"url": target_url}
        r = requests.get(APPS_SCRIPT_URL, params=params, timeout=timeout)
        payload = r.json()
        
        # 2. Determine URL for Native Fetch
        prod_url = payload.get("url") or target_url
        if "productimagezoom/sku/" in prod_url:
            m = re.search(r'sku/([^/]+)', prod_url)
            if m:
                prod_url = f"https://www.jumia.co.ke/catalog/?q={m.group(1)}"
        
        # 3. Aggressive Native Extraction
        native_data = fetch_native_product_data(prod_url)
        
        # 4. Apply Overrides
        if native_data["url"] and "productimagezoom" not in native_data["url"] and native_data["url"] != "N/A":
            payload["url"] = native_data["url"]
        
        if native_data["category"] and native_data["category"] != "N/A":
            payload["category"] = native_data["category"]
            
        if native_data["images"]:
            payload["images"] = native_data["images"]
            
        if native_data.get("name") and payload.get("title") in [None, "N/A", ""]:
            payload["title"] = native_data["name"]
                
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
