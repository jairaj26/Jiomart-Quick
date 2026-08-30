#!/usr/bin/env python3
"""
=============================================================================
Dynamic Multi-User JioMart Telegram Bot & 5x Daily Deal Engine
=============================================================================
A standalone, interactive Telegram Bot that:
1. Greets users on /start and dynamically saves their 6-digit delivery PIN.
2. Supports interactive Category Buttons (Atta/Rice/Oil, Snacks, Kitchen, Electronics).
3. Supports /more pagination, /search <keyword>, and category commands.
4. Automatically runs 5 times a day (12:05 AM, 6 AM, 12 PM, 4 PM, 8 PM IST).
5. Uses smart deal diffing and a Two-Tier Alert Cycle (Daily 12:05 AM Master Digest
   and Intra-Day Flash Price Drops).
=============================================================================
"""

import os
import sys
import json
import time
import datetime
import threading
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Any, Optional

# Ensure UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import core fetcher and database modules
from jiomart_fetcher import JioMartProductFetcher, resolve_jiomart_location, Colors
from database import (
    init_db,
    get_user,
    save_or_update_user,
    update_user_pincode,
    set_user_min_discount,
    set_user_nav_state,
    get_user_nav_state,
    toggle_user_active,
    get_all_active_users,
    get_unique_active_pincodes,
    get_users_by_pincode
)
from deal_differ import (
    analyze_and_update_deals,
    group_products_by_category,
    filter_by_category_code,
    CATEGORY_MAP,
    DiffType
)

# Load .env if present
def load_env(filepath: str = ".env") -> None:
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

load_env()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


# --- Telegram API Client ---

