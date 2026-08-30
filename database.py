"""
=============================================================================
JioMart Bot Database Layer (SQLite)
=============================================================================
Manages user profiles, preferences, navigation pagination states,
product price history, and daily alert state.
=============================================================================
"""

import os
import sqlite3
import datetime
from typing import Dict, List, Any, Optional, Tuple

DB_PATH = os.environ.get("DB_PATH", "jiomart_bot.db")


def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with dictionary row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes the database schema and performs safe migrations."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                pincode TEXT,
                city TEXT,
                state TEXT,
                min_discount REAL DEFAULT 60.0,
                deal_limit INTEGER DEFAULT 15,
                is_active BOOLEAN DEFAULT 1,
                nav_page INTEGER DEFAULT 1,
                nav_category TEXT DEFAULT '',
                nav_query TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Product Price History (for deal diffing & deduplication)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_history (
                product_uid TEXT,
                pincode TEXT,
                name TEXT,
                brand TEXT,
                category_bucket TEXT,
                effective_price REAL,
                mrp REAL,
                discount_pct REAL,
                savings REAL,
                in_stock BOOLEAN,
                url TEXT,
                quantity TEXT,
                last_alert_date TEXT,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (product_uid, pincode)
            )
        """)

        # Safe migrations for existing databases
        migrations = [
            "ALTER TABLE product_history ADD COLUMN last_alert_date TEXT",
            "ALTER TABLE product_history ADD COLUMN category_bucket TEXT",
            "ALTER TABLE users ADD COLUMN nav_page INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN nav_category TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN nav_query TEXT DEFAULT ''"
        ]
        for m in migrations:
            try:
                cursor.execute(m)
            except sqlite3.OperationalError:
                pass

        # 3. Alert Logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_uid TEXT,
                alert_type TEXT,
                sent_price REAL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


# --- User Management Operations ---

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves user profile by Telegram user_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def save_or_update_user(
    user_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    pincode: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    min_discount: Optional[float] = None,
    is_active: Optional[bool] = None
) -> Dict[str, Any]:
    """Creates or updates a user profile."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        existing = get_user(user_id)
        
        if existing:
            new_username = username if username is not None else existing.get("username")
            new_fname = first_name if first_name is not None else existing.get("first_name")
            new_pincode = pincode if pincode is not None else existing.get("pincode")
            new_city = city if city is not None else existing.get("city")
            new_state = state if state is not None else existing.get("state")
            new_disc = min_discount if min_discount is not None else existing.get("min_discount", 60.0)
            new_active = is_active if is_active is not None else existing.get("is_active", 1)

            cursor.execute("""
                UPDATE users
                SET username = ?, first_name = ?, pincode = ?, city = ?, state = ?,
                    min_discount = ?, is_active = ?, last_active_at = ?
                WHERE user_id = ?
            """, (new_username, new_fname, new_pincode, new_city, new_state, new_disc, new_active, now, user_id))
        else:
            cursor.execute("""
                INSERT INTO users (user_id, username, first_name, pincode, city, state, min_discount, is_active, created_at, last_active_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                username or "",
                first_name or "",
                pincode or "",
                city or "",
                state or "",
                min_discount or 60.0,
                1 if is_active is None or is_active else 0,
                now,
                now
            ))
        conn.commit()
    return get_user(user_id) or {}


def update_user_pincode(user_id: int, pincode: str, city: str, state: str) -> None:
    """Updates user pincode and resolved city/state."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET pincode = ?, city = ?, state = ?, last_active_at = ?
            WHERE user_id = ?
        """, (pincode, city, state, now, user_id))
        conn.commit()


def set_user_min_discount(user_id: int, min_discount: float) -> None:
    """Updates user minimum discount preference."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET min_discount = ?, last_active_at = ?
            WHERE user_id = ?
        """, (min_discount, now, user_id))
        conn.commit()


def set_user_nav_state(
    user_id: int,
    page: int = 1,
    category: Optional[str] = None,
    query: Optional[str] = None
) -> None:
    """Updates the user's pagination, active category, or active search query."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET nav_page = ?, nav_category = COALESCE(?, nav_category),
                nav_query = COALESCE(?, nav_query), last_active_at = ?
            WHERE user_id = ?
        """, (page, category, query, now, user_id))
        conn.commit()


def get_user_nav_state(user_id: int) -> Tuple[int, str, str]:
    """Returns (nav_page, nav_category, nav_query) for the user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nav_page, nav_category, nav_query FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return (
                row["nav_page"] or 1,
                row["nav_category"] or "",
                row["nav_query"] or ""
            )
        return (1, "", "")


def toggle_user_active(user_id: int, is_active: bool) -> None:
    """Enables or pauses scheduled deal broadcasts for a user."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET is_active = ?, last_active_at = ?
            WHERE user_id = ?
        """, (1 if is_active else 0, now, user_id))
        conn.commit()


