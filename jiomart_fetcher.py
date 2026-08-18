#!/usr/bin/env python3
"""
=============================================================================
JioMart Fast Ad-Free Discount Item Fetcher
=============================================================================
A high-performance CLI tool to fetch and filter items sorted by discount
directly from JioMart Vertex APIs, bypassing all web ads, trackers, and bloat.

Features:
- Dynamic IP-based location auto-detection or manual PIN code override.
- Real-time delivery promise, store mapping, and polygon resolution.
- Direct Vertex API product retrieval with server-side discount sorting.
- Advanced filtering (min discount, price range, in-stock only, search query).
- Clean colored terminal table view, summary analytics, and JSON/CSV export.
=============================================================================
"""

import os
import sys
import json
import argparse
import time
import urllib.parse
from typing import Dict, List, Any, Optional, Tuple

# Ensure UTF-8 output encoding across Windows / Linux / macOS terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


# --- Configuration & Constants ---
JIOMART_BASE = "https://www.jiomart.com"
AUTH_BEARER = "Bearer Njg1OTQ1ZjQ2YzhjN2FlZTNmM2FmNjA1OlRwS3c3d0Q5aA=="
DEFAULT_PINCODE = "560045"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# ANSI Color Codes for Terminal
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BLUE = "\033[94m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"


# Enable ANSI escape processing on Windows if needed
if os.name == 'nt':
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Tuple[int, Any]:
    """Robust HTTP GET request using requests or urllib."""
    hdrs = headers.copy() if headers else {}
    if "User-Agent" not in hdrs and "user-agent" not in hdrs:
        hdrs["User-Agent"] = DEFAULT_USER_AGENT

    if HAS_REQUESTS:
        try:
            resp = requests.get(url, headers=hdrs, timeout=timeout)
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            return resp.status_code, data
        except Exception as e:
            return 0, str(e)
    else:
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = response.getcode()
                raw = response.read().decode('utf-8')
                try:
                    data = json.loads(raw)
                except Exception:
                    data = raw
                return status, data
        except urllib.error.HTTPError as e:
            try:
                data = json.loads(e.read().decode('utf-8'))
            except Exception:
                data = str(e)
            return e.code, data
        except Exception as e:
            return 0, str(e)


# --- Location Services ---
def detect_location_from_ip() -> Dict[str, Any]:
    """Auto-detects location (pincode, city, state, lat/long) via public IP geolocation APIs."""
    providers = [
        ("http://ip-api.com/json", lambda d: {
            "pincode": str(d.get("zip", "")).strip(),
            "city": d.get("city", ""),
            "state": d.get("regionName", ""),
            "country": d.get("country", "India"),
            "latitude": d.get("lat", 13.036),
            "longitude": d.get("lon", 77.6226),
            "source": "ip-api.com"
        }),
        ("https://freeipapi.com/api/json", lambda d: {
            "pincode": str(d.get("zipCode", "")).strip(),
            "city": d.get("cityName", ""),
            "state": d.get("regionName", ""),
            "country": d.get("countryName", "India"),
            "latitude": d.get("latitude", 13.036),
            "longitude": d.get("longitude", 77.6226),
            "source": "freeipapi.com"
        }),
        ("https://ipapi.co/json/", lambda d: {
            "pincode": str(d.get("postal", "")).strip(),
            "city": d.get("city", ""),
            "state": d.get("region", ""),
            "country": d.get("country_name", "India"),
            "latitude": d.get("latitude", 13.036),
            "longitude": d.get("longitude", 77.6226),
            "source": "ipapi.co"
        })
    ]

    for url, parser in providers:
        status, data = http_get(url, timeout=4)
        if status == 200 and isinstance(data, dict) and not data.get("error"):
            try:
                parsed = parser(data)
                if parsed.get("city") or parsed.get("pincode"):
                    return parsed
            except Exception:
                continue

    return {
        "pincode": DEFAULT_PINCODE,
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "India",
        "latitude": 13.036,
        "longitude": 77.6226,
        "source": "default_fallback"
    }