def escape_html(text: str) -> str:
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def call_telegram_api(method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Calls Telegram Bot API methods."""
    if not BOT_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "JioMartBot/2.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except Exception:
        return None


def answer_callback_query(callback_query_id: str, text: Optional[str] = None) -> None:
    """Answers a Telegram inline button click to stop the loading spinner."""
    params = {"callback_query_id": callback_query_id}
    if text:
        params["text"] = text
    call_telegram_api("answerCallbackQuery", params)


def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
    reply_markup: Optional[Dict[str, Any]] = None
) -> bool:
    """Sends a Telegram message to a specific chat/user with clean chunking and buttons."""
    if len(text) <= 4000:
        chunks = [text]
    else:
        chunks = []
        lines = text.split("\n")
        curr = ""
        for line in lines:
            if len(curr) + len(line) > 3800:
                chunks.append(curr)
                curr = line + "\n"
            else:
                curr += line + "\n"
        if curr:
            chunks.append(curr)

    success = True
    for idx, chunk in enumerate(chunks):
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }
        # Attach reply markup to the last chunk
        if idx == len(chunks) - 1 and reply_markup:
            payload["reply_markup"] = reply_markup

        res = call_telegram_api("sendMessage", payload)
        if not (res and res.get("ok")):
            success = False
    return success


# --- Interactive Keyboards ---

def get_deals_inline_keyboard(active_cat: str = "cat_all") -> Dict[str, Any]:
    """Generates clean inline buttons for category filtering and pagination."""
    return {
        "inline_keyboard": [
            [
                {"text": "🌾 Atta, Rice & Oil", "callback_data": "cat_atta"},
                {"text": "🥨 Dry Fruits & Snacks", "callback_data": "cat_snacks"}
            ],
            [
                {"text": "🧼 Kitchen & Cookware", "callback_data": "cat_kitchen"},
                {"text": "🧴 Bath & Beauty", "callback_data": "cat_personal"}
            ],
            [
                {"text": "🎧 Electronics & Gadgets", "callback_data": "cat_electronics"},
                {"text": "🎁 Festive & General", "callback_data": "cat_general"}
            ],
            [
                {"text": "⏩ Next 15 Deals (/more)", "callback_data": "action_more"},
                {"text": "🔥 All Top Deals", "callback_data": "cat_all"}
            ]
        ]
    }


# --- Category-Grouped Deal Formatting Helpers ---

def format_deals_list(
    products: List[Dict[str, Any]],
    location_title: str,
    pincode: str,
    header_title: str = "JioMart Top Deals",
    header_subtitle: str = "",
    include_diff_tag: bool = False
) -> str:
    """Formats products into visually grouped category sections."""
    if not products:
        return f"🛒 <b>JioMart Deals</b>\n\nNo matching deals found for <b>{escape_html(location_title)}</b> (PIN: <code>{pincode}</code>)."

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    time_str = ist_now.strftime("%d %b, %I:%M %p IST")

    grouped = group_products_by_category(products)
    total_count = len(products)
    total_savings = sum(p.get("savings", 0.0) for p in products)
    avg_discount = sum(p.get("discount_pct", 0.0) for p in products) / total_count if total_count else 0.0

    sub_line = f"\n🎯 <i>{escape_html(header_subtitle)}</i>" if header_subtitle else ""

    msg = (
        f"🔥 <b>{escape_html(header_title)}</b>\n"
        f"📍 <b>Location:</b> {escape_html(location_title)} (PIN: <code>{pincode}</code>)\n"
        f"🕒 <b>Updated:</b> {time_str}{sub_line}\n"
        f"{'═' * 32}\n\n"
    )

    item_idx = 1
    for bucket_name, bucket_items in grouped.items():
        if not bucket_items:
            continue
        msg += f"<b>{bucket_name} ({len(bucket_items)} Deals)</b>\n"
        for p in bucket_items:
            name = escape_html(p.get("name", "Product"))
            brand = escape_html(p.get("brand", ""))
            price = p.get("effective_price", 0.0)
            mrp = p.get("mrp", 0.0)
            disc = p.get("discount_pct", 0.0)
            savings = p.get("savings", 0.0)
            url = p.get("url", "")
            qty = escape_html(p.get("quantity", ""))
            diff_tag = p.get("diff_tag")

            brand_prefix = f"<b>{brand}</b> - " if brand and brand.lower() != "jiomart" else ""
            badge_str = f" (📦 <i>{qty}</i>)" if qty else ""
            tag_str = f" 🏷️ <i>[{diff_tag}]</i>" if (include_diff_tag and diff_tag) else ""

            if url:
                title_line = f"<b>{item_idx}.</b> <a href=\"{url}\">{brand_prefix}{name}</a>{badge_str}{tag_str}"
            else:
                title_line = f"<b>{item_idx}.</b> {brand_prefix}{name}{badge_str}{tag_str}"

            price_line = (
                f"   💰 <b>₹{price:,.2f}</b> <s>₹{mrp:,.2f}</s> "
                f"| 💥 <b>{disc:.1f}% OFF</b> (Save ₹{savings:,.2f})"
            )

            msg += f"{title_line}\n{price_line}\n"
            item_idx += 1
        msg += "\n"

    msg += (
        f"{'═' * 32}\n"
        f"📊 <b>Summary:</b> {total_count} Deals across {len(grouped)} Categories | Avg: <b>{avg_discount:.1f}% OFF</b>\n"
        f"💵 <b>Total Potential Savings:</b> ₹{total_savings:,.2f}\n"
        f"⚡ <i>Direct from JioMart Vertex API (Ad-Free)</i>"
    )
    return msg


# --- Bot Command Handlers ---

def handle_start(user_id: int, username: str, first_name: str) -> None:
    user = get_user(user_id)
    if user and user.get("pincode"):
        pincode = user["pincode"]
        city = user.get("city", "Your Area")
        text = (
            f"👋 <b>Welcome back, {escape_html(first_name)}!</b>\n\n"
            f"📍 <b>Current Location:</b> {escape_html(city)} (PIN: <code>{pincode}</code>)\n"
            f"🎯 <b>Min Discount:</b> {user.get('min_discount', 60.0):.0f}%\n"
            f"🔔 <b>Alerts:</b> {'Active (5x Daily)' if user.get('is_active', 1) else 'Paused'}\n\n"
            f"<b>Quick Actions:</b>\n"
            f"• <code>/deals</code> — Fetch latest top deals (with category buttons)\n"
            f"• <code>/more</code> — Browse next 15 deals\n"
            f"• <code>/search &lt;keyword&gt;</code> — Search (e.g. <code>/search atta</code>)\n"
            f"• <code>/pincode &lt;PIN&gt;</code> — Change your delivery location\n"
            f"• <code>/mindiscount &lt;%&gt;</code> — Change discount filter\n"
            f"• <code>/pause</code> / <code>/resume</code> — Toggle automated alerts"
        )
        send_message(user_id, text, reply_markup=get_deals_inline_keyboard())
    else:
        save_or_update_user(user_id=user_id, username=username, first_name=first_name)
        text = (
            f"👋 <b>Hello {escape_html(first_name)}! Welcome to JioMart Deals Hunter.</b>\n\n"
            f"I help you find high-discount grocery & electronics deals directly from JioMart without ads or slow pages.\n\n"
            f"📍 <b>To get started, please reply with your 6-digit delivery PIN code:</b>\n"
            f"<i>Example: Send <code>560045</code> or type <code>/pincode 560045</code></i>"
        )
        send_message(user_id, text)


def handle_set_pincode(user_id: int, pincode_str: str) -> None:
    pincode_str = pincode_str.strip()
    if not (len(pincode_str) == 6 and pincode_str.isdigit()):
        send_message(user_id, "⚠️ Please provide a valid <b>6-digit Indian PIN code</b> (e.g. <code>/pincode 560045</code>).")
        return

    send_message(user_id, f"🔍 Validating PIN <code>{pincode_str}</code> with JioMart logistics...")

    resolved = resolve_jiomart_location(pincode_str)
    if not resolved:
        send_message(user_id, f"❌ PIN code <code>{pincode_str}</code> was not found in JioMart's logistics network. Please check the digits and try again.")
        return

    city = resolved.get("city", "Bengaluru")
    state = resolved.get("state", "Karnataka")

    save_or_update_user(
        user_id=user_id,
        pincode=pincode_str,
        city=city,
        state=state
    )

    msg = (
        f"✅ <b>Location Saved Successfully!</b>\n\n"
        f"📍 <b>City:</b> {escape_html(city)}, {escape_html(state)}\n"
        f"📮 <b>PIN Code:</b> <code>{pincode_str}</code>\n"
        f"⏰ <b>Scheduled Alerts:</b> Active at 12:05 AM (Master Digest) & 6 AM, 12 PM, 4 PM, 8 PM (Flash Deals).\n\n"
        f"⚡ <i>Fetching top deals for your location right now...</i>"
    )
    send_message(user_id, msg)

    # Deliver immediate deals
    handle_fetch_deals(user_id, target_pincode=pincode_str, category_code="cat_all", page_start=1)


def handle_fetch_deals(
    user_id: int,
    target_pincode: Optional[str] = None,
    category_code: str = "cat_all",
    page_start: int = 1,
    query: Optional[str] = None
) -> None:
    """Fetches deals with category filtering, search, and pagination."""
    user = get_user(user_id)
    pincode = target_pincode or (user.get("pincode") if user else None)

    if not pincode:
        send_message(user_id, "📍 Please set your PIN code first by sending a 6-digit number (e.g. <code>560045</code>) or <code>/pincode 560045</code>.")
        return

    min_discount = user.get("min_discount", 60.0) if user else 60.0
    display_limit = user.get("deal_limit", 15) if user else 15

    # Update navigation state in DB
    set_user_nav_state(user_id, page=page_start, category=category_code, query=query or "")

    # Determine department
    department = "electronics" if category_code == "cat_electronics" else "groceries"

    fetcher = JioMartProductFetcher(pincode=pincode)
    result = fetcher.fetch_products(
        department=department,
        sort_on="discount_dsc",
        limit=60,
        page_start=page_start,
        max_pages=5,
        query=query if query else None,
        min_discount=min_discount if not query else None,
        in_stock_only=True
    )

    all_products = result.get("products", [])
    city = fetcher.location_info.get("city", "Bengaluru")

    # Apply category filter
    if category_code and category_code != "cat_all":
        products = filter_by_category_code(all_products, category_code)
    else:
        products = all_products

    # Analyze & update database history
    changed, stale = analyze_and_update_deals(all_products, pincode)

    cat_title = CATEGORY_MAP.get(category_code, "Top Deals")
    page_range_str = f"Pages {page_start}–{page_start + 4}"

    if query:
        header_title = f"Search Results for '{escape_html(query)}'"
        header_sub = f"Location: {city} | {page_range_str}"
    else:
        header_title = f"{cat_title}"
        header_sub = f"Location: {city} | {page_range_str} (≥{min_discount:.0f}% OFF)"

    if not products:
        msg = (
            f"🛒 <b>No Deals Found</b>\n\n"
            f"No deals matched in <b>{escape_html(cat_title)}</b> for PIN <code>{pincode}</code> on {page_range_str}.\n"
            f"💡 Try clicking a different category button below or type <code>/deals</code> to return to top deals."
        )
    else:
        msg = format_deals_list(
            products=products[:display_limit],
            location_title=city,
            pincode=pincode,
            header_title=header_title,
            header_subtitle=header_sub
        )

    send_message(
        user_id,
        msg,
        reply_markup=get_deals_inline_keyboard(active_cat=category_code)
    )


def handle_more_deals(user_id: int) -> None:
    """Fetches the next batch of deals (Pages 6-10, 11-15, etc.)."""
    curr_page, curr_cat, curr_query = get_user_nav_state(user_id)
    next_page = curr_page + 5
    handle_fetch_deals(
        user_id,
        category_code=curr_cat or "cat_all",
        page_start=next_page,
        query=curr_query if curr_query else None
    )


def handle_set_mindiscount(user_id: int, disc_str: str) -> None:
    try:
        disc_val = float(disc_str.replace("%", "").strip())
        if not (1 <= disc_val <= 95):
            send_message(user_id, "⚠️ Please enter a discount percentage between <b>1</b> and <b>95</b> (e.g. <code>/mindiscount 70</code>).")
            return
        set_user_min_discount(user_id, disc_val)
        send_message(user_id, f"✅ Minimum discount filter updated to <b>{disc_val:.0f}%</b>. You will only receive deals with ≥{disc_val:.0f}% discount.")
    except ValueError:
        send_message(user_id, "⚠️ Invalid format. Example usage: <code>/mindiscount 65</code>")


def handle_settings(user_id: int) -> None:
    user = get_user(user_id)
    if not user:
        send_message(user_id, "📍 No profile found. Send your 6-digit PIN code to register!")
        return

    pincode = user.get("pincode") or "Not set"
    city = user.get("city") or "Not set"
    min_disc = user.get("min_discount", 60.0)
    is_active = bool(user.get("is_active", 1))

    text = (
        f"⚙️ <b>Your Deal Preferences</b>\n\n"
        f"📮 <b>PIN Code:</b> <code>{pincode}</code>\n"
        f"📍 <b>City:</b> {escape_html(city)}\n"
        f"🎯 <b>Min Discount:</b> {min_disc:.0f}%\n"
        f"🔔 <b>Scheduled Broadcasts:</b> {'✅ Active (5x Daily)' if is_active else '⏸️ Paused'}\n\n"
        f"<b>Commands to modify:</b>\n"
        f"• <code>/pincode &lt;pin&gt;</code> — Change location\n"
        f"• <code>/mindiscount &lt;pct&gt;</code> — Change discount threshold\n"
        f"• <code>/pause</code> / <code>/resume</code> — Toggle automated alerts"
    )
    send_message(user_id, text, reply_markup=get_deals_inline_keyboard())


def handle_toggle_pause(user_id: int, pause: bool) -> None:
    toggle_user_active(user_id, not pause)
    if pause:
        send_message(user_id, "⏸️ <b>Scheduled alerts paused.</b> You will not receive automated daily broadcasts. Type <code>/resume</code> to re-enable anytime.")
    else:
        send_message(user_id, "🔔 <b>Scheduled alerts resumed!</b> You will receive updates at 12:05 AM (Daily Digest) and 6 AM, 12 PM, 4 PM, 8 PM (Flash Deals).")


def handle_help(user_id: int) -> None:
    text = (
        f"📖 <b>JioMart Deals Hunter — Commands & Shortcuts</b>\n\n"
        f"<b>Deals & Categories:</b>\n"
        f"• <code>/deals</code> — Top deals with interactive category buttons\n"
        f"• <code>/more</code> — Browse next 15 deals (Pages 6–10, 11–15...)\n"
        f"• <code>/atta</code> or <code>/rice</code> or <code>/oil</code> — Atta, Rice, Dal & Oil deals\n"
        f"• <code>/snacks</code> or <code>/dryfruits</code> — Dry Fruits & Snacks deals\n"
        f"• <code>/kitchen</code> or <code>/home</code> — Kitchen & Cookware deals\n"
        f"• <code>/beauty</code> or <code>/personal</code> — Personal Care deals\n"
        f"• <code>/electronics</code> — Gadgets & Electronics\n"
        f"• <code>/search &lt;item&gt;</code> — Search any keyword (e.g. <code>/search ghee</code>)\n\n"
        f"<b>Settings:</b>\n"
        f"• <code>/pincode &lt;pin&gt;</code> — Update delivery location\n"
        f"• <code>/mindiscount &lt;pct&gt;</code> — Filter by minimum discount (e.g. 70)\n"
        f"• <code>/settings</code> — View current profile\n"
        f"• <code>/pause</code> / <code>/resume</code> — Toggle scheduled alerts\n\n"
        f"⏰ <b>Broadcast Schedule:</b>\n"
        f"• <b>12:05 AM IST:</b> Daily Master Digest (All Top Deals)\n"
        f"• <b>6 AM, 12 PM, 4 PM, 8 PM IST:</b> Flash Alerts (New Price Drops Only)"
    )
    send_message(user_id, text, reply_markup=get_deals_inline_keyboard())


# --- Dispatcher for Incoming Messages & Callback Queries ---

def process_telegram_update(update: Dict[str, Any]) -> None:
    # 1. Handle Inline Button Callback Queries
    callback_query = update.get("callback_query")
    if callback_query:
        cb_id = callback_query.get("id")
        user_id = callback_query.get("from", {}).get("id")
        data = callback_query.get("data", "")

        if not user_id or not cb_id:
            return

        answer_callback_query(cb_id)

        if data == "action_more":
            handle_more_deals(user_id)
        elif data.startswith("cat_"):
            handle_fetch_deals(user_id, category_code=data, page_start=1)
        return

    # 2. Handle Text Messages
    message = update.get("message")
    if not message:
        return

    chat = message.get("chat", {})
    user_id = chat.get("id")
    username = message.get("from", {}).get("username", "")
    first_name = message.get("from", {}).get("first_name", "User")
    text = (message.get("text") or "").strip()

    if not user_id or not text:
        return

    # Check for direct 6-digit PIN input
    if len(text) == 6 and text.isdigit():
        handle_set_pincode(user_id, text)
        return

    # Command parsing
    parts = text.split()
    cmd = parts[0].lower()

    if cmd == "/start":
        handle_start(user_id, username, first_name)
    elif cmd == "/pincode" and len(parts) > 1:
        handle_set_pincode(user_id, parts[1])
    elif cmd == "/pincode":
        send_message(user_id, "📍 Please specify your 6-digit PIN code. Example: <code>/pincode 560045</code>")
    elif cmd == "/deals" and len(parts) > 1:
        # Check if second argument is a PIN code or category
        arg = parts[1].strip()
        if len(arg) == 6 and arg.isdigit():
            handle_fetch_deals(user_id, target_pincode=arg, category_code="cat_all", page_start=1)
        elif arg.lower() in ["atta", "rice", "oil", "staples"]:
            handle_fetch_deals(user_id, category_code="cat_atta", page_start=1)
        elif arg.lower() in ["snacks", "dryfruits", "dairy"]:
            handle_fetch_deals(user_id, category_code="cat_snacks", page_start=1)
        elif arg.lower() in ["kitchen", "home", "cleaning"]:
            handle_fetch_deals(user_id, category_code="cat_kitchen", page_start=1)
        elif arg.lower() in ["beauty", "personal", "care"]:
            handle_fetch_deals(user_id, category_code="cat_personal", page_start=1)
        elif arg.lower() in ["electronics", "gadgets"]:
            handle_fetch_deals(user_id, category_code="cat_electronics", page_start=1)
        else:
            handle_fetch_deals(user_id, query=" ".join(parts[1:]), page_start=1)
    elif cmd == "/deals":
        handle_fetch_deals(user_id, category_code="cat_all", page_start=1)
    elif cmd == "/more":
        handle_more_deals(user_id)
    elif cmd in ["/atta", "/rice", "/oil", "/staples"]:
        handle_fetch_deals(user_id, category_code="cat_atta", page_start=1)
    elif cmd in ["/snacks", "/dryfruits"]:
        handle_fetch_deals(user_id, category_code="cat_snacks", page_start=1)
    elif cmd in ["/kitchen", "/home", "/cleaning"]:
        handle_fetch_deals(user_id, category_code="cat_kitchen", page_start=1)
    elif cmd in ["/beauty", "/personal", "/personalcare"]:
        handle_fetch_deals(user_id, category_code="cat_personal", page_start=1)
    elif cmd in ["/electronics", "/gadgets"]:
        handle_fetch_deals(user_id, category_code="cat_electronics", page_start=1)
    elif cmd in ["/categories", "/cat"]:
        send_message(user_id, "📂 <b>Select a Category below:</b>", reply_markup=get_deals_inline_keyboard())
    elif cmd == "/search" and len(parts) > 1:
        query_str = " ".join(parts[1:])
        handle_fetch_deals(user_id, query=query_str, page_start=1)
    elif cmd == "/search":
        send_message(user_id, "🔍 Please specify a keyword to search. Example: <code>/search dry fruits</code> or <code>/search atta</code>")
    elif cmd == "/mindiscount" and len(parts) > 1:
        handle_set_mindiscount(user_id, parts[1])
    elif cmd == "/mindiscount":
        send_message(user_id, "🎯 Please specify discount percentage. Example: <code>/mindiscount 70</code>")
    elif cmd == "/settings":
        handle_settings(user_id)
    elif cmd == "/pause":
        handle_toggle_pause(user_id, pause=True)
    elif cmd == "/resume":
        handle_toggle_pause(user_id, pause=False)
    elif cmd in ["/help", "help", "?"]:
        handle_help(user_id)
    else:
        send_message(user_id, "💡 Send <code>/deals</code> to view current deals or <code>/help</code> for available commands.", reply_markup=get_deals_inline_keyboard())


# --- Background Scheduler (5x Daily IST: 12:05am, 6am, 12pm, 4pm, 8pm) ---

SCHEDULED_TIMES_IST = [
    (0, 5),   # 12:05 AM IST (Daily Master Digest)
    (6, 0),   # 06:00 AM IST (Flash Delta)
    (12, 0),  # 12:00 PM IST (Flash Delta)
    (16, 0),  # 04:00 PM IST (Flash Delta)
    (20, 0)   # 08:00 PM IST (Flash Delta)
]

def run_scheduled_broadcast(is_master_digest: bool = False) -> None:
    """
    Executes a scheduled broadcast across all registered unique pincodes.
    - 12:05 AM IST (Master Digest): Resets daily tracker and sends full top deals.
    - 6am/12pm/4pm/8pm (Flash Delta): Only sends fresh price drops/restocks today.
    """
    digest_type_str = "Daily Master Digest (12:05 AM)" if is_master_digest else "Intra-Day Flash Delta"
    print(f"\n{Colors.CYAN}⏰ Running Scheduled Broadcast [{digest_type_str}] across unique pincodes...{Colors.RESET}")
    
    pincodes = get_unique_active_pincodes()
    if not pincodes:
        print("No active subscribed users found.")
        return

    print(f"Subscribed Pincodes: {pincodes}")

    for pin in pincodes:
        users = get_users_by_pincode(pin)
        if not users:
            continue

        try:
            fetcher = JioMartProductFetcher(pincode=pin)
            result = fetcher.fetch_products(
                department="groceries",
                sort_on="discount_dsc",
                limit=60,
                page_start=1,
                max_pages=5,
                min_discount=50.0,
                in_stock_only=True
            )
            products = result.get("products", [])
            city = fetcher.location_info.get("city", "Your City")

            # Run diff against historical records
            changed_deals, stale_deals = analyze_and_update_deals(products, pin, is_master_digest=is_master_digest)
            print(f"PIN {pin}: {len(products)} total items | {len(changed_deals)} active deals | {len(stale_deals)} stale items filtered out.")

            if not changed_deals:
                print(f"PIN {pin}: No deal changes or price drops. Skipping broadcast to avoid spam.")
                continue

            # Broadcast to each user matching their min_discount threshold
            for u in users:
                user_min_disc = u.get("min_discount", 60.0)
                user_deals = [d for d in changed_deals if d.get("discount_pct", 0) >= user_min_disc][:20]

                if not user_deals:
                    continue

                if is_master_digest:
                    header_title = "JioMart Daily Deals Digest"
                    header_sub = f"Daily Top Picks across 5 Pages (≥{user_min_disc:.0f}% OFF)"
                    include_diff_tag = False
                else:
                    header_title = "JioMart Flash Deals"
                    header_sub = "⚡ Fresh Price Drops & New Items Today"
                    include_diff_tag = True

                msg = format_deals_list(
                    products=user_deals,
                    location_title=city,
                    pincode=pin,
                    header_title=header_title,
                    header_subtitle=header_sub,
                    include_diff_tag=include_diff_tag
                )
                send_message(
                    u["user_id"],
                    msg,
                    reply_markup=get_deals_inline_keyboard()
                )
                print(f"✓ Sent {len(user_deals)} categorized deals to User ID: {u['user_id']}")

        except Exception as e:
            print(f"{Colors.RED}Error processing scheduled deals for PIN {pin}: {e}{Colors.RESET}")


def scheduler_worker() -> None:
    """Continuously checks if current time matches the 5 daily IST trigger times."""
    last_triggered_slot = None

    while True:
        try:
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
            curr_hour = ist_now.hour
            curr_min = ist_now.minute

            current_slot = f"{curr_hour:02d}:{curr_min:02d}"

            for h, m in SCHEDULED_TIMES_IST:
                if curr_hour == h and curr_min == m and last_triggered_slot != current_slot:
                    last_triggered_slot = current_slot
                    is_master = (h == 0 and m == 5)
                    run_scheduled_broadcast(is_master_digest=is_master)
                    break

        except Exception as e:
            print(f"Scheduler worker exception: {e}")

        time.sleep(30)


# --- HTTP Health Check Server (For Free Render / Koyeb Web Services) ---

def start_health_server() -> None:
    """Starts a minimal HTTP server on PORT so cloud platforms can verify service health."""
    port_str = os.environ.get("PORT")
    if not port_str:
        return

    try:
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"JioMart Telegram Bot is running healthy!\n")

            def log_message(self, format, *args):
                pass

        port = int(port_str)
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
        print(f"{Colors.CYAN}🌐 Health-check server listening on port {port} for Free Web Service{Colors.RESET}")
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
    except Exception as e:
        print(f"Health server warning: {e}")


# --- Long Polling Listener ---

def start_polling() -> None:
    """Starts Telegram long-polling loop."""
    if not BOT_TOKEN:
        print(f"{Colors.RED}❌ Error: TELEGRAM_BOT_TOKEN is not set in environment or .env!{Colors.RESET}")
        print("Please configure TELEGRAM_BOT_TOKEN and rerun.")
        sys.exit(1)

    init_db()
    print(f"\n{Colors.GREEN}===================================================={Colors.RESET}")
    print(f"{Colors.GREEN}🤖 JioMart Deals Hunter Bot is Online!{Colors.RESET}")
    print(f"⏰ Scheduler Active (5x Daily: 12:05am, 6am, 12pm, 4pm, 8pm IST)")
    print(f"🔘 Interactive Category Buttons & /more Pagination Enabled")
    print(f"{Colors.GREEN}===================================================={Colors.RESET}\n")

    # Start HTTP health check server for Render Free Web Service
    start_health_server()

    # Start background scheduler thread
    sched_thread = threading.Thread(target=scheduler_worker, daemon=True)
    sched_thread.start()

    offset = 0
    while True:
        try:
            res = call_telegram_api("getUpdates", {"offset": offset, "timeout": 20})
            if res and res.get("ok"):
                for update in res.get("result", []):
                    offset = update["update_id"] + 1
                    process_telegram_update(update)
            time.sleep(0.5)
        except Exception as e:
            print(f"Polling loop error: {e}")
            time.sleep(3)


if __name__ == "__main__":
    start_polling()
