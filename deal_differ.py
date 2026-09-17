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


PRIORITY_HOME_BRANDS = {
    "prestige", "milton", "pigeon", "hawkins", "cello",
    "scotch-brite", "scotch brite", "borosil", "philips",
    "wonderchef", "bajaj", "butterfly", "treo", "tupperware", "signoraware"
}


def is_priority_brand(brand: str) -> bool:
    """Checks if a brand is recognized as a reputable, high-demand household brand."""
    if not brand:
        return False
    b_lower = brand.lower().strip()
    return any(pb in b_lower for pb in PRIORITY_HOME_BRANDS)


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
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compares current deals against historical database records with hybrid 7-day cooldown.
    
    Separates items into:
    - main_deals: Core essentials, priority home brands, new deals, and price drops.
    - home_deals_pool: Suppressed static Home & Kitchen items (accessible via Telegram button).
    - pooja_deals_pool: Suppressed static Pooja & Seasonal items (accessible via Telegram button).
    - stale_deals: Items already alerted today or without changes.
    
    Returns:
        (main_deals, home_deals_pool, pooja_deals_pool, stale_deals)
    """
    today_date = get_current_ist_date()
    today_dt = datetime.datetime.strptime(today_date, "%Y-%m-%d").date()

    main_deals = []
    home_deals_pool = []
    pooja_deals_pool = []
    stale_deals = []

    for p in current_products:
        uid = p.get("uid") or p.get("url") or p.get("name")
        curr_price = float(p.get("effective_price", 0.0))
        curr_disc = float(p.get("discount_pct", 0.0))
        curr_stock = bool(p.get("in_stock", True))
        brand = p.get("brand", "")
        bucket = classify_category_bucket(p)
        p["category_bucket"] = bucket

        is_home = (bucket == "🧼 Kitchen, Cookware & Cleaning")
        is_pooja = (bucket == "🎁 Pooja, Seasonal & General")
        is_secondary = is_home or is_pooja
        is_prio = is_priority_brand(brand)

        history = get_product_history(uid, pincode)

        if not history:
            # 1. Brand New Deal detected (First time seen in database)
            p_copy = dict(p)
            p_copy["diff_type"] = DiffType.NEW
            p_copy["diff_tag"] = "🆕 NEW DEAL"
            p_copy["diff_reason"] = "First time detected at high discount"
            main_deals.append(p_copy)
            upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

        else:
            prev_price = float(history.get("effective_price", curr_price))
            prev_disc = float(history.get("discount_pct", curr_disc))
            prev_stock = bool(history.get("in_stock", True))
            last_alert_date_str = history.get("last_alert_date")
            last_alert_price = float(history.get("last_alert_price") or prev_price)

            days_since_alert = 999
            if last_alert_date_str:
                try:
                    last_alert_dt = datetime.datetime.strptime(last_alert_date_str, "%Y-%m-%d").date()
                    days_since_alert = (today_dt - last_alert_dt).days
                except Exception:
                    pass

            has_price_drop = curr_price < (prev_price - 1.0) or curr_price < (last_alert_price - 1.0)
            has_disc_increase = curr_disc >= (prev_disc + 2.0)
            was_restocked = not prev_stock and curr_stock

            # 2. Price Drop (Trigger B)
            if has_price_drop:
                drop_amt = min(prev_price, last_alert_price) - curr_price
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.PRICE_DROP
                p_copy["diff_tag"] = f"📉 PRICE DROP (-₹{drop_amt:,.0f})"
                p_copy["diff_reason"] = f"Dropped from ₹{last_alert_price:,.0f} to ₹{curr_price:,.0f}"
                main_deals.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            # 3. Restocked Item
            elif was_restocked:
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.RESTOCKED
                p_copy["diff_tag"] = "🔄 BACK IN STOCK"
                p_copy["diff_reason"] = "Previously out of stock"
                main_deals.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            # 4. Significant Discount Increase (+2% or more)
            elif has_disc_increase:
                disc_diff = curr_disc - prev_disc
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.DISCOUNT_UP
                p_copy["diff_tag"] = f"💥 DISCOUNT UP (+{disc_diff:.0f}%)"
                p_copy["diff_reason"] = f"Discount increased from {prev_disc:.0f}% to {curr_disc:.0f}%"
                main_deals.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            # 5. Weekly Reset: If 7+ days have elapsed since this item was last alerted
            elif days_since_alert >= 7:
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.NEW
                p_copy["diff_tag"] = "🗓️ WEEKLY TOP PICK"
                p_copy["diff_reason"] = "7-day refresh for active high-discount item"
                main_deals.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            # 6. Unchanged Price within 7-Day Window -> DO NOT SHOW (Universal Anti-Repeat Filter)
            else:
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.STALE
                if is_home:
                    home_deals_pool.append(p_copy)
                elif is_pooja:
                    pooja_deals_pool.append(p_copy)
                stale_deals.append(p_copy)
                upsert_product_history(p, pincode)

    return main_deals, home_deals_pool, pooja_deals_pool, stale_deals
