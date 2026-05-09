"""
apps_script.py  –  Direct Jumia scraper with bot-detection resilience
                   (replaces Google Apps Script backend)

Drop-in replacement: all public function signatures are identical to the
original.  Product data is now fetched directly from Jumia using a three-tier
resilience strategy:

  Tier 1 – cloudscraper  : bypasses Cloudflare / JS-challenge pages
  Tier 2 – requests      : plain HTTP with rotating User-Agent headers
  Tier 3 – retry + backoff: exponential back-off on 429 / 503 responses

No new dependencies needed — cloudscraper is already in requirements.txt.
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
    # Chrome – Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox – Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari – macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge – Windows
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
# CLOUDSCRAPER SESSION  (cached per Streamlit session to reuse cookies)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def _get_cloudscraper() -> cloudscraper.CloudScraper:
    """
    Returns a single CloudScraper instance shared across the Streamlit session.
    CloudScraper automatically handles Cloudflare JS-challenge / IUAM pages.
    """
    scraper = cloudscraper.create_scraper(
        browser={
            "browser": "chrome",
            "platform": "windows",
            "mobile": False,
        },
        delay=3,
    )
    scraper.headers.update(_random_headers())
    return scraper


# ══════════════════════════════════════════════════════════════════════════════
# RESILIENT FETCH  (3-tier with exponential back-off)
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
    """
    Fetch a URL with three escalating strategies:
      1. cloudscraper  – handles JS challenges / Cloudflare
      2. requests      – plain HTTP fallback with rotating UA
      3. Retry with exponential back-off on rate-limit responses (429/503)

    Returns a Response on success, or None on total failure.
    """
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
                    logger.warning(
                        "[%s] HTTP %s for %s – backing off %.1fs (attempt %d/%d)",
                        strategy_name, r.status_code, url, wait, attempt, _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue

                if r.ok:
                    return r

                # Hard client errors – no point retrying
                if r.status_code in {403, 404, 410}:
                    logger.warning("[%s] HTTP %s – aborting %s", strategy_name, r.status_code, url)
                    return r

            except Exception as exc:
                logger.warning("[%s] Exception fetching %s: %s", strategy_name, url, exc)
                time.sleep(random.uniform(0.5, 1.5))

        # Jitter between full retry rounds
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
    label = label_map.get(country_code, "Kenya (KE)")
    return DOMAIN_MAP.get(label, "jumia.co.ke")


def _sku_to_search_url(sku: str, country_code: str = "KE") -> str:
    domain = _domain_for_country(country_code)
    return f"https://www.{domain}/catalog/?q={sku.strip().upper()}"


def _search_url_to_product_url(sku: str, country_code: str = "KE") -> str | None:
    """Search Jumia for a SKU; return the first matching product URL or None."""
    search_url = _sku_to_search_url(sku, country_code)
    r = _fetch_with_resilience(search_url)
    if not r or not r.ok:
        return None
    soup = BeautifulSoup(r.content, "html.parser")
    a = soup.select_one("article.prd a.core")
    if a and a.get("href"):
        domain = _domain_for_country(country_code)
        href = a["href"]
        return href if href.startswith("http") else f"https://www.{domain}{href}"
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CORE PAGE SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

def _scrape_product_page(url: str) -> dict:
    """
    Fetch a Jumia product page and return a raw payload dict mirroring
    what the old Apps Script returned.
    """
    payload = {"found": False, "url": url}

    # Randomised polite delay
    time.sleep(random.uniform(0.4, 1.2))

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

        # Product name
        name_tag = (
            soup.select_one("h1.-fs20.-pts.-pbxs")
            or soup.select_one("h1.name")
            or soup.select_one("h1")
        )
        name = name_tag.get_text(strip=True) if name_tag else "N/A"

        # Brand
        brand_tag = soup.select_one("a.-brand.-pvxs")
        brand = brand_tag.get_text(strip=True) if brand_tag else (
            name.split()[0] if name != "N/A" else "N/A"
        )

        # Seller
        seller_tag = (
            soup.select_one("a.seller-info__name")
            or soup.select_one("[data-seller]")
        )
        seller = seller_tag.get_text(strip=True) if seller_tag else "N/A"

        # Price
        price_tag = (
            soup.select_one("span.-b.-lgl.-tal.-fs24")
            or soup.select_one("span.prc")
            or soup.select_one("[data-price]")
        )
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        # Rating
        rating_tag = soup.select_one("div.stars._m._al") or soup.select_one(".stars")
        rating = rating_tag.get_text(strip=True) if rating_tag else "N/A"

        # Category breadcrumb
        crumbs = soup.select("div.-pvs.-mbs a")
        category = (
            " > ".join(c.get_text(strip=True) for c in crumbs[1:])
            if len(crumbs) > 1 else "N/A"
        )

        # SKU
        sku_match = (
            re.search(r"(\d{5,}p)\b", url, re.I)
            or re.search(r"(\d{5,}p)\b", r.text, re.I)
        )
        sku = sku_match.group(1).upper() if sku_match else "N/A"

        # Images
        images, seen_imgs = [], set()
        for img in soup.select("div.-pbs.-oh img, div.sldr img, img.img"):
            src = img.get("data-src") or img.get("src") or ""
            if src and "data:image" not in src and src not in seen_imgs:
                src = re.sub(r"fit-in/\d+x\d+/", "fit-in/500x500/", src)
                seen_imgs.add(src)
                images.append(src)

        # Key features / description
        features_block = (
            soup.select_one("div.-pvs.-mvxs.-phm.-lpl")
            or soup.select_one("div.markup.-pam")
        )
        features_text = features_block.get_text(" ", strip=True) if features_block else ""

        # Express badge
        express = "Yes" if (
            soup.select_one("span.exp") or "jumia express" in r.text.lower()
        ) else "No"

        payload.update({
            "found":             True,
            "name":              name,
            "brand":             brand,
            "seller":            seller,
            "price":             price,
            "rating":            rating,
            "category":          category,
            "sku":               sku,
            "images":            images,
            "key_features":      [features_text],
            "whats_in_the_box":  [],
            "express":           express,
            "source_url":        url,
        })

    except Exception as e:
        payload["error"] = str(e)

    return payload


# ══════════════════════════════════════════════════════════════════════════════
# PAYLOAD → PRODUCT DATA
# ══════════════════════════════════════════════════════════════════════════════

def apps_script_payload_to_original_data(
    payload: dict,
    target: dict,
    country_code: str = "KE",
) -> dict:
    data = _empty_data(target)

    if not payload:
        data["Product Name"] = "ERROR_FETCHING"
        data["Error"] = "Empty scraper response"
        return data

    if payload.get("blocked"):
        data["Product Name"] = "ERROR_FETCHING"
        data["Error"] = "Blocked / challenged by Jumia (all strategies failed)"
        data["Apps Script Status"] = "BLOCKED"
        return data

    if payload.get("found") is False:
        data["Product Name"] = "SKU_NOT_FOUND"
        data["Error"] = payload.get("error", "Not found")
        data["Apps Script Status"] = "NOT_FOUND"
        return data

    name        = payload.get("name") or "N/A"
    sku         = payload.get("sku") or target.get("original_sku") or "N/A"
    images      = payload.get("images") or []
    product_url = payload.get("source_url") or target.get("value", "N/A")

    data["Input Source"]         = target.get("original_sku", target.get("value", ""))
    data["Product Name"]         = name
    data["Brand"]                = payload.get("brand") or (name.split()[0] if name != "N/A" else "N/A")
    data["Seller Name"]          = payload.get("seller") or "N/A"
    data["Category"]             = payload.get("category") or "N/A"
    data["SKU"]                  = clean_jumia_sku(str(sku))
    data["Product URL"]          = product_url
    data["Primary Image URL"]    = images[0] if images else "N/A"
    data["Image URLs"]           = images
    data["Total Product Images"] = len(images)
    data["Price"]                = payload.get("price") or "N/A"
    data["Product Rating"]       = payload.get("rating") or "N/A"
    data["Express"]              = payload.get("express") or "No"

    # Warranty
    desc_text = " ".join(
        payload.get("key_features", []) + payload.get("whats_in_the_box", [])
    )
    wi = extract_warranty_info(BeautifulSoup(desc_text, "html.parser"), name)
    data["Has Warranty"]      = wi["has_warranty"]
    data["Warranty Duration"] = wi["warranty_duration"]
    data["Warranty Source"]   = wi["warranty_source"]
    data["Warranty Address"]  = wi["warranty_address"]

    # Refurb detection
    rs = detect_refurbished_status(BeautifulSoup("", "html.parser"), name)
    data["Title has Refurbished"]  = rs["is_refurbished"]
    data["Has refurb tag"]         = rs["has_refurb_tag"]
    data["Refurbished Indicators"] = ", ".join(rs["refurb_indicators"]) or "None"
    if data["Brand"] == "Renewed":
        data["Title has Refurbished"] = "YES"

    # Seller authorization
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

    data["grading tag"]                   = "Not Checked"
    data["Grading last image"]            = "NO"
    data["Description has Grading guide"] = "NO"
    data["Has info-graphics"]             = "NO"
    data["Infographic Image Count"]       = 0
    data["Apps Script Status"]            = "OK"
    return data


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API  (identical signatures to the original apps_script.py)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_item_via_apps_script(
    target: dict,
    timeout: int = 60,
    country_code: str = "KE",
) -> dict:
    try:
        if target.get("type") == "sku":
            sku = target.get("original_sku", target.get("value", "")).strip().upper()
            product_url = _search_url_to_product_url(sku, country_code)
            if not product_url:
                data = _empty_data(target)
                data["Product Name"] = "SKU_NOT_FOUND"
                data["Error"] = "No product found for this SKU"
                data["Apps Script Status"] = "NOT_FOUND"
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
        data["Product Name"] = "ERROR_FETCHING"
        data["Error"] = str(e)
        data["Apps Script Status"] = "CALL_FAILED"
        return data


def fetch_image_from_sku_via_apps_script(
    sku: str,
    active_country: str | None = None,
) -> tuple[Image.Image | None, str | None]:
    country_code = active_country or "KE"
    product_url  = _search_url_to_product_url(sku.strip().upper(), country_code)
    if not product_url:
        return None, None
    return fetch_image_from_product_url_via_apps_script(product_url, active_country)


def fetch_image_from_product_url_via_apps_script(
    url: str,
    active_country: str | None = None,
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