def resolve_jiomart_location(pincode: str) -> Optional[Dict[str, Any]]:
    """Resolves pincode coordinates, city, and state using JioMart logistics API."""
    url = f"{JIOMART_BASE}/api/service/application/logistics/v1.0/pincode/{pincode}"
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": AUTH_BEARER,
        "x-currency-code": "INR"
    }
    status, res = http_get(url, headers=headers, timeout=6)
    if status == 200 and isinstance(res, dict) and res.get("data"):
        data = res["data"][0]
        coords = data.get("lat_long", {}).get("coordinates", [77.6226, 13.036])
        lon, lat = coords[0], coords[1]
        city = "BENGALURU"
        state = "KARNATAKA"
        country = "INDIA"
        for parent in data.get("parents", []):
            stype = parent.get("sub_type")
            if stype == "city":
                city = parent.get("name")
            elif stype == "state":
                state = parent.get("name")
            elif stype == "country":
                country = parent.get("name")
        return {
            "pincode": pincode,
            "latitude": lat,
            "longitude": lon,
            "city": city,
            "state": state,
            "country": country,
            "raw": data
        }
    return None


def fetch_delivery_promise(loc_info: Dict[str, Any]) -> Dict[str, Any]:
    """Fetches delivery stores and quick-commerce polygon IDs for the given location."""
    url = f"{JIOMART_BASE}/api/service/application/logistics/v1.0/delivery-promise"
    headers = {
        "accept": "application/json, text/plain, */*",
        "authorization": AUTH_BEARER,
        "x-currency-code": "INR",
        "x-geolocation": json.dumps({
            "latitude": str(loc_info["latitude"]),
            "longitude": str(loc_info["longitude"])
        }),
        "x-location-detail": json.dumps({
            "country": loc_info.get("country", "INDIA"),
            "country_iso_code": "IN",
            "city": loc_info.get("city", "BENGALURU"),
            "pincode": loc_info["pincode"],
            "state": loc_info.get("state", "KARNATAKA")
        })
    }
    status, res = http_get(url, headers=headers, timeout=6)
    store_ids = []
    polygon_ids = []
    if status == 200 and isinstance(res, dict):
        store_ids = res.get("query_params", {}).get("store_ids", [])
        for item in res.get("items", []):
            for jp in item.get("journey_wise_promise", []):
                poly = jp.get("meta", {}).get("polygon_id")
                if poly and poly not in polygon_ids:
                    polygon_ids.append(poly)
    return {
        "store_ids": store_ids,
        "polygon_ids": polygon_ids,
        "raw": res if status == 200 else {}
    }


