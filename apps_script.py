"""
apps_script.py  –  Direct Jumia scraper with bot-detection resilience
                   + parallel bulk processing

Drop-in replacement for the Google Apps Script backend.

Resilience strategy:
  Tier 1 – cloudscraper  : bypasses Cloudflare / JS-challenge pages
  Tier 2 – requests      : plain HTTP with rotating User-Agent headers
  Tier 3 – retry + backoff: exponential back-off on 429 / 503 responses

Bulk speed:
  scrape_items_bulk()  runs targets in parallel using ThreadPoolExecutor.
  Default 5 workers — safe for Jumia without triggering rate limits.
  Increase to 10 for speed, but expect occasional 429s (handled by back-off).
"""

import re
import time
import random
import logging
import streamlit as st
from io import BytesIO
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import cloudscraper

from config import _SESSION, DOMAIN_MAP, _CAT_MAPPING, _AUTH_SELLERS
from analyzer import (
    _empty_data, clean_jumia_sku, extract_warranty_info,
    detect_refurbished_status,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# ROTATING USER-AGENTS
# ══════════════════════════════════════════════════════════════════════════════

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

def _random_headers(referer: str = "https://www.jumia.co.ke/") -> dict:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept-Language": random.choice([
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-US,en;q=0.8,sw;q=0.6",
        ]),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": referer,
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }


# ══════════════════════════════════════════════════════════════════════════════
# CLOUDSCRAPER SESSION
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def _get_cloudscraper() -> cloudscraper.CloudScraper:
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
        delay=3,
    )
    scraper.headers.update(_random_headers())
    return scraper


# ══════════════════════════════════════════════════════════════════════════════
# RESILIENT FETCH
# ══════════════════════════════════════════════════════════════════════════════

_RETRY_STATUS = {429, 503, 502, 504}
_MAX_RETRIES  = 3
_BACKOFF_BASE = 2.0


def _host_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return "www.jumia.co.ke"


def _fetch_with_resilience(url: str, timeout: int = 25) -> requests.Response | None:
    strategies = [
        ("cloudscraper", _get_cloudscraper()),
        ("requests",     _SESSION),
    ]
    for attempt in range(1, _MAX_RETRIES + 1):
        for strategy_name, session in strategies:
            try:
                headers = _random_headers(referer=f"https://{_host_from_url(url)}/")
                r = session.get(url, headers=headers, timeout=timeout)
                if r.status_code in _RETRY_STATUS:
                    wait = _BACKOFF_BASE ** attempt + random.uniform(0, 1)
                    logger.warning("[%s] HTTP %s – backing off %.1fs", strategy_name, r.status_code, wait)
                    time.sleep(wait)
                    continue
                if r.ok:
                    return r
                if r.status_code in {403, 404, 410}:
                    return r
            except Exception as exc:
                logger.warning("[%s] Exception fetching %s: %s", strategy_name, url, exc)
                time.sleep(random.uniform(0.5, 1.5))
        if attempt < _MAX_RETRIES:
            time.sleep(_BACKOFF_BASE * attempt + random.uniform(0.3, 1.0))
    return None


# ══════════════════════════════════════════════════════════════════════════════
# COUNTRY / DOMAIN HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _domain_for_country(country_code: str) -> str:
    label_map = {
        "KE": "Kenya (KE)", "UG": "Uganda (UG)", "NG": "Nigeria (NG)",
        "MA": "Morocco (MA)", "GH": "Ghana (GH)",
    }
    return DOMAIN_MAP.get(label_map.get(country_code, "Kenya (KE)"), "jumia.co.ke")


def _sku_to_search_url(sku: str, country_code: str = "KE") -> str:
    return f"https://www.{_domain_for_country(country_code)}/catalog/?q={sku.strip().upper()}"


