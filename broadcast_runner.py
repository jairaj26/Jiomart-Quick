"""
Standalone Multi-User Broadcast Runner for Cloud Schedulers (GitHub Actions / Cron).
Executes scheduled deal broadcasts across all active users in the database.
"""
import os
import sys
import datetime

# Ensure UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db
from bot import run_scheduled_broadcast, load_env

def main():
    load_env()
    init_db()

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    hour = ist_now.hour

    # If it's around 12:00 AM - 12:30 AM IST, treat as Daily Master Digest (reset daily tracker)
    is_master = (hour == 0)

    print(f"⏰ Triggering Multi-User Scheduled Broadcast (IST Time: {ist_now.strftime('%I:%M %p')}, Master Digest: {is_master})...")
    run_scheduled_broadcast(is_master_digest=is_master)

if __name__ == "__main__":
    main()
