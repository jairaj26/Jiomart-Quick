"""
=============================================================================
JioMart Smart Deal Diffing & Deduplication Engine
=============================================================================
Filters out stale "permanent 85% discount" items and only detects:
1. Brand New High-Discount Deals
2. Price Drops (e.g. ₹99 -> ₹69)
3. Significant Discount Increases
4. Restocked Items (previously out of stock)
=============================================================================
"""

import datetime
from typing import Dict, List, Any, Tuple
from database import get_product_history, upsert_product_history


class DiffType:
    NEW = "NEW"
    PRICE_DROP = "PRICE_DROP"
    DISCOUNT_UP = "DISCOUNT_UP"
    RESTOCKED = "RESTOCKED"
    STALE = "STALE"


def analyze_and_update_deals(
    current_products: List[Dict[str, Any]],
    pincode: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compares current deals against historical database records.
    Returns:
        changed_deals: List of products with actionable changes (New, Price Drop, Restocked).
        stale_deals: List of products whose price/discount remained unchanged.
    """
    changed_deals = []
    stale_deals = []

    for p in current_products:
        uid = p.get("uid") or p.get("url") or p.get("name")
        curr_price = float(p.get("effective_price", 0.0))
        curr_disc = float(p.get("discount_pct", 0.0))
        curr_stock = bool(p.get("in_stock", True))

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

            else:
                # 5. Stale / Unchanged Deal -> Ignored for scheduled broadcasts
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.STALE
                stale_deals.append(p_copy)

        # Update database with latest state
        upsert_product_history(p, pincode)

    return changed_deals, stale_deals