def _search_url_to_product_url(sku: str, country_code: str = "KE") -> str | None:
    r = _fetch_with_resilience(_sku_to_search_url(sku, country_code))
    if not r or not r.ok:
        return None
    soup = BeautifulSoup(r.content, "html.parser")
    a = soup.select_one("article.prd a.core")
    if a and a.get("href"):
        href = a["href"]
        domain = _domain_for_country(country_code)
        return href if href.startswith("http") else f"https://www.{domain}{href}"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CORE PAGE SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

def _scrape_product_page(url: str) -> dict:
    payload = {"found": False, "url": url}
    time.sleep(random.uniform(0.3, 0.8))   # reduced delay — parallelism adds natural spread

    r = _fetch_with_resilience(url)
    if r is None:
        payload["error"] = "All fetch strategies exhausted"
        return payload
    if r.status_code == 403:
        payload["blocked"] = True
        return payload
    if not r.ok:
        payload["error"] = f"HTTP {r.status_code}"
        return payload

    try:
        soup = BeautifulSoup(r.content, "html.parser")

        name_tag = (
            soup.select_one("h1.-fs20.-pts.-pbxs")
            or soup.select_one("h1.name")
            or soup.select_one("h1")
        )
        name = name_tag.get_text(strip=True) if name_tag else "N/A"

        brand_tag = soup.select_one("a.-brand.-pvxs")
        brand = brand_tag.get_text(strip=True) if brand_tag else (
            name.split()[0] if name != "N/A" else "N/A"
        )

        seller_tag = soup.select_one("a.seller-info__name") or soup.select_one("[data-seller]")
        seller = seller_tag.get_text(strip=True) if seller_tag else "N/A"

        price_tag = (
            soup.select_one("span.-b.-lgl.-tal.-fs24")
            or soup.select_one("span.prc")
            or soup.select_one("[data-price]")
        )
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        rating_tag = soup.select_one("div.stars._m._al") or soup.select_one(".stars")
        rating = rating_tag.get_text(strip=True) if rating_tag else "N/A"

        crumbs = soup.select("div.-pvs.-mbs a")
        category = (
            " > ".join(c.get_text(strip=True) for c in crumbs[1:])
            if len(crumbs) > 1 else "N/A"
        )

        sku_match = (
            re.search(r"(\d{5,}p)\b", url, re.I)
            or re.search(r"(\d{5,}p)\b", r.text, re.I)
        )
        sku = sku_match.group(1).upper() if sku_match else "N/A"

        images, seen_imgs = [], set()
        for img in soup.select("div.-pbs.-oh img, div.sldr img, img.img"):
            src = img.get("data-src") or img.get("src") or ""
            if src and "data:image" not in src and src not in seen_imgs:
                src = re.sub(r"fit-in/\d+x\d+/", "fit-in/500x500/", src)
                seen_imgs.add(src)
                images.append(src)

        features_block = (
            soup.select_one("div.-pvs.-mvxs.-phm.-lpl")
            or soup.select_one("div.markup.-pam")
        )
        features_text = features_block.get_text(" ", strip=True) if features_block else ""

        express = "Yes" if (
            soup.select_one("span.exp") or "jumia express" in r.text.lower()
        ) else "No"

        payload.update({
            "found": True, "name": name, "brand": brand, "seller": seller,
            "price": price, "rating": rating, "category": category, "sku": sku,
            "images": images, "key_features": [features_text],
            "whats_in_the_box": [], "express": express, "source_url": url,
        })

    except Exception as e:
        payload["error"] = str(e)

    return payload


# ══════════════════════════════════════════════════════════════════════════════
# PAYLOAD → PRODUCT DATA
# ══════════════════════════════════════════════════════════════════════════════

