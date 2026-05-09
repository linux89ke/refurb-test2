import numpy as np
from PIL import Image
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
from config import (
    _SESSION, WHITE_THRESHOLD, VERT_STRIP_RATIO, 
    BANNER_RATIO, MARGIN_PERCENT, get_tag_path, TAG_FILES_FR, TAG_FILES
)

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

def load_tag_image(grade: str, region: str) -> Image.Image | None:
    filename = TAG_FILES_FR[grade] if region == "Morocco (MA)" else TAG_FILES[grade]
    path = get_tag_path(filename)
    import os
    if not os.path.exists(path):
        st.error(f"Tag file not found: **{filename}**")
        return None
    return Image.open(path).convert("RGBA")

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
    cw, ch  = tag.size
    safe_w  = cw - int(cw * VERT_STRIP_RATIO)
    safe_h  = ch - int(ch * BANNER_RATIO)
    mx, my  = int(safe_w * MARGIN_PERCENT), int(safe_h * MARGIN_PERCENT)
    inner_w, inner_h = safe_w - 2 * mx, safe_h - 2 * my
    mult    = scale_pct / 100.0
    target_w, target_h = int(inner_w * mult), int(inner_h * mult)
    pw, ph   = product.size
    scale    = min(target_w / pw, target_h / ph)
    nw, nh   = int(pw * scale), int(ph * scale)
    resized  = product.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas   = Image.new("RGB", (cw, ch), (255, 255, 255))
    x, y = mx + (inner_w - nw) // 2, my + (inner_h - nh) // 2
    if resized.mode == "RGBA":
        canvas.paste(resized, (max(0, x), max(0, y)), resized)
    else:
        canvas.paste(resized, (max(0, x), max(0, y)))
    canvas.paste(tag, (0, 0), tag)
    return canvas

def apply_tag(product: Image.Image, tag: Image.Image, scale_pct: int = 100) -> Image.Image:
    cropped = auto_crop_whitespace(product.convert("RGBA"))
    return fit_product_onto_tag(cropped, tag, scale_pct)

def detect_tag_boundaries(img: Image.Image):
    arr  = np.array(img.convert("RGB"))
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
            if consec_white == 0: streak_start = x
            consec_white += 1
            if consec_white >= int(w * 0.015):
                strip_left, found_gap = streak_start - 2, True
                break
    banner_top   = h - int(h * BANNER_RATIO)
    scan_h_start = int(h * 0.60)
    non_white    = ~((arr[:, :, 0] > 235) & (arr[:, :, 1] > 235) & (arr[:, :, 2] > 235))
    nw_counts    = non_white[:, :strip_left].sum(axis=1)
    threshold    = max(5, int(strip_left * 0.01))
    consec_white = 0
    for y in range(h - 1, scan_h_start - 1, -1):
        if nw_counts[y] <= threshold:
            if consec_white == 0: streak_start = y
            consec_white += 1
            if consec_white >= int(h * 0.015):
                banner_top = streak_start - 2
                break
        else: consec_white = 0
    return strip_left, banner_top

def strip_and_retag(tagged: Image.Image, new_tag: Image.Image) -> Image.Image:
    rgb = tagged.convert("RGB")
    sl, bt = detect_tag_boundaries(rgb)
    product_region = rgb.crop((0, 0, sl, bt))
    cropped = auto_crop_whitespace(product_region.convert("RGBA"))
    return fit_product_onto_tag(cropped, new_tag, 100)

def _fetch_and_dhash(url: str):
    try:
        r = _SESSION.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px  = np.array(img)
        return (px[:, 1:] > px[:, :-1]).flatten()
    except Exception: return None

@st.cache_data
def get_target_promo_hash():
    url = "https://ke.jumia.is/unsafe/fit-in/680x680/filters:fill(white)/product/21/3620523/3.jpg?0053"
    try:
        r = _SESSION.get(url, timeout=10)
        img = Image.open(BytesIO(r.content)).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        px  = np.array(img)
        return (px[:, 1:] > px[:, :-1]).flatten()
    except Exception: return None

PROMO_HASH = get_target_promo_hash()

def _run_image_checks_parallel(data: dict) -> dict:
    image_urls = data.get("Image URLs", [])
    primary    = data.get("Primary Image URL", "N/A")
    tasks = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        if primary != "N/A":
            def check_badge(u):
                try:
                    img = Image.open(BytesIO(_SESSION.get(u, timeout=8).content)).convert("RGB").resize((300, 300))
                    # Check top-right for red badge
                    arr = np.array(img)[:100, 200:, :]
                    mask = (arr[:, :, 0] > 180) & (arr[:, :, 1] < 100) & (arr[:, :, 2] < 100)
                    return "YES" if mask.mean() > 0.05 else "NO"
                except: return "NO"
            tasks["badge"] = ex.submit(check_badge, primary)
        if image_urls and PROMO_HASH is not None:
            tasks["last_dhash"] = ex.submit(_fetch_and_dhash, image_urls[-1])
        desc_imgs = data.pop("_desc_img_urls", [])
        for i, u in enumerate(desc_imgs[:6]):
            tasks[f"desc_{i}"] = ex.submit(_fetch_and_dhash, u)
        
        data["grading tag"] = tasks["badge"].result() if "badge" in tasks else "NO"
        if "last_dhash" in tasks:
            lh = tasks["last_dhash"].result()
            data["Grading last image"] = "YES" if lh is not None and np.count_nonzero(PROMO_HASH != lh) <= 12 else "NO"
        data["Description has Grading guide"] = "NO"
        for i in range(6):
            task = tasks.get(f"desc_{i}")
            if task and task.result() is not None and np.count_nonzero(PROMO_HASH != task.result()) <= 12:
                data["Description has Grading guide"] = "YES"; break
    return data
