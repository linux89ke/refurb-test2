import streamlit as st
from image_utils import pil_to_bytes


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
            f"Switch to {found_country}",
            type="primary",
            use_container_width=True,
            icon=":material/swap_horiz:",
            key=f"mismatch_switch_{context}",
        ):
            st.session_state["region_select"] = found_country
            _commit_pending_image(context)
            st.session_state["mismatch_detected"] = False
            st.session_state["mismatch_resolved"] = True
            st.rerun()
    with col_b:
        if st.button(
            f"Keep {active_country}",
            use_container_width=True,
            icon=":material/check:",
            key=f"mismatch_keep_{context}",
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


def trigger_mismatch_or_commit(
    img,
    label: str,
    source: str,
    found_country: str | None,
    active_country: str,
    target_slot: str,
):
    fmt       = "PNG" if source == "upload" else "JPEG"
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
