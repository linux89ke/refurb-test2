import streamlit as st
import streamlit.components.v1 as components
import math

def render_product_grid(products, cols=5, key="pgrid"):
    """
    Renders a grid where the X button and image are part of the same 
    HTML structure to allow for CSS overlapping.
    """
    if not products:
        return None

    # 1. Handle the return value from the component via session state
    # We use a hidden state to track which SKU was last clicked
    grid_state_key = f"{key}_selected_sku"
    if grid_state_key not in st.session_state:
        st.session_state[grid_state_key] = None

    # 2. Build the HTML string
    cards_html = ""
    for p in products:
        sku = str(p.get("SKU", ""))
        img = p.get("Primary Image URL", "https://placehold.co/200x200")
        name = p.get("Product Name", "N/A")
        price = p.get("Price", "")
        
        cards_html += f"""
        <div class="card">
            <div class="img-container">
                <button class="x-btn" onclick="removeItem('{sku}')">✕</button>
                <img src="{img}" alt="product">
            </div>
            <div class="card-body">
                <div class="sku-label">{sku}</div>
                <div class="name-label">{name}</div>
                <div class="price-label">{price}</div>
            </div>
        </div>
        """

    # 3. Complete HTML with CSS and JS postMessage
    html_content = f"""
    <style>
        .grid {{
            display: grid;
            grid-template-columns: repeat({cols}, 1fr);
            gap: 12px;
            font-family: sans-serif;
            padding: 10px;
        }}
        .card {{
            background: white;
            border: 1px solid #eee;
            border-radius: 4px;
            position: relative;
        }}
        .img-container {{
            position: relative; /* This is the anchor */
            width: 100%;
            padding-top: 100%;
            background: #f9f9f9;
        }}
        .img-container img {{
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            object-fit: contain;
        }}
        .x-btn {{
            position: absolute;
            top: -10px;    /* Half-overlap top */
            right: -10px;  /* Half-overlap right */
            z-index: 10;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #f68b1e;
            color: white;
            border: 2px solid white;
            cursor: pointer;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .card-body {{ padding: 8px; }}
        .sku-label {{ font-size: 10px; color: #f68b1e; font-weight: bold; }}
        .name-label {{ font-size: 12px; height: 32px; overflow: hidden; margin-top: 4px; }}
        .price-label {{ font-weight: bold; margin-top: 4px; font-size: 14px; }}
    </style>

    <div class="grid">{cards_html}</div>

    <script>
        function removeItem(sku) {{
            // This sends the SKU back to Streamlit
            window.parent.postMessage({{
                type: 'streamlit:setComponentValue',
                value: sku
            }}, '*');
        }}
    </script>
    """

    # 4. Render and capture click
    rows = math.ceil(len(products) / cols)
    calc_height = rows * 280 # Adjusted for card height
    
    # components.html returns the 'value' sent via postMessage
    clicked_sku = components.html(html_content, height=calc_height, key=f"html_{key}")

    return clicked_sku
