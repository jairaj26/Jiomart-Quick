#!/usr/bin/env python3
"""
=============================================================================
Dynamic Multi-User JioMart Telegram Bot & 5x Daily Deal Engine
=============================================================================
A standalone, interactive Telegram Bot that:
1. Greets users on /start and dynamically saves their 6-digit delivery PIN.
2. Serves on-demand deals specific to each user's location (/deals).
3. Automatically runs 5 times a day (12:05 AM, 6 AM, 12 PM, 4 PM, 8 PM IST).
4. Uses smart deal diffing to ONLY broadcast new deals, price drops, and restocks,
   completely filtering out permanent/stale 85% discount items.
5. Zero external heavy dependencies (pure requests/urllib + SQLite + threading).
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
    toggle_user_active,
    get_all_active_users,
    get_unique_active_pincodes,
    get_users_by_pincode
)
from deal_differ import analyze_and_update_deals, DiffType

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
    except Exception as e:
        # print error for debugging
        return None


def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True
) -> bool:
    """Sends a Telegram message to a specific chat/user."""
    # Chunk message if it exceeds Telegram 4096 char limit
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
    for chunk in chunks:
        res = call_telegram_api("sendMessage", {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        })
        if not (res and res.get("ok")):
            success = False
    return success


# --- Deal Formatting Helpers ---

def format_deals_list(
    products: List[Dict[str, Any]],
    location_title: str,
    pincode: str,
    header_subtitle: str = "Top Discount Deals",
    include_diff_tag: bool = False
) -> str:
    """Formats a list of products into a clean Telegram HTML message."""
    if not products:
        return f"🛒 <b>JioMart Deals</b>\n\nNo matching deals found for <b>{escape_html(location_title)}</b> (PIN: <code>{pincode}</code>)."

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    time_str = ist_now.strftime("%d %b, %I:%M %p IST")

    msg = (
        f"🔥 <b>JioMart Deals — {escape_html(header_subtitle)}</b>\n"
        f"📍 <b>Location:</b> {escape_html(location_title)} (PIN: <code>{pincode}</code>)\n"
        f"🕒 <b>Updated:</b> {time_str}\n"
        f"{'═' * 32}\n\n"
    )

    for idx, p in enumerate(products, 1):
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

        tag_line = f"   🏷️ <b>[{diff_tag}]</b>\n" if (include_diff_tag and diff_tag) else ""

        if url:
            title_line = f"<b>{idx}.</b> <a href=\"{url}\">{brand_prefix}{name}</a>{badge_str}"
        else:
            title_line = f"<b>{idx}.</b> {brand_prefix}{name}{badge_str}"

        price_line = (
            f"   💰 <b>₹{price:,.2f}</b> <s>₹{mrp:,.2f}</s> "
            f"| 💥 <b>{disc:.1f}% OFF</b> (Save ₹{savings:,.2f})"
        )

        msg += f"{title_line}\n{tag_line}{price_line}\n\n"

    msg += (
        f"{'═' * 32}\n"
        f"⚡ <i>Direct from JioMart Vertex API (Ad-Free)</i>\n"
        f"💡 <i>Tip: Run /deals anytime to refresh on-demand.</i>"
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
            f"<b>Available Commands:</b>\n"
            f"• <code>/deals</code> — Fetch latest top deals right now\n"
            f"• <code>/pincode &lt;6-digit PIN&gt;</code> — Change your delivery location\n"
            f"• <code>/mindiscount &lt;percent&gt;</code> — Change min discount filter\n"
            f"• <code>/pause</code> or <code>/resume</code> — Toggle automated deal alerts\n"
            f"• <code>/settings</code> — View your preferences"
        )
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
        f"⏰ <b>Scheduled Alerts:</b> Active at 12:05 AM, 6 AM, 12 PM, 4 PM & 8 PM IST.\n\n"
        f"⚡ <i>Fetching top deals for your location right now...</i>"
    )
    send_message(user_id, msg)

    # Deliver immediate deals
    handle_fetch_deals(user_id, target_pincode=pincode_str)


def handle_fetch_deals(user_id: int, target_pincode: Optional[str] = None) -> None:
    user = get_user(user_id)
    pincode = target_pincode or (user.get("pincode") if user else None)

    if not pincode:
        send_message(user_id, "📍 Please set your PIN code first by sending a 6-digit number (e.g. <code>560045</code>) or <code>/pincode 560045</code>.")
        return

    min_discount = user.get("min_discount", 60.0) if user else 60.0
    display_limit = user.get("deal_limit", 15) if user else 15

    fetcher = JioMartProductFetcher(pincode=pincode)
    result = fetcher.fetch_products(
        department="groceries",
        sort_on="discount_dsc",
        limit=60,
        max_pages=5,
        min_discount=min_discount,
        in_stock_only=True
    )

    products = result.get("products", [])
    city = fetcher.location_info.get("city", "Bengaluru")

    # Analyze & update database history
    changed, stale = analyze_and_update_deals(products, pincode)

    # Display top matching deals from the 5 pages
    msg = format_deals_list(
        products=products[:display_limit],
        location_title=city,
        pincode=pincode,
        header_subtitle=f"Top Deals across 5 Pages (≥{min_discount:.0f}% OFF)"
    )
    send_message(user_id, msg)


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
        f"🔔 <b>Scheduled Broadcasts:</b> {'✅ Active' if is_active else '⏸️ Paused'}\n\n"
        f"<b>Commands to modify:</b>\n"
        f"• <code>/pincode &lt;pin&gt;</code> — Change location\n"
        f"• <code>/mindiscount &lt;pct&gt;</code> — Change discount threshold\n"
        f"• <code>/pause</code> / <code>/resume</code> — Toggle automated alerts"
    )
    send_message(user_id, text)


def handle_toggle_pause(user_id: int, pause: bool) -> None:
    toggle_user_active(user_id, not pause)
    if pause:
        send_message(user_id, "⏸️ <b>Scheduled alerts paused.</b> You will not receive automated daily broadcasts. Type <code>/resume</code> to re-enable anytime.")
    else:
        send_message(user_id, "🔔 <b>Scheduled alerts resumed!</b> You will receive updates at 12:05 AM, 6 AM, 12 PM, 4 PM, and 8 PM IST.")


def handle_help(user_id: int) -> None:
    text = (
        f"📖 <b>JioMart Deals Hunter — Commands</b>\n\n"
        f"• <code>/deals</code> — Get top deals for your saved PIN\n"
        f"• <code>/deals &lt;pin&gt;</code> — Search deals for any other PIN\n"
        f"• <code>/pincode &lt;pin&gt;</code> — Update your delivery location\n"
        f"• <code>/mindiscount &lt;pct&gt;</code> — Filter by minimum discount (e.g. 70)\n"
        f"• <code>/settings</code> — View your current profile & preferences\n"
        f"• <code>/pause</code> — Mute automated scheduled alerts\n"
        f"• <code>/resume</code> — Unmute scheduled alerts\n\n"
        f"⚡ <i>Broadcast Schedule: 12:05 AM, 6:00 AM, 12:00 PM, 4:00 PM & 8:00 PM IST</i>"
    )
    send_message(user_id, text)


# --- Dispatcher for Incoming Messages ---

def process_telegram_update(update: Dict[str, Any]) -> None:
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
        handle_fetch_deals(user_id, target_pincode=parts[1])
    elif cmd == "/deals":
        handle_fetch_deals(user_id)
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
        # Default guidance
        send_message(user_id, "💡 Send <code>/deals</code> to view current deals or <code>/help</code> for available commands.")


# --- Background Scheduler (5x Daily IST: 12:05am, 6am, 12pm, 4pm, 8pm) ---

SCHEDULED_TIMES_IST = [
    (0, 5),   # 12:05 AM IST
    (6, 0),   # 06:00 AM IST
    (12, 0),  # 12:00 PM IST
    (16, 0),  # 04:00 PM IST
    (20, 0)   # 08:00 PM IST
]

def run_scheduled_broadcast() -> None:
    """
    Executes a scheduled broadcast across all registered unique pincodes.
    Uses smart deal diffing to only send newly detected deals, price drops, or restocks.
    """
    print(f"\n{Colors.CYAN}⏰ Running Scheduled Deal Broadcast across unique pincodes...{Colors.RESET}")
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
                max_pages=5,
                min_discount=50.0,
                in_stock_only=True
            )
            products = result.get("products", [])
            city = fetcher.location_info.get("city", "Your City")

            # Run diff against historical records
            changed_deals, stale_deals = analyze_and_update_deals(products, pin)
            print(f"PIN {pin}: {len(products)} total items across 5 pages | {len(changed_deals)} changes | {len(stale_deals)} stale items filtered out.")

            if not changed_deals:
                print(f"PIN {pin}: No new deal changes or price drops. Skipping broadcast to avoid spam.")
                continue

            # Broadcast changes to each user matching their min_discount threshold
            for u in users:
                user_min_disc = u.get("min_discount", 60.0)
                user_deals = [d for d in changed_deals if d.get("discount_pct", 0) >= user_min_disc][:15]

                if not user_deals:
                    continue

                msg = format_deals_list(
                    products=user_deals,
                    location_title=city,
                    pincode=pin,
                    header_subtitle="🔥 New Deals & Price Drops",
                    include_diff_tag=True
                )
                send_message(u["user_id"], msg)
                print(f"✓ Sent {len(user_deals)} fresh deals to User ID: {u['user_id']}")

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
                    run_scheduled_broadcast()
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
                pass  # Suppress HTTP access logs to keep console clean

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

