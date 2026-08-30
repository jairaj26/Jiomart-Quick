"""
=============================================================================
JioMart Smart Deal Diffing & Categorization Engine
=============================================================================
1. Groups deals into clean visual category buckets:
   - 🌾 Atta, Rice, Dal & Oil
   - 🥨 Dry Fruits, Snacks & Dairy
   - 🧼 Kitchen, Cookware & Cleaning
   - 🧴 Personal Care, Bath & Beauty
   - 🎧 Electronics & Gadgets
   - 🎁 Pooja, Seasonal & General
2. Manages Two-Tier Alert Cycles:
   - Daily Master Digest (12:05 AM IST): Resets daily tracker and sends full top deals.
   - Intra-Day Delta Alerts (6am, 12pm, 4pm, 8pm IST): Only alerts for fresh changes/price drops today.
=============================================================================
"""

import datetime
from typing import Dict, List, Any, Tuple, Optional
from database import get_product_history, upsert_product_history, mark_products_alerted


class DiffType:
    NEW = "NEW"
    PRICE_DROP = "PRICE_DROP"
    DISCOUNT_UP = "DISCOUNT_UP"
    RESTOCKED = "RESTOCKED"
    STALE = "STALE"


# --- Category Buckets & Classification ---

CATEGORY_MAP = {
    "cat_atta": "🌾 Atta, Rice, Dal & Oil",
    "cat_snacks": "🥨 Dry Fruits, Snacks & Dairy",
    "cat_kitchen": "🧼 Kitchen, Cookware & Cleaning",
    "cat_personal": "🧴 Personal Care, Bath & Beauty",
    "cat_electronics": "🎧 Electronics & Gadgets",
    "cat_general": "🎁 Pooja, Seasonal & General",
    "cat_all": "🔥 All Top Deals"
}

CATEGORY_BUCKETS = [
    ("🌾 Atta, Rice, Dal & Oil", [
        "atta", "flour", "sooji", "rice", "oil", "ghee", "dal", "pulse", "masala",
        "spice", "sugar", "jaggery", "salt", "besan", "poha", "wheat", "grain",
        "staples", "cooking essentials", "mustard", "sunflower", "refined", "rajma",
        "chana", "moong", "toor", "urad", "rava", "maida"
    ]),
    ("🥨 Dry Fruits, Snacks & Dairy", [
        "snack", "branded food", "dry fruit", "nut", "date", "biscuit", "cookie",
        "beverage", "tea", "coffee", "juice", "dairy", "bakery", "milk", "butter",
        "cheese", "chocolate", "sweet", "almond", "cashew", "chia", "seed",
        "pista", "raisin", "namkeen", "noodle", "pasta", "khakhra", "syrup", "drink",
        "kaju", "badam", "kishmish", "makhana", "peanut", "chips", "namkeen"
    ]),
    ("🧼 Kitchen, Cookware & Cleaning", [
        "home care", "kitchen", "cleaning", "detergent", "disposable", "plastic",
        "chopper", "bottle", "scissor", "board", "mop", "container", "cookware",
        "utensil", "plate", "flask", "knife", "cutlery", "storage", "broom",
        "scrubber", "dishwash", "floor cleaner", "tissue", "foil", "glassware",
        "lunch box", "bucket", "hanger", "tiffin", "pan", "kadai", "pressure cooker"
    ]),
    ("🧴 Personal Care, Bath & Beauty", [
        "personal care", "hair care", "skin care", "oral care", "baby care",
        "bath", "hand wash", "handwash", "soap", "shampoo", "face wash", "facewash",
        "lotion", "cream", "toothpaste", "brush", "deo", "perfume", "sanitary",
        "diaper", "shaving", "conditioner", "sunscreen", "body wash", "bodywash",
        "serum", "cleanse", "dettol", "savlon", "lifebuoy", "nivea", "colgate"
    ]),
    ("🎧 Electronics & Gadgets", [
        "mobile", "audio", "smart watch", "small appliance", "electronic",
        "headphone", "earphone", "tws", "speaker", "cable", "charger", "trimmer",
        "kettle", "iron", "watch", "power bank", "gadget", "bluetooth", "adapter"
    ]),
    ("🎁 Pooja, Seasonal & General", [
        "pooja", "rakhi", "festival", "stationery", "luggage", "bag", "toy",
        "fashion", "apparel", "clothing", "footwear", "gift", "agarbatti", "diya"
    ])
]


def classify_category_bucket(product: Dict[str, Any]) -> str:
    """Classifies a product into one of the clean category buckets."""
    search_text = (
        f"{product.get('name', '')} "
        f"{product.get('brand', '')} "
        f"{' '.join(product.get('categories', []))} "
        f"{product.get('url', '')}"
    ).lower()

    for bucket_name, keywords in CATEGORY_BUCKETS[:-1]:
        for kw in keywords:
            if kw in search_text:
                return bucket_name

    return CATEGORY_BUCKETS[-1][0]  # Default to Pooja, Seasonal & General


