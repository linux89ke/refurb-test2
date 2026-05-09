import re
import numpy as np
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import streamlit as st
from PIL import Image
from bs4 import BeautifulSoup

from config import _SESSION, _get_base_from_url
from data_loaders import load_seller_auth_data

# Pre-load at module level (cached — no repeated file I/O)
_CAT_MAPPING, _AUTH_SELLERS = load_seller_auth_data()


# ══════════════════════════════════════════════════════════════════════════════
#  dHASH HELPERS
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
    url = (
        "https://ke.jumia.is/unsafe/fit-in/680x680/filters:fill(white)"
        "/product/21/3620523/3.jpg?0053"
    )
    try:
        r = _SESSION.get(url, timeout=10)
        return get_dhash(Image.open(BytesIO(r.content)))
    except Exception:
        return None


PROMO_HASH = get_target_promo_hash()


# ══════════════════════════════════════════════════════════════════════════════
#  BADGE & PARALLEL IMAGE CHECKS
# ══════════════════════════════════════════════════════════════════════════════
def has_red_badge(image_url: str) -> str:
    """Check top-right corner only — where Jumia badges live."""
    try:
        r      = _SESSION.get(image_url, timeout=8)
        img    = Image.open(BytesIO(r.content)).convert("RGB").resize((300, 300))
        arr    = np.array(img).astype(float)
        corner = arr[:100, 200:, :]
        mask   = (corner[:, :, 0] > 180) & (corner[:, :, 1] < 100) & (corner[:, :, 2] < 100)
        return "YES (Red Badge)" if mask.sum() / mask.size > 0.05 else "NO"
    except Exception as e:
        return f"ERROR ({str(e)[:20]})"


def _run_image_checks_parallel(data: dict) -> dict:
    """Run badge + dhash checks concurrently instead of sequentially."""
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
                if (dh is not None and PROMO_HASH is not None
                        and np.count_nonzero(PROMO_HASH != dh) <= 12):
                    data["Description has Grading guide"] = "YES"
                    break
            except Exception:
                pass

    return data


# ══════════════════════════════════════════════════════════════════════════════
#  WARRANTY / REFURB / SELLER EXTRACTION
# ══════════════════════════════════════════════════════════════════════════════
def extract_warranty_info(soup: BeautifulSoup, product_name: str) -> dict:
    data = {
        "has_warranty": "NO", "warranty_duration": "N/A",
        "warranty_source": "None", "warranty_details": "", "warranty_address": "N/A",
    }
    patterns = [
        r"(\d+)\s*(?:months?|month|mnths?|mths?)\s*(?:warranty|wrty|wrnty)",
        r"(\d+)\s*(?:year|yr|years|yrs)\s*(?:warranty|wrty|wrnty)",
        r"warranty[:\s]*(\d+)\s*(?:months?|years?)",
    ]
    heading = soup.find(["h3","h4","div","dt"], string=re.compile(r"^\s*Warranty\s*$", re.I))
    if heading:
        val = heading.find_next(["div","dd","p"])
        if val:
            text = val.get_text().strip()
            if text and text.lower() not in ["n/a","na","none",""]:
                for p in patterns:
                    m = re.search(p, text, re.I)
                    if m:
                        unit = "months" if "month" in m.group(0).lower() else "years"
                        data.update({"has_warranty":"YES","warranty_duration":f"{m.group(1)} {unit}",
                                     "warranty_source":"Warranty Section","warranty_details":text[:100]})
                        break
                if data["has_warranty"] == "NO":
                    sm = re.search(r"(\d+)\s*(month|year)", text, re.I)
                    if sm:
                        data.update({"has_warranty":"YES","warranty_duration":text.strip(),
                                     "warranty_source":"Warranty Section"})
    if data["has_warranty"] == "NO":
        for p in patterns:
            m = re.search(p, product_name, re.I)
            if m:
                unit = "months" if "month" in m.group(0).lower() else "years"
                data.update({"has_warranty":"YES","warranty_duration":f"{m.group(1)} {unit}",
                             "warranty_source":"Product Name","warranty_details":m.group(0)})
                break
    lbl = soup.find(string=re.compile(r"Warranty\s+Address", re.I))
    if lbl:
        el = lbl.find_next(["dd","p","div"])
        if el:
            addr = re.sub(r"<[^>]+>","",el.get_text()).strip()
            if addr and len(addr) > 10:
                data["warranty_address"] = addr
    if data["has_warranty"] == "NO" and not heading:
        for row in soup.find_all(["tr","div","li"], class_=re.compile(r"spec|detail|attribute|row")):
            text = row.get_text()
            if "warranty" in text.lower():
                for p in patterns:
                    m = re.search(p, text, re.I)
                    if m:
                        unit = "months" if "month" in m.group(0).lower() else "years"
                        data.update({"has_warranty":"YES","warranty_duration":f"{m.group(1)} {unit}",
                                     "warranty_source":"Specifications","warranty_details":text.strip()[:100]})
                        break
                if data["has_warranty"] == "YES":
                    break
    return data


def detect_refurbished_status(soup: BeautifulSoup, product_name: str) -> dict:
    data = {"is_refurbished":"NO","refurb_indicators":[],"has_refurb_tag":"NO"}
    kws  = ["refurbished","renewed","refurb","recon","reconditioned",
            "ex-uk","ex uk","pre-owned","certified","restored"]
    scope = soup
    h1    = soup.find("h1")
    if h1:
        c = h1.find_parent("div", class_=re.compile(r"col10|-pvs|-p"))
        scope = c if c else h1.parent.parent
    if scope.find("a", href=re.compile(r"/all-products/\?tag=REFU", re.I)):
        data.update({"is_refurbished":"YES","has_refurb_tag":"YES"})
        data["refurb_indicators"].append("REFU tag badge")
    ri = scope.find("img", attrs={"alt": re.compile(r"^REFU$", re.I)})
    if ri:
        p = ri.parent
        if p and p.name == "a" and "tag=REFU" in p.get("href",""):
            if "REFU tag badge" not in data["refurb_indicators"]:
                data.update({"is_refurbished":"YES","has_refurb_tag":"YES"})
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
                    if not text or any(
                        x in text.lower()
                        for x in ["follow","score","seller","information","%","rating","verified"]
                    ):
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