def apps_script_payload_to_original_data(
    payload: dict, target: dict, country_code: str = "KE"
) -> dict:
    data = _empty_data(target)

    if not payload:
        data.update({"Product Name": "ERROR_FETCHING", "Error": "Empty scraper response"})
        return data
    if payload.get("blocked"):
        data.update({"Product Name": "ERROR_FETCHING",
                     "Error": "Blocked by Jumia (all strategies failed)",
                     "Apps Script Status": "BLOCKED"})
        return data
    if payload.get("found") is False:
        data.update({"Product Name": "SKU_NOT_FOUND",
                     "Error": payload.get("error", "Not found"),
                     "Apps Script Status": "NOT_FOUND"})
        return data

    name        = payload.get("name") or "N/A"
    sku         = payload.get("sku") or target.get("original_sku") or "N/A"
    images      = payload.get("images") or []
    product_url = payload.get("source_url") or target.get("value", "N/A")

    data.update({
        "Input Source":         target.get("original_sku", target.get("value", "")),
        "Product Name":         name,
        "Brand":                payload.get("brand") or (name.split()[0] if name != "N/A" else "N/A"),
        "Seller Name":          payload.get("seller") or "N/A",
        "Category":             payload.get("category") or "N/A",
        "SKU":                  clean_jumia_sku(str(sku)),
        "Product URL":          product_url,
        "Primary Image URL":    images[0] if images else "N/A",
        "Image URLs":           images,
        "Total Product Images": len(images),
        "Price":                payload.get("price") or "N/A",
        "Product Rating":       payload.get("rating") or "N/A",
        "Express":              payload.get("express") or "No",
    })

    desc_text = " ".join(payload.get("key_features", []) + payload.get("whats_in_the_box", []))
    wi = extract_warranty_info(BeautifulSoup(desc_text, "html.parser"), name)
    data.update({
        "Has Warranty": wi["has_warranty"], "Warranty Duration": wi["warranty_duration"],
        "Warranty Source": wi["warranty_source"], "Warranty Address": wi["warranty_address"],
    })

    rs = detect_refurbished_status(BeautifulSoup("", "html.parser"), name)
    data.update({
        "Title has Refurbished":  rs["is_refurbished"],
        "Has refurb tag":         rs["has_refurb_tag"],
        "Refurbished Indicators": ", ".join(rs["refurb_indicators"]) or "None",
    })
    if data["Brand"] == "Renewed":
        data["Title has Refurbished"] = "YES"

    norm_cat  = data["Category"].replace(" > ", ">").replace(" ", "").lower()
    prod_type = _CAT_MAPPING.get(norm_cat)
    if not prod_type:
        for p, t in _CAT_MAPPING.items():
            if p in norm_cat or norm_cat in p:
                prod_type = t
                break
    if not prod_type:
        if any(kw in norm_cat for kw in ["computing", "laptop", "macbook", "pc"]):
            prod_type = "Laptops"
        elif any(kw in norm_cat for kw in ["phone", "smartphone", "mobile"]):
            prod_type = "Phones"

    data["Seller authorized"] = "NO"
    seller_lower = data["Seller Name"].strip().lower()
    if prod_type and seller_lower and seller_lower != "n/a":
        auth_list = _AUTH_SELLERS.get(country_code, {}).get(prod_type, set())
        if seller_lower in auth_list:
            data["Seller authorized"] = "YES"
        else:
            for auth_s in auth_list:
                if auth_s and (auth_s in seller_lower or seller_lower in auth_s):
                    data["Seller authorized"] = "YES"
                    break

    data.update({
        "grading tag": "Not Checked", "Grading last image": "NO",
        "Description has Grading guide": "NO", "Has info-graphics": "NO",
        "Infographic Image Count": 0, "Apps Script Status": "OK",
    })
    return data


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE-ITEM SCRAPE  (unchanged public API)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_item_via_apps_script(
    target: dict, timeout: int = 60, country_code: str = "KE"
) -> dict:
    try:
        if target.get("type") == "sku":
            sku = target.get("original_sku", target.get("value", "")).strip().upper()
            product_url = _search_url_to_product_url(sku, country_code)
            if not product_url:
                data = _empty_data(target)
                data.update({"Product Name": "SKU_NOT_FOUND",
                             "Error": "No product found for this SKU",
                             "Apps Script Status": "NOT_FOUND"})
                return data
        else:
            product_url = target.get("value", "").strip()

        payload = _scrape_product_page(product_url)

        if "last_raw_payloads" not in st.session_state:
            st.session_state["last_raw_payloads"] = []
        st.session_state["last_raw_payloads"].append(payload)

        return apps_script_payload_to_original_data(payload, target, country_code=country_code)

    except Exception as e:
        data = _empty_data(target)
        data.update({"Product Name": "ERROR_FETCHING", "Error": str(e),
                     "Apps Script Status": "CALL_FAILED"})
        return data


