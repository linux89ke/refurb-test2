import requests
import streamlit as st
from io import BytesIO
from bs4 import BeautifulSoup
from PIL import Image

from config import _SESSION, APPS_SCRIPT_URL
from analyzer import (
    _empty_data, clean_jumia_sku, extract_warranty_info,
    detect_refurbished_status, _CAT_MAPPING, _AUTH_SELLERS,
)


# ══════════════════════════════════════════════════════════════════════════════
#  LOW-LEVEL CALL
# ══════════════════════════════════════════════════════════════════════════════
def apps_script_call(params: dict, timeout: int = 60) -> dict:
    try:
        r = requests.get(APPS_SCRIPT_URL, params=params, timeout=timeout)
        try:
            payload = r.json()
        except Exception:
            return {
                "ok": False,
                "error": "Apps Script did not return JSON",
                "status_code": r.status_code,
                "content_type": r.headers.get("Content-Type", ""),
                "text_sample": r.text[:1000],
            }
        return {"ok": True, "payload": payload, "status_code": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def apps_script_lookup_target(target: dict, timeout: int = 60) -> dict:
    if target.get("type") == "sku":
        sku = target.get("original_sku", target.get("value", "")).strip().upper()
        return apps_script_call({"sku": sku}, timeout=timeout)
    return apps_script_call({"url": target.get("value", "").strip()}, timeout=timeout)


# ══════════════════════════════════════════════════════════════════════════════
#  PAYLOAD → PRODUCT DATA
# ══════════════════════════════════════════════════════════════════════════════
def apps_script_payload_to_original_data(
    payload: dict,
    target: dict,
    country_code: str = "KE",
) -> dict:
    data = _empty_data(target)
    if not payload:
        data["Product Name"] = "ERROR_FETCHING"
        data["Error"]        = "Empty Apps Script response"
        return data
    if payload.get("blocked"):
        data["Product Name"]     = "ERROR_FETCHING"
        data["Error"]            = "Apps Script reached Jumia but was blocked/challenged"
        data["Apps Script Status"] = "BLOCKED"
        return data
    if payload.get("found") is False:
        data["Product Name"]     = "SKU_NOT_FOUND"
        data["Error"]            = payload.get("error", "Not found")
        data["Apps Script Status"] = "NOT_FOUND"
        return data

    name = payload.get("name") or payload.get("Product Name") or payload.get("title") or "N/A"
    sku  = (
        payload.get("sku") or payload.get("input_sku")
        or target.get("original_sku") or "N/A"
    )
    images = payload.get("images") or payload.get("Image URLs") or payload.get("image_urls") or []
    if not isinstance(images, list):
        images = []
    product_url = (
        payload.get("product_url") or payload.get("url") or payload.get("source_url")
        or target.get("value", "N/A")
    )

    data["Input Source"]         = target.get("original_sku", target.get("value", ""))
    data["Product Name"]         = name
    data["Brand"]                = (
        payload.get("brand") or payload.get("Brand")
        or (name.split()[0] if name and name != "N/A" else "N/A")
    )
    data["Seller Name"]          = (
        payload.get("seller") or payload.get("seller_name")
        or payload.get("Seller Name") or "N/A"
    )
    data["Category"]             = payload.get("category") or payload.get("Category") or "N/A"
    data["SKU"]                  = clean_jumia_sku(str(sku))
    data["Product URL"]          = product_url
    data["Primary Image URL"]    = images[0] if images else "N/A"
    data["Image URLs"]           = images
    data["Total Product Images"] = len(images)
    data["Price"]                = payload.get("price") or payload.get("Price") or "N/A"
    data["Product Rating"]       = payload.get("rating") or payload.get("Product Rating") or "N/A"
    data["Express"]              = payload.get("express") or "No"

    warranty = payload.get("warranty") or payload.get("warranty_details") or ""
    if warranty:
        data["Has Warranty"]      = "YES"
        data["Warranty Duration"] = payload.get("warranty_duration") or warranty
        data["Warranty Source"]   = "Apps Script"
    else:
        wi = extract_warranty_info(BeautifulSoup("", "html.parser"), name)
        data["Has Warranty"]      = wi["has_warranty"]
        data["Warranty Duration"] = wi["warranty_duration"]
        data["Warranty Source"]   = wi["warranty_source"]
        data["Warranty Address"]  = wi["warranty_address"]

    rs = detect_refurbished_status(BeautifulSoup("", "html.parser"), name)
    data["Title has Refurbished"]  = rs["is_refurbished"]
    data["Has refurb tag"]         = rs["has_refurb_tag"]
    data["Refurbished Indicators"] = ", ".join(rs["refurb_indicators"]) or "None"
    if data["Brand"] == "Renewed":
        data["Title has Refurbished"] = "YES"

    norm_cat  = data["Category"].replace(" > ",">").replace(" ","").lower()
    prod_type = _CAT_MAPPING.get(norm_cat)
    if not prod_type:
        for p, t in _CAT_MAPPING.items():
            if p in norm_cat or norm_cat in p:
                prod_type = t
                break
    if not prod_type:
        if any(kw in norm_cat for kw in ["computing","laptop","macbook","pc"]):
            prod_type = "Laptops"
        elif any(kw in norm_cat for kw in ["phone","smartphone","mobile"]):
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
#  PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════
def scrape_item_via_apps_script(
    target: dict,
    timeout: int = 60,
    country_code: str = "KE",
) -> dict:
    call = apps_script_lookup_target(target, timeout=timeout)
    if not call.get("ok"):
        data = _empty_data(target)
        data["Product Name"]             = "ERROR_FETCHING"
        data["Error"]                    = call.get("error", "Apps Script call failed")
        data["Apps Script Status"]       = "CALL_FAILED"
        data["Apps Script Status Code"]  = call.get("status_code", "N/A")
        data["Apps Script Content Type"] = call.get("content_type", "N/A")
        data["Apps Script Sample"]       = call.get("text_sample", "")
        return data
    payload = call.get("payload", {})
    if "last_raw_payloads" not in st.session_state:
        st.session_state["last_raw_payloads"] = []
    st.session_state["last_raw_payloads"].append(payload)
    return apps_script_payload_to_original_data(payload, target, country_code=country_code)


def fetch_image_from_sku_via_apps_script(
    sku: str,
    active_country: str | None = None,
) -> tuple[Image.Image | None, str | None]:
    call = apps_script_call({"sku": sku.strip().upper()}, timeout=60)
    if not call.get("ok"):
        return None, None
    payload = call.get("payload", {})
    if not payload.get("found"):
        return None, None
    images = payload.get("images") or []
    if not images:
        return None, None
    try:
        r = _SESSION.get(images[0], timeout=20)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA"), active_country
    except Exception:
        return None, None


def fetch_image_from_product_url_via_apps_script(
    url: str,
    active_country: str | None = None,
) -> tuple[Image.Image | None, str | None]:
    call = apps_script_call({"url": url.strip()}, timeout=60)
    if not call.get("ok"):
        return None, None
    payload = call.get("payload", {})
    if not payload.get("found"):
        return None, None
    images = payload.get("images") or []
    if not images:
        return None, None
    try:
        r = _SESSION.get(images[0], timeout=20)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA"), active_country
    except Exception:
        return None, None