def _empty_data(target: dict) -> dict:
    return {
        "Input Source": target.get("original_sku", target.get("value", "")),
        "Product Name":"N/A","Brand":"N/A","Seller Name":"N/A","Category":"N/A",
        "SKU":"N/A","Title has Refurbished":"NO","Has refurb tag":"NO",
        "Refurbished Indicators":"None","Has Warranty":"NO","Warranty Duration":"N/A",
        "Warranty Source":"None","Warranty Address":"N/A","grading tag":"Not Checked",
        "Primary Image URL":"N/A","Image URLs":[],"Total Product Images":0,
        "Grading last image":"NO","Description has Grading guide":"NO",
        "Price":"N/A","Product Rating":"N/A","Express":"No","Product URL":"N/A",
        "Has info-graphics":"NO","Infographic Image Count":0,"Seller authorized":"NO",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  FULL PRODUCT DATA EXTRACTION FROM SOUP
# ══════════════════════════════════════════════════════════════════════════════
def extract_product_data(
    soup: BeautifulSoup,
    data: dict,
    is_sku: bool,
    target: dict,
    do_check: bool = True,
    country_code: str = "KE",
) -> dict:
    cc_to_domain = {
        "KE": "jumia.co.ke", "UG": "jumia.ug", "NG": "jumia.com.ng",
        "MA": "jumia.ma",    "GH": "jumia.com.gh",
    }
    h1           = soup.find("h1")
    product_name = h1.text.strip() if h1 else "N/A"
    data["Product Name"] = product_name
    data["Product URL"]  = target.get("resolved_url", target.get("value", "N/A"))

    bl = soup.find(string=re.compile(r"Brand:\s*", re.I))
    if bl and bl.parent:
        ba = bl.parent.find("a")
        data["Brand"] = (
            ba.text.strip() if ba
            else bl.parent.get_text().replace("Brand:","").split("|")[0].strip()
        )
    brand = data.get("Brand","")
    if any(x in brand for x in ["window.fbq","undefined","function("]):
        data["Brand"] = "Renewed"
    if not brand or brand in ["N/A"] or brand.lower() in ["generic","renewed","refurbished"]:
        fw = product_name.split()[0] if product_name != "N/A" else "N/A"
        data["Brand"] = "Renewed" if fw.lower() in ["renewed","refurbished"] else fw

    data["Seller Name"] = extract_seller_info(soup)["seller_name"]

    cats = [
        b.text.strip()
        for b in soup.select(".osh-breadcrumb a,.brcbs a,[class*='breadcrumb'] a")
        if b.text.strip()
    ]
    data["Category"] = " > ".join(cats) if cats else "N/A"

    sku_el = soup.find(attrs={"data-sku": True})
    if sku_el:
        sku_raw = sku_el["data-sku"]
    else:
        tc  = soup.get_text()
        m   = (
            re.search(r"SKU[:\s]*([A-Z0-9]+NAFAM[A-Z])", tc)
            or re.search(r"SKU[:\s]*([A-Z0-9\-]+)", tc)
        )
        sku_raw = m.group(1) if m else target.get("original_sku","N/A")
    data["SKU"] = clean_jumia_sku(sku_raw)

    data["Image URLs"] = []
    image_url     = None
    fallback_base = f"https://www.{cc_to_domain.get(country_code, 'jumia.co.ke')}"
    page_base     = _get_base_from_url(
        target.get("resolved_url", target.get("value", "")), fallback=fallback_base
    )
    gallery = (
        soup.find("div", id="imgs") or
        soup.find("div", class_=re.compile(r"\bsldr\b|\bgallery\b|-pas", re.I))
    )
    scope = gallery if gallery else soup
    for img in scope.find_all("img"):
        src = (img.get("data-src") or img.get("src") or "").strip()
        if src and "/product/" in src and not src.startswith("data:"):
            if src.startswith("//"):
                src = "https:" + src
            elif src.startswith("/"):
                src = urljoin(page_base, src)
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

    # Seller authorization
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

    wi = extract_warranty_info(soup, product_name)
    data["Has Warranty"]      = wi["has_warranty"]
    data["Warranty Duration"] = wi["warranty_duration"]
    data["Warranty Source"]   = wi["warranty_source"]
    data["Warranty Address"]  = wi["warranty_address"]

    data["grading tag"]                   = "Not Checked"
    data["Grading last image"]            = "NO"
    data["Description has Grading guide"] = "NO"

    if soup.find(["svg","img","span"], attrs={"aria-label": re.compile(r"Jumia Express", re.I)}):
        data["Express"] = "Yes"

    pt = (
        soup.find("span", class_=re.compile(r"price|prc|-b")) or
        soup.find(["div","span"], string=re.compile(r"KSh\s*[\d,]+"))
    )
    if pt:
        pm = re.search(r"KSh\s*([\d,]+)", pt.get_text())
        data["Price"] = ("KSh " + pm.group(1)) if pm else pt.get_text().strip()

    re_ = soup.find(["span","div"], class_=re.compile(r"rating|stars"))
    if re_:
        rm = re.search(r"([\d.]+)\s*out of\s*5", re_.get_text())
        if rm:
            data["Product Rating"] = rm.group(1) + "/5"

    return data