def group_products_by_category(products: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Groups a list of products by their category bucket preserving internal order."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for p in products:
        bucket = p.get("category_bucket") or classify_category_bucket(p)
        p["category_bucket"] = bucket
        if bucket not in grouped:
            grouped[bucket] = []
        grouped[bucket].append(p)
    return grouped


def filter_by_category_code(products: List[Dict[str, Any]], cat_code: str) -> List[Dict[str, Any]]:
    """Filters products to match a specific category code (e.g. cat_atta)."""
    if not cat_code or cat_code == "cat_all":
        return products
    target_bucket_name = CATEGORY_MAP.get(cat_code)
    if not target_bucket_name:
        return products

    return [p for p in products if (p.get("category_bucket") or classify_category_bucket(p)) == target_bucket_name]


# --- Deal Diffing & Daily Alert Engine ---

def get_current_ist_date() -> str:
    """Returns today's date string in IST (YYYY-MM-DD)."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    return ist_now.strftime("%Y-%m-%d")


def analyze_and_update_deals(
    current_products: List[Dict[str, Any]],
    pincode: str,
    is_master_digest: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compares current deals against historical database records.
    
    Parameters:
        current_products: List of freshly fetched products across pages.
        pincode: Location pincode.
        is_master_digest: True for 12:05 AM runs (all top deals sent and reset for the day).
                          False for 6am/12pm/4pm/8pm runs (only new items/price drops sent).
    
    Returns:
        (changed_deals, stale_deals)
    """
    today_date = get_current_ist_date()
    changed_deals = []
    stale_deals = []

    for p in current_products:
        uid = p.get("uid") or p.get("url") or p.get("name")
        curr_price = float(p.get("effective_price", 0.0))
        curr_disc = float(p.get("discount_pct", 0.0))
        curr_stock = bool(p.get("in_stock", True))
        bucket = classify_category_bucket(p)
        p["category_bucket"] = bucket

        history = get_product_history(uid, pincode)

        if not history:
            # 1. Brand New Deal detected
            p_copy = dict(p)
            p_copy["diff_type"] = DiffType.NEW
            p_copy["diff_tag"] = "🆕 NEW DEAL"
            p_copy["diff_reason"] = "First time detected at high discount"
            changed_deals.append(p_copy)

        else:
            prev_price = float(history.get("effective_price", curr_price))
            prev_disc = float(history.get("discount_pct", curr_disc))
            prev_stock = bool(history.get("in_stock", True))
            last_alert_date = history.get("last_alert_date")

            # 2. Price Drop
            if curr_price < (prev_price - 1.0):
                drop_amt = prev_price - curr_price
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.PRICE_DROP
                p_copy["diff_tag"] = f"📉 PRICE DROP (-₹{drop_amt:,.0f})"
                p_copy["diff_reason"] = f"Dropped from ₹{prev_price:,.0f} to ₹{curr_price:,.0f}"
                changed_deals.append(p_copy)

            # 3. Restocked Item
            elif not prev_stock and curr_stock:
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.RESTOCKED
                p_copy["diff_tag"] = "🔄 BACK IN STOCK"
                p_copy["diff_reason"] = "Previously out of stock"
                changed_deals.append(p_copy)

            # 4. Significant Discount Increase (+2% or more)
            elif curr_disc >= (prev_disc + 2.0):
                disc_diff = curr_disc - prev_disc
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.DISCOUNT_UP
                p_copy["diff_tag"] = f"💥 DISCOUNT UP (+{disc_diff:.0f}%)"
                p_copy["diff_reason"] = f"Discount increased from {prev_disc:.0f}% to {curr_disc:.0f}%"
                changed_deals.append(p_copy)

            # 5. Master Digest Reset (12:05 AM IST)
            elif is_master_digest:
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.NEW
                p_copy["diff_tag"] = "🔥 DAILY TOP DEAL"
                changed_deals.append(p_copy)

            # 6. Intra-Day Check: Was it already alerted today?
            elif last_alert_date != today_date:
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.NEW
                p_copy["diff_tag"] = "🆕 TODAY'S DEAL"
                changed_deals.append(p_copy)

            else:
                # 7. Stale / Already alerted today -> Ignored for intra-day broadcast
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.STALE
                stale_deals.append(p_copy)

        # Update product history in database
        alert_date_to_set = today_date if is_master_digest else (history.get("last_alert_date") if history else today_date)
        upsert_product_history(p, pincode, last_alert_date=alert_date_to_set)

    return changed_deals, stale_deals
