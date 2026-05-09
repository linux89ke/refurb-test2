import os
import re
import pandas as pd
import requests
import streamlit as st
from urllib.parse import urlparse

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS & SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
MARGIN_PERCENT   = 0.12
BANNER_RATIO     = 0.095
VERT_STRIP_RATIO = 0.18
WHITE_THRESHOLD  = 230

# Your specific deployment URL
APPS_SCRIPT_URL = st.secrets.get(
    "APPS_SCRIPT_URL",
    "https://script.google.com/macros/s/AKfycbzipgCxqlT0NFpPNfXzl6EzfdABS6ZB6muvq6KZItXqFgdviXBeAABkrYz0sDzEg5sD/exec"
)
USE_APPS_SCRIPT_BACKEND = True

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

_DOMAIN_TO_COUNTRY = {v: k for k, v in DOMAIN_MAP.items()}
_COUNTRY_CODE_MAP = {
    "KE": "Kenya (KE)", "UG": "Uganda (UG)", "NG": "Nigeria (NG)",
    "MA": "Morocco (MA)", "GH": "Ghana (GH)"
}

# ── Shared HTTP session with connection pooling ───────────────────────────────
_HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
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
        host = urlparse(url).netloc.lower().lstrip("www.")
        for domain, country_key in _DOMAIN_TO_COUNTRY.items():
            if host == domain or host.endswith("." + domain):
                return country_key
    except Exception:
        pass
    return None

def _detect_country() -> str | None:
    try:
        r = _SESSION.get("https://ipapi.co/json/", timeout=4)
        code = r.json().get("country_code", "")
        return _COUNTRY_CODE_MAP.get(code)
    except Exception:
        return None

def get_tag_path(filename: str) -> str:
    for path in [filename, os.path.join(os.path.dirname(__file__), filename), os.path.join(os.getcwd(), filename)]:
        if os.path.exists(path):
            return path
    return filename

@st.cache_data(ttl=3600)
def load_seller_auth_data():
    """Loads Authorized Seller & Category mappings from Refurb.xlsx."""
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
    except Exception:
        pass
    return cat_mapping, auth_sellers

_CAT_MAPPING, _AUTH_SELLERS = load_seller_auth_data()
