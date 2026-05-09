import os
import re
import time
import zipfile
import hashlib
import asyncio
import aiohttp
import base64
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

from config import (
    DOMAIN_MAP, TAG_FILES, TAG_FILES_FR, _COUNTRY_CODE_MAP, _SESSION,
    _DOMAIN_TO_COUNTRY, _detect_country, detect_country_from_url
)
from image_utils import (
    pil_to_bytes, bytes_to_pil, image_to_jpeg_bytes, 
    apply_tag, strip_and_retag, load_tag_image, PROMO_HASH
)
from scraper import (
    scrape_item, process_inputs,
    fetch_image_from_sku_via_apps_script, fetch_image_from_product_url_via_apps_script
)

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Jumia Refurbished Suite",
    page_icon=":material/label:",
    layout="wide"
)

# ══════════════════════════════════════════════════════════════════════════════
#  JUMIA BRAND THEME & CUSTOM CARD CSS
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #1A1A1A; }
.stApp { background-color: #FAFAFA; }

/* Sticky footer spacing */
.main .block-container { padding-bottom: 90px !important; }
footer { display: none !important; }

[data-testid="stSidebar"] { background: linear-gradient(180deg, #1A1A1A 0%, #2D2D2D 100%); border-right: 3px solid #F68B1E; }
[data-testid="stSidebar"] * { color: #F5F5F5 !important; }
[data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stSlider label, [data-testid="stSidebar"] .stCheckbox label, [data-testid="stSidebar"] .stRadio label { color: #CCCCCC !important; font-size: 0.85rem; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #F68B1E !important; font-weight: 800; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #F68B1E44; padding-bottom: 4px; margin-bottom: 8px; }
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child { background-color: #3A3A3A !important; border-color: #F68B1E !important; border-radius: 6px !important; }
[data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stSelectboxValue"], [data-testid="stSidebar"] [data-baseweb="select"] span, [data-testid="stSidebar"] [data-baseweb="select"] div { color: #FFFFFF !important; }
[data-baseweb="popover"] [data-baseweb="menu"] { background-color: #2D2D2D !important; }
[data-baseweb="popover"] [role="option"] { background-color: #2D2D2D !important; color: #F5F5F5 !important; }
[data-baseweb="popover"] [role="option"]:hover, [data-baseweb="popover"] [aria-selected="true"] { background-color: #F68B1E !important; color: #FFFFFF !important; }

.jumia-header { background: linear-gradient(135deg, #F68B1E 0%, #D4730A 100%); border-radius: 12px; padding: 20px 28px 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 16px; box-shadow: 0 4px 16px #F68B1E44; }
.jumia-header h1 { margin: 0; color: #FFFFFF; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; }
.jumia-header p { margin: 4px 0 0; color: #FFE0B2; font-size: 0.9rem; }
.jumia-logo-dot { width: 48px; height: 48px; background: #FFFFFF; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.6rem; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }

[data-testid="stTabs"] [role="tablist"] { gap: 4px; border-bottom: 2px solid #F68B1E; }
[data-testid="stTabs"] button[role="tab"] { background: #FFFFFF; border: 1px solid #E0E0E0; border-bottom: none; border-radius: 8px 8px 0 0; color: #6B6B6B; font-weight: 600; font-size: 0.88rem; padding: 8px 18px; transition: all 0.2s ease; }
[data-testid="stTabs"] button[role="tab"]:hover { background: #FFF4E6; color: #F68B1E; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { background: #F68B1E; color: #FFFFFF !important; border-color: #F68B1E; font-weight: 700; border-top-left-radius: 10px; border-top-right-radius: 10px; }

[data-testid="stButton"] button[kind="primary"], [data-testid="stBaseButton-primary"] { background: linear-gradient(135deg, #F68B1E 0%, #D4730A 100%) !important; color: #FFFFFF !important; border: none !important; border-radius: 8px !important; font-weight: 700 !important; font-size: 0.9rem !important; padding: 10px 20px !important; box-shadow: 0 3px 10px #F68B1E55 !important; transition: all 0.2s ease !important; }
[data-testid="stButton"] button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover { box-shadow: 0 5px 18px #F68B1E88 !important; transform: translateY(-2px); }

/* Orange hover for secondary buttons */
[data-testid="stButton"] button:not([kind="primary"]):hover {
    background: #F68B1E !important;
    color: #FFFFFF !important;
    border-color: #F68B1E !important;
}

/* Smooth Load Animation for Cards */
@keyframes fadeSlideUp {
    from { opacity: 0; transform: translateY(15px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Premium Custom Product Card */
div[data-testid="column"]:has([title="RemoveCard"]) {
    position: relative;
    background: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 10px;
    padding-top: 10px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.04);
    margin-bottom: 16px;
    transition: all 0.25s ease-in-out;
    animation: fadeSlideUp 0.4s ease-out forwards;
}
div[data-testid="column"]:has([title="RemoveCard"]):hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 20px rgba(246,139,30,0.12);
    border-color: #F68B1E;
}

/* Floating Close Button - Styled Orange Overlay half touching */
div[data-testid="stTooltipHoverTarget"]:has([title="RemoveCard"]),
div[title="RemoveCard"] {
    position: absolute !important;
    top: -12px !important;
    right: -12px !important;
    z-index: 999 !important;
    width: auto !important;
}
button[title="RemoveCard"], div[title="RemoveCard"] > button {
    background: #F68B1E !important;
    color: white !important;
    border: 2px solid white !important;
    border-radius: 50% !important;
    width: 24px !important;
    height: 24px !important;
    min-height: 24px !important;
    min-width: 24px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
    font-weight: 900;
    font-size: 12px !important;
    transition: transform 0.2s ease, background 0.2s ease !important;
    line-height: 1 !important;
}
button[title="RemoveCard"]:hover, div[title="RemoveCard"] > button:hover {
    background: #D4730A !important;
    transform: scale(1.15) !important;
}

[data-testid="stImage"] img { border-radius: 8px; border: 1px solid #f0f0f0; }
[data-testid="stProgress"] div[role="progressbar"] > div { background: linear-gradient(90deg, #F68B1E, #D4730A) !important; }
[data-testid="stSpinner"] svg { color: #F68B1E !important; }

/* Product Image Hover Effects & Link Badge */
.img-hover-container { transition: transform 0.2s ease; display: block; position: relative; }
.img-hover-container:hover { transform: scale(1.03); }
.jumia-badge { position:absolute; top:8px; left:8px; background:#F68B1E; color:#fff !important; font-size:11px; font-weight:900; padding:4px 10px; border-radius:12px; box-shadow:0 3px 6px rgba(0,0,0,0.25); transition: background 0.2s; letter-spacing: 0.5px; z-index: 10; text-decoration:none; }
.jumia-badge:hover { background:#D4730A !important; color:#fff !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  CATEGORY SCRAPING & FLAG SVG LOADER
# ══════════════════════════════════════════════════════════════════════════════
def extract_category_links(category_url: str, max_pages: int = 1) -> list:
    """Extracts product URLs from a category page via standard Python requests."""
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
        except Exception as e:
            st.warning(f"Error fetching category page {page}: {e}")
            
    return list(dict.fromkeys(extracted))

def extract_category_images(category_url: str, max_pages: int = 1) -> list:
    """Extracts high-res image URLs directly from a category page for bulk tagging."""
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
                            img_url = re.sub(r"fit-in/\d+x\d+/", "fit-in/500x500/", img_url) # Force High Res
                            
                            name = "product"
                            a_tag = article.find("a", class_="core")
                            if a_tag:
                                name = a_tag.get("data-id") or a_tag.get("data-name") or "product"
                                name = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_")[:30]
                                
                            extracted.append({"url": img_url, "name": f"{name}_{len(extracted)}"})
        except Exception as e:
            st.warning(f"Error fetching images from page {page}: {e}")
            
    return extracted

def get_flag_html(country_code: str) -> str:
    """Reads the SVG from the flags folder and returns an HTML img tag with base64."""
    for ext in [".svg", ""]:
        path = os.path.join("flags", f"{country_code.lower()}{ext}")
        if os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                return f"<img src='data:image/svg+xml;base64,{b64}' style='height:3.2em; vertical-align:middle; margin-left:12px; box-shadow:0 4px 8px rgba(0,0,0,0.15); border-radius:6px;'/>"
    return ""

@st.dialog("Image Processing")
def process_image_dialog(pu, sku, has_badge, region_choice, default_tag):
    if pu == "N/A" or not pu:
        st.error("No image available to process.")
        return

    fr_display_names = {
        "Renewed": "Renouvelé", "Refurbished": "Reconditionné",
        "Grade A": "Grade A",   "Grade B": "Grade B", "Grade C": "Grade C"
    }

    is_red_badge = "YES" in str(has_badge).upper()
    
    st.markdown(f"**SKU:** `{sku}` &nbsp;&nbsp;|&nbsp;&nbsp; **Mode:** {'🔄 Convert Image' if is_red_badge else '🏷 Tag Image'}")

    chosen_tag = st.selectbox(
        "Select Grade:", list(TAG_FILES.keys()), 
        index=list(TAG_FILES.keys()).index(default_tag) if default_tag in TAG_FILES else 0,
        format_func=lambda x: fr_display_names.get(x, x) if region_choice == "Morocco (MA)" else x
    )
    
    scale = 100
    if not is_red_badge:
        scale = st.slider("Product Size %", 50, 150, 100)

    with st.spinner("Processing image..."):
        try:
            r = requests.get(pu, timeout=10)
            raw_img = Image.open(BytesIO(r.content))
            tag_img = load_tag_image(chosen_tag, region_choice)
            
            clean_sku = re.sub(r"[^\w\s-]", "", str(sku)).strip()[:40] or "product"
            
            if is_red_badge:
                res_img = strip_and_retag(raw_img.convert("RGB"), tag_img)
                dl_name = f"converted_{clean_sku}.jpg"
            else:
                res_img = apply_tag(raw_img.convert("RGBA"), tag_img, scale)
                dl_name = f"tagged_{clean_sku}.jpg"
                
            st.image(res_img, use_container_width=True)
            st.download_button("📥 Download Image", image_to_jpeg_bytes(res_img), dl_name, "image/jpeg", use_container_width=True, type="primary")

        except Exception as e:
            st.error(f"Failed to process image: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE INITIALISATION
# ══════════════════════════════════════════════════════════════════════════════
_defaults = {
    "scraped_results":       [],
    "failed_items":          [],
    "single_img_bytes":      None,
    "single_img_label":      "",
    "single_img_source":     None,
    "single_scale":          100,
    "cv_img_bytes":          None,
    "cv_img_label":          "",
    "cv_img_source":         None,
    "bulk_upload_products":  [],
    "bulk_url_products":     [],
    "bulk_excel_products":   [],
    "bulk_sku_results":      [],
    "cv_bulk_sku_results":   [],
    "cv_bulk_upload":        [],
    "cv_bulk_url":           [],
    "individual_scales":     {},
    "geo_country":           None,
    "mismatch_detected":     False,
    "mismatch_url_country":  None,
    "mismatch_active_country": None,
    "mismatch_context":      None,
    "mismatch_resolved":     False,
    "pending_img_bytes":     None,
    "pending_img_label":     "",
    "pending_img_source":    None,
    "pending_img_target":    None,
    "b_bulk_zip":            None,
    "b_bulk_preview":        [],
    "b_bulk_total":          0,
    "cv_bulk_zip":           None,
    "cv_bulk_preview":       [],
    "cv_bulk_total":         0,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state["geo_country"] is None:
    st.session_state["geo_country"] = _detect_country()

_geo_default  = st.session_state["geo_country"]
_country_list = list(DOMAIN_MAP.keys())
_default_idx  = _country_list.index(_geo_default) if _geo_default and _geo_default in _country_list else 0

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("Region")
    if _geo_default:
        st.markdown(
            f"""<div style="background:#F68B1E22;border:1px solid #F68B1E55;border-radius:6px;padding:6px 10px;margin-bottom:8px;font-size:0.78rem;color:#F68B1E!important;">
            &#128205; Auto-detected: <strong style="color:#F68B1E">{_geo_default}</strong></div>""",
            unsafe_allow_html=True)

    region_choice = st.selectbox("Select Country:", _country_list, index=_default_idx,
                                  key="region_select",
                                  help="Used for product analysis and all SKU image lookups")
    domain   = DOMAIN_MAP[region_choice]
    base_url = f"https://www.{domain}"
    active_cc = region_choice.split("(")[-1].strip(")")
    sidebar_flag = get_flag_html(active_cc)

    st.markdown(
        f"""<div style="display:flex; justify-content:center; align-items:center; background:linear-gradient(135deg,#F68B1E,#D4730A);border-radius:20px;padding:5px 12px;margin:4px 0 8px;font-size:0.8rem;font-weight:700;color:#fff!important;letter-spacing:0.03em;">
        Active: {region_choice} {sidebar_flag}</div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.header("Tag Settings")

    fr_display_names = {
        "Renewed": "Renouvelé", "Refurbished": "Reconditionné",
        "Grade A": "Grade A",   "Grade B": "Grade B", "Grade C": "Grade C"
    }

    tag_type = st.selectbox(
        "Refurbished Grade:", list(TAG_FILES.keys()), key="tag_select",
        format_func=lambda x: fr_display_names.get(x, x) if region_choice == "Morocco (MA)" else x
    )
    display_tag = fr_display_names.get(tag_type, tag_type) if region_choice == "Morocco (MA)" else tag_type

    st.markdown(
        f"""<div style="background:#2D2D2D;border:1px solid #F68B1E;border-radius:20px;padding:5px 12px;text-align:center;margin:4px 0 8px;font-size:0.8rem;font-weight:700;color:#F68B1E!important;">
        Grade: {display_tag}</div>""", unsafe_allow_html=True)

    st.markdown("---")
    
    with st.expander("⚙️ Advanced Analyzer Settings", expanded=False):
        show_browser    = st.checkbox("Show Browser (Debug Mode)", value=False)
        max_workers     = st.slider("Parallel Workers:", 1, 10, 5)
        timeout_seconds = st.slider("Page Timeout (s):", 10, 30, 20)
        check_images    = st.checkbox("Analyze Images for Red Badges", value=True)
        force_selenium  = st.checkbox("Force Browser Mode (slower)", value=False)
        st.info(f"{max_workers} workers · {timeout_seconds}s timeout", icon=":material/bolt:")

        if PROMO_HASH is None:
            st.warning("Grading image hash unavailable — grading guide checks temporarily disabled.", icon="⚠️")

# ══════════════════════════════════════════════════════════════════════════════
#  COUNTRY-MISMATCH DIALOG
# ══════════════════════════════════════════════════════════════════════════════
@st.dialog("Country Mismatch Detected")
def show_country_mismatch_dialog(active_country: str, found_country: str, context: str):
    st.markdown(
        f"""<div style="text-align:center;padding:8px 0 16px;">
  <div style="font-size:2.5rem;margin-bottom:8px;">🌍</div>
  <div style="font-size:1.05rem;font-weight:700;color:#1A1A1A;margin-bottom:6px;">Product is from a different country</div>
  <div style="font-size:0.9rem;color:#6B6B6B;line-height:1.5;">The product belongs to <strong style="color:#F68B1E">{found_country}</strong>, but your active region is <strong style="color:#1A1A1A">{active_country}</strong>.</div>
</div>""", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(f"Switch to {found_country}", type="primary", use_container_width=True,
                     icon=":material/swap_horiz:", key=f"mismatch_switch_{context}"):
            st.session_state["region_select"] = found_country
            _commit_pending_image(context)
            st.session_state["mismatch_detected"] = False
            st.session_state["mismatch_resolved"] = True
            st.rerun()
    with col_b:
        if st.button(f"Keep {active_country}", use_container_width=True,
                     icon=":material/check:", key=f"mismatch_keep_{context}"):
            _commit_pending_image(context)
            st.session_state["mismatch_detected"] = False
            st.session_state["mismatch_resolved"] = True
            st.rerun()
    st.caption("The image has been loaded — this choice only affects which country will be used for future searches.")

def _commit_pending_image(context: str):
    b = st.session_state.get("pending_img_bytes")
    if b is None: return
    target = st.session_state.get("pending_img_target", context)
    if target == "single":
        st.session_state["single_img_bytes"]  = b
        st.session_state["single_img_label"]  = st.session_state.get("pending_img_label", "")
        st.session_state["single_img_source"] = st.session_state.get("pending_img_source", "sku")
        st.session_state["single_scale"]      = 100
    elif target == "cv_single":
        st.session_state["cv_img_bytes"]  = b
        st.session_state["cv_img_label"]  = st.session_state.get("pending_img_label", "")
        st.session_state["cv_img_source"] = st.session_state.get("pending_img_source", "sku")
    st.session_state.update({"pending_img_bytes": None, "pending_img_label": "", "pending_img_source": None, "pending_img_target": None})

def trigger_mismatch_or_commit(img: Image.Image, label: str, source: str, found_country: str | None, active_country: str, target_slot: str):
    fmt = "PNG" if source == "upload" else "JPEG"
    img_bytes = pil_to_bytes(img, fmt=fmt)
    if found_country and found_country != active_country:
        st.session_state.update({
            "pending_img_bytes":       img_bytes,
            "pending_img_label":       label,
            "pending_img_source":      source,
            "pending_img_target":      target_slot,
            "mismatch_detected":       True,
            "mismatch_url_country":    found_country,
            "mismatch_active_country": active_country,
            "mismatch_context":        target_slot,
            "mismatch_resolved":       False,
        })
    else:
        st.session_state.update({
            "pending_img_bytes":  img_bytes,
            "pending_img_label":  label,
            "pending_img_source": source,
            "pending_img_target": target_slot,
        })
        _commit_pending_image(target_slot)

if st.session_state.get("mismatch_detected"):
    show_country_mismatch_dialog(
        active_country=st.session_state["mismatch_active_country"],
        found_country=st.session_state["mismatch_url_country"],
        context=st.session_state["mismatch_context"],
    )

# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_analyze, tab_single, tab_bulk, tab_convert = st.tabs([
    "Analyze Products",
    "Tag — Single Image",
    "Tag — Bulk",
    "Convert Tag",
])

# ┌─────────────────────────────────────────────────────────────────────────────
# │  TAB 1 — ANALYZE PRODUCTS
# └─────────────────────────────────────────────────────────────────────────────
with tab_analyze:
    tab_flag_html = get_flag_html(active_cc)
    st.markdown(f"<h3 style='display:flex; align-items:center;'>Analyze Products {tab_flag_html}</h3>", unsafe_allow_html=True)

    analyze_method = st.radio(
        "Input method:",
        ["Paste SKUs / URLs", "Upload Excel / CSV", "Category URL"],
        horizontal=True, key="a_method"
    )

    text_in = None; file_in = None; cat_url_in = None; max_cat_pages = 1

    if analyze_method == "Paste SKUs / URLs":
        text_in = st.text_area("Paste SKUs or URLs:", height=100,
                               placeholder="One SKU or URL per line\nExample: SA948MP5EER52NAFAMZ", key="a_text")
    elif analyze_method == "Upload Excel / CSV":
        file_in = st.file_uploader("Upload Excel / CSV with SKUs:", type=["xlsx","csv"], key="a_file")
    else:
        cat_url_in    = st.text_input("Category URL:", placeholder=f"https://www.{domain}/smartphones/", key="a_cat")
        max_cat_pages = st.number_input("Max pages (40 products/page):", min_value=1, max_value=50, value=1, step=1)

    st.markdown("---")

    if st.button("Start Analysis", type="primary", icon=":material/play_arrow:", key="a_run"):
        targets = process_inputs(text_in, file_in, domain)

        if cat_url_in:
            with st.spinner(f"Extracting links from up to {max_cat_pages} page(s)…"):
                links = extract_category_links(cat_url_in, max_cat_pages)
                for lnk in links:
                    targets.append({"type":"url","value":lnk,"original_sku":""})
                if links:
                    st.success(f"Extracted {len(links)} products.", icon=":material/check_circle:")
                else:
                    st.warning("No product links found.", icon=":material/warning:")

        if not targets:
            st.warning("No valid input.", icon=":material/warning:")
        else:
            st.session_state["scraped_results"] = []
            st.session_state["failed_items"]    = []

            prog = st.progress(0)
            t0   = time.time()

            with st.status(f"Analyzing {len(targets)} products…", expanded=True) as run_status:
                info_text       = st.empty()
                c1, c2          = st.columns([1, 3])
                img_placeholder = c1.empty()
                txt_placeholder = c2.empty()

                all_results, all_failed = [], []
                processed = 0

                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    fs = {
                        ex.submit(scrape_item, t, timeout=timeout_seconds, country_code=active_cc, do_check=check_images): i
                        for i, t in enumerate(targets)
                    }
                    ordered_results = [None] * len(targets)

                    for f in as_completed(fs):
                        i = fs[f]
                        t = targets[i]
                        try:
                            r = f.result()
                            if r["Product Name"] in {"SYSTEM_ERROR", "TIMEOUT", "CONNECTION_ERROR", "ERROR_FETCHING", "SKU_NOT_FOUND"}:
                                all_failed.append({
                                    "input": t.get("original_sku", t["value"]),
                                    "error": r["Product Name"]
                                })
                            else:
                                ordered_results[i] = r
                                img_url = r.get("Primary Image URL","N/A")
                                if img_url != "N/A":
                                    try: img_placeholder.image(img_url, width=150)
                                    except Exception: img_placeholder.empty()
                                txt_placeholder.caption(
                                    f"**{r.get('Product Name','N/A')[:70]}** \n"
                                    f"Refurb: {r.get('Title has Refurbished','NO')} | "
                                    f"Auth: {r.get('Seller authorized','NO')} | "
                                    f"Images: {r.get('Total Product Images',0)}"
                                )
                        except Exception as e:
                            all_failed.append({"input": t.get("original_sku", t.get("value","")), "error": str(e)})

                        processed += 1
                        prog.progress(processed / len(targets))
                        elapsed = time.time() - t0
                        rem = (len(targets) - processed) * (elapsed / processed) if processed else 0
                        run_status.update(label=f"Analyzing… {processed}/{len(targets)}")
                        info_text.markdown(
                            f"**Speed:** {processed/max(elapsed,0.1):.1f} items/sec &nbsp;|&nbsp; "
                            f"**Remaining:** ~{rem:.0f}s &nbsp;|&nbsp; "
                            f"**Mode:** Apps Script Backend"
                        )

                all_results = [r for r in ordered_results if r is not None]
                elapsed = time.time() - t0

                if all_failed:
                    run_status.update(label=f"Done with issues: {len(all_results)} ok, {len(all_failed)} failed ({elapsed:.1f}s)", state="error")
                else:
                    run_status.update(label=f"Done — {len(targets)} products in {elapsed:.1f}s", state="complete")

            st.session_state["scraped_results"] = all_results
            st.session_state["failed_items"]    = all_failed
            time.sleep(0.5)
            st.rerun()

    if st.session_state["failed_items"]:
        with st.expander(f"Failed Items ({len(st.session_state['failed_items'])})", expanded=False):
            st.dataframe(pd.DataFrame(st.session_state["failed_items"]), use_container_width=True)

    if st.session_state["scraped_results"]:
        df = pd.DataFrame(st.session_state["scraped_results"])
        priority_cols = [
            "SKU","Product Name","Brand","Title has Refurbished","Has refurb tag",
            "Has Warranty","Warranty Duration","Seller Name","Seller authorized",
            "Total Product Images","Grading last image","Description has Grading guide",
            "grading tag","Has info-graphics","Infographic Image Count","Price",
            "Product Rating","Express","Category","Refurbished Indicators",
            "Warranty Source","Warranty Address","Primary Image URL","Product URL","Input Source",
        ]
        df = df[[c for c in priority_cols if c in df.columns]]

        st.subheader("Summary")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Analyzed", len(df))
        m2.metric("Refurbished",   int((df.get("Title has Refurbished","NO") == "YES").sum()))
        m3.metric("Auth Sellers",  int((df.get("Seller authorized","NO")     == "YES").sum()))
        m4.metric("Red Badges",    int(df.get("grading tag","").str.contains("YES", na=False).sum()))
        m5.metric("Avg Images",    f"{df.get('Total Product Images',pd.Series([0])).mean():.1f}")
        st.markdown("---")

        gal_c1, gal_c2 = st.columns([3,1])
        with gal_c1: st.subheader("Product Gallery")
        with gal_c2: show_gallery = st.toggle("Show Gallery", value=True, key="a_show_gallery")

        if show_gallery:
            gcol, fcol = st.columns([3,1])
            with fcol:
                view_mode        = st.radio("View:", ["Grid","List"], horizontal=True, key="a_view")
                show_refurb_only = st.checkbox("Refurbished only", key="a_refurb_filter")
            display_df = df[df["Title has Refurbished"]=="YES"] if (show_refurb_only and "Title has Refurbished" in df.columns) else df

            if view_mode == "Grid":
                for row in range((len(display_df)+4)//5):
                    cols_ = st.columns(5)
                    for ci in range(5):
                        idx = row*5 + ci
                        if idx >= len(display_df): break
                        
                        orig_idx = display_df.index[idx]
                        item = display_df.iloc[idx]
                        
                        with cols_[ci]:
                            if st.button("✖", key=f"del_a_{orig_idx}", help="RemoveCard"):
                                st.session_state["scraped_results"].pop(orig_idx)
                                st.rerun()
                                
                            pu = item.get("Primary Image URL", "https://via.placeholder.com/200?text=No+Image")
                            if pu == "N/A": pu = "https://via.placeholder.com/200?text=No+Image"
                            prod_url = item.get("Product URL", "#")
                            
                            st.markdown(f"""
                            <div class="img-hover-container">
                                <img src="{pu}" style="width:100%; border-radius:8px; border:1px solid #e0e0e0; display:block;">
                                <a href="{prod_url}" target="_blank" class="jumia-badge">🔗 Jumia</a>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            sku = item.get("SKU", "N/A")
                            seller = item.get("Seller Name", "N/A")
                            has_badge = item.get("grading tag", "NO")
                            
                            st.markdown(f"""
                            <div style="font-size:12px; line-height:1.4; margin-top:12px; margin-bottom:12px; text-align:center;">
                                <div style="font-weight:800; color:#FFF; letter-spacing:0.5px; background:#F68B1E; padding:4px 10px; display:inline-block; border-radius:6px; border:1px solid #D4730A; margin-bottom:6px; font-family:monospace;">{sku}</div><br>
                                <div style="display:inline-block; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#555;" title="{seller}"><b style="color:#111; font-size:13px;">{seller}</b></div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            btn_label = "🔄 Convert image" if "YES" in str(has_badge).upper() else "🏷 Tag image"
                            if st.button(btn_label, key=f"qproc_{orig_idx}", use_container_width=True):
                                process_image_dialog(pu, sku, has_badge, region_choice, tag_type)
            else:
                for orig_idx, item in display_df.iterrows():
                    with st.container():
                        c1, c2, c3 = st.columns([1,4,1])
                        with c1:
                            pu = item.get("Primary Image URL", "https://via.placeholder.com/200?text=No+Image")
                            if pu == "N/A": pu = "https://via.placeholder.com/200?text=No+Image"
                            prod_url = item.get("Product URL", "#")
                            st.markdown(f"""
                            <div class="img-hover-container" style="width:150px;">
                                <img src="{pu}" style="width:100%; border-radius:8px; border:1px solid #e0e0e0; display:block;">
                                <a href="{prod_url}" target="_blank" class="jumia-badge" style="top:4px; left:4px; padding:2px 6px; font-size:9px;">🔗 Jumia</a>
                            </div>
                            """, unsafe_allow_html=True)
                        with c2:
                            st.markdown(f"**<a href='{prod_url}' target='_blank' style='color:#1A1A1A; text-decoration:none;'>{item.get('Product Name','N/A')}</a>**", unsafe_allow_html=True)
                            r1 = st.columns(5)
                            r1[0].caption(f"**Brand:** {item.get('Brand','N/A')}")
                            r1[1].caption(f"**Refurb:** {item.get('Title has Refurbished','NO')}")
                            r1[2].caption(f"**Grade Img:** {item.get('Grading last image','NO')}")
                            r1[3].caption(f"**Auth Seller:** {item.get('Seller authorized','NO')}")
                            r1[4].caption(f"**Price:** {item.get('Price','N/A')}")
                            r2 = st.columns(3)
                            r2[0].caption(f"**Seller:** {item.get('Seller Name','N/A')}")
                            r2[1].caption(f"**SKU:** {item.get('SKU','N/A')}")
                            r2[2].caption(f"**Desc Guide:** {item.get('Description has Grading guide','NO')}")
                        with c3:
                            has_badge = item.get("grading tag", "NO")
                            btn_label = "🔄 Convert image" if "YES" in str(has_badge).upper() else "🏷 Tag image"
                            if st.button(btn_label, key=f"qproc_list_{orig_idx}", use_container_width=True):
                                process_image_dialog(pu, item.get('SKU', 'N/A'), has_badge, region_choice, tag_type)
                            if st.button("✖ Remove", key=f"del_a_list_{orig_idx}"):
                                st.session_state["scraped_results"].pop(orig_idx)
                                st.rerun()
                        st.divider()

        if "Title has Refurbished" in df.columns and (df["Title has Refurbished"]=="YES").any():
            st.markdown("---")
            st.subheader("Refurbished Items Detail")
            st.dataframe(df[df["Title has Refurbished"]=="YES"], use_container_width=True)

        st.markdown("---")
        st.subheader("Full Results")
        st.caption("Use the dropdown to show/hide columns. Select rows to download a subset.")

        all_cols = list(df.columns)
        default_visible = [c for c in [
            "SKU","Product Name","Brand","Title has Refurbished","Has refurb tag",
            "Has Warranty","Warranty Duration","Seller Name","Seller authorized",
            "Total Product Images","Grading last image","Description has Grading guide",
            "grading tag","Price"
        ] if c in all_cols]

        selected_cols   = st.multiselect("Visible Columns:", options=all_cols, default=default_visible)
        display_full_df = df[selected_cols] if selected_cols else df

        def _highlight(row):
            return (["background-color:#fffacd"] * len(row) if "Brand" in row.index and row["Brand"] == "Renewed" else [""] * len(row))

        selected_indices = []

        try:
            event = st.dataframe(
                display_full_df.style.apply(_highlight, axis=1),
                use_container_width=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="interactive_df"
            )
            selected_indices = list(event.selection.rows or [])
        except Exception:
            st.dataframe(display_full_df, use_container_width=True)
            selected_indices = []

        valid_selected_positions = [i for i in selected_indices if isinstance(i, int) and 0 <= i < len(df)]
        download_df = df.iloc[valid_selected_positions] if valid_selected_positions else df

        if valid_selected_positions: st.caption(f"Selected {len(valid_selected_positions)} row(s) for download.")
        elif selected_indices: st.caption("Previous row selection was cleared because results changed — downloading all rows.")
        else: st.caption("No rows selected — downloading all rows.")

        st.download_button(
            "Download CSV",
            download_df.to_csv(index=False).encode("utf-8"),
            f"analysis_{int(time.time())}.csv",
            "text/csv",
            icon=":material/download:",
            key="a_dl"
        )
    else:
        st.info("No analysis data available yet. Please use the controls above to begin.", icon="ℹ️")

# ┌─────────────────────────────────────────────────────────────────────────────
# │  TAB 2 — TAG: SINGLE IMAGE
# └─────────────────────────────────────────────────────────────────────────────
with tab_single:
    tab_flag_html2 = get_flag_html(active_cc)
    st.markdown(f"<h3 style='display:flex; align-items:center;'>Tag — Single Image &nbsp;&nbsp;<span style='font-size:16px; font-weight:normal; color:#666;'>Grade: {display_tag}</span> {tab_flag_html2}</h3>", unsafe_allow_html=True)
    
    col_in, col_out = st.columns([1, 1])

    with col_in:
        st.markdown("#### Image Source")
        src_method = st.radio("Source:", ["Upload from device","Load from Image URL","Load from SKU"], horizontal=True, key="s_src")

        if st.session_state.get("s_src_prev") != src_method:
            st.session_state.update({
                "single_img_bytes": None, "single_img_label": "",
                "single_img_source": None, "single_scale": 100,
                "s_src_prev": src_method
            })

        if src_method == "Upload from device":
            f = st.file_uploader("Choose an image file:", type=["png","jpg","jpeg","webp"], key="s_upload")
            if f is not None:
                fhash = hashlib.md5(f.getvalue()).hexdigest()
                if st.session_state.get("single_img_label") != fhash:
                    img = Image.open(f).convert("RGBA")
                    st.session_state.update({
                        "single_img_bytes":  pil_to_bytes(img, fmt="PNG"),
                        "single_img_label":  fhash,
                        "single_img_source": "upload",
                        "single_scale":      100,
                    })

        elif src_method == "Load from Image URL":
            img_url = st.text_input("Image URL:", key="s_url")
            if st.button("Load Image", icon=":material/download:", key="s_url_load"):
                if img_url:
                    with st.spinner("Fetching image…"):
                        try:
                            url_country = detect_country_from_url(img_url)
                            r = _SESSION.get(img_url, timeout=15)
                            r.raise_for_status()
                            img = Image.open(BytesIO(r.content)).convert("RGBA")
                            trigger_mismatch_or_commit(img, img_url, "url", url_country, region_choice, "single")
                            if not st.session_state.get("mismatch_detected"): st.success("Image loaded.", icon=":material/check_circle:")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not load image: {e}", icon=":material/error:")
                else: st.warning("Please enter a URL.", icon=":material/warning:")

        else:
            sku_val = st.text_input("Product SKU:", placeholder="e.g. GE840EA6C62GANAFAMZ", key="s_sku")
            st.caption(f"Searches **{base_url}** first, then all other Jumia countries.")
            if st.button("Search & Extract Image", icon=":material/search:", key="s_sku_search", type="primary"):
                if sku_val.strip():
                    holder = st.empty()
                    holder.info(f"Searching for SKU `{sku_val.strip()}`…", icon=":material/search:")
                    img, found_country = fetch_image_from_sku_via_apps_script(sku_val.strip(), active_country=region_choice)
                    holder.empty()
                    if img is not None:
                        trigger_mismatch_or_commit(img, sku_val.strip(), "sku", found_country, region_choice, "single")
                        if not st.session_state.get("mismatch_detected"): st.success(f"Image loaded for **{sku_val.strip()}**", icon=":material/check_circle:")
                        st.rerun()
                    else: st.error(f"SKU **{sku_val.strip()}** not found on any Jumia country.", icon=":material/search_off:")
                else: st.warning("Please enter a SKU.", icon=":material/warning:")

        if st.session_state["single_img_bytes"] is not None:
            src  = st.session_state["single_img_source"]
            icon = ":material/upload:" if src == "upload" else ":material/link:" if src == "url" else ":material/qr_code:"
            st.info(f"Image loaded — {st.session_state['single_img_label']}", icon=icon)
            st.markdown("---")
            st.markdown("#### Image Size")
            st.caption("100% = auto-fit. Increase to fill more of the frame.")
            new_scale = st.slider("Product size (% of frame):", 40, 180, st.session_state["single_scale"], 5, key="s_scale_slider")
            st.session_state["single_scale"] = new_scale
            sc1, sc2, sc3 = st.columns(3)
            if sc1.button("Smaller", icon=":material/remove:", key="s_smaller"):
                st.session_state["single_scale"] = max(40,  st.session_state["single_scale"] - 5); st.rerun()
            if sc2.button("Reset (100%)", icon=":material/refresh:", key="s_reset"):
                st.session_state["single_scale"] = 100; st.rerun()
            if sc3.button("Larger", icon=":material/add:", key="s_larger"):
                st.session_state["single_scale"] = min(180, st.session_state["single_scale"] + 5); st.rerun()

    with col_out:
        st.markdown("#### Preview")
        if st.session_state["single_img_bytes"] is not None:
            tag_img = load_tag_image(tag_type, region_choice)
            if tag_img is not None:
                product_img = bytes_to_pil(st.session_state["single_img_bytes"]).convert("RGBA")
                result      = apply_tag(product_img, tag_img, st.session_state["single_scale"])
                st.image(result, use_container_width=True, caption=f"Grade: {display_tag}  ·  Size: {st.session_state['single_scale']}%")
                st.markdown("---")
                st.download_button("Download Tagged Image (JPEG)", image_to_jpeg_bytes(result), f"tagged_{tag_type.lower().replace(' ','_')}.jpg", "image/jpeg", use_container_width=True, icon=":material/download:", key="s_dl")
        else: st.info("Load an image using one of the source options on the left.", icon=":material/image:")

# ┌─────────────────────────────────────────────────────────────────────────────
# │  TAB 3 — TAG: BULK
# └─────────────────────────────────────────────────────────────────────────────
with tab_bulk:
    tab_flag_html3 = get_flag_html(active_cc)
    st.markdown(f"<h3 style='display:flex; align-items:center;'>Tag — Bulk Processing &nbsp;&nbsp;<span style='font-size:16px; font-weight:normal; color:#666;'>Grade: {display_tag}</span> {tab_flag_html3}</h3>", unsafe_allow_html=True)
    st.caption("Images are auto-cropped and fitted. Per-image size controls are available before processing.")

    bulk_method = st.radio("Input method:", ["Upload multiple images","Enter URLs manually","Upload Excel file with URLs","Enter SKUs", "Category URL"], key="b_method")

    active_bulk_list = "bulk_upload_products"
    if bulk_method == "Upload multiple images":
        files = st.file_uploader("Choose image files:", type=["png","jpg","jpeg","webp"], accept_multiple_files=True, key="b_upload")
        if files:
            new_hash = hashlib.md5(b"".join(f.getvalue()[:64] for f in files)).hexdigest()
            if st.session_state.get("_bulk_upload_hash") != new_hash:
                loaded = []
                for f in files:
                    try:
                        img = Image.open(f).convert("RGBA")
                        loaded.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": f.name.rsplit(".",1)[0]})
                    except Exception as e:
                        st.warning(f"Could not load {f.name}: {e}", icon=":material/warning:")
                st.session_state["bulk_upload_products"] = loaded
                st.session_state["_bulk_upload_hash"]    = new_hash
            st.info(f"{len(st.session_state['bulk_upload_products'])} files ready.", icon=":material/photo_library:")
        products_to_process = st.session_state.get("bulk_upload_products", [])

    elif bulk_method == "Enter URLs manually":
        active_bulk_list = "bulk_url_products"
        raw_urls = st.text_area("Image URLs (one per line):", height=160, placeholder="https://example.com/image1.jpg", key="b_urls")
        if st.button("Load Images from URLs", icon=":material/download:", key="b_url_load"):
            if raw_urls.strip():
                url_list = [u.strip() for u in raw_urls.splitlines() if u.strip()]
                loaded   = []
                prog_url = st.progress(0)
                for i, u in enumerate(url_list):
                    try:
                        r = _SESSION.get(u, timeout=12)
                        r.raise_for_status()
                        loaded.append({"bytes": pil_to_bytes(Image.open(BytesIO(r.content)).convert("RGBA"), fmt="JPEG"), "name": f"image_{i+1}"})
                    except Exception as e: st.warning(f"URL {i+1} failed: {e}", icon=":material/warning:")
                    prog_url.progress((i+1)/len(url_list))
                st.session_state["bulk_url_products"] = loaded
                st.success(f"Loaded {len(loaded)}/{len(url_list)} images.", icon=":material/check_circle:")
        if st.session_state["bulk_url_products"]: st.info(f"{len(st.session_state['bulk_url_products'])} images ready.", icon=":material/check_circle:")
        products_to_process = st.session_state.get("bulk_url_products", [])

    elif bulk_method == "Upload Excel file with URLs":
        active_bulk_list = "bulk_excel_products"
        st.caption("**Column A:** Image URLs  ·  **Column B (optional):** Product name")
        xf = st.file_uploader("Excel file (.xlsx / .xls):", type=["xlsx","xls"], key="b_excel")
        if xf:
            xhash = hashlib.md5(xf.getvalue()[:256]).hexdigest()
            if st.session_state.get("_bulk_excel_hash") != xhash:
                try:
                    df_xl = pd.read_excel(xf)
                    urls  = df_xl.iloc[:,0].dropna().astype(str).tolist()
                    names = (df_xl.iloc[:,1].dropna().astype(str).tolist() if len(df_xl.columns) > 1 else [f"product_{i+1}" for i in range(len(urls))])
                    st.info(f"Found {len(urls)} URLs. Loading…", icon=":material/table:")
                    loaded = []
                    prog_xl = st.progress(0)
                    for i,(u,n) in enumerate(zip(urls,names)):
                        try:
                            r = _SESSION.get(u, timeout=12)
                            r.raise_for_status()
                            clean = re.sub(r"[^\w\s-]","",n).strip().replace(" ","_")
                            loaded.append({"bytes": pil_to_bytes(Image.open(BytesIO(r.content)).convert("RGBA"), fmt="JPEG"), "name": clean or f"product_{i+1}"})
                        except Exception as e: st.warning(f"Could not load {n}: {e}", icon=":material/warning:")
                        prog_xl.progress((i+1)/len(urls))
                    st.session_state["bulk_excel_products"] = loaded
                    st.session_state["_bulk_excel_hash"]    = xhash
                except Exception as e: st.error(f"Excel read error: {e}", icon=":material/error:")
            if st.session_state["bulk_excel_products"]: st.info(f"{len(st.session_state['bulk_excel_products'])} images ready.", icon=":material/check_circle:")
        products_to_process = st.session_state.get("bulk_excel_products", [])

    elif bulk_method == "Category URL":
        active_bulk_list = "bulk_url_products"
        cat_url_bulk = st.text_input("Category URL:", placeholder=f"https://www.{domain}/smartphones/", key="b_cat_url")
        max_cat_pages_bulk = st.number_input("Max pages (40 products/page):", min_value=1, max_value=50, value=1, step=1, key="b_cat_pages")
        if st.button("Extract & Load Images", type="primary", key="b_cat_load"):
            if cat_url_bulk.strip():
                with st.spinner("Extracting images from category..."):
                    from scraper import extract_category_images
                    extracted_imgs = extract_category_images(cat_url_bulk.strip(), max_cat_pages_bulk)
                    if not extracted_imgs:
                        st.warning("No images found.")
                    else:
                        loaded = []
                        prog_url = st.progress(0)
                        for i, item in enumerate(extracted_imgs):
                            try:
                                r = _SESSION.get(item["url"], timeout=10)
                                if r.ok:
                                    img = Image.open(BytesIO(r.content)).convert("RGBA")
                                    loaded.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": item["name"]})
                            except Exception: pass
                            prog_url.progress((i+1)/len(extracted_imgs))
                        st.session_state["bulk_url_products"] = loaded
                        st.success(f"Loaded {len(loaded)} images from category.", icon=":material/check_circle:")
            else:
                st.warning("Please enter a category URL.")
        if st.session_state.get("bulk_url_products"):
            st.info(f"{len(st.session_state['bulk_url_products'])} images ready.", icon=":material/check_circle:")
        products_to_process = st.session_state.get("bulk_url_products", [])

    else:
        active_bulk_list = "bulk_sku_results"
        skus_raw = st.text_area("SKUs (one per line):", height=160, placeholder="GE840EA6C62GANAFAMZ", key="b_skus")
        st.caption(f"Will search on **{base_url}**")
        if skus_raw.strip():
            skus = [s.strip() for s in skus_raw.splitlines() if s.strip()]
            st.info(f"{len(skus)} SKUs entered", icon=":material/list:")
            if st.button("Search All SKUs", icon=":material/search:", key="b_sku_search", type="primary"):
                prog_sku, status_sku = st.progress(0), st.empty()
                new_results, mismatches = [], []
                for i, sku in enumerate(skus):
                    status_sku.text(f"Fetching {i+1}/{len(skus)}: {sku}")
                    img, found_country = fetch_image_from_sku_via_apps_script(sku, active_country=region_choice)
                    if img:
                        new_results.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": sku})
                        if found_country and found_country != region_choice: mismatches.append({"sku": sku, "found_in": found_country})
                    else: st.warning(f"No image for SKU: {sku}", icon=":material/image_not_supported:")
                    prog_sku.progress((i+1)/len(skus))
                st.session_state["bulk_sku_results"] = new_results
                if mismatches: st.warning(f"**{len(mismatches)} SKU(s) from a different country:**\n" + "  \n".join(f"• **{m['sku']}** — found in {m['found_in']}" for m in mismatches), icon=":material/public:")
                status_sku.success(f"Found {len(new_results)}/{len(skus)} images.", icon=":material/check_circle:")
        products_to_process = st.session_state.get("bulk_sku_results", [])
        if products_to_process: st.info(f"{len(products_to_process)} SKU images ready.", icon=":material/check_circle:")

    if products_to_process:
        st.markdown("---")
        st.subheader(f"{len(products_to_process)} images ready")

        with st.container():
            st.markdown("**Global Scale Override:**")
            g_col1, g_col2 = st.columns([3,1])
            with g_col1: global_scale = st.slider("Scale for all images:", 40, 180, 100, 5, key="g_scale_slider", label_visibility="collapsed")
            with g_col2:
                if st.button("Apply to All", use_container_width=True, icon=":material/done_all:"):
                    for ci, item in enumerate(products_to_process): st.session_state["individual_scales"][f"bsc_{ci}_{item['name']}"] = global_scale
                    st.rerun()
        st.markdown("---")

        # Render 5 columns per row for Bulk Processing
        for row_s in range(0, len(products_to_process), 5):
            chunk  = products_to_process[row_s:row_s+5]
            cols_  = st.columns(5)
            for ci, item in enumerate(chunk):
                idx, k = row_s + ci, f"bsc_{row_s + ci}_{item['name']}"
                if k not in st.session_state["individual_scales"]: st.session_state["individual_scales"][k] = 100
                with cols_[ci]:
                    if st.button("✖", key=f"del_b_{idx}", help="RemoveCard"):
                        st.session_state[active_bulk_list].pop(idx)
                        st.rerun()
                        
                    try: st.image(bytes_to_pil(item["bytes"]).convert("RGB"), use_container_width=True)
                    except Exception: pass
                    
                    st.markdown(f"""
                    <div style="background:#f0f0f0; color:#333; font-size:11px; text-align:center; padding:4px; border-radius:4px; font-weight:bold; letter-spacing:0.5px; margin: 8px 0;">{item['name']}</div>
                    """, unsafe_allow_html=True)
                    
                    sc = st.slider("Size %", 40, 180, st.session_state["individual_scales"][k], 5, key=f"bsl_{k}", label_visibility="collapsed")
                    st.session_state["individual_scales"][k] = sc

        st.markdown("---")
        if st.button("Process All Images", icon=":material/tune:", key="b_process", type="primary"):
            tag_img = load_tag_image(tag_type, region_choice)
            if tag_img is not None:
                prog_proc, processed_imgs = st.progress(0), []
                for i, item in enumerate(products_to_process):
                    try:
                        sc = st.session_state["individual_scales"].get(f"bsc_{i}_{item['name']}", 100)
                        processed_imgs.append({"img": apply_tag(bytes_to_pil(item["bytes"]).convert("RGBA"), tag_img, sc), "name": item["name"]})
                    except Exception as e: st.warning(f"Error on {item['name']}: {e}", icon=":material/warning:")
                    prog_proc.progress((i+1)/len(products_to_process))

                if processed_imgs:
                    st.success(f"{len(processed_imgs)} images processed.", icon=":material/check_circle:")
                    zb = BytesIO()
                    with zipfile.ZipFile(zb, "w", zipfile.ZIP_DEFLATED) as zf:
                        for p in processed_imgs: zf.writestr(f"{p['name']}_1.jpg", image_to_jpeg_bytes(p["img"]))
                    zb.seek(0)
                    st.session_state["b_bulk_zip"]     = zb.getvalue()
                    st.session_state["b_bulk_preview"] = processed_imgs[:8]
                    st.session_state["b_bulk_total"]   = len(processed_imgs)
                else: st.error("No images processed.", icon=":material/error:")

        if st.session_state.get("b_bulk_zip"):
            st.download_button(
                f"Download All {st.session_state['b_bulk_total']} Images (ZIP)",
                st.session_state["b_bulk_zip"],
                f"tagged_{tag_type.lower().replace(' ','_')}.zip",
                "application/zip", use_container_width=True, icon=":material/download:", key="b_dl"
            )
            st.markdown("### Preview")
            pcols = st.columns(4)
            for i, p in enumerate(st.session_state["b_bulk_preview"]):
                with pcols[i%4]: st.image(p["img"], caption=p["name"], use_container_width=True)
            if st.session_state["b_bulk_total"] > 8: st.caption(f"Showing 8 of {st.session_state['b_bulk_total']}")
    else: st.info("No items in queue. Provide images using one of the input methods above.", icon="ℹ️")

# ┌─────────────────────────────────────────────────────────────────────────────
# │  TAB 4 — CONVERT TAG
# └─────────────────────────────────────────────────────────────────────────────
with tab_convert:
    tab_flag_html4 = get_flag_html(active_cc)
    st.markdown(f"<h3 style='display:flex; align-items:center;'>Convert Tag &nbsp;&nbsp;<span style='font-size:16px; font-weight:normal; color:#666;'>→ {display_tag}</span> {tab_flag_html4}</h3>", unsafe_allow_html=True)
    st.caption("Load an already-tagged image. The old tag is detected via pixel scanning and replaced with the selected grade.")

    conv_qty = st.radio("Processing mode:", ["Single image","Multiple images"], horizontal=True, key="cv_qty")

    if conv_qty == "Single image":
        col_src, col_out = st.columns([1,1])

        with col_src:
            st.markdown("#### Image Source")
            cv_method = st.radio("Source:", ["Upload from device","Load from Image URL","Load from Product URL","Load from SKU"], horizontal=False, key="cv_src_method")

            if st.session_state.get("cv_src_prev") != cv_method:
                st.session_state.update({"cv_img_bytes": None, "cv_img_label": "", "cv_img_source": None, "cv_src_prev": cv_method})

            if cv_method == "Upload from device":
                cf = st.file_uploader("Choose a tagged image:", type=["png","jpg","jpeg","webp"], key="cv_s_upload")
                if cf is not None:
                    fhash = hashlib.md5(cf.getvalue()).hexdigest()
                    if st.session_state["cv_img_label"] != fhash:
                        st.session_state.update({"cv_img_bytes": pil_to_bytes(Image.open(cf).convert("RGB"), fmt="PNG"), "cv_img_label": fhash, "cv_img_source": "upload"})

            elif cv_method == "Load from Image URL":
                img_url_cv = st.text_input("Direct image URL:", key="cv_s_img_url")
                if st.button("Load Image", icon=":material/download:", key="cv_s_img_load"):
                    if img_url_cv.strip():
                        with st.spinner("Fetching image…"):
                            try:
                                url_country = detect_country_from_url(img_url_cv.strip())
                                r = _SESSION.get(img_url_cv.strip(), timeout=15)
                                r.raise_for_status()
                                trigger_mismatch_or_commit(Image.open(BytesIO(r.content)).convert("RGB"), img_url_cv.strip(), "url", url_country, region_choice, "cv_single")
                                if not st.session_state.get("mismatch_detected"): st.success("Image loaded.", icon=":material/check_circle:")
                                st.rerun()
                            except Exception as e: st.error(f"Could not load image: {e}", icon=":material/error:")
                    else: st.warning("Please enter a URL.", icon=":material/warning:")

            elif cv_method == "Load from Product URL":
                prod_url_cv = st.text_input("Jumia product page URL:", key="cv_s_prod_url")
                if st.button("Extract Image from Page", icon=":material/travel_explore:", key="cv_s_prod_load"):
                    if prod_url_cv.strip():
                        url_country = detect_country_from_url(prod_url_cv.strip())
                        with st.spinner("Extracting image from page…"):
                            img, _found_country = fetch_image_from_product_url_via_apps_script(prod_url_cv.strip(), active_country=region_choice)
                            if img:
                                trigger_mismatch_or_commit(img.convert("RGB"), prod_url_cv.strip(), "product_url", url_country, region_choice, "cv_single")
                                if not st.session_state.get("mismatch_detected"): st.success("Image extracted.", icon=":material/check_circle:")
                                st.rerun()
                            else: st.warning("Could not find an image on that page.", icon=":material/image_not_supported:")
                    else: st.warning("Please enter a product URL.", icon=":material/warning:")

            else:
                sku_cv = st.text_input("Product SKU:", placeholder="e.g. GE840EA6C62GANAFAMZ", key="cv_s_sku")
                st.caption(f"Searches **{base_url}** first, then all other countries.")
                if st.button("Search & Extract Image", icon=":material/search:", key="cv_s_sku_search", type="primary"):
                    if sku_cv.strip():
                        holder_cv = st.empty()
                        holder_cv.info(f"Searching for `{sku_cv.strip()}`…", icon=":material/search:")
                        img, found_country = fetch_image_from_sku_via_apps_script(sku_cv.strip(), active_country=region_choice)
                        holder_cv.empty()
                        if img is not None:
                            trigger_mismatch_or_commit(img, sku_cv.strip(), "sku", found_country, region_choice, "cv_single")
                            if not st.session_state.get("mismatch_detected"): st.success(f"Image loaded for **{sku_cv.strip()}**", icon=":material/check_circle:")
                            st.rerun()
                        else: st.error(f"SKU **{sku_cv.strip()}** not found.", icon=":material/search_off:")
                    else: st.warning("Please enter a SKU.", icon=":material/warning:")

            if st.session_state["cv_img_bytes"] is not None:
                src_icons = {"upload":":material/upload:","url":":material/link:", "product_url":":material/travel_explore:","sku":":material/qr_code:"}
                st.info(f"Loaded: {st.session_state['cv_img_label']}", icon=src_icons.get(st.session_state["cv_img_source"],":material/image:"))

        with col_out:
            st.markdown("#### Result")
            if st.session_state["cv_img_bytes"] is not None:
                tag_img = load_tag_image(tag_type, region_choice)
                if tag_img is not None:
                    tagged_cv = bytes_to_pil(st.session_state["cv_img_bytes"]).convert("RGB")
                    result_cv = strip_and_retag(tagged_cv, tag_img)
                    fname_cv  = re.sub(r"[^\w\s-]","", st.session_state["cv_img_label"]).strip()[:40] or "converted"
                    st.image(result_cv, caption=f"Converted → {display_tag}", use_container_width=True)
                    st.markdown("---")
                    st.download_button(
                        f"Download as {display_tag} (JPEG)", image_to_jpeg_bytes(result_cv),
                        f"{fname_cv}_{tag_type.lower().replace(' ','_')}.jpg", "image/jpeg", use_container_width=True, icon=":material/download:", key="cv_s_dl"
                    )
            else: st.info("Load an image on the left.", icon=":material/swap_horiz:")

    # ── Multiple images ───────────────────────────────────────────────────────
    else:
        st.markdown("#### Image Sources")
        cv_bulk_method = st.radio("Input method:", ["Upload multiple images","Enter Image URLs","Enter SKUs", "Category URL"], horizontal=True, key="cv_bulk_method")

        if cv_bulk_method == "Upload multiple images":
            conv_files = st.file_uploader("Choose tagged images:", type=["png","jpg","jpeg","webp"], accept_multiple_files=True, key="cv_b_upload")
            if conv_files:
                new_hash = hashlib.md5(b"".join(f.getvalue()[:64] for f in conv_files)).hexdigest()
                if st.session_state.get("_cv_upload_hash") != new_hash:
                    loaded = []
                    for f in conv_files:
                        try: loaded.append({"bytes": pil_to_bytes(Image.open(f).convert("RGB"), fmt="JPEG"), "name": f.name.rsplit(".",1)[0]})
                        except Exception as e: st.warning(f"Could not load {f.name}: {e}", icon=":material/warning:")
                    st.session_state["cv_bulk_upload"]  = loaded
                    st.session_state["_cv_upload_hash"] = new_hash
                st.info(f"{len(st.session_state['cv_bulk_upload'])} files ready.", icon=":material/photo_library:")
            cv_images = st.session_state.get("cv_bulk_upload", [])

        elif cv_bulk_method == "Enter Image URLs":
            raw_cv_urls = st.text_area("Image URLs (one per line):", height=150, key="cv_b_urls")
            if st.button("Load Images", icon=":material/download:", key="cv_b_url_load"):
                if raw_cv_urls.strip():
                    url_list_cv = [u.strip() for u in raw_cv_urls.splitlines() if u.strip()]
                    loaded, prog_cv_url = [], st.progress(0)
                    for i, u in enumerate(url_list_cv):
                        try:
                            r = _SESSION.get(u, timeout=12)
                            r.raise_for_status()
                            loaded.append({"bytes": pil_to_bytes(Image.open(BytesIO(r.content)).convert("RGB"), fmt="JPEG"), "name": f"image_{i+1}"})
                        except Exception as e: st.warning(f"URL {i+1} failed: {e}", icon=":material/warning:")
                        prog_cv_url.progress((i+1)/len(url_list_cv))
                    st.session_state["cv_bulk_url"] = loaded
                    st.success(f"Loaded {len(loaded)}/{len(url_list_cv)} images.", icon=":material/check_circle:")
            if st.session_state["cv_bulk_url"]: st.info(f"{len(st.session_state['cv_bulk_url'])} images ready.", icon=":material/check_circle:")
            cv_images = st.session_state.get("cv_bulk_url", [])

        elif cv_bulk_method == "Category URL":
            active_bulk_list = "cv_bulk_url"
            cat_url_bulk = st.text_input("Category URL:", placeholder=f"https://www.{domain}/smartphones/", key="cv_b_cat_url")
            max_cat_pages_bulk = st.number_input("Max pages (40 products/page):", min_value=1, max_value=50, value=1, step=1, key="cv_b_cat_pages")
            if st.button("Extract & Load Images", type="primary", key="cv_b_cat_load"):
                if cat_url_bulk.strip():
                    with st.spinner("Extracting images from category..."):
                        from scraper import extract_category_images
                        extracted_imgs = extract_category_images(cat_url_bulk.strip(), max_cat_pages_bulk)
                        if not extracted_imgs:
                            st.warning("No images found.")
                        else:
                            loaded = []
                            prog_url = st.progress(0)
                            for i, item in enumerate(extracted_imgs):
                                try:
                                    r = _SESSION.get(item["url"], timeout=10)
                                    if r.ok:
                                        img = Image.open(BytesIO(r.content)).convert("RGB")
                                        loaded.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": item["name"]})
                                except Exception: pass
                                prog_url.progress((i+1)/len(extracted_imgs))
                            st.session_state["cv_bulk_url"] = loaded
                            st.success(f"Loaded {len(loaded)} images from category.", icon=":material/check_circle:")
                else:
                    st.warning("Please enter a category URL.")
            if st.session_state.get("cv_bulk_url"):
                st.info(f"{len(st.session_state['cv_bulk_url'])} images ready.", icon=":material/check_circle:")
            cv_images = st.session_state.get("cv_bulk_url", [])

        else:
            cv_skus_raw = st.text_area("SKUs (one per line):", height=150, key="cv_b_skus")
            st.caption(f"Will search on **{base_url}**")
            if cv_skus_raw.strip():
                skus_ = [s.strip() for s in cv_skus_raw.splitlines() if s.strip()]
                st.info(f"{len(skus_)} SKUs entered", icon=":material/list:")
                if st.button("Search All SKUs", icon=":material/search:", key="cv_b_sku_search", type="primary"):
                    prog_cv_sku, status_cv = st.progress(0), st.empty()
                    new_cv, cv_mismatches = [], []
                    for i, sku_ in enumerate(skus_):
                        status_cv.text(f"Fetching {i+1}/{len(skus_)}: {sku_}")
                        img_, found_ = fetch_image_from_sku_via_apps_script(sku_, active_country=region_choice)
                        if img_:
                            new_cv.append({"bytes": pil_to_bytes(img_.convert("RGB"), fmt="JPEG"), "name": sku_})
                            if found_ and found_ != region_choice: cv_mismatches.append({"sku": sku_, "found_in": found_})
                        else: st.warning(f"No image for SKU: {sku_}", icon=":material/image_not_supported:")
                        prog_cv_sku.progress((i+1)/len(skus_))
                    st.session_state["cv_bulk_sku_results"] = new_cv
                    if cv_mismatches: st.warning(f"**{len(cv_mismatches)} SKU(s) from different country:**\n" + "  \n".join(f"• **{m['sku']}** — found in {m['found_in']}" for m in cv_mismatches), icon=":material/public:")
                    status_cv.success(f"Found {len(new_cv)}/{len(skus_)} images.", icon=":material/check_circle:")
            cv_images = st.session_state.get("cv_bulk_sku_results", [])
            if cv_images: st.info(f"{len(cv_images)} SKU images ready.", icon=":material/check_circle:")

        if cv_images:
            st.markdown("---")
            st.subheader(f"{len(cv_images)} tagged images ready to convert")
            st.markdown("**Originals (with old tags):**")
            for rs in range(0, len(cv_images), 4):
                cols_ = st.columns(4)
                for ci, item in enumerate(cv_images[rs:rs+4]):
                    with cols_[ci]:
                        try: st.image(bytes_to_pil(item["bytes"]).convert("RGB"), caption=item["name"], use_container_width=True)
                        except Exception: st.caption(f"[{item['name']}]")
            st.markdown("---")

            if st.button(f"Convert All to {display_tag}", icon=":material/swap_horiz:", use_container_width=True, key="cv_b_process", type="primary"):
                tag_img = load_tag_image(tag_type, region_choice)
                if tag_img is not None:
                    prog_cv_proc, converted = st.progress(0), []
                    for i, item in enumerate(cv_images):
                        try:
                            converted.append({"img": strip_and_retag(bytes_to_pil(item["bytes"]).convert("RGB"), tag_img), "name": item["name"]})
                        except Exception as e: st.warning(f"Error on {item['name']}: {e}", icon=":material/warning:")
                        prog_cv_proc.progress((i+1)/len(cv_images))
                    if converted:
                        st.success(f"{len(converted)} images converted.", icon=":material/check_circle:")
                        zb = BytesIO()
                        with zipfile.ZipFile(zb,"w",zipfile.ZIP_DEFLATED) as zf:
                            for c in converted: zf.writestr(f"{c['name']}_{tag_type.lower().replace(' ','_')}.jpg", image_to_jpeg_bytes(c["img"]))
                        zb.seek(0)
                        st.session_state.update({"cv_bulk_zip": zb.getvalue(), "cv_bulk_preview": converted[:8], "cv_bulk_total": len(converted)})
                    else: st.error("No images converted.", icon=":material/error:")

            if st.session_state.get("cv_bulk_zip"):
                st.download_button(
                    f"Download All {st.session_state['cv_bulk_total']} Converted Images (ZIP)",
                    data=st.session_state["cv_bulk_zip"],
                    file_name=f"converted_{tag_type.lower().replace(' ','_')}.zip",
                    mime="application/zip", use_container_width=True, icon=":material/download:", key="cv_b_dl"
                )
                st.markdown("### Preview")
                pcols = st.columns(4)
                for i, c in enumerate(st.session_state["cv_bulk_preview"]):
                    with pcols[i%4]: st.image(c["img"], caption=c["name"], use_container_width=True)
                if st.session_state["cv_bulk_total"] > 8: st.caption(f"Showing 8 of {st.session_state['cv_bulk_total']}")
        else: st.info("No items to convert. Please provide images using one of the input methods.", icon="ℹ️")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="position:fixed; bottom:0; right:0; left:0; z-index:9999; background:linear-gradient(135deg,#1A1A1A 0%,#2D2D2D 100%); border-top:3px solid #F68B1E; padding:15px 30px; display:flex; align-items:center; justify-content:space-between; box-shadow:0 -4px 10px rgba(0,0,0,0.3);">
  <div style="display:flex; align-items:center; gap:12px;">
      <span style="color:#F68B1E;font-weight:900;font-size:1.1rem;letter-spacing:0.5px;">Refurbished Suite</span>
      <span style="color:#444;font-size:1.2rem;">|</span>
      <span style="color:#AAA;font-size:0.85rem;font-weight:600;">Fast HTTP scraping · Auto-crop · Tag removal</span>
  </div>
</div>
""", unsafe_allow_html=True)
