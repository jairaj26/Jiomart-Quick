#!/usr/bin/env python3
"""
=============================================================================
JioMart Daily Telegram Deal Broadcaster & Notifier
=============================================================================
Fetches top ad-free discount deals from JioMart and broadcasts them cleanly
to a Telegram Chat, Group, or Channel using the Telegram Bot API.

Designed for automated daily cron runs (e.g. GitHub Actions at 12:05 AM IST)
and manual runs. Zero hardcoded personal information.
=============================================================================
"""

import os
import sys
import json
import argparse
import datetime
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Any, Optional

# Ensure UTF-8 output encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import core JioMart fetcher
try:
    from jiomart_fetcher import JioMartProductFetcher, Colors
except ImportError:
    # If running from a different directory, add parent dir to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from jiomart_fetcher import JioMartProductFetcher, Colors


def load_env_file(filepath: str = ".env") -> None:
    """Simple lightweight .env parser to avoid requiring external libraries."""
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
    except Exception as e:
        print(f"Note: Could not parse .env file: {e}")


def escape_html(text: str) -> str:
    """Escapes HTML special characters for Telegram HTML parse mode."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True
) -> bool:
    """
    Sends a message via Telegram Bot API using pure standard library urllib.
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "JioMartDealNotifier/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            if res_json.get("ok"):
                return True
            else:
                print(f"{Colors.RED}Telegram API Error: {res_json.get('description')}{Colors.RESET}")
                return False
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"{Colors.RED}Telegram HTTP Error {e.code}: {err_msg}{Colors.RESET}")
        return False
    except Exception as e:
        print(f"{Colors.RED}Telegram Network Error: {e}{Colors.RESET}")
        return False


def format_deal_messages(
    products: List[Dict[str, Any]],
    location_info: Dict[str, Any],
    department: str = "groceries",
    min_discount: float = 60.0
) -> List[str]:
    """
    Formats a list of deals into one or more Telegram messages (HTML mode),
    partitioned to respect Telegram's 4096 character limit.
    """
    if not products:
        return [
            f"🛒 <b>JioMart Deals Alert</b>\n\n"
            f"No deals found with ≥{min_discount}% discount in <b>{escape_html(department)}</b> for PIN <code>{location_info.get('pincode', 'N/A')}</code>."
        ]

    # Current timestamp in IST
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    date_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")

    city = location_info.get("city", "Bengaluru")
    pincode = location_info.get("pincode", "")

    header = (
        f"🔥 <b>Top JioMart Deals ({escape_html(department.capitalize())})</b>\n"
        f"📍 <b>Location:</b> {escape_html(city)} (PIN: <code>{pincode}</code>)\n"
        f"📅 <b>Updated:</b> {date_str}\n"
        f"🎯 <b>Min Discount:</b> {min_discount}%+\n"
        f"{'═' * 30}\n\n"
    )

    items_text = []
    total_savings = 0.0

    for idx, p in enumerate(products, 1):
        name = escape_html(p.get("name", "Product"))
        brand = escape_html(p.get("brand", ""))
        price = p.get("effective_price") if p.get("effective_price") is not None else p.get("price", 0.0)
        mrp = p.get("mrp", 0.0)
        discount = p.get("discount_pct", 0.0)
        savings = p.get("savings", 0.0)
        url = p.get("url", "")
        qty = escape_html(p.get("quantity", ""))
        in_stock = p.get("in_stock", True)

        total_savings += savings

        # Stock & quantity tags
        badges = []
        if qty:
            badges.append(f"📦 <i>{qty}</i>")
        if not in_stock:
            badges.append("⚠️ <b>Out of Stock</b>")

        badge_str = f" ({' | '.join(badges)})" if badges else ""
        brand_prefix = f"<b>{brand}</b> - " if brand and brand.lower() != "jiomart" else ""

        # Hyperlink item name directly
        if url:
            title_line = f"<b>{idx}.</b> <a href=\"{url}\">{brand_prefix}{name}</a>{badge_str}"
        else:
            title_line = f"<b>{idx}.</b> {brand_prefix}{name}{badge_str}"

        price_line = (
            f"   💰 <b>₹{price:,.2f}</b> <s>₹{mrp:,.2f}</s> "
            f"| 💥 <b>{discount:.1f}% OFF</b> (Save ₹{savings:,.2f})"
        )

        item_block = f"{title_line}\n{price_line}\n"
        items_text.append(item_block)

    # Split into chunks under 3800 chars (safe margin for Telegram 4096 limit)
    messages = []
    current_msg = header
    
    for block in items_text:
        if len(current_msg) + len(block) > 3800:
            messages.append(current_msg)
            current_msg = "🔥 <b>JioMart Deals (Continued)...</b>\n\n" + block
        else:
            current_msg += block + "\n"

    # Add summary footer to the last message
    avg_discount = sum(p.get("discount_pct", 0.0) for p in products) / len(products) if products else 0
    footer = (
        f"\n{'═' * 30}\n"
        f"📊 <b>Summary:</b> {len(products)} deals | Avg Discount: <b>{avg_discount:.1f}%</b>\n"
        f"💵 <b>Total Potential Savings:</b> ₹{total_savings:,.2f}\n"
        f"⚡ <i>Ad-Free pure data direct from JioMart Vertex API</i>"
    )

    if len(current_msg) + len(footer) > 4000:
        messages.append(current_msg)
        messages.append(footer)
    else:
        current_msg += footer
        messages.append(current_msg)

    return messages