def get_all_active_users() -> List[Dict[str, Any]]:
    """Returns all active users with a valid pincode configured."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users
            WHERE is_active = 1 AND pincode IS NOT NULL AND pincode != ''
        """)
        return [dict(r) for r in cursor.fetchall()]


def get_unique_active_pincodes() -> List[str]:
    """Returns a distinct list of pincodes for all active users."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT pincode FROM users
            WHERE is_active = 1 AND pincode IS NOT NULL AND pincode != ''
        """)
        return [r["pincode"] for r in cursor.fetchall()]


def get_users_by_pincode(pincode: str) -> List[Dict[str, Any]]:
    """Returns all active users registered to a specific pincode."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users
            WHERE is_active = 1 AND pincode = ?
        """, (pincode,))
        return [dict(r) for r in cursor.fetchall()]


# --- Product History & Deal Diffing Operations ---

def get_product_history(product_uid: str, pincode: str) -> Optional[Dict[str, Any]]:
    """Gets historical price/discount record for a specific product and pincode."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM product_history
            WHERE product_uid = ? AND pincode = ?
        """, (product_uid, pincode))
        row = cursor.fetchone()
        return dict(row) if row else None


def upsert_product_history(
    product: Dict[str, Any],
    pincode: str,
    last_alert_date: Optional[str] = None
) -> None:
    """Inserts or updates product price history record."""
    uid = product.get("uid") or product.get("url") or product.get("name")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    category_bucket = product.get("category_bucket") or ""
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO product_history (
                product_uid, pincode, name, brand, category_bucket, effective_price, mrp,
                discount_pct, savings, in_stock, url, quantity, last_alert_date, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_uid, pincode) DO UPDATE SET
                name = excluded.name,
                brand = excluded.brand,
                category_bucket = CASE WHEN excluded.category_bucket != '' THEN excluded.category_bucket ELSE product_history.category_bucket END,
                effective_price = excluded.effective_price,
                mrp = excluded.mrp,
                discount_pct = excluded.discount_pct,
                savings = excluded.savings,
                in_stock = excluded.in_stock,
                url = excluded.url,
                quantity = excluded.quantity,
                last_alert_date = COALESCE(excluded.last_alert_date, product_history.last_alert_date),
                last_seen_at = excluded.last_seen_at
        """, (
            uid,
            pincode,
            product.get("name", ""),
            product.get("brand", ""),
            category_bucket,
            product.get("effective_price", 0.0),
            product.get("mrp", 0.0),
            product.get("discount_pct", 0.0),
            product.get("savings", 0.0),
            1 if product.get("in_stock", True) else 0,
            product.get("url", ""),
            product.get("quantity", ""),
            last_alert_date,
            now,
            now
        ))
        conn.commit()


def mark_products_alerted(product_uids: List[str], pincode: str, alert_date: str) -> None:
    """Updates the last_alert_date for a batch of products in a pincode."""
    if not product_uids:
        return
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            UPDATE product_history
            SET last_alert_date = ?
            WHERE product_uid = ? AND pincode = ?
        """, [(alert_date, uid, pincode) for uid in product_uids])
        conn.commit()


# Initialize schema automatically when module is loaded
init_db()