# --- Product Fetcher ---
class JioMartProductFetcher:
    def __init__(self, pincode: Optional[str] = None):
        self.pincode = pincode
        self.location_info: Dict[str, Any] = {}
        self.delivery_info: Dict[str, Any] = {}
        self._init_location()

    def _init_location(self):
        """Initializes location resolution."""
        if not self.pincode:
            print(f"{Colors.CYAN}🔍 Auto-detecting your location via IP...{Colors.RESET}", end=" ", flush=True)
            detected = detect_location_from_ip()
            detected_pin = detected.get("pincode", "")
            lat = detected.get("latitude", 0)
            lon = detected.get("longitude", 0)

            resolved = None

            # Strategy 1: Try to resolve coordinates directly using JioMart's delivery-promise
            # This gives us the nearest QC store list, which is more accurate than IP zip codes
            if lat and lon:
                dummy_loc = {
                    "pincode": detected_pin or DEFAULT_PINCODE,
                    "latitude": lat,
                    "longitude": lon,
                    "city": detected.get("city", ""),
                    "state": detected.get("state", ""),
                    "country": detected.get("country", "INDIA")
                }
                delivery = fetch_delivery_promise(dummy_loc)
                store_ids = delivery.get("store_ids", [])

                if store_ids:
                    # Stores found for these coordinates — use the IP-detected pincode if valid
                    pin_to_try = detected_pin if (len(detected_pin) == 6 and detected_pin.isdigit()) else DEFAULT_PINCODE
                    resolved = resolve_jiomart_location(pin_to_try)
                    if resolved:
                        self.delivery_info = delivery
                        self.pincode = pin_to_try
                        self.location_info = resolved
                        print(f"{Colors.GREEN}Done! ({resolved['city']}, {resolved['state']}, PIN: {self.pincode}){Colors.RESET}")
                        stores_count = len(store_ids)
                        print(f"{Colors.GREEN}✓ Active Quick Commerce Stores: {stores_count} | Polygons: {len(delivery.get('polygon_ids', []))}{Colors.RESET}")
                        return

            # Strategy 2: Try IP-detected pincode directly
            if len(detected_pin) == 6 and detected_pin.isdigit():
                resolved = resolve_jiomart_location(detected_pin)

            if resolved:
                self.pincode = detected_pin
                self.location_info = resolved
                print(f"\n{Colors.GREEN}Done! ({resolved['city']}, {resolved['state']}, PIN: {self.pincode}){Colors.RESET}")
                print(f"{Colors.YELLOW}ℹ️  IP-based location may not match your exact address.")
                print(f"   For precise Quick Commerce store routing, use: --pincode <your_pin>{Colors.RESET}")
            else:
                # IP could not give a serviceable pin — prompt user
                print(f"\n{Colors.YELLOW}⚠️  Could not auto-detect a serviceable JioMart location from your IP.")
                print(f"    IP-reported area: {detected.get('city', '?')}, PIN: {detected_pin or 'unknown'}")
                print(f"    Tip: Run with --pincode <your_6_digit_pin> for accurate results.")
                print(f"    Using default PIN {DEFAULT_PINCODE} (Bengaluru) as fallback.{Colors.RESET}")
                self.pincode = DEFAULT_PINCODE
                self.location_info = resolve_jiomart_location(DEFAULT_PINCODE) or {
                    "pincode": self.pincode, "latitude": 13.036, "longitude": 77.6226,
                    "city": "BENGALURU", "state": "KARNATAKA", "country": "INDIA"
                }
        else:
            print(f"{Colors.CYAN}📍 Resolving specified PIN: {self.pincode}...{Colors.RESET}", end=" ", flush=True)
            resolved = resolve_jiomart_location(self.pincode)
            if not resolved:
                print(f"\n{Colors.YELLOW}⚠️ PIN code {self.pincode} not found in JioMart logistics. Falling back to {DEFAULT_PINCODE}.{Colors.RESET}")
                self.pincode = DEFAULT_PINCODE
                resolved = resolve_jiomart_location(DEFAULT_PINCODE)
            else:
                print(f"{Colors.GREEN}Done! ({resolved['city']}, {resolved['state']}){Colors.RESET}")

            self.location_info = resolved or {
                "pincode": self.pincode,
                "latitude": 13.036,
                "longitude": 77.6226,
                "city": "BENGALURU",
                "state": "KARNATAKA",
                "country": "INDIA"
            }

        # Resolve delivery stores & polygons
        self.delivery_info = fetch_delivery_promise(self.location_info)
        stores_count = len(self.delivery_info.get("store_ids", []))
        print(f"{Colors.GREEN}✓ Active Quick Commerce Stores: {stores_count} | Polygons: {len(self.delivery_info.get('polygon_ids', []))}{Colors.RESET}")

    def fetch_products(
        self,
        department: str = "groceries",
        sort_on: str = "discount_dsc",
        limit: int = 50,
        page_start: int = 1,
        max_pages: Optional[int] = None,
        query: Optional[str] = None,
        category: Optional[str] = None,
        min_discount: Optional[float] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        in_stock_only: bool = False
    ) -> Dict[str, Any]:
        """Fetches products with pagination and filters applied."""
        results: List[Dict[str, Any]] = []
        page_size = min(50, limit if limit > 0 else 50)
        current_page = page_start
        total_available = 0
        next_cursor = None

        store_ids = self.delivery_info.get("store_ids", [])
        store_filter = "||".join(store_ids[:10]) if store_ids else ""

        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": AUTH_BEARER,
            "x-currency-code": "INR",
            "x-geolocation": json.dumps({
                "latitude": str(self.location_info["latitude"]),
                "longitude": str(self.location_info["longitude"]),
                "polygon_ids": self.delivery_info.get("polygon_ids", [])
            }),
            "x-location-detail": json.dumps({
                "country": self.location_info.get("country", "INDIA"),
                "country_iso_code": "IN",
                "city": self.location_info.get("city", "BENGALURU"),
                "pincode": self.location_info["pincode"],
                "state": self.location_info.get("state", "KARNATAKA")
            })
        }

        print(f"\n{Colors.BOLD}⚡ Fetching ad-free products sorted by discount ({department})...{Colors.RESET}")
        start_time = time.time()

        while True:
            # Build filter string
            f_parts = []
            if department and department.lower() != "all":
                f_parts.append(f"department:{department.lower()}")
            
            # If quick commerce stores are available for this location, include them
            if store_filter:
                f_parts.append("journey:quickcommerce")
                f_parts.append(f"store_ids:{store_filter}")

            if category:
                f_parts.append(f"l1_category:{category}")

            f_param = ":::".join(f_parts)

            params = {
                "f": f_param,
                "page_id": next_cursor if next_cursor else "*",
                "page_size": str(page_size),
                "sort_on": sort_on
            }
            if current_page > 1:
                params["page_no"] = str(current_page)
                params["page_type"] = "number"
            if query:
                params["q"] = query

            encoded_params = urllib.parse.urlencode(params)
            url = f"{JIOMART_BASE}/ext/vertex/application/api/v1.0/products?{encoded_params}"

            status, res = http_get(url, headers=headers, timeout=10)

            if status != 200 or not isinstance(res, dict):
                print(f"{Colors.RED}❌ Error fetching page {current_page}: HTTP {status}{Colors.RESET}")
                break

            page_info = res.get("page", {})
            total_available = page_info.get("item_total", total_available)
            next_cursor = page_info.get("next_id")
            items = res.get("items", [])

            if not items:
                break

            for it in items:
                parsed = self._parse_product(it)
                if parsed:
                    # Apply local filters
                    if min_discount is not None and parsed["discount_pct"] < min_discount:
                        continue
                    if max_price is not None and parsed["effective_price"] > max_price:
                        continue
                    if min_price is not None and parsed["effective_price"] < min_price:
                        continue
                    if in_stock_only and not parsed["in_stock"]:
                        continue

                    results.append(parsed)
                    if limit and len(results) >= limit:
                        break

            if limit and len(results) >= limit:
                break

            if not page_info.get("has_next", False):
                break

            if max_pages and current_page >= max_pages:
                break

            current_page += 1

        elapsed = time.time() - start_time
        return {
            "total_available": total_available,
            "fetched_count": len(results),
            "elapsed_seconds": round(elapsed, 2),
            "products": results
        }

    def _parse_product(self, it: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extracts and normalizes product information."""
        try:
            name = it.get("name", "Unknown Product")
            brand = it.get("brand", {}).get("name") if isinstance(it.get("brand"), dict) else it.get("brand_name", "")
            if not brand:
                brand = "JioMart"

            price_obj = it.get("price", {})
            effective_price = price_obj.get("effective", {}).get("max")
            if effective_price is None:
                effective_price = price_obj.get("marked", {}).get("max", 0.0)
            marked_price = price_obj.get("marked", {}).get("max", effective_price)

            # Calculate accurate discount percentage
            if marked_price and marked_price > 0 and effective_price is not None:
                calc_discount = round(((marked_price - effective_price) / marked_price) * 100, 1)
            else:
                calc_discount = 0.0

            savings = round(marked_price - effective_price, 2) if marked_price and effective_price is not None else 0.0

            slug = it.get("slug", "")
            product_url = f"{JIOMART_BASE}/product/{slug}" if slug else ""

            # Check stock status:
            # - `sellable` must be True (product is purchasable)
            # - `instock_variants` with non-empty `sizes` list = actually in stock
            # - `in_stock_variant` field is unreliable (always False in API response); ignore it
            sellable = it.get("sellable", True)
            instock_variants = it.get("instock_variants")
            has_instock_sizes = (
                isinstance(instock_variants, dict) and
                bool(instock_variants.get("sizes"))
            )
            in_stock = sellable and has_instock_sizes

            # Net quantity
            qty_val = it.get("net-quantity-value") or it.get("net_quantity") or ""
            qty_unit = it.get("net-quantity-unit") or ""
            quantity_str = f"{qty_val} {qty_unit}".strip() if qty_val else ""

            # Ratings
            rating = it.get("rating", {}).get("average") if isinstance(it.get("rating"), dict) else None

            # Categories
            categories = []
            for cat in it.get("categories", []):
                if isinstance(cat, dict) and cat.get("name"):
                    categories.append(cat["name"])

            return {
                "uid": it.get("uid"),
                "name": name,
                "brand": brand,
                "effective_price": float(effective_price) if effective_price is not None else 0.0,
                "mrp": float(marked_price) if marked_price is not None else 0.0,
                "discount_pct": float(calc_discount),
                "savings": float(savings),
                "in_stock": in_stock,
                "quantity": quantity_str,
                "rating": rating,
                "categories": categories,
                "url": product_url
            }
        except Exception:
            return None


# --- Presentation & Formatting ---
def display_results_table(data: Dict[str, Any], show_links: bool = True):
    """Renders a clean, aesthetic colored table in the console."""
    products = data.get("products", [])
    total_avail = data.get("total_available", 0)
    elapsed = data.get("elapsed_seconds", 0)

    if not products:
        print(f"\n{Colors.YELLOW}No products matched your criteria.{Colors.RESET}\n")
        return

    print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Found {len(products)} deals (Total catalog: {total_avail:,} items) in {elapsed}s{Colors.RESET}\n")

    # Column widths
    col_rank = 4
    col_brand = 15
    col_name = 42
    col_price = 10
    col_mrp = 10
    col_disc = 12
    col_save = 10

    # Header
    hdr = (
        f"{'#':<{col_rank}} "
        f"{'Brand':<{col_brand}} "
        f"{'Product Name':<{col_name}} "
        f"{'Price (₹)':>{col_price}} "
        f"{'MRP (₹)':>{col_mrp}} "
        f"{'Discount':>{col_disc}} "
        f"{'Savings':>{col_save}}"
    )
    separator = "─" * len(hdr)

    print(f"{Colors.BOLD}{Colors.CYAN}{hdr}{Colors.RESET}")
    print(f"{Colors.DIM}{separator}{Colors.RESET}")

    for idx, p in enumerate(products, 1):
        brand_trunc = (p['brand'][:col_brand-2] + '..') if len(p['brand']) > col_brand else p['brand']
        name_trunc = (p['name'][:col_name-3] + '...') if len(p['name']) > col_name else p['name']
        
        disc_val = p['discount_pct']
        if disc_val >= 60:
            disc_str = f"{Colors.GREEN}{Colors.BOLD}{disc_val:.1f}% OFF{Colors.RESET}"
        elif disc_val >= 40:
            disc_str = f"{Colors.YELLOW}{Colors.BOLD}{disc_val:.1f}% OFF{Colors.RESET}"
        elif disc_val > 0:
            disc_str = f"{disc_val:.1f}% OFF"
        else:
            disc_str = "0%"

        stock_badge = "" if p["in_stock"] else f" {Colors.RED}[Out of Stock]{Colors.RESET}"

        row_str = (
            f"{idx:<{col_rank}} "
            f"{Colors.MAGENTA}{brand_trunc:<{col_brand}}{Colors.RESET} "
            f"{name_trunc:<{col_name}} "
            f"{Colors.BOLD}₹{p['effective_price']:>{col_price-2}.2f}{Colors.RESET} "
            f"{Colors.DIM}₹{p['mrp']:>{col_mrp-2}.2f}{Colors.RESET} "
            f"{disc_str:>{col_disc}} "
            f"{Colors.GREEN}₹{p['savings']:>{col_save-2}.2f}{Colors.RESET}"
            f"{stock_badge}"
        )
        print(row_str)

        if show_links and p.get("url"):
            print(f"     {Colors.DIM}🔗 {p['url']}{Colors.RESET}")

    print(f"{Colors.DIM}{separator}{Colors.RESET}")

    # Summary Statistics
    discounts = [p["discount_pct"] for p in products if p["discount_pct"] > 0]
    savings_list = [p["savings"] for p in products]
    if discounts:
        max_disc = max(discounts)
        avg_disc = sum(discounts) / len(discounts)
        total_savings = sum(savings_list)
        print(f"\n{Colors.BOLD}📊 Deals Summary:{Colors.RESET}")
        print(f"  • {Colors.CYAN}Top Discount:{Colors.RESET} {Colors.GREEN}{Colors.BOLD}{max_disc:.1f}% OFF{Colors.RESET}")
        print(f"  • {Colors.CYAN}Average Discount:{Colors.RESET} {avg_disc:.1f}% OFF")
        print(f"  • {Colors.CYAN}Total Potential Savings:{Colors.RESET} ₹{total_savings:,.2f}")
        print(f"  • {Colors.CYAN}Ad Networks Blocked:{Colors.RESET} 100% (Pure Vertex API data)")


def export_csv(products: List[Dict[str, Any]], filename: str):
    """Exports results to a CSV file."""
    import csv
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Item UID", "Brand", "Product Name", "Quantity",
            "Effective Price (INR)", "MRP (INR)", "Discount (%)",
            "Savings (INR)", "In Stock", "Rating", "Categories", "Product URL"
        ])
        for p in products:
            writer.writerow([
                p.get("uid", ""),
                p.get("brand", ""),
                p.get("name", ""),
                p.get("quantity", ""),
                p.get("effective_price", 0.0),
                p.get("mrp", 0.0),
                p.get("discount_pct", 0.0),
                p.get("savings", 0.0),
                "Yes" if p.get("in_stock") else "No",
                p.get("rating") or "",
                " > ".join(p.get("categories", [])),
                p.get("url", "")
            ])
    print(f"\n{Colors.GREEN}✓ Successfully exported {len(products)} items to CSV: {filename}{Colors.RESET}")


def export_json(data: Dict[str, Any], filename: str):
    """Exports results to a JSON file."""
    with open(filename, mode='w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n{Colors.GREEN}✓ Successfully exported to JSON: {filename}{Colors.RESET}")


# --- Main Entry Point ---
def main():
    parser = argparse.ArgumentParser(
        description="⚡ JioMart Fast Ad-Free Discount Item Fetcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python jiomart_fetcher.py
  python jiomart_fetcher.py --pincode 560045 --min-discount 60
  python jiomart_fetcher.py --dept electronics --limit 20
  python jiomart_fetcher.py --query "dry fruits" --min-discount 40 --export csv
  python jiomart_fetcher.py --max-price 200 --min-discount 50 --in-stock
        """
    )

    parser.add_argument("-p", "--pincode", type=str, help="6-digit Indian PIN code (default: auto-detected via IP)")
    parser.add_argument("-d", "--dept", type=str, default="groceries", choices=["groceries", "electronics", "fashion", "beauty", "home", "all"], help="Department to browse (default: groceries)")
    parser.add_argument("-q", "--query", type=str, help="Search keyword (e.g. 'atta', 'almonds', 'headphones')")
    parser.add_argument("-c", "--category", type=str, help="L1 category slug (e.g. 'cooking-essentials', 'fresh-l1')")
    parser.add_argument("-s", "--sort", type=str, default="discount_dsc", choices=["discount_dsc", "price_asc", "price_dsc", "popularity_dsc"], help="Sort order (default: discount_dsc)")
    parser.add_argument("-l", "--limit", type=int, default=50, help="Maximum number of items to display (default: 50)")
    parser.add_argument("--pages", type=int, default=3, help="Max API pages to traverse (default: 3)")
    parser.add_argument("--min-discount", type=float, help="Filter items with minimum discount percentage (e.g. 50)")
    parser.add_argument("--max-price", type=float, help="Filter items with price <= max_price")
    parser.add_argument("--min-price", type=float, help="Filter items with price >= min_price")
    parser.add_argument("--in-stock", action="store_true", help="Only show in-stock items")
    parser.add_argument("--no-links", action="store_true", help="Hide product URLs in table output")
    parser.add_argument("--export", choices=["csv", "json"], help="Export results to file ('csv' or 'json')")
    parser.add_argument("--output", type=str, help="Custom export output file path")

    args = parser.parse_args()

    # Print banner
    print(f"\n{Colors.BOLD}{Colors.BG_BLUE}{Colors.WHITE}  JioMart Fast Ad-Free Discount Fetcher  {Colors.RESET}\n")

    fetcher = JioMartProductFetcher(pincode=args.pincode)

    result = fetcher.fetch_products(
        department=args.dept,
        sort_on=args.sort,
        limit=args.limit,
        max_pages=args.pages,
        query=args.query,
        category=args.category,
        min_discount=args.min_discount,
        max_price=args.max_price,
        min_price=args.min_price,
        in_stock_only=args.in_stock
    )

    display_results_table(result, show_links=not args.no_links)

    # Handle Exports
    if args.export == "csv" or (args.output and args.output.endswith(".csv")):
        outfile = args.output or f"jiomart_deals_{args.dept}_{int(time.time())}.csv"
        export_csv(result.get("products", []), outfile)
    elif args.export == "json" or (args.output and args.output.endswith(".json")):
        outfile = args.output or f"jiomart_deals_{args.dept}_{int(time.time())}.json"
        export_json(result, outfile)


if __name__ == "__main__":
    main()