def broadcast_deals(
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    pincode: Optional[str] = None,
    department: str = "groceries",
    min_discount: float = 60.0,
    limit: int = 20,
    in_stock_only: bool = True,
    dry_run: bool = False
) -> bool:
    """
    Main orchestration function to fetch and broadcast deals.
    """
    load_env_file()

    # Resolve credentials from arguments or environment variables
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    target_chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    target_pin = pincode or os.environ.get("JIOMART_PINCODE", "").strip() or None

    print(f"\n{Colors.CYAN}🚀 Initializing JioMart Telegram Deal Notifier...{Colors.RESET}")

    if not dry_run and (not token or not target_chat):
        print(f"{Colors.RED}❌ Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing.{Colors.RESET}")
        print(f"   Please specify them as environment variables, in a .env file, or via CLI flags.")
        print(f"   Example: python telegram_notifier.py --token <BOT_TOKEN> --chat-id <CHAT_ID>\n")
        return False

    # 1. Fetch products
    fetcher = JioMartProductFetcher(pincode=target_pin)
    result = fetcher.fetch_products(
        department=department,
        sort_on="discount_dsc",
        limit=limit,
        min_discount=min_discount,
        in_stock_only=in_stock_only
    )

    products = result.get("products", [])
    print(f"{Colors.GREEN}✓ Fetched {len(products)} deals matching criteria (≥{min_discount}% discount).{Colors.RESET}")

    # 2. Format Telegram message
    messages = format_deal_messages(
        products=products,
        location_info=fetcher.location_info,
        department=department,
        min_discount=min_discount
    )

    # 3. Dry run or send
    if dry_run:
        print(f"\n{Colors.YELLOW}--- [DRY RUN: Telegram Message Preview] ---{Colors.RESET}\n")
        for idx, msg in enumerate(messages, 1):
            print(f"--- Message Chunk {idx}/{len(messages)} ({len(msg)} chars) ---")
            print(msg)
            print()
        print(f"{Colors.YELLOW}--- [End of Preview] ---{Colors.RESET}\n")
        return True

    print(f"{Colors.CYAN}📤 Sending {len(messages)} message(s) to Telegram chat ID: {target_chat}...{Colors.RESET}")
    all_success = True
    for idx, msg in enumerate(messages, 1):
        success = send_telegram_message(
            bot_token=token,
            chat_id=target_chat,
            text=msg,
            parse_mode="HTML"
        )
        if success:
            print(f"{Colors.GREEN}✓ Message {idx}/{len(messages)} sent successfully!{Colors.RESET}")
        else:
            print(f"{Colors.RED}✗ Failed to send message {idx}/{len(messages)}.{Colors.RESET}")
            all_success = False

    return all_success


def main():
    parser = argparse.ArgumentParser(
        description="JioMart Daily Telegram Deal Broadcaster",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--token", help="Telegram Bot Token (or set TELEGRAM_BOT_TOKEN env var)")
    parser.add_argument("--chat-id", help="Telegram Chat ID or @channel (or set TELEGRAM_CHAT_ID env var)")
    parser.add_argument("--pincode", help="Delivery PIN code (or set JIOMART_PINCODE env var)")
    parser.add_argument("--dept", default=os.environ.get("DEPARTMENT", "groceries"), help="Department (default: groceries)")
    parser.add_argument("--min-discount", type=float, default=float(os.environ.get("MIN_DISCOUNT", 60)), help="Minimum discount percentage (default: 60)")
    parser.add_argument("--limit", type=int, default=int(os.environ.get("DEAL_LIMIT", 20)), help="Number of deals to send (default: 20)")
    parser.add_argument("--include-oos", action="store_true", help="Include out-of-stock items")
    parser.add_argument("--dry-run", action="store_true", help="Print the Telegram message preview to console without sending")

    args = parser.parse_args()

    success = broadcast_deals(
        bot_token=args.token,
        chat_id=args.chat_id,
        pincode=args.pincode,
        department=args.dept,
        min_discount=args.min_discount,
        limit=args.limit,
        in_stock_only=not args.include_oos,
        dry_run=args.dry_run
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
