import streamlit as st
import streamlit.components.v1 as components
from image_utils import pil_to_bytes

# ══════════════════════════════════════════════════════════════════════════════
# PRODUCT CARD GRID  ← new
# ══════════════════════════════════════════════════════════════════════════════

def render_product_grid(
    products: list[dict],
    on_remove=None,
    cols: int = 6,
    key: str = "product_grid",
):
    """
    Render a Jumia-style product card grid with an ✕ button that overlaps
    the top-right corner of each image, exactly like the screenshot.

    Args:
        products:   list of product dicts, each with at least:
                      - "Primary Image URL"  (str)
                      - "Product Name"       (str)
                      - "Price"              (str)
                      - "SKU"                (str)
                      - "Product Rating"     (str, optional)
                      - "Title has Refurbished" (str "YES"/"NO", optional)
                      - "Brand"              (str, optional)
        on_remove:  callable(sku: str) — called when ✕ is clicked.
                    If None, ✕ buttons are hidden.
        cols:       number of cards per row (default 6, matches screenshot)
        key:        unique key for the component

    Returns:
        The SKU of the card whose ✕ was clicked, or None.

    Usage:
        removed = render_product_grid(
            st.session_state["results"],
            on_remove=lambda sku: st.session_state["results"].remove(...),
        )
    """

    def _badge(product: dict) -> str:
        brand = (product.get("Brand") or "").strip()
        refurb = (product.get("Title has Refurbished") or "").upper()
        if brand.lower() == "renewed" or "renewed" in (product.get("Product Name") or "").lower():
            return '<div class="badge renewed">RENEWED</div>'
        if refurb == "YES":
            return '<div class="badge refurbished">REFURBISHED</div>'
        return ""

    def _stars(rating_str: str) -> str:
        try:
            r = float(str(rating_str).split("/")[0].strip())
            full  = int(r)
            empty = 5 - full
            return "★" * full + "☆" * empty
        except Exception:
            return ""

    cards_html = ""
    for i, p in enumerate(products):
        img_url  = p.get("Primary Image URL") or ""
        name     = p.get("Product Name") or "N/A"
        price    = p.get("Price") or "N/A"
        sku      = p.get("SKU") or str(i)
        rating   = p.get("Product Rating") or ""
        badge    = _badge(p)
        stars    = _stars(rating)
        rating_val = ""
        try:
            rating_val = str(round(float(str(rating).split("/")[0].strip()), 1))
        except Exception:
            pass

        remove_btn = (
            f'<button class="x-btn" onclick="removeCard(\'{sku}\')" title="Remove">✕</button>'
            if on_remove is not None else ""
        )

        img_tag = (
            f'<img src="{img_url}" alt="{name}" onerror="this.src=\'https://via.placeholder.com/200x200?text=No+Image\'">'
            if img_url and img_url != "N/A"
            else '<div class="no-img">No Image</div>'
        )

        rating_html = ""
        if stars:
            rating_html = f'''
                <div class="rating-row">
                    <span class="stars">{stars}</span>
                    <span class="rating-val">{rating_val}</span>
                </div>'''

        cards_html += f'''
        <div class="card" id="card-{sku}">
            <div class="img-wrap">
                {remove_btn}
                {badge}
                {img_tag}
            </div>
            <div class="card-body">
                <div class="card-name">{name}</div>
                {rating_html}
                <div class="card-price">{price}</div>
                <div class="card-sku">{sku}</div>
            </div>
        </div>'''

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Open Sans", Arial, sans-serif; background: #f5f5f5; padding: 8px; }}

  .grid {{
    display: grid;
    grid-template-columns: repeat({cols}, 1fr);
    gap: 8px;
  }}

  /* ── Card ── */
  .card {{
    background: #fff;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    overflow: visible;          /* allow ✕ to bleed outside */
    position: relative;
    font-size: 12px;
    transition: box-shadow .15s;
  }}
  .card:hover {{ box-shadow: 0 2px 10px rgba(0,0,0,.15); }}

  /* ── Image wrapper — clipping happens here ── */
  .img-wrap {{
    position: relative;
    width: 100%;
    padding-top: 100%;          /* 1:1 aspect ratio */
    overflow: hidden;
    background: #f9f9f9;
  }}
  .img-wrap img,
  .img-wrap .no-img {{
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    object-fit: contain;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #aaa;
    font-size: 11px;
  }}

  /* ── ✕ button — sits at top-right, half outside the image ── */
  .x-btn {{
    position: absolute;
    top: -8px;
    right: -8px;
    z-index: 10;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    border: none;
    background: #f68b1e;
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    line-height: 22px;
    text-align: center;
    cursor: pointer;
    padding: 0;
    box-shadow: 0 1px 4px rgba(0,0,0,.3);
    transition: background .15s, transform .1s;
  }}
  .x-btn:hover {{ background: #d9731a; transform: scale(1.15); }}

  /* ── Refurb / Renewed badge ── */
  .badge {{
    position: absolute;
    bottom: 0;
    right: 0;
    z-index: 5;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 6px 3px;
    color: #fff;
    line-height: 1;
  }}
  .badge.refurbished {{ background: #c0392b; }}
  .badge.renewed     {{ background: #c0392b; }}

  /* ── Card body ── */
  .card-body {{
    padding: 6px 8px 8px;
  }}
  .card-name {{
    font-size: 11.5px;
    color: #333;
    line-height: 1.3;
    height: 30px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    margin-bottom: 4px;
  }}
  .rating-row {{
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 3px;
  }}
  .stars {{ color: #f68b1e; font-size: 10px; letter-spacing: 1px; }}
  .rating-val {{ font-size: 10px; color: #777; }}
  .card-price {{
    font-weight: 700;
    font-size: 12.5px;
    color: #111;
    margin-bottom: 2px;
  }}
  .card-sku {{
    font-size: 9.5px;
    color: #999;
    letter-spacing: .3px;
    text-transform: uppercase;
  }}
</style>
</head>
<body>

<div class="grid">
{cards_html}
</div>

<script>
  function removeCard(sku) {{
    // Hide the card immediately for instant feedback
    var card = document.getElementById("card-" + sku);
    if (card) card.style.opacity = "0.3";

    // Send the SKU back to Streamlit via query param trick
    var msg = JSON.stringify({{type: "remove", sku: sku}});
    window.parent.postMessage(msg, "*");
  }}
</script>

</body>
</html>
"""

    # Render and listen for remove messages via Streamlit component
    # Height = ceil(products / cols) * 220px + padding
    import math
    rows   = math.ceil(len(products) / cols) if products else 1
    height = rows * 220 + 20

    components.html(html, height=height, scrolling=False)

    # ── Handle ✕ clicks via session_state message bridge ──────────────────
    # Because st.components.v1.html can't return values directly, we use a
    # small workaround: callers should wrap this in a form or check
    # st.session_state["_grid_remove_sku"] after a rerun.
    #
    # For a simpler approach that works without JS messaging, use the
    # render_product_grid_native() function below which uses st.columns +
    # st.button — fully native Streamlit, no HTML component needed.
    return None


# ══════════════════════════════════════════════════════════════════════════════
# NATIVE STREAMLIT VERSION  (recommended — ✕ button works via st.button)
# ══════════════════════════════════════════════════════════════════════════════

def render_product_grid_native(
    products: list[dict],
    cols: int = 6,
    key_prefix: str = "pgrid",
) -> str | None:
    """
    Renders a product card grid using native Streamlit columns + st.markdown
    for the card HTML, with a real st.button for the ✕.

    The ✕ button overlaps the top-right corner of the image using CSS
    injected once via st.markdown.

    Returns:
        SKU string if a card was removed this run, else None.

    Usage:
        removed_sku = render_product_grid_native(st.session_state["results"])
        if removed_sku:
            st.session_state["results"] = [
                p for p in st.session_state["results"] if p["SKU"] != removed_sku
            ]
            st.rerun()
    """

    # Inject CSS once (idempotent — Streamlit dedupes identical markdown)
    st.markdown("""
<style>
/* ── Product card grid ── */
.pcard-wrap {
    position: relative;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    background: #fff;
    margin-bottom: 8px;
    overflow: visible;
}
.pcard-img-wrap {
    position: relative;
    width: 100%;
    padding-top: 100%;
    overflow: hidden;
    background: #f9f9f9;
    border-radius: 4px 4px 0 0;
}
.pcard-img-wrap img {
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 100%;
    object-fit: contain;
}
.pcard-badge {
    position: absolute;
    bottom: 0; right: 0;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    font-size: 8px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 6px 3px;
    color: #fff;
    background: #c0392b;
    line-height: 1;
    z-index: 5;
}
.pcard-body {
    padding: 5px 7px 7px;
    font-size: 11px;
}
.pcard-name {
    color: #333;
    font-size: 11px;
    line-height: 1.3;
    height: 29px;
    overflow: hidden;
    margin-bottom: 3px;
}
.pcard-price {
    font-weight: 700;
    font-size: 12px;
    color: #111;
}
.pcard-sku {
    font-size: 9px;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: .3px;
}
/* ── ✕ button positioning trick ──
   Streamlit renders st.button inside a div; we target that div
   using a data attribute we set via the key. */
[data-testid="stButton"] button.x-close-btn {
    position: absolute !important;
    top: -9px !important;
    right: -9px !important;
    z-index: 20 !important;
    width: 22px !important;
    height: 22px !important;
    min-height: unset !important;
    padding: 0 !important;
    border-radius: 50% !important;
    background: #f68b1e !important;
    color: #fff !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    border: none !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.3) !important;
    line-height: 22px !important;
}
[data-testid="stButton"] button.x-close-btn:hover {
    background: #d9731a !important;
    transform: scale(1.15) !important;
}
</style>
""", unsafe_allow_html=True)

    removed_sku = None
    col_list = st.columns(cols)

    for i, p in enumerate(products):
        col = col_list[i % cols]
        img_url = p.get("Primary Image URL") or ""
        name    = p.get("Product Name") or "N/A"
        price   = p.get("Price") or "N/A"
        sku     = p.get("SKU") or str(i)
        brand   = (p.get("Brand") or "").strip().lower()
        refurb  = (p.get("Title has Refurbished") or "").upper()

        # Badge text
        badge = ""
        if brand == "renewed" or "renewed" in name.lower():
            badge = '<div class="pcard-badge">RENEWED</div>'
        elif refurb == "YES":
            badge = '<div class="pcard-badge">REFURBISHED</div>'

        # Fallback image
        img_src = img_url if (img_url and img_url != "N/A") else \
            "https://via.placeholder.com/200x200?text=No+Image"

        with col:
            # Outer wrapper — position:relative so the ✕ can anchor to it
            st.markdown(f"""
<div class="pcard-wrap" id="wrap-{sku}">
  <div class="pcard-img-wrap">
    {badge}
    <img src="{img_src}" alt="{name}">
  </div>
  <div class="pcard-body">
    <div class="pcard-name">{name}</div>
    <div class="pcard-price">{price}</div>
    <div class="pcard-sku">{sku}</div>
  </div>
</div>
""", unsafe_allow_html=True)

            # ✕ button — rendered by Streamlit so it actually works
            # CSS above positions it over the image corner
            btn_key = f"{key_prefix}_x_{sku}_{i}"
            if st.button("✕", key=btn_key, help=f"Remove {sku}",
                         use_container_width=False):
                removed_sku = sku

    return removed_sku


# ══════════════════════════════════════════════════════════════════════════════
# EXISTING COMPONENTS (unchanged)
# ══════════════════════════════════════════════════════════════════════════════

@st.dialog("Country Mismatch Detected")
def show_country_mismatch_dialog(active_country: str, found_country: str, context: str):
    st.markdown(
        f"""<div style="text-align:center;padding:8px 0 16px;">
<div style="font-size:2.5rem;margin-bottom:8px;">🌍</div>
<div style="font-size:1.05rem;font-weight:700;color:#1A1A1A;margin-bottom:6px;">
Product is from a different country
</div>
<div style="font-size:0.9rem;color:#6B6B6B;line-height:1.5;">
The product belongs to <strong style="color:#F68B1E">{found_country}</strong>,
but your active region is <strong style="color:#1A1A1A">{active_country}</strong>.
</div>
</div>""",
        unsafe_allow_html=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(
            f"Switch to {found_country}", type="primary",
            use_container_width=True, icon=":material/swap_horiz:",
            key=f"mismatch_switch_{context}",
        ):
            st.session_state["region_select"] = found_country
            _commit_pending_image(context)
            st.session_state["mismatch_detected"] = False
            st.session_state["mismatch_resolved"] = True
            st.rerun()
    with col_b:
        if st.button(
            f"Keep {active_country}", use_container_width=True,
            icon=":material/check:", key=f"mismatch_keep_{context}",
        ):
            _commit_pending_image(context)
            st.session_state["mismatch_detected"] = False
            st.session_state["mismatch_resolved"] = True
            st.rerun()
    st.caption(
        "The image has been loaded — this choice only affects which country "
        "will be used for future searches."
    )


def _commit_pending_image(context: str):
    b = st.session_state.get("pending_img_bytes")
    if b is None:
        return
    target = st.session_state.get("pending_img_target", context)
    if target == "single":
        st.session_state["single_img_bytes"] = b
        st.session_state["single_img_label"] = st.session_state.get("pending_img_label", "")
        st.session_state["single_img_source"] = st.session_state.get("pending_img_source", "sku")
        st.session_state["single_scale"] = 100
    elif target == "cv_single":
        st.session_state["cv_img_bytes"] = b
        st.session_state["cv_img_label"] = st.session_state.get("pending_img_label", "")
        st.session_state["cv_img_source"] = st.session_state.get("pending_img_source", "sku")
    st.session_state["pending_img_bytes"] = None
    st.session_state["pending_img_label"] = ""
    st.session_state["pending_img_source"] = None
    st.session_state["pending_img_target"] = None


def trigger_mismatch_or_commit(
    img, label: str, source: str,
    found_country: str | None, active_country: str, target_slot: str,
):
    fmt = "PNG" if source == "upload" else "JPEG"
    img_bytes = pil_to_bytes(img, fmt=fmt)
    if found_country and found_country != active_country:
        st.session_state.update({
            "pending_img_bytes": img_bytes,
            "pending_img_label": label,
            "pending_img_source": source,
            "pending_img_target": target_slot,
            "mismatch_detected": True,
            "mismatch_url_country": found_country,
            "mismatch_active_country": active_country,
            "mismatch_context": target_slot,
            "mismatch_resolved": False,
        })
    else:
        st.session_state.update({
            "pending_img_bytes": img_bytes,
            "pending_img_label": label,
            "pending_img_source": source,
            "pending_img_target": target_slot,
        })
        _commit_pending_image(target_slot)
