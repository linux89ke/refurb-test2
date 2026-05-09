import os
import re
import pandas as pd
import streamlit as st
from PIL import Image

from config import TAG_FILES, TAG_FILES_FR


def get_tag_path(filename: str) -> str:
    """Resolve a filename against common search paths."""
    for path in [
        filename,
        os.path.join(os.path.dirname(__file__), filename),
        os.path.join(os.getcwd(), filename),
    ]:
        if os.path.exists(path):
            return path
    return filename


def load_tag_image(grade: str, region: str) -> Image.Image | None:
    """Load a PNG tag overlay for the given grade and region."""
    filename = TAG_FILES_FR[grade] if region == "Morocco (MA)" else TAG_FILES[grade]
    path = get_tag_path(filename)
    if not os.path.exists(path):
        st.error(
            f"Tag file not found: **{filename}**\n"
            "Ensure all tag PNG files are in the same directory.",
            icon=":material/error:",
        )
        return None
    return Image.open(path).convert("RGBA")


@st.cache_data(ttl=3600)
def load_seller_auth_data():
    """
    Loads Authorized Seller & Category mappings from Refurb.xlsx.
    Returns (cat_mapping, auth_sellers). Cached for 1 hour.
    """
    cat_mapping  = {}
    auth_sellers = {cc: {"Phones": set(), "Laptops": set()} for cc in ["KE", "UG", "NG", "MA", "GH"]}
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
        for cc in ["KE", "UG", "NG", "MA", "GH"]:
            try:
                df_s = pd.read_excel(xl_path, sheet_name=cc)
                if "Phones" in df_s.columns:
                    auth_sellers[cc]["Phones"] = set(
                        df_s["Phones"].dropna().astype(str).str.strip().str.lower()
                    )
                if "Laptops" in df_s.columns:
                    auth_sellers[cc]["Laptops"] = set(
                        df_s["Laptops"].dropna().astype(str).str.strip().str.lower()
                    )
            except Exception:
                pass
    except Exception as e:
        st.warning(f"Could not load seller auth data: {e}")
    return cat_mapping, auth_sellers
