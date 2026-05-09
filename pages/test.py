from __future__ import annotations

import os
import re
import json
import time
import zipfile
import hashlib
import asyncio
import aiohttp
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

# ══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Jumia Refurbished Suite",
    page_icon=":material/label:",
    layout="wide"
)

# ══════════════════════════════════════════════════════════════════════════════
#  JUMIA BRAND THEME
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #1A1A1A; }
.stApp { background-color: #FAFAFA; }

[data-testid="stSidebar"] { background: linear-gradient(180deg, #1A1A1A 0%, #2D2D2D 100%); border-right: 3px solid #F68B1E; }
[data-testid="stSidebar"] * { color: #F5F5F5 !important; }
[data-testid="stSidebar"] .stSelectbox label, [data-testid="stSidebar"] .stSlider label, [data-testid="stSidebar"] .stCheckbox label, [data-testid="stSidebar"] .stRadio label { color: #CCCCCC !important; font-size: 0.85rem; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #F68B1E !important; font-weight: 800; font-size: 0.95rem; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #F68B1E44; padding-bottom: 4px; margin-bottom: 8px; }
[data-testid="stSidebar"] [data-baseweb="select"] > div:first-child { background-color: #3A3A3A !important; border-color: #F68B1E !important; border-radius: 6px !important; }
[data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stSelectboxValue"], [data-testid="stSidebar"] [data-baseweb="select"] span, [data-testid="stSidebar"] [data-baseweb="select"] div { color: #FFFFFF !important; }
[data-baseweb="popover"] [data-baseweb="menu"] { background-color: #2D2D2D !important; }
[data-baseweb="popover"] [role="option"] { background-color: #2D2D2D !important; color: #F5F5F5 !important; }
[data-baseweb="popover"] [role="option"]:hover, [data-baseweb="popover"] [aria-selected="true"] { background-color: #F68B1E !important; color: #FFFFFF !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #AAAAAA !important; font-size: 0.8rem; }
[data-testid="stSidebar"] .stAlert { background-color: #F68B1E22 !important; border-left: 4px solid #F68B1E !important; color: #F68B1E !important; }

.jumia-header { background: linear-gradient(135deg, #F68B1E 0%, #D4730A 100%); border-radius: 12px; padding: 20px 28px 16px; margin-bottom: 20px; display: flex; align-items: center; gap: 16px; box-shadow: 0 4px 16px #F68B1E44; }
.jumia-header h1 { margin: 0; color: #FFFFFF; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; }
.jumia-header p { margin: 4px 0 0; color: #FFE0B2; font-size: 0.9rem; }
.jumia-logo-dot { width: 48px; height: 48px; background: #FFFFFF; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.6rem; flex-shrink: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }

[data-testid="stTabs"] [role="tablist"] { gap: 4px; border-bottom: 2px solid #F68B1E; }
[data-testid="stTabs"] button[role="tab"] { background: #FFFFFF; border: 1px solid #E0E0E0; border-bottom: none; border-radius: 8px 8px 0 0; color: #6B6B6B; font-weight: 600; font-size: 0.88rem; padding: 8px 18px; transition: all 0.2s ease; }
[data-testid="stTabs"] button[role="tab"]:hover { background: #FFF4E6; color: #F68B1E; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { background: #F68B1E; color: #FFFFFF !important; border-color: #F68B1E; font-weight: 700; }

[data-testid="stButton"] button[kind="primary"], [data-testid="stBaseButton-primary"] { background: linear-gradient(135deg, #F68B1E 0%, #D4730A 100%) !important; color: #FFFFFF !important; border: none !important; border-radius: 8px !important; font-weight: 700 !important; font-size: 0.9rem !important; padding: 10px 20px !important; box-shadow: 0 3px 10px #F68B1E55 !important; transition: all 0.2s ease !important; }
[data-testid="stButton"] button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover { box-shadow: 0 5px 18px #F68B1E88 !important; transform: translateY(-1px); }
[data-testid="stButton"] button:not([kind="primary"]), [data-testid="stBaseButton-secondary"] { background: #FFFFFF !important; color: #F68B1E !important; border: 1.5px solid #F68B1E !important; border-radius: 8px !important; font-weight: 600 !important; transition: all 0.2s ease !important; }
[data-testid="stButton"] button:not([kind="primary"]):hover { background: #FFF4E6 !important; }
[data-testid="stDownloadButton"] button { background: linear-gradient(135deg, #F68B1E 0%, #D4730A 100%) !important; color: #FFFFFF !important; border: none !important; border-radius: 8px !important; font-weight: 700 !important; box-shadow: 0 3px 10px #F68B1E44 !important; }

[data-testid="stMetric"] { background: #FFFFFF; border: 1px solid #F0E0CC; border-left: 4px solid #F68B1E; border-radius: 10px; padding: 14px 16px !important; box-shadow: 0 2px 8px rgba(246,139,30,0.1); }
[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #F68B1E; font-weight: 800; font-size: 1.6rem; }
[data-testid="stMetric"] [data-testid="stMetricLabel"] { color: #6B6B6B; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
[data-testid="stExpander"] { border: 1px solid #F0E0CC !important; border-radius: 10px !important; overflow: hidden; }
[data-testid="stExpander"] summary { background: #FFF4E6 !important; color: #1A1A1A !important; font-weight: 600; }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { border: 1.5px solid #E0E0E0 !important; border-radius: 8px !important; font-family: 'Nunito', sans-serif !important; transition: border-color 0.2s; }
[data-testid="stTextInput"] input:focus, [data-testid="stTextArea"] textarea:focus { border-color: #F68B1E !important; box-shadow: 0 0 0 3px #F68B1E22 !important; }
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] { background: #F68B1E !important; border-color: #F68B1E !important; }
[data-testid="stAlert"][data-baseweb="notification"] { border-radius: 8px; }
[data-testid="stDataFrame"] th { background-color: #F68B1E !important; color: #FFFFFF !important; font-weight: 700 !important; }
[data-testid="stFileUploader"] { border: 2px dashed #F68B1E !important; border-radius: 10px !important; background: #FFF4E688 !important; }
[data-testid="stFileUploaderDropzone"] { background: transparent !important; }
[data-testid="stRadio"] label[data-baseweb="radio"] div:first-child { border-color: #F68B1E !important; }
[data-testid="stRadio"] [aria-checked="true"] div:first-child { background: #F68B1E !important; border-color: #F68B1E !important; }
[data-testid="stCheckbox"] input:checked + div { background: #F68B1E !important; border-color: #F68B1E !important; }
[data-testid="stCheckbox"] input:checked + div svg { color: #1A1A1A !important; fill: #1A1A1A !important; stroke: #1A1A1A !important; }
[data-testid="stSidebar"] [data-testid="stCheckbox"] input:checked ~ div p { color: #000000 !important; font-weight: 700 !important; text-shadow: 0px 0px 4px rgba(255,255,255,0.8); background-color: #F68B1E; padding: 2px 8px; border-radius: 4px; }
[data-baseweb="select"]:focus-within { border-color: #F68B1E !important; box-shadow: 0 0 0 3px #F68B1E22 !important; }
hr { border-color: #F0E0CC !important; }
[data-testid="stCaptionContainer"] { color: #6B6B6B; font-size: 0.8rem; }
h2, h3 { color: #1A1A1A; font-weight: 700; }
h2::after { content: ''; display: block; width: 48px; height: 3px; background: #F68B1E; border-radius: 2px; margin-top: 4px; }
[data-testid="stImage"] img { border-radius: 8px; border: 1px solid #F0E0CC; }
[data-testid="stProgress"] div[role="progressbar"] > div { background: linear-gradient(90deg, #F68B1E, #D4730A) !important; }
[data-testid="stSpinner"] svg { color: #F68B1E !important; }
</style>

<div class="jumia-header">
  <div class="jumia-logo-dot">🏷</div>
  <div>
    <h1>Jumia Refurbished Suite</h1>
    <p>Analyze listings &nbsp;·&nbsp; Apply grade tags &nbsp;·&nbsp; Convert existing tags</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
MARGIN_PERCENT   = 0.12
BANNER_RATIO     = 0.095
VERT_STRIP_RATIO = 0.18
WHITE_THRESHOLD  = 230

TAG_FILES = {
    "Renewed":     "RefurbishedStickerUpdated-Renewd.png",
    "Refurbished": "RefurbishedStickerUpdate-No-Grading.png",
    "Grade A":     "Refurbished-StickerUpdated-Grade-A.png",
    "Grade B":     "Refurbished-StickerUpdated-Grade-B.png",
    "Grade C":     "Refurbished-StickerUpdated-Grade-C.png",
}

TAG_FILES_FR = {
    "Renewed":     "RenewedStickerUpdatedFrench.png",
    "Refurbished": "RefurbishedStickerUpdatedFrench.png",
    "Grade A":     "RefurbishedStickerGradeAFrench.png",
    "Grade B":     "RefurbishedStickerGradeBFrench.png",
    "Grade C":     "RefurbishedStickerGradeCFrench.png",
}

DOMAIN_MAP = {
    "Kenya (KE)":   "jumia.co.ke",
    "Uganda (UG)":  "jumia.ug",
    "Nigeria (NG)": "jumia.com.ng",
    "Morocco (MA)": "jumia.ma",
    "Ghana (GH)":   "jumia.com.gh",
}

_DOMAIN_TO_COUNTRY: dict[str, str] = {v: k for k, v in DOMAIN_MAP.items()}

_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}
_SESSION = requests.Session()
_SESSION.headers.update(_HTTP_HEADERS)
_adapter = requests.adapters.HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=requests.adapters.Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
)
_SESSION.mount("https://", _adapter)
_SESSION.mount("http://",  _adapter)

def detect_country_from_url(url: str) -> str | None:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        for domain, country_key in _DOMAIN_TO_COUNTRY.items():
            if host == domain or host.endswith("." + domain):
                return country_key
    except Exception:
        pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
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

# ══════════════════════════════════════════════════════════════════════════════
#  GEO-DETECTION
# ══════════════════════════════════════════════════════════════════════════════
_COUNTRY_CODE_MAP = {
    "KE": "Kenya (KE)", "UG": "Uganda (UG)", "NG": "Nigeria (NG)",
    "MA": "Morocco (MA)", "GH": "Ghana (GH)"
}

def _detect_country() -> str | None:
    try:
        r = _SESSION.get("https://ipapi.co/json/", timeout=4)
        code = r.json().get("country_code", "")
        return _COUNTRY_CODE_MAP.get(code)
    except Exception:
        return None

if st.session_state["geo_country"] is None:
    st.session_state["geo_country"] = _detect_country()

_geo_default  = st.session_state["geo_country"]
_country_list = list(DOMAIN_MAP.keys())
_default_idx  = _country_list.index(_geo_default) if _geo_default and _geo_default in _country_list else 0

# ══════════════════════════════════════════════════════════════════════════════
#  PIL / BYTES HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def pil_to_bytes(img: Image.Image, fmt="PNG") -> bytes:
    buf = BytesIO()
    if fmt == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    return buf.getvalue()

def bytes_to_pil(b: bytes) -> Image.Image:
    return Image.open(BytesIO(b))

def image_to_jpeg_bytes(img: Image.Image, quality: int = 95) -> bytes:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE ANALYSIS HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def get_dhash(img: Image.Image):
    try:
        resample = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
        img = img.convert("L").resize((9, 8), resample)
        px  = np.array(img)
        return (px[:, 1:] > px[:, :-1]).flatten()
    except Exception:
        return None

def _fetch_and_dhash(url: str):
    try:
        r = _SESSION.get(url, timeout=8)
        return get_dhash(Image.open(BytesIO(r.content)))
    except Exception:
        return None

@st.cache_data
def get_target_promo_hash():
    url = ("https://ke.jumia.is/unsafe/fit-in/680x680/filters:fill(white)"
           "/product/21/3620523/3.jpg?0053")
    try:
        r = _SESSION.get(url, timeout=10)
        return get_dhash(Image.open(BytesIO(r.content)))
    except Exception:
        return None

PROMO_HASH = get_target_promo_hash()

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.header("Region")
    if _geo_default:
        st.markdown(
            f"""<div style="background:#F68B1E22;border:1px solid #F68B1E55;border-radius:6px;padding:6px 10px;margin-bottom:8px;font-size:0.78rem;color:#F68B1E!important;">
            📍 Auto-detected: <strong style="color:#F68B1E">{_geo_default}</strong></div>""",
            unsafe_allow_html=True)

    region_choice = st.selectbox("Select Country:", _country_list, index=_default_idx,
                                  key="region_select",
                                  help="Used for product analysis and all SKU image lookups")
    domain   = DOMAIN_MAP[region_choice]
    base_url = f"https://www.{domain}"

    st.markdown(
        f"""<div style="background:linear-gradient(135deg,#F68B1E,#D4730A);border-radius:20px;padding:5px 12px;text-align:center;margin:4px 0 8px;font-size:0.8rem;font-weight:700;color:#fff!important;letter-spacing:0.03em;">
        Active: {region_choice}</div>""", unsafe_allow_html=True)

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
    st.header("Analyzer Settings")
    show_browser    = st.checkbox("Show Browser (Debug Mode)", value=False)
    max_workers     = st.slider("Parallel Workers:", 1, 10, 5)
    timeout_seconds = st.slider("Page Timeout (s):", 10, 30, 20)
    check_images    = st.checkbox("Analyze Images for Red Badges", value=True)
    force_selenium  = st.checkbox("Force Browser Mode (slower, more accurate)", value=False)
    st.info(f"{max_workers} workers · {timeout_seconds}s timeout", icon=":material/bolt:")

    if PROMO_HASH is None:
        st.warning("Grading image hash unavailable — grading guide checks temporarily disabled.", icon="⚠️")

# ══════════════════════════════════════════════════════════════════════════════
#  FILE RESOLUTION & SELLER AUTH
# ══════════════════════════════════════════════════════════════════════════════
def get_tag_path(filename: str) -> str:
    for path in [filename, os.path.join(os.path.dirname(__file__), filename), os.path.join(os.getcwd(), filename)]:
        if os.path.exists(path):
            return path
    return filename

def load_tag_image(grade: str, region: str) -> Image.Image | None:
    filename = TAG_FILES_FR[grade] if region == "Morocco (MA)" else TAG_FILES[grade]
    path = get_tag_path(filename)
    if not os.path.exists(path):
        st.error(f"Tag file not found: **{filename}**\nEnsure all tag PNG files are in the same directory.", icon=":material/error:")
        return None
    return Image.open(path).convert("RGBA")

@st.cache_data(ttl=3600)
def load_seller_auth_data():
    cat_mapping  = {}
    auth_sellers = {cc: {"Phones": set(), "Laptops": set()} for cc in ["KE","UG","NG","MA","GH"]}
    try:
        xl_path = get_tag_path("Refurb.xlsx")
        if not os.path.exists(xl_path):
            return cat_mapping, auth_sellers
        df_cat = pd.read_excel(xl_path, sheet_name="Categories")
        for _, row in df_cat.iterrows():
            if pd.notna(row.get("Path")) and pd.notna(row.get("type")):
                raw_path  = str(row["Path"])
                norm_path = re.sub(r"\s*/\s*", ">", raw_path).replace(" ", "").lower()
                cat_mapping[norm_path] = str(row["type"]).strip()
        for cc in ["KE","UG","NG","MA","GH"]:
            try:
                df_s = pd.read_excel(xl_path, sheet_name=cc)
                if "Phones"  in df_s.columns: auth_sellers[cc]["Phones"]  = set(df_s["Phones"].dropna().astype(str).str.strip().str.lower())
                if "Laptops" in df_s.columns: auth_sellers[cc]["Laptops"] = set(df_s["Laptops"].dropna().astype(str).str.strip().str.lower())
            except Exception:
                pass
    except Exception as e:
        st.warning(f"Could not load seller auth data: {e}")
    return cat_mapping, auth_sellers

_CAT_MAPPING, _AUTH_SELLERS = load_seller_auth_data()

with st.sidebar:
    if st.button("Reload Seller Data", icon=":material/refresh:", use_container_width=True):
        load_seller_auth_data.clear()
        _CAT_MAPPING, _AUTH_SELLERS = load_seller_auth_data()
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
#  SELENIUM DRIVER
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource
def get_driver_path():
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        from webdriver_manager.core.os_manager import ChromeType
        return ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
    except Exception:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            return ChromeDriverManager().install()
        except Exception:
            return None

def get_chrome_options(headless: bool = True):
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    for arg in [
        "--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled",
        "--disable-gpu", "--disable-extensions", "--window-size=1920,1080", "--disable-notifications",
        "--disable-logging", "--log-level=3", "--silent", "--blink-settings=imagesEnabled=false",
    ]:
        opts.add_argument(arg)
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    for p in ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome-stable", "/usr/bin/google-chrome"]:
        if os.path.exists(p):
            opts.binary_location = p
            break
    return opts

def get_driver(headless: bool = True, timeout: int = 20):
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
    except ImportError:
        return None
    opts = get_chrome_options(headless)
    driver = None
    try:
        dp = get_driver_path()
        if dp:
            svc = Service(dp)
            svc.log_path = os.devnull
            driver = webdriver.Chrome(service=svc, options=opts)
    except Exception:
        try:
            driver = webdriver.Chrome(options=opts)
        except Exception:
            return None
    if driver:
        try:
            driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            driver.set_page_load_timeout(timeout)
            driver.implicitly_wait(3)
        except Exception:
            pass
    return driver

# ══════════════════════════════════════════════════════════════════════════════
#  FAST HTTP SCRAPING
# ══════════════════════════════════════════════════════════════════════════════
def _lxml_available() -> bool:
    try:
        import lxml  # noqa
        return True
    except ImportError:
        return False

def _page_is_rendered(soup: BeautifulSoup) -> bool:
    return bool(soup.find("h1") and (
        soup.find(attrs={"data-sku": True}) or
        soup.find("div", class_=re.compile(r"osh-breadcrumb|brcbs"))
    ))

def fetch_soup_fast(url: str, timeout: int = 15) -> BeautifulSoup | None:
    try:
        r = _SESSION.get(url, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        try:
            soup = BeautifulSoup(r.content, "lxml")
        except Exception:
            soup = BeautifulSoup(r.content, "html.parser")
        if _page_is_rendered(soup):
            return soup
        return None
    except Exception:
        return None

def fetch_soup_selenium(url: str, headless: bool = True, timeout: int = 20,
                        is_sku_search: bool = False) -> tuple[BeautifulSoup | None, str | None]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException

    driver = get_driver(headless, timeout)
    if not driver:
        return None, None
    final_url = url
    try:
        try:
            driver.get(url)
        except (TimeoutException, WebDriverException):
            return None, None

        if is_sku_search:
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.prd, h1"))
                )
                if "There are no results for" in driver.page_source:
                    return None, None
                links = driver.find_elements(By.CSS_SELECTOR, "article.prd a.core")
                if not links:
                    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='.html']")
                if links:
                    href = links[0].get_attribute("href")
                    try:
                        driver.get(href)
                        final_url = href
                    except TimeoutException:
                        return None, None
            except Exception:
                pass

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        except TimeoutException:
            return None, None

        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.4)
        except Exception:
            pass

        soup = BeautifulSoup(driver.page_source, "lxml" if _lxml_available() else "html.parser")
        return soup, final_url
    except Exception:
        return None, None
    finally:
        try:
            driver.quit()
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
#  SKU → IMAGE
# ══════════════════════════════════════════════════════════════════════════════
def _extract_image_from_soup(soup: BeautifulSoup, b_url: str) -> Image.Image | None:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        image_url = og["content"]
    else:
        image_url = None
        for img in soup.find_all("img", limit=20):
            src = img.get("data-src") or img.get("src") or ""
            if any(x in src for x in ["/product/", "/unsafe/", "jumia.is"]):
                if src.startswith("//"): src = "https:" + src
                elif src.startswith("/"): src = b_url + src
                image_url = src
                break
    if not image_url:
        return None
    try:
        r = _SESSION.get(image_url, timeout=12)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None

def fetch_image_from_sku(sku: str, primary_b_url: str, try_all_countries: bool = True) -> tuple[Image.Image | None, str | None]:
    def _try_single(b_url: str) -> Image.Image | None:
        search_url = f"{b_url}/catalog/?q={sku}"
        soup = fetch_soup_fast(search_url, timeout=12)
        if soup:
            links = soup.select("article.prd a.core")
            if links:
                prod_url = links[0].get("href", "")
                if prod_url:
                    prod_soup = fetch_soup_fast(prod_url, timeout=12)
                    if prod_soup:
                        return _extract_image_from_soup(prod_soup, b_url)
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException
        driver = get_driver(headless=True)
        if not driver:
            return None
        try:
            driver.get(search_url)
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article.prd, h1")))
            except TimeoutException:
                return None
            if "There are no results" in driver.page_source:
                return None
            links = driver.find_elements(By.CSS_SELECTOR, "article.prd a.core")
            if not links:
                return None
            driver.get(links[0].get_attribute("href"))
            try:
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            except TimeoutException:
                return None
            soup = BeautifulSoup(driver.page_source, "lxml" if _lxml_available() else "html.parser")
            return _extract_image_from_soup(soup, b_url)
        except Exception:
            return None
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    img = _try_single(primary_b_url)
    if img is not None:
        domain_ = primary_b_url.replace("https://www.", "")
        return img, _DOMAIN_TO_COUNTRY.get(domain_)

    if not try_all_countries:
        return None, None

    primary_domain = primary_b_url.replace("https://www.", "")
    remaining = [(f"https://www.{DOMAIN_MAP[ck]}", ck) for ck in DOMAIN_MAP if DOMAIN_MAP[ck] != primary_domain]
    if remaining:
        with ThreadPoolExecutor(max_workers=len(remaining)) as executor:
            futures = {executor.submit(_try_single, url): ck for url, ck in remaining}
            for future in as_completed(futures):
                ck = futures[future]
                try:
                    res_img = future.result()
                    if res_img is not None:
                        return res_img, ck
                except Exception:
                    pass
    return None, None

# ══════════════════════════════════════════════════════════════════════════════
#  MISMATCH DIALOG
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
    if b is None:
        return
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
    st.session_state["pending_img_bytes"]  = None
    st.session_state["pending_img_label"]  = ""
    st.session_state["pending_img_source"] = None
    st.session_state["pending_img_target"] = None

def trigger_mismatch_or_commit(img: Image.Image, label: str, source: str,
                                found_country: str | None, active_country: str, target_slot: str):
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

# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE PROCESSING — TAGGING
# ══════════════════════════════════════════════════════════════════════════════
def auto_crop_whitespace(img: Image.Image) -> Image.Image:
    arr  = np.array(img.convert("RGB"))
    mask = ~((arr[:, :, 0] > WHITE_THRESHOLD) &
             (arr[:, :, 1] > WHITE_THRESHOLD) &
             (arr[:, :, 2] > WHITE_THRESHOLD))
    rows, cols = np.where(mask)
    if len(rows) == 0 or len(cols) == 0:
        return img
    return img.crop((cols.min(), rows.min(), cols.max() + 1, rows.max() + 1))

def fit_product_onto_tag(product: Image.Image, tag: Image.Image, scale_pct: int = 100) -> Image.Image:
    cw, ch   = tag.size
    safe_w   = cw - int(cw * VERT_STRIP_RATIO)
    safe_h   = ch - int(ch * BANNER_RATIO)
    mx       = int(safe_w * MARGIN_PERCENT)
    my       = int(safe_h * MARGIN_PERCENT)
    inner_w  = safe_w - 2 * mx
    inner_h  = safe_h - 2 * my
    mult     = scale_pct / 100.0
    target_w = int(inner_w * mult)
    target_h = int(inner_h * mult)
    pw, ph   = product.size
    scale    = min(target_w / pw, target_h / ph)
    nw, nh   = int(pw * scale), int(ph * scale)
    resized  = product.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas   = Image.new("RGB", (cw, ch), (255, 255, 255))
    x = max(0, mx + (inner_w - nw) // 2)
    y = max(0, my + (inner_h - nh) // 2)
    if resized.mode == "RGBA":
        canvas.paste(resized, (x, y), resized)
    else:
        canvas.paste(resized, (x, y))
    if tag.mode == "RGBA":
        canvas.paste(tag, (0, 0), tag)
    else:
        canvas.paste(tag, (0, 0))
    return canvas

def apply_tag(product: Image.Image, tag: Image.Image, scale_pct: int = 100) -> Image.Image:
    cropped = auto_crop_whitespace(product.convert("RGBA"))
    return fit_product_onto_tag(cropped, tag, scale_pct)

# ══════════════════════════════════════════════════════════════════════════════
#  IMAGE PROCESSING — TAG CONVERSION
# ══════════════════════════════════════════════════════════════════════════════
def detect_tag_boundaries(img: Image.Image):
    arr     = np.array(img.convert("RGB"))
    h, w, _ = arr.shape
    red_mask    = (arr[:, :, 0] > 150) & (arr[:, :, 1] < 80) & (arr[:, :, 2] < 80)
    red_counts  = red_mask.sum(axis=0)
    strip_left  = w - int(w * VERT_STRIP_RATIO)
    scan_w_start = int(w * 0.65)
    consec_white = 0
    streak_start = w - 1
    found_gap    = False
    for x in range(w - 1, scan_w_start - 1, -1):
        if red_counts[x] > h * 0.02:
            consec_white = 0
        else:
            if consec_white == 0:
                streak_start = x
            consec_white += 1
            if consec_white >= int(w * 0.015):
                strip_left = streak_start - 2
                found_gap  = True
                break
    if not found_gap:
        strip_left = w - int(w * VERT_STRIP_RATIO)

    banner_top   = h - int(h * BANNER_RATIO)
    scan_h_start = int(h * 0.60)
    non_white    = ~((arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235))
    nw_cropped   = non_white[:, :strip_left]
    nw_counts    = nw_cropped.sum(axis=1)
    threshold    = max(5, int(strip_left * 0.01))
    consec_white = 0
    streak_start = h - 1
    found_gap    = False
    for y in range(h - 1, scan_h_start - 1, -1):
        if nw_counts[y] <= threshold:
            if consec_white == 0:
                streak_start = y
            consec_white += 1
            if consec_white >= int(h * 0.015):
                banner_top = streak_start - 2
                found_gap  = True
                break
        else:
            consec_white = 0
    if not found_gap:
        banner_top = h - int(h * BANNER_RATIO)
    return strip_left, banner_top

def strip_and_retag(tagged: Image.Image, new_tag: Image.Image) -> Image.Image:
    rgb = tagged.convert("RGB")
    w, h = rgb.size
    strip_left, banner_top = detect_tag_boundaries(rgb)
    strip_left = max(0, min(strip_left, w))
    banner_top = max(0, min(banner_top, h))
    product_region = rgb.crop((0, 0, strip_left, banner_top))
    cropped = auto_crop_whitespace(product_region.convert("RGBA"))
    return fit_product_onto_tag(cropped, new_tag, 100)

# ══════════════════════════════════════════════════════════════════════════════
#  PARALLEL IMAGE CHECKS
# ══════════════════════════════════════════════════════════════════════════════
def has_red_badge(image_url: str) -> str:
    try:
        r   = _SESSION.get(image_url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("RGB").resize((300, 300))
        arr = np.array(img).astype(float)
        corner = arr[:100, 200:, :]
        mask   = (corner[:, :, 0] > 180) & (corner[:, :, 1] < 100) & (corner[:, :, 2] < 100)
        return "YES (Red Badge)" if mask.sum() / mask.size > 0.05 else "NO"
    except Exception as e:
        return f"ERROR ({str(e)[:20]})"

def _run_image_checks_parallel(data: dict) -> dict:
    image_urls = data.get("Image URLs", [])
    primary    = data.get("Primary Image URL", "N/A")
    tasks: dict = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        if primary and primary != "N/A":
            tasks["badge"] = ex.submit(has_red_badge, primary)
        if image_urls and PROMO_HASH is not None:
            tasks["last_dhash"] = ex.submit(_fetch_and_dhash, image_urls[-1])
        desc_imgs = data.pop("_desc_img_urls", [])
        for i, u in enumerate(desc_imgs[:6]):
            tasks[f"desc_{i}"] = ex.submit(_fetch_and_dhash, u)

        data["grading tag"] = "Not Checked"
        if "badge" in tasks:
            try:
                data["grading tag"] = tasks["badge"].result()
            except Exception:
                pass

        data["Grading last image"] = "NO"
        if "last_dhash" in tasks and PROMO_HASH is not None:
            try:
                lh = tasks["last_dhash"].result()
                if lh is not None and np.count_nonzero(PROMO_HASH != lh) <= 12:
                    data["Grading last image"] = "YES"
            except Exception:
                pass

        data["Description has Grading guide"] = "NO"
        for i in range(len(desc_imgs[:6])):
            key = f"desc_{i}"
            if key not in tasks:
                break
            try:
                dh = tasks[key].result()
                if dh is not None and PROMO_HASH is not None and np.count_nonzero(PROMO_HASH != dh) <= 12:
                    data["Description has Grading guide"] = "YES"
                    break
            except Exception:
                pass
    return data

# ══════════════════════════════════════════════════════════════════════════════
#  WARRANTY HELPERS  (all new — were absent in the original)
# ══════════════════════════════════════════════════════════════════════════════
_W_DURATION_PATTERNS = [
    r"(\d+)[\s\-]*(?:months?|mnths?|mths?)\s*(?:warranty|wrty|wrnty|guarantee)",
    r"(\d+)[\s\-]*(?:years?|yrs?)\s*(?:warranty|wrty|wrnty|guarantee)",
    r"(?:warranty|guarantee)[:\s]*(?:of\s*)?(\d+)\s*(?:months?|years?|days?)",
    r"(\d+)[\s\-]*days?\s*(?:warranty|guarantee)",
]
_LIFETIME_RE   = re.compile(r"lifetime\s*(?:warranty|guarantee)", re.I)
_NO_WARRANT_RE = re.compile(r"\b(?:no|without|w\/o)\s*warranty\b", re.I)

_WARRANTY_TYPE_RULES = [
    (re.compile(r"manufacturer|official|brand",  re.I), "Manufacturer"),
    (re.compile(r"\bseller\b|\bvendor\b",        re.I), "Seller"),
    (re.compile(r"international",                re.I), "International"),
    (re.compile(r"\blocal\b",                    re.I), "Local"),
]

def _parse_duration(text: str) -> tuple[str, str]:
    for pat in _W_DURATION_PATTERNS:
        m = re.search(pat, text, re.I)
        if m:
            raw  = m.group(0).lower()
            unit = "days" if "day" in raw else "months" if "month" in raw else "years"
            return f"{m.group(1)} {unit}", m.group(0)
    if _LIFETIME_RE.search(text):
        return "Lifetime", "Lifetime warranty"
    return "", ""

def _get_warranty_type(text: str) -> str:
    for pat, label in _WARRANTY_TYPE_RULES:
        if pat.search(text):
            return label
    return "Unspecified"

def _find_warranty_heading(soup: BeautifulSoup):
    for tag in soup.find_all(["h3", "h4", "dt", "th", "span", "label", "div", "p"]):
        txt = tag.get_text(strip=True)
        if re.match(r"^warranty[\w\s]*$", txt, re.I) and len(txt) <= 30:
            return tag
    return None

def _check_jsonld_warranty(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or ""
            if not raw.strip():
                continue
            payload = json.loads(raw)
            items   = payload if isinstance(payload, list) else [payload]
            for item in items:
                w = (item.get("warranty") or item.get("warrantyScope") or item.get("warrantyDuration"))
                if w:
                    return str(w).strip()
        except Exception:
            continue
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACT WARRANTY INFO  (fully rewritten — 9 bugs fixed)
# ══════════════════════════════════════════════════════════════════════════════
def extract_warranty_info(soup: BeautifulSoup, product_name: str) -> dict:
    data = {
        "has_warranty":      "NO",
        "warranty_duration": "N/A",
        "warranty_type":     "N/A",
        "warranty_source":   "None",
        "warranty_details":  "N/A",
        "warranty_address":  "N/A",
    }

    def _apply(duration, details, source, full_text=""):
        data.update({
            "has_warranty":      "YES",
            "warranty_duration": duration,
            "warranty_details":  details[:120] if details and details != "N/A" else "N/A",
            "warranty_source":   source,
            "warranty_type":     _get_warranty_type(full_text or details),
        })

    # Step 1 — JSON-LD (most reliable, was completely absent before)
    jld = _check_jsonld_warranty(soup)
    if jld:
        dur, det = _parse_duration(jld)
        if dur:
            _apply(dur, det, "JSON-LD", jld)
        elif not _NO_WARRANT_RE.search(jld):
            _apply(jld[:80], jld[:80], "JSON-LD", jld)

    # Step 2 — Heading → next sibling (fixed: uses get_text not broken string=)
    if data["has_warranty"] == "NO":
        heading = _find_warranty_heading(soup)
        if heading:
            val = heading.find_next(["div", "dd", "p", "td", "span", "li"])
            if val:
                text = val.get_text(strip=True)
                if text and text.lower() not in ["n/a", "na", "none", ""]:
                    if not _NO_WARRANT_RE.search(text):
                        dur, det = _parse_duration(text)
                        if dur:
                            _apply(dur, det, "Warranty Section", text)
                        else:
                            data.update({
                                "has_warranty":      "YES",
                                "warranty_duration": text[:80],
                                "warranty_details":  text[:120],
                                "warranty_source":   "Warranty Section",
                                "warranty_type":     _get_warranty_type(text),
                            })

    # Step 3 — Product title
    if data["has_warranty"] == "NO":
        dur, det = _parse_duration(product_name)
        if dur:
            _apply(dur, det, "Product Name", product_name)

    # Step 4 — Spec rows (fixed: removed "and not heading" that blocked this)
    if data["has_warranty"] == "NO":
        for row in soup.find_all(["tr", "div", "li", "dl"],
                                  class_=re.compile(r"spec|detail|attribute|row|feature", re.I)):
            row_text = row.get_text(" ", strip=True)
            if "warranty" not in row_text.lower():
                continue
            if len(row_text) > 500:
                continue
            dur, det = _parse_duration(row_text)
            if dur:
                _apply(dur, det, "Specifications", row_text)
                break

    # Step 5 — Bare table rows with th/td (was fully absent before)
    if data["has_warranty"] == "NO":
        for row in soup.select("table tr"):
            th = row.find("th")
            td = row.find("td")
            if not (th and td):
                continue
            if "warranty" not in th.get_text().lower():
                continue
            text = td.get_text(strip=True)
            if _NO_WARRANT_RE.search(text):
                break
            dur, det = _parse_duration(text)
            if dur:
                _apply(dur, det, "Specifications Table", text)
            elif text and text.lower() not in ["n/a", "na", "none", ""]:
                data.update({
                    "has_warranty":      "YES",
                    "warranty_duration": text[:80],
                    "warranty_details":  text[:120],
                    "warranty_source":   "Specifications Table",
                    "warranty_type":     _get_warranty_type(text),
                })
            break

    # Step 6 — Description body (was fully absent before)
    if data["has_warranty"] == "NO":
        desc = soup.find("div", class_=re.compile(r"markup|product-desc|-mhm", re.I))
        if desc:
            desc_text = desc.get_text(" ", strip=True)[:2000]
            if "warranty" in desc_text.lower() or "guarantee" in desc_text.lower():
                dur, det = _parse_duration(desc_text)
                if dur:
                    _apply(dur, det, "Description", desc_text)

    # Step 7 — Warranty Address (always runs)
    lbl = soup.find(string=re.compile(r"Warranty\s+Address", re.I))
    if lbl:
        el = lbl.find_next(["dd", "p", "div", "td"])
        if el:
            addr = el.get_text(strip=True)
            if addr and len(addr) > 10:
                data["warranty_address"] = addr

    return data

# ══════════════════════════════════════════════════════════════════════════════
#  REFURB / SELLER / SKU HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def detect_refurbished_status(soup: BeautifulSoup, product_name: str) -> dict:
    data = {"is_refurbished": "NO", "refurb_indicators": [], "has_refurb_tag": "NO"}
    kws  = ["refurbished","renewed","refurb","recon","reconditioned",
            "ex-uk","ex uk","pre-owned","certified","restored"]
    scope = soup
    h1    = soup.find("h1")
    if h1:
        c = h1.find_parent("div", class_=re.compile(r"col10|-pvs|-p"))
        scope = c if c else h1.parent.parent
    if scope.find("a", href=re.compile(r"/all-products/\?tag=REFU", re.I)):
        data.update({"is_refurbished": "YES", "has_refurb_tag": "YES"})
        data["refurb_indicators"].append("REFU tag badge")
    ri = scope.find("img", attrs={"alt": re.compile(r"^REFU$", re.I)})
    if ri:
        p = ri.parent
        if p and p.name == "a" and "tag=REFU" in p.get("href", ""):
            if "REFU tag badge" not in data["refurb_indicators"]:
                data.update({"is_refurbished": "YES", "has_refurb_tag": "YES"})
                data["refurb_indicators"].append("REFU badge image")
    for crumb in soup.find_all(["a","span"], class_=re.compile(r"breadcrumb|brcb")):
        if "renewed" in crumb.get_text().lower():
            data["is_refurbished"] = "YES"
            data["refurb_indicators"].append('Breadcrumb: "Renewed"')
            break
    for kw in kws:
        if kw in product_name.lower():
            data["is_refurbished"] = "YES"
            ind = f'Title: "{kw}"'
            if ind not in data["refurb_indicators"]:
                data["refurb_indicators"].append(ind)
    for badge in [
        scope.find(["span","div"], class_=re.compile(r"refurb|renewed", re.I)),
        scope.find(["span","div"], string=re.compile(r"REFURBISHED|RENEWED", re.I)),
        scope.find("img", attrs={"alt": re.compile(r"refurb|renewed", re.I)}),
    ]:
        if badge:
            data["is_refurbished"] = "YES"
            if "Refurbished badge" not in data["refurb_indicators"]:
                data["refurb_indicators"].append("Refurbished badge")
            break
    page_text = (scope if scope != soup else soup).get_text()[:3000]
    for pat in [
        r"condition[:\s]*(renewed|refurbished|excellent|good|like new|grade [a-c])",
        r"(renewed|refurbished)[,\s]*(no scratches|excellent|good condition|like new)",
        r"product condition[:\s]*([^\n]+)",
    ]:
        m = re.search(pat, page_text, re.I)
        if m:
            if data["is_refurbished"] == "NO" and any(k in m.group(0).lower() for k in kws):
                data["is_refurbished"] = "YES"
            if "Condition statement" not in data["refurb_indicators"]:
                data["refurb_indicators"].append("Condition statement")
            break
    return data

def extract_seller_info(soup: BeautifulSoup) -> dict:
    data = {"seller_name": "N/A"}
    sec  = soup.find(["h2","h3","div","p"], string=re.compile(r"Seller\s+Information", re.I))
    if not sec:
        sec = soup.find(["div","section"], class_=re.compile(r"seller-info|seller-box", re.I))
    if sec:
        container = sec.find_parent("div") or sec.parent
        if container:
            el = container.find(["p","div"], class_=re.compile(r"-pbs|-m"))
            if el and len(el.get_text().strip()) > 1:
                data["seller_name"] = el.get_text().strip()
            else:
                for c in container.find_all(["a","p","b"]):
                    text = c.get_text().strip()
                    if not text or any(x in text.lower() for x in ["follow","score","seller","information","%","rating","verified"]):
                        continue
                    if re.search(r"\d+%", text):
                        continue
                    data["seller_name"] = text
                    break
    return data

def clean_jumia_sku(raw: str) -> str:
    if not raw or raw == "N/A":
        return "N/A"
    raw = raw.upper()
    m   = re.search(r"([A-Z0-9]+NAFAM[A-Z])", raw)
    return m.group(1) if m else raw.strip()

# ══════════════════════════════════════════════════════════════════════════════
#  CATEGORY LINK EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════
def extract_category_links(category_url: str, headless: bool = True,
                           timeout: int = 20, max_pages: int = 1) -> list[str]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    base_url  = re.sub(r"[?&]page=\d+", "", category_url).rstrip("?&")
    sep       = "&" if "?" in base_url else "?"
    extracted = set()

    for page in range(1, max_pages + 1):
        current_url = f"{base_url}{sep}page={page}" if page > 1 else base_url
        soup = fetch_soup_fast(current_url, timeout=timeout)
        if soup:
            links = soup.select("article.prd a.core")
            if not links:
                break
            for a in links:
                href = a.get("href", "")
                if href and ("/product/" in href or ".html" in href):
                    extracted.add(href)
            continue
        driver = get_driver(headless, timeout)
        if not driver:
            break
        try:
            driver.get(current_url)
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.prd a.core"))
                )
            except TimeoutException:
                break
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
            for elem in driver.find_elements(By.CSS_SELECTOR, "article.prd a.core"):
                href = elem.get_attribute("href")
                if href and ("/product/" in href or ".html" in href):
                    extracted.add(href)
        except Exception as e:
            st.error(f"Error on page {page}: {e}", icon=":material/error:")
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    return list(extracted)

# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPER — FULL PRODUCT DATA
# ══════════════════════════════════════════════════════════════════════════════
def _empty_data(target: dict) -> dict:
    return {
        "Input Source":                  target.get("original_sku", target.get("value", "")),
        "Product Name":                  "N/A",
        "Brand":                         "N/A",
        "Seller Name":                   "N/A",
        "Category":                      "N/A",
        "SKU":                           "N/A",
        "Title has Refurbished":         "NO",
        "Has refurb tag":                "NO",
        "Refurbished Indicators":        "None",
        "Has Warranty":                  "NO",
        "Warranty Duration":             "N/A",
        "Warranty Type":                 "N/A",
        "Warranty Source":               "None",
        "Warranty Address":              "N/A",
        "grading tag":                   "Not Checked",
        "Primary Image URL":             "N/A",
        "Image URLs":                    [],
        "Total Product Images":          0,
        "Grading last image":            "NO",
        "Description has Grading guide": "NO",
        "Price":                         "N/A",
        "Product Rating":                "N/A",
        "Express":                       "No",
        "Has info-graphics":             "NO",
        "Infographic Image Count":       0,
        "Seller authorized":             "NO",
    }

def extract_product_data(soup: BeautifulSoup, data: dict, is_sku: bool,
                         target: dict, do_check: bool = True, country_code: str = "KE") -> dict:
    h1           = soup.find("h1")
    product_name = h1.text.strip() if h1 else "N/A"
    data["Product Name"] = product_name

    bl = soup.find(string=re.compile(r"Brand:\s*", re.I))
    if bl and bl.parent:
        ba = bl.parent.find("a")
        data["Brand"] = ba.text.strip() if ba else bl.parent.get_text().replace("Brand:","").split("|")[0].strip()
    brand = data.get("Brand","")
    if any(x in brand for x in ["window.fbq","undefined","function("]):
        data["Brand"] = "Renewed"
    if not brand or brand in ["N/A"] or brand.lower() in ["generic","renewed","refurbished"]:
        fw = product_name.split()[0] if product_name != "N/A" else "N/A"
        data["Brand"] = "Renewed" if fw.lower() in ["renewed","refurbished"] else fw

    data["Seller Name"] = extract_seller_info(soup)["seller_name"]

    cats = [b.text.strip() for b in soup.select(".osh-breadcrumb a,.brcbs a,[class*='breadcrumb'] a") if b.text.strip()]
    data["Category"] = " > ".join(cats) if cats else "N/A"

    sku_el = soup.find(attrs={"data-sku": True})
    if sku_el:
        sku_raw = sku_el["data-sku"]
    else:
        tc  = soup.get_text()
        m   = re.search(r"SKU[:\s]*([A-Z0-9]+NAFAM[A-Z])", tc) or re.search(r"SKU[:\s]*([A-Z0-9\-]+)", tc)
        sku_raw = m.group(1) if m else target.get("original_sku", "N/A")
    data["SKU"] = clean_jumia_sku(sku_raw)

    data["Image URLs"] = []
    image_url          = None
    gallery = (soup.find("div", id="imgs") or
               soup.find("div", class_=re.compile(r"\bsldr\b|\bgallery\b|-pas", re.I)))
    scope = gallery if gallery else soup
    for img in scope.find_all("img"):
        src = (img.get("data-src") or img.get("src") or "").strip()
        if src and "/product/" in src and not src.startswith("data:"):
            if src.startswith("//"): src = "https:" + src
            elif src.startswith("/"): src = "https://www.jumia.co.ke" + src
            bm = re.search(r"(/product/[a-z0-9_/-]+\.(?:jpg|jpeg|png|webp))", src, re.I)
            bp = bm.group(1) if bm else src
            if not any(bp in eu for eu in data["Image URLs"]):
                data["Image URLs"].append(src)
                if not image_url:
                    image_url = src
    data["Primary Image URL"]    = image_url or "N/A"
    data["Total Product Images"] = len(data["Image URLs"])

    rs = detect_refurbished_status(soup, product_name)
    data["Title has Refurbished"]  = rs["is_refurbished"]
    data["Has refurb tag"]         = rs["has_refurb_tag"]
    data["Refurbished Indicators"] = ", ".join(rs["refurb_indicators"]) or "None"
    if data["Brand"] == "Renewed":
        data["Title has Refurbished"] = "YES"

    desc_imgs = set()
    for cont in soup.find_all("div", class_=re.compile(r"\bmarkup\b|product-desc|-mhm", re.I)):
        for img in cont.find_all("img"):
            src = (img.get("data-src") or img.get("src") or "").strip()
            if src and not src.startswith("data:") and len(src) >= 15 and "1x1" not in src:
                desc_imgs.add(src)
    if not desc_imgs:
        for img in soup.find_all("img"):
            src = (img.get("data-src") or img.get("src") or "").strip()
            if "/cms/external/" in src and not src.endswith(".svg"):
                desc_imgs.add(src)
    data["Infographic Image Count"] = len(desc_imgs)
    data["Has info-graphics"]       = "YES" if desc_imgs else "NO"
    data["_desc_img_urls"]          = list(desc_imgs)

    norm_cat  = data["Category"].replace(" > ", ">").replace(" ", "").lower()
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

    wi = extract_warranty_info(soup, product_name)
    data["Has Warranty"]      = wi["has_warranty"]
    data["Warranty Duration"] = wi["warranty_duration"]
    data["Warranty Type"]     = wi["warranty_type"]
    data["Warranty Source"]   = wi["warranty_source"]
    data["Warranty Address"]  = wi["warranty_address"]

    data["grading tag"]                   = "Not Checked"
    data["Grading last image"]            = "NO"
    data["Description has Grading guide"] = "NO"

    if soup.find(["svg","img","span"], attrs={"aria-label": re.compile(r"Jumia Express", re.I)}):
        data["Express"] = "Yes"

    pt = (soup.find("span", class_=re.compile(r"price|prc|-b")) or
          soup.find(["div","span"], string=re.compile(r"KSh\s*[\d,]+")))
    if pt:
        pm = re.search(r"KSh\s*([\d,]+)", pt.get_text())
        data["Price"] = ("KSh " + pm.group(1)) if pm else pt.get_text().strip()

    re_ = soup.find(["span","div"], class_=re.compile(r"rating|stars"))
    if re_:
        rm = re.search(r"([\d.]+)\s*out of\s*5", re_.get_text())
        if rm:
            data["Product Rating"] = rm.group(1) + "/5"

    return data

def scrape_item(target: dict, headless: bool = True, timeout: int = 20,
                do_check: bool = True, country_code: str = "KE",
                use_fast: bool = True) -> dict:
    url    = target["value"]
    is_sku = target["type"] == "sku"
    data   = _empty_data(target)
    soup   = None

    if use_fast and not is_sku:
        soup = fetch_soup_fast(url, timeout=timeout)

    if use_fast and is_sku and soup is None:
        catalog_soup = fetch_soup_fast(url, timeout=timeout)
        if catalog_soup:
            links = catalog_soup.select("article.prd a.core")
            if links:
                prod_url = links[0].get("href", "")
                if prod_url:
                    soup = fetch_soup_fast(prod_url, timeout=timeout)

    if soup is None:
        soup, _ = fetch_soup_selenium(url, headless=headless, timeout=timeout, is_sku_search=is_sku)

    if soup is None:
        data["Product Name"] = "ERROR_FETCHING"
        return data

    try:
        data = extract_product_data(soup, data, is_sku, target, do_check, country_code)
    except Exception:
        data["Product Name"] = "ERROR_FETCHING"
        return data

    if do_check:
        try:
            data = _run_image_checks_parallel(data)
        except Exception:
            data.pop("_desc_img_urls", None)

    return data

def scrape_parallel(targets: list, n_workers: int, headless: bool = True,
                    timeout: int = 20, do_check: bool = True,
                    country_code: str = "KE", use_fast: bool = True):
    results      = [None] * len(targets)
    failed       = []
    error_states = {"SYSTEM_ERROR","TIMEOUT","CONNECTION_ERROR"}

    with ThreadPoolExecutor(max_workers=n_workers) as ex:
        fs = {
            ex.submit(scrape_item, t, headless, timeout, do_check, country_code, use_fast): i
            for i, t in enumerate(targets)
        }
        for f in as_completed(fs):
            i = fs[f]
            t = targets[i]
            try:
                r = f.result()
                if r["Product Name"] in error_states:
                    failed.append({"input": t.get("original_sku", t["value"]), "error": r["Product Name"]})
                elif r["Product Name"] != "SKU_NOT_FOUND":
                    results[i] = r
            except Exception as e:
                failed.append({"input": t.get("original_sku", t.get("value","")), "error": str(e)})

    return [r for r in results if r is not None], failed

def process_inputs(text_in, file_in, d: str) -> list[dict]:
    raw = set()
    if text_in:
        raw.update(i.strip() for i in re.split(r"[\n,]", text_in) if i.strip())
    if file_in:
        try:
            df = (pd.read_excel(file_in, header=None) if file_in.name.endswith(".xlsx")
                  else pd.read_csv(file_in, header=None))
            raw.update(str(c).strip() for c in df.values.flatten()
                       if str(c).strip() and str(c).lower() != "nan")
        except Exception as e:
            st.error(f"File read error: {e}", icon=":material/error:")
    targets = []
    for item in raw:
        v = item.replace("SKU:", "").strip()
        if v.startswith("http") or v.startswith("www."):
            if not v.startswith("http"): v = "https://" + v
            targets.append({"type": "url", "value": v})
        elif len(v) > 3:
            targets.append({"type": "sku", "value": f"https://www.{d}/catalog/?q={v}", "original_sku": v})
    return targets

# ── Fire mismatch dialog if pending ──────────────────────────────────────────
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
    st.subheader(f"Analyze Products  ·  {region_choice}")

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
                links = extract_category_links(cat_url_in, not show_browser, timeout_seconds, max_cat_pages)
                for lnk in links:
                    targets.append({"type": "url", "value": lnk, "original_sku": lnk})
                if links:
                    st.success(f"Extracted {len(links)} products.", icon=":material/check_circle:")
                else:
                    st.warning("No product links found.", icon=":material/warning:")

        if not targets:
            st.warning("No valid input.", icon=":material/warning:")
        else:
            st.session_state["scraped_results"] = []
            st.session_state["failed_items"]    = []
            current_cc = region_choice.split("(")[-1].strip(")")
            use_fast   = not force_selenium

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
                        ex.submit(scrape_item, t, not show_browser,
                                  timeout_seconds, check_images, current_cc, use_fast): i
                        for i, t in enumerate(targets)
                    }
                    ordered_results = [None] * len(targets)

                    for f in as_completed(fs):
                        i = fs[f]
                        t = targets[i]
                        try:
                            r = f.result()
                            if r["Product Name"] in {"SYSTEM_ERROR","TIMEOUT","CONNECTION_ERROR"}:
                                all_failed.append({"input": t.get("original_sku", t["value"]), "error": r["Product Name"]})
                            elif r["Product Name"] != "SKU_NOT_FOUND":
                                ordered_results[i] = r
                                img_url = r.get("Primary Image URL", "N/A")
                                if img_url != "N/A":
                                    try:
                                        img_placeholder.image(img_url, width=150)
                                    except Exception:
                                        img_placeholder.empty()
                                txt_placeholder.caption(
                                    f"**{r.get('Product Name','N/A')[:70]}**  \n"
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
                            f"**Mode:** {'Fast (HTTP)' if use_fast else 'Browser'}"
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
            "Has Warranty","Warranty Duration","Warranty Type",
            "Seller Name","Seller authorized",
            "Total Product Images","Grading last image","Description has Grading guide",
            "grading tag","Has info-graphics","Infographic Image Count","Price",
            "Product Rating","Express","Category","Refurbished Indicators",
            "Warranty Source","Warranty Address","Primary Image URL","Input Source",
        ]
        df = df[[c for c in priority_cols if c in df.columns]]

        st.subheader("Summary")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Analyzed", len(df))
        m2.metric("Refurbished",    int((df.get("Title has Refurbished","NO") == "YES").sum()))
        m3.metric("Auth Sellers",   int((df.get("Seller authorized","NO")     == "YES").sum()))
        m4.metric("Red Badges",     int(df.get("grading tag","").str.contains("YES", na=False).sum()))
        m5.metric("Avg Images",     f"{df.get('Total Product Images',pd.Series([0])).mean():.1f}")
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
                for row in range((len(display_df)+3)//4):
                    cols_ = st.columns(4)
                    for ci in range(4):
                        idx = row*4+ci
                        if idx >= len(display_df): break
                        item = display_df.iloc[idx]
                        with cols_[ci]:
                            pu = item.get("Primary Image URL","N/A")
                            try:
                                st.image(pu if pu != "N/A" else "https://via.placeholder.com/200?text=No+Image", use_container_width=True)
                            except Exception:
                                st.image("https://via.placeholder.com/200?text=No+Image", use_container_width=True)
                            st.caption(f"**{item.get('Brand','N/A')}**")
                            pn = item.get("Product Name","N/A")
                            st.caption(pn[:50]+"…" if len(pn)>50 else pn)
                            badges = []
                            if item.get("Title has Refurbished")=="YES": badges.append("Refurb")
                            if item.get("Seller authorized")=="YES":     badges.append("Auth")
                            if item.get("Grading last image")=="YES":    badges.append("Grade Img")
                            n_img = item.get("Total Product Images",0)
                            if n_img: badges.append(f"{n_img} imgs")
                            if badges: st.caption(" · ".join(f"[{b}]" for b in badges))
                            st.caption(item.get("Price","N/A"))
                            with st.expander("Details"):
                                st.caption(f"SKU: {item.get('SKU','N/A')}")
                                st.caption(f"Seller: {item.get('Seller Name','N/A')}")
            else:
                for _, item in display_df.iterrows():
                    with st.container():
                        c1, c2 = st.columns([1,4])
                        with c1:
                            pu = item.get("Primary Image URL","N/A")
                            try: st.image(pu if pu!="N/A" else "https://via.placeholder.com/150?text=N/A", width=150)
                            except Exception: pass
                        with c2:
                            st.markdown(f"**{item.get('Product Name','N/A')}**")
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
            "Has Warranty","Warranty Duration","Warranty Type",
            "Seller Name","Seller authorized",
            "Total Product Images","Grading last image","Description has Grading guide",
            "grading tag","Price"
        ] if c in all_cols]

        selected_cols   = st.multiselect("Visible Columns:", options=all_cols, default=default_visible)
        display_full_df = df[selected_cols] if selected_cols else df

        def _highlight(row):
            return (["background-color:#fffacd"] * len(row)
                    if "Brand" in row.index and row["Brand"] == "Renewed"
                    else [""] * len(row))

        selected_indices = []
        try:
            event = st.dataframe(
                display_full_df.style.apply(_highlight, axis=1),
                use_container_width=True,
                on_select="rerun",
                selection_mode="multi-row",
                key="interactive_df"
            )
            selected_indices = event.selection.rows
        except Exception:
            st.dataframe(display_full_df, use_container_width=True)

        download_df = df.iloc[selected_indices] if selected_indices else df
        if selected_indices:
            st.caption(f"Selected {len(selected_indices)} row(s) for download.")
        else:
            st.caption("No rows selected — downloading all rows.")

        st.download_button("Download CSV",
                           download_df.to_csv(index=False).encode("utf-8"),
                           f"analysis_{int(time.time())}.csv", "text/csv",
                           icon=":material/download:", key="a_dl")

# ┌─────────────────────────────────────────────────────────────────────────────
# │  TAB 2 — TAG: SINGLE IMAGE
# └─────────────────────────────────────────────────────────────────────────────
with tab_single:
    st.subheader(f"Tag — Single Image  ·  Grade: {display_tag}  ·  {region_choice}")
    col_in, col_out = st.columns([1, 1])

    with col_in:
        st.markdown("#### Image Source")
        src_method = st.radio("Source:", ["Upload from device","Load from Image URL","Load from SKU"],
                              horizontal=True, key="s_src")

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
                            if not st.session_state.get("mismatch_detected"):
                                st.success("Image loaded.", icon=":material/check_circle:")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not load image: {e}", icon=":material/error:")
                else:
                    st.warning("Please enter a URL.", icon=":material/warning:")

        else:
            sku_val = st.text_input("Product SKU:", placeholder="e.g. GE840EA6C62GANAFAMZ", key="s_sku")
            st.caption(f"Searches **{base_url}** first, then all other Jumia countries.")
            if st.button("Search & Extract Image", icon=":material/search:", key="s_sku_search", type="primary"):
                if sku_val.strip():
                    holder = st.empty()
                    holder.info(f"Searching for SKU `{sku_val.strip()}`…", icon=":material/search:")
                    img, found_country = fetch_image_from_sku(sku_val.strip(), base_url, try_all_countries=True)
                    holder.empty()
                    if img is not None:
                        trigger_mismatch_or_commit(img, sku_val.strip(), "sku", found_country, region_choice, "single")
                        if not st.session_state.get("mismatch_detected"):
                            st.success(f"Image loaded for **{sku_val.strip()}**" + (f" (found in {found_country})" if found_country and found_country != region_choice else ""), icon=":material/check_circle:")
                        st.rerun()
                    else:
                        st.error(f"SKU **{sku_val.strip()}** not found on any Jumia country.", icon=":material/search_off:")
                else:
                    st.warning("Please enter a SKU.", icon=":material/warning:")

        if st.session_state["single_img_bytes"] is not None:
            src  = st.session_state["single_img_source"]
            icon = ":material/upload:" if src == "upload" else ":material/link:" if src == "url" else ":material/qr_code:"
            st.info(f"Image loaded — {st.session_state['single_img_label']}", icon=icon)
            st.markdown("---")
            st.markdown("#### Image Size")
            st.caption("100% = auto-fit. Increase to fill more of the frame.")
            new_scale = st.slider("Product size (% of frame):", 40, 180,
                                  st.session_state["single_scale"], 5, key="s_scale_slider")
            st.session_state["single_scale"] = new_scale
            sc1, sc2, sc3 = st.columns(3)
            if sc1.button("Smaller", icon=":material/remove:", key="s_smaller"):
                st.session_state["single_scale"] = max(40, st.session_state["single_scale"] - 5); st.rerun()
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
                st.image(result, use_container_width=True,
                         caption=f"Grade: {display_tag}  ·  Size: {st.session_state['single_scale']}%")
                st.markdown("---")
                st.download_button("Download Tagged Image (JPEG)",
                                   image_to_jpeg_bytes(result),
                                   f"tagged_{tag_type.lower().replace(' ','_')}.jpg",
                                   "image/jpeg", use_container_width=True,
                                   icon=":material/download:", key="s_dl")
        else:
            st.info("Load an image using one of the source options on the left.", icon=":material/image:")

# ┌─────────────────────────────────────────────────────────────────────────────
# │  TAB 3 — TAG: BULK
# └─────────────────────────────────────────────────────────────────────────────
with tab_bulk:
    st.subheader(f"Tag — Bulk Processing  ·  Grade: {display_tag}  ·  {region_choice}")
    st.caption("Images are auto-cropped and fitted. Per-image size controls are available before processing.")

    bulk_method = st.radio("Input method:",
                           ["Upload multiple images","Enter URLs manually","Upload Excel file with URLs","Enter SKUs"],
                           key="b_method")

    if bulk_method == "Upload multiple images":
        files = st.file_uploader("Choose image files:", type=["png","jpg","jpeg","webp"],
                                 accept_multiple_files=True, key="b_upload")
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
        raw_urls = st.text_area("Image URLs (one per line):", height=160,
                                placeholder="https://example.com/image1.jpg", key="b_urls")
        if st.button("Load Images from URLs", icon=":material/download:", key="b_url_load"):
            if raw_urls.strip():
                url_list = [u.strip() for u in raw_urls.splitlines() if u.strip()]
                loaded   = []
                prog_url = st.progress(0)
                for i, u in enumerate(url_list):
                    try:
                        r = _SESSION.get(u, timeout=12)
                        r.raise_for_status()
                        img = Image.open(BytesIO(r.content)).convert("RGBA")
                        loaded.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": f"image_{i+1}"})
                    except Exception as e:
                        st.warning(f"URL {i+1} failed: {e}", icon=":material/warning:")
                    prog_url.progress((i+1)/len(url_list))
                st.session_state["bulk_url_products"] = loaded
                st.success(f"Loaded {len(loaded)}/{len(url_list)} images.", icon=":material/check_circle:")
        if st.session_state["bulk_url_products"]:
            st.info(f"{len(st.session_state['bulk_url_products'])} images ready.", icon=":material/check_circle:")
        products_to_process = st.session_state.get("bulk_url_products", [])

    elif bulk_method == "Upload Excel file with URLs":
        st.caption("**Column A:** Image URLs  ·  **Column B (optional):** Product name")
        xf = st.file_uploader("Excel file (.xlsx / .xls):", type=["xlsx","xls"], key="b_excel")
        if xf:
            xhash = hashlib.md5(xf.getvalue()[:256]).hexdigest()
            if st.session_state.get("_bulk_excel_hash") != xhash:
                try:
                    df_xl = pd.read_excel(xf)
                    urls  = df_xl.iloc[:,0].dropna().astype(str).tolist()
                    names = (df_xl.iloc[:,1].dropna().astype(str).tolist()
                             if len(df_xl.columns) > 1 else [f"product_{i+1}" for i in range(len(urls))])
                    st.info(f"Found {len(urls)} URLs. Loading…", icon=":material/table:")
                    loaded  = []
                    prog_xl = st.progress(0)
                    for i,(u,n) in enumerate(zip(urls,names)):
                        try:
                            r = _SESSION.get(u, timeout=12)
                            r.raise_for_status()
                            img   = Image.open(BytesIO(r.content)).convert("RGBA")
                            clean = re.sub(r"[^\w\s-]","",n).strip().replace(" ","_")
                            loaded.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": clean or f"product_{i+1}"})
                        except Exception as e:
                            st.warning(f"Could not load {n}: {e}", icon=":material/warning:")
                        prog_xl.progress((i+1)/len(urls))
                    st.session_state["bulk_excel_products"] = loaded
                    st.session_state["_bulk_excel_hash"]    = xhash
                except Exception as e:
                    st.error(f"Excel read error: {e}", icon=":material/error:")
            if st.session_state["bulk_excel_products"]:
                st.info(f"{len(st.session_state['bulk_excel_products'])} images ready.", icon=":material/check_circle:")
        products_to_process = st.session_state.get("bulk_excel_products", [])

    else:
        skus_raw = st.text_area("SKUs (one per line):", height=160,
                                placeholder="GE840EA6C62GANAFAMZ", key="b_skus")
        st.caption(f"Will search on **{base_url}**")
        if skus_raw.strip():
            skus = [s.strip() for s in skus_raw.splitlines() if s.strip()]
            st.info(f"{len(skus)} SKUs entered", icon=":material/list:")
            if st.button("Search All SKUs", icon=":material/search:", key="b_sku_search", type="primary"):
                prog_sku   = st.progress(0)
                status_sku = st.empty()
                new_results: list[dict] = []
                mismatches:  list[dict] = []
                for i, sku in enumerate(skus):
                    status_sku.text(f"Fetching {i+1}/{len(skus)}: {sku}")
                    img, found_country = fetch_image_from_sku(sku, base_url, try_all_countries=True)
                    if img:
                        new_results.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": sku})
                        if found_country and found_country != region_choice:
                            mismatches.append({"sku": sku, "found_in": found_country})
                    else:
                        st.warning(f"No image for SKU: {sku}", icon=":material/image_not_supported:")
                    prog_sku.progress((i+1)/len(skus))
                st.session_state["bulk_sku_results"] = new_results
                if mismatches:
                    mm = "  \n".join(f"• **{m['sku']}** — found in {m['found_in']}" for m in mismatches)
                    st.warning(f"**{len(mismatches)} SKU(s) from a different country:**\n{mm}", icon=":material/public:")
                status_sku.success(f"Found {len(new_results)}/{len(skus)} images.", icon=":material/check_circle:")
        products_to_process = st.session_state.get("bulk_sku_results", [])
        if products_to_process:
            st.info(f"{len(products_to_process)} SKU images ready.", icon=":material/check_circle:")

    if products_to_process:
        st.markdown("---")
        st.subheader(f"{len(products_to_process)} images ready")
        with st.container():
            st.markdown("**Global Scale Override:**")
            g_col1, g_col2 = st.columns([3,1])
            with g_col1:
                global_scale = st.slider("Scale for all images:", 40, 180, 100, 5,
                                         key="g_scale_slider", label_visibility="collapsed")
            with g_col2:
                if st.button("Apply to All", use_container_width=True, icon=":material/done_all:"):
                    for ci, item in enumerate(products_to_process):
                        k = f"bsc_{ci}_{item['name']}"
                        st.session_state["individual_scales"][k] = global_scale
                    st.rerun()
        st.markdown("---")

        for row_s in range(0, len(products_to_process), 4):
            chunk  = products_to_process[row_s:row_s+4]
            cols_  = st.columns(4)
            for ci, item in enumerate(chunk):
                idx = row_s + ci
                k   = f"bsc_{idx}_{item['name']}"
                if k not in st.session_state["individual_scales"]:
                    st.session_state["individual_scales"][k] = 100
                with cols_[ci]:
                    try:
                        st.image(bytes_to_pil(item["bytes"]).convert("RGB"),
                                 caption=item["name"], use_container_width=True)
                    except Exception:
                        st.caption(f"[{item['name']}]")
                    sc = st.slider("Size %", 40, 180,
                                   st.session_state["individual_scales"][k],
                                   5, key=f"bsl_{k}", label_visibility="collapsed")
                    st.session_state["individual_scales"][k] = sc
                    st.caption(f"{sc}%")

        st.markdown("---")
        if st.button("Process All Images", icon=":material/tune:", key="b_process", type="primary"):
            tag_img = load_tag_image(tag_type, region_choice)
            if tag_img is not None:
                prog_proc      = st.progress(0)
                processed_imgs = []
                for i, item in enumerate(products_to_process):
                    try:
                        k      = f"bsc_{i}_{item['name']}"
                        sc     = st.session_state["individual_scales"].get(k, 100)
                        result = apply_tag(bytes_to_pil(item["bytes"]).convert("RGBA"), tag_img, sc)
                        processed_imgs.append({"img": result, "name": item["name"]})
                    except Exception as e:
                        st.warning(f"Error on {item['name']}: {e}", icon=":material/warning:")
                    prog_proc.progress((i+1)/len(products_to_process))

                if processed_imgs:
                    st.success(f"{len(processed_imgs)} images processed.", icon=":material/check_circle:")
                    zb = BytesIO()
                    with zipfile.ZipFile(zb, "w", zipfile.ZIP_DEFLATED) as zf:
                        for p in processed_imgs:
                            zf.writestr(f"{p['name']}_1.jpg", image_to_jpeg_bytes(p["img"]))
                    zb.seek(0)
                    st.session_state["b_bulk_zip"]     = zb.getvalue()
                    st.session_state["b_bulk_preview"] = processed_imgs[:8]
                    st.session_state["b_bulk_total"]   = len(processed_imgs)
                else:
                    st.error("No images processed.", icon=":material/error:")

        if st.session_state.get("b_bulk_zip"):
            st.download_button(
                f"Download All {st.session_state['b_bulk_total']} Images (ZIP)",
                st.session_state["b_bulk_zip"],
                f"tagged_{tag_type.lower().replace(' ','_')}.zip",
                "application/zip", use_container_width=True,
                icon=":material/download:", key="b_dl"
            )
            st.markdown("### Preview")
            pcols = st.columns(4)
            for i, p in enumerate(st.session_state["b_bulk_preview"]):
                with pcols[i%4]:
                    st.image(p["img"], caption=p["name"], use_container_width=True)
            if st.session_state["b_bulk_total"] > 8:
                st.caption(f"Showing 8 of {st.session_state['b_bulk_total']}")
    else:
        st.info("Provide images using one of the input methods above.", icon=":material/image:")

# ┌─────────────────────────────────────────────────────────────────────────────
# │  TAB 4 — CONVERT TAG
# └─────────────────────────────────────────────────────────────────────────────
with tab_convert:
    st.subheader(f"Convert Tag  →  {display_tag}  ·  {region_choice}")
    st.caption("Load an already-tagged image. The old tag is detected via pixel scanning and replaced with the selected grade.")

    conv_qty = st.radio("Processing mode:", ["Single image","Multiple images"], horizontal=True, key="cv_qty")

    if conv_qty == "Single image":
        col_src, col_out = st.columns([1,1])

        with col_src:
            st.markdown("#### Image Source")
            cv_method = st.radio("Source:",
                                 ["Upload from device","Load from Image URL","Load from Product URL","Load from SKU"],
                                 horizontal=False, key="cv_src_method")

            if st.session_state.get("cv_src_prev") != cv_method:
                st.session_state.update({
                    "cv_img_bytes": None, "cv_img_label": "",
                    "cv_img_source": None, "cv_src_prev": cv_method
                })

            if cv_method == "Upload from device":
                cf = st.file_uploader("Choose a tagged image:", type=["png","jpg","jpeg","webp"], key="cv_s_upload")
                if cf is not None:
                    fhash = hashlib.md5(cf.getvalue()).hexdigest()
                    if st.session_state["cv_img_label"] != fhash:
                        img = Image.open(cf).convert("RGB")
                        st.session_state.update({
                            "cv_img_bytes":  pil_to_bytes(img, fmt="PNG"),
                            "cv_img_label":  fhash,
                            "cv_img_source": "upload",
                        })

            elif cv_method == "Load from Image URL":
                img_url_cv = st.text_input("Direct image URL:", key="cv_s_img_url")
                if st.button("Load Image", icon=":material/download:", key="cv_s_img_load"):
                    if img_url_cv.strip():
                        with st.spinner("Fetching image…"):
                            try:
                                url_country = detect_country_from_url(img_url_cv.strip())
                                r = _SESSION.get(img_url_cv.strip(), timeout=15)
                                r.raise_for_status()
                                img = Image.open(BytesIO(r.content)).convert("RGB")
                                trigger_mismatch_or_commit(img, img_url_cv.strip(), "url", url_country, region_choice, "cv_single")
                                if not st.session_state.get("mismatch_detected"):
                                    st.success("Image loaded.", icon=":material/check_circle:")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not load image: {e}", icon=":material/error:")
                    else:
                        st.warning("Please enter a URL.", icon=":material/warning:")

            elif cv_method == "Load from Product URL":
                prod_url_cv = st.text_input("Jumia product page URL:", key="cv_s_prod_url")
                if st.button("Extract Image from Page", icon=":material/travel_explore:", key="cv_s_prod_load"):
                    if prod_url_cv.strip():
                        url_country = detect_country_from_url(prod_url_cv.strip())
                        with st.spinner("Extracting image from page…"):
                            soup_ = fetch_soup_fast(prod_url_cv.strip(), timeout=15)
                            img   = None
                            if soup_:
                                img = _extract_image_from_soup(soup_, base_url)
                            if img is None:
                                soup_, _ = fetch_soup_selenium(prod_url_cv.strip(), headless=True, timeout=20)
                                if soup_:
                                    img = _extract_image_from_soup(soup_, base_url)
                            if img:
                                trigger_mismatch_or_commit(img.convert("RGB"), prod_url_cv.strip(), "product_url", url_country, region_choice, "cv_single")
                                if not st.session_state.get("mismatch_detected"):
                                    st.success("Image extracted.", icon=":material/check_circle:")
                                st.rerun()
                            else:
                                st.warning("Could not find an image on that page.", icon=":material/image_not_supported:")
                    else:
                        st.warning("Please enter a product URL.", icon=":material/warning:")

            else:
                sku_cv = st.text_input("Product SKU:", placeholder="e.g. GE840EA6C62GANAFAMZ", key="cv_s_sku")
                st.caption(f"Searches **{base_url}** first, then all other countries.")
                if st.button("Search & Extract Image", icon=":material/search:", key="cv_s_sku_search", type="primary"):
                    if sku_cv.strip():
                        holder_cv = st.empty()
                        holder_cv.info(f"Searching for `{sku_cv.strip()}`…", icon=":material/search:")
                        img, found_country = fetch_image_from_sku(sku_cv.strip(), base_url, try_all_countries=True)
                        holder_cv.empty()
                        if img is not None:
                            trigger_mismatch_or_commit(img, sku_cv.strip(), "sku", found_country, region_choice, "cv_single")
                            if not st.session_state.get("mismatch_detected"):
                                st.success(f"Image loaded for **{sku_cv.strip()}**", icon=":material/check_circle:")
                            st.rerun()
                        else:
                            st.error(f"SKU **{sku_cv.strip()}** not found.", icon=":material/search_off:")
                    else:
                        st.warning("Please enter a SKU.", icon=":material/warning:")

            if st.session_state["cv_img_bytes"] is not None:
                src_icons = {"upload":":material/upload:","url":":material/link:",
                             "product_url":":material/travel_explore:","sku":":material/qr_code:"}
                st.info(f"Loaded: {st.session_state['cv_img_label']}",
                        icon=src_icons.get(st.session_state["cv_img_source"],":material/image:"))

        with col_out:
            st.markdown("#### Result")
            if st.session_state["cv_img_bytes"] is not None:
                tag_img = load_tag_image(tag_type, region_choice)
                if tag_img is not None:
                    tagged_cv = bytes_to_pil(st.session_state["cv_img_bytes"]).convert("RGB")
                    result_cv = strip_and_retag(tagged_cv, tag_img)
                    fname_cv  = re.sub(r"[^\w\s-]","", st.session_state["cv_img_label"]).strip()[:40] or "converted"
                    bc, ac    = st.columns(2)
                    bc.image(tagged_cv, caption="Before (old tag)", use_container_width=True)
                    ac.image(result_cv, caption=f"After → {display_tag}", use_container_width=True)
                    st.markdown("---")
                    st.download_button(
                        f"Download as {display_tag} (JPEG)",
                        image_to_jpeg_bytes(result_cv),
                        f"{fname_cv}_{tag_type.lower().replace(' ','_')}.jpg",
                        "image/jpeg", use_container_width=True,
                        icon=":material/download:", key="cv_s_dl"
                    )
            else:
                st.info("Load an image on the left.", icon=":material/swap_horiz:")

    else:
        st.markdown("#### Image Sources")
        cv_bulk_method = st.radio("Input method:",
                                  ["Upload multiple images","Enter Image URLs","Enter SKUs"],
                                  horizontal=True, key="cv_bulk_method")

        if cv_bulk_method == "Upload multiple images":
            conv_files = st.file_uploader("Choose tagged images:", type=["png","jpg","jpeg","webp"],
                                          accept_multiple_files=True, key="cv_b_upload")
            if conv_files:
                new_hash = hashlib.md5(b"".join(f.getvalue()[:64] for f in conv_files)).hexdigest()
                if st.session_state.get("_cv_upload_hash") != new_hash:
                    loaded = []
                    for f in conv_files:
                        try:
                            img = Image.open(f).convert("RGB")
                            loaded.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": f.name.rsplit(".",1)[0]})
                        except Exception as e:
                            st.warning(f"Could not load {f.name}: {e}", icon=":material/warning:")
                    st.session_state["cv_bulk_upload"]  = loaded
                    st.session_state["_cv_upload_hash"] = new_hash
                st.info(f"{len(st.session_state['cv_bulk_upload'])} files ready.", icon=":material/photo_library:")
            cv_images = st.session_state.get("cv_bulk_upload", [])

        elif cv_bulk_method == "Enter Image URLs":
            raw_cv_urls = st.text_area("Image URLs (one per line):", height=150, key="cv_b_urls")
            if st.button("Load Images", icon=":material/download:", key="cv_b_url_load"):
                if raw_cv_urls.strip():
                    url_list_cv = [u.strip() for u in raw_cv_urls.splitlines() if u.strip()]
                    loaded      = []
                    prog_cv_url = st.progress(0)
                    for i, u in enumerate(url_list_cv):
                        try:
                            r = _SESSION.get(u, timeout=12)
                            r.raise_for_status()
                            img = Image.open(BytesIO(r.content)).convert("RGB")
                            loaded.append({"bytes": pil_to_bytes(img, fmt="JPEG"), "name": f"image_{i+1}"})
                        except Exception as e:
                            st.warning(f"URL {i+1} failed: {e}", icon=":material/warning:")
                        prog_cv_url.progress((i+1)/len(url_list_cv))
                    st.session_state["cv_bulk_url"] = loaded
                    st.success(f"Loaded {len(loaded)}/{len(url_list_cv)} images.", icon=":material/check_circle:")
            if st.session_state["cv_bulk_url"]:
                st.info(f"{len(st.session_state['cv_bulk_url'])} images ready.", icon=":material/check_circle:")
            cv_images = st.session_state.get("cv_bulk_url", [])

        else:
            cv_skus_raw = st.text_area("SKUs (one per line):", height=150, key="cv_b_skus")
            st.caption(f"Will search on **{base_url}**")
            if cv_skus_raw.strip():
                skus_ = [s.strip() for s in cv_skus_raw.splitlines() if s.strip()]
                st.info(f"{len(skus_)} SKUs entered", icon=":material/list:")
                if st.button("Search All SKUs", icon=":material/search:", key="cv_b_sku_search", type="primary"):
                    prog_cv_sku   = st.progress(0)
                    status_cv     = st.empty()
                    new_cv:       list[dict] = []
                    cv_mismatches: list[dict] = []
                    for i, sku_ in enumerate(skus_):
                        status_cv.text(f"Fetching {i+1}/{len(skus_)}: {sku_}")
                        img_, found_ = fetch_image_from_sku(sku_, base_url, try_all_countries=True)
                        if img_:
                            new_cv.append({"bytes": pil_to_bytes(img_.convert("RGB"), fmt="JPEG"), "name": sku_})
                            if found_ and found_ != region_choice:
                                cv_mismatches.append({"sku": sku_, "found_in": found_})
                        else:
                            st.warning(f"No image for SKU: {sku_}", icon=":material/image_not_supported:")
                        prog_cv_sku.progress((i+1)/len(skus_))
                    st.session_state["cv_bulk_sku_results"] = new_cv
                    if cv_mismatches:
                        mm = "  \n".join(f"• **{m['sku']}** — found in {m['found_in']}" for m in cv_mismatches)
                        st.warning(f"**{len(cv_mismatches)} SKU(s) from different country:**\n{mm}", icon=":material/public:")
                    status_cv.success(f"Found {len(new_cv)}/{len(skus_)} images.", icon=":material/check_circle:")
            cv_images = st.session_state.get("cv_bulk_sku_results", [])
            if cv_images:
                st.info(f"{len(cv_images)} SKU images ready.", icon=":material/check_circle:")

        if cv_images:
            st.markdown("---")
            st.subheader(f"{len(cv_images)} tagged images ready to convert")
            st.markdown("**Originals (with old tags):**")
            for rs in range(0, len(cv_images), 4):
                cols_ = st.columns(4)
                for ci, item in enumerate(cv_images[rs:rs+4]):
                    with cols_[ci]:
                        try:
                            st.image(bytes_to_pil(item["bytes"]).convert("RGB"),
                                     caption=item["name"], use_container_width=True)
                        except Exception:
                            st.caption(f"[{item['name']}]")
            st.markdown("---")

            if st.button(f"Convert All to {display_tag}", icon=":material/swap_horiz:",
                         use_container_width=True, key="cv_b_process", type="primary"):
                tag_img = load_tag_image(tag_type, region_choice)
                if tag_img is not None:
                    prog_cv_proc = st.progress(0)
                    converted    = []
                    for i, item in enumerate(cv_images):
                        try:
                            tagged_ = bytes_to_pil(item["bytes"]).convert("RGB")
                            converted.append({"img": strip_and_retag(tagged_, tag_img), "name": item["name"]})
                        except Exception as e:
                            st.warning(f"Error on {item['name']}: {e}", icon=":material/warning:")
                        prog_cv_proc.progress((i+1)/len(cv_images))
                    if converted:
                        st.success(f"{len(converted)} images converted.", icon=":material/check_circle:")
                        zb = BytesIO()
                        with zipfile.ZipFile(zb,"w",zipfile.ZIP_DEFLATED) as zf:
                            for c in converted:
                                zf.writestr(f"{c['name']}_{tag_type.lower().replace(' ','_')}.jpg",
                                            image_to_jpeg_bytes(c["img"]))
                        zb.seek(0)
                        st.session_state["cv_bulk_zip"]     = zb.getvalue()
                        st.session_state["cv_bulk_preview"] = converted[:8]
                        st.session_state["cv_bulk_total"]   = len(converted)
                    else:
                        st.error("No images converted.", icon=":material/error:")

            if st.session_state.get("cv_bulk_zip"):
                st.download_button(
                    f"Download All {st.session_state['cv_bulk_total']} Converted Images (ZIP)",
                    data=st.session_state["cv_bulk_zip"],
                    file_name=f"converted_{tag_type.lower().replace(' ','_')}.zip",
                    mime="application/zip", use_container_width=True,
                    icon=":material/download:", key="cv_b_dl"
                )
                st.markdown("### Preview")
                pcols = st.columns(4)
                for i, c in enumerate(st.session_state["cv_bulk_preview"]):
                    with pcols[i%4]:
                        st.image(c["img"], caption=c["name"], use_container_width=True)
                if st.session_state["cv_bulk_total"] > 8:
                    st.caption(f"Showing 8 of {st.session_state['cv_bulk_total']}")
        else:
            st.info("Provide images using one of the input methods above.", icon=":material/image:")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:40px;padding:18px 24px;background:linear-gradient(135deg,#1A1A1A 0%,#2D2D2D 100%);border-radius:10px;border-top:3px solid #F68B1E;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
  <span style="color:#F68B1E;font-weight:800;font-size:0.95rem;font-family:'Nunito',sans-serif;">Refurbished Suite</span>
  <span style="color:#999;font-size:0.78rem;font-family:'Nunito',sans-serif;">Fast HTTP scraping · Parallel image checks · Auto-crop · Pixel-scan tag removal</span>
</div>
""", unsafe_allow_html=True)