# ══════════════════════════════════════════════════════════════════════════════
# BULK PARALLEL SCRAPE  ← new
# ══════════════════════════════════════════════════════════════════════════════

def scrape_items_bulk(
    targets: list[dict],
    country_code: str = "KE",
    workers: int = 5,
    progress_callback=None,
) -> list[dict]:
    """
    Scrape a list of targets in parallel.

    Args:
        targets:           list of target dicts (same format as scrape_item_via_apps_script)
        country_code:      Jumia country code, e.g. "KE"
        workers:           number of parallel threads (5 = safe, 10 = fast but riskier)
        progress_callback: optional callable(completed: int, total: int) for UI progress

    Returns:
        list of product data dicts in the same order as the input targets.

    Usage in your Streamlit page:
        results = scrape_items_bulk(
            targets,
            country_code=active_country,
            workers=5,
            progress_callback=lambda done, total: progress_bar.progress(done / total),
        )
    """
    total   = len(targets)
    results = [None] * total   # preserve input order

    # Stagger thread starts slightly to avoid a simultaneous burst
    def _scrape_with_jitter(idx_target):
        idx, target = idx_target
        time.sleep(idx % workers * random.uniform(0.1, 0.4))
        return idx, scrape_item_via_apps_script(target, country_code=country_code)

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_scrape_with_jitter, (i, t)): i
            for i, t in enumerate(targets)
        }
        for future in as_completed(futures):
            try:
                idx, data = future.result()
                results[idx] = data
            except Exception as e:
                idx = futures[future]
                err = _empty_data(targets[idx])
                err.update({"Product Name": "ERROR_FETCHING", "Error": str(e),
                            "Apps Script Status": "CALL_FAILED"})
                results[idx] = err

            completed += 1
            if progress_callback:
                try:
                    progress_callback(completed, total)
                except Exception:
                    pass

    return results


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def fetch_image_from_sku_via_apps_script(
    sku: str, active_country: str | None = None
) -> tuple[Image.Image | None, str | None]:
    country_code = active_country or "KE"
    product_url  = _search_url_to_product_url(sku.strip().upper(), country_code)
    if not product_url:
        return None, None
    return fetch_image_from_product_url_via_apps_script(product_url, active_country)


def fetch_image_from_product_url_via_apps_script(
    url: str, active_country: str | None = None
) -> tuple[Image.Image | None, str | None]:
    payload = _scrape_product_page(url.strip())
    images  = payload.get("images") or []
    if not images:
        return None, None
    try:
        r = _fetch_with_resilience(images[0])
        if not r or not r.ok:
            return None, None
        return Image.open(BytesIO(r.content)).convert("RGBA"), active_country
    except Exception:
        return None, None


# ── Legacy compatibility shims ────────────────────────────────────────────────

def apps_script_call(params: dict, timeout: int = 60) -> dict:
    sku = params.get("sku", "")
    url = params.get("url", "")
    if sku:
        product_url = _search_url_to_product_url(sku)
        if not product_url:
            return {"ok": True, "payload": {"found": False, "error": "SKU not found"}}
        payload = _scrape_product_page(product_url)
    elif url:
        payload = _scrape_product_page(url)
    else:
        return {"ok": False, "error": "No sku or url provided"}
    return {"ok": True, "payload": payload, "status_code": 200}


def apps_script_lookup_target(target: dict, timeout: int = 60) -> dict:
    if target.get("type") == "sku":
        sku = target.get("original_sku", target.get("value", "")).strip().upper()
        return apps_script_call({"sku": sku}, timeout=timeout)
    return apps_script_call({"url": target.get("value", "").strip()}, timeout=timeout)
