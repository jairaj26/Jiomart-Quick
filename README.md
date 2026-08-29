# ⚡ JioMart Fast Ad-Free Deals & Interactive Multi-User Telegram Bot

A high-performance, ad-free JioMart deal engine and interactive Telegram Bot. It queries JioMart's internal Vertex APIs directly, automatically resolves Quick Commerce delivery routing in real-time, supports **dynamic per-user location onboarding**, and uses a **smart deal-diffing engine** to eliminate permanent stale discounts.

---

## 🌟 Key Features

1. **Dynamic Multi-User Location Onboarding**:
   - Centralized bot: Any user can `/start` the bot and send their own 6-digit delivery PIN code (e.g. `560045` or `/pincode 400001`).
   - Each user gets deals tailored **100% to their specific location**, without needing to create their own bot or manage API tokens.

2. **Smart Deal Diffing & Deduplication (Zero Stale Spam)**:
   - Tracks product price and discount history in SQLite (`jiomart_bot.db`).
   - Automatically filters out permanent/fake 85% discount items (like generic chopping boards).
   - Only triggers automated alerts when:
     - 🆕 **New Deal**: A product crosses the discount threshold for the first time.
     - 📉 **Price Drop**: The price drops further than previously seen (e.g. ₹99 → ₹69).
     - 💥 **Discount Increased**: Significant discount percentage jump.
     - 🔄 **Back in Stock**: High-discount item restocked.

3. **5x Daily Scheduled Broadcasts (IST)**:
   - Runs automatically at: **12:05 AM**, **6:00 AM**, **12:00 PM**, **4:00 PM**, and **8:00 PM** IST.
   - **Unique Pincode Optimization**: Fetches JioMart's API **once per unique pincode**, calculates diffs, and broadcasts to all users subscribed to that location.

4. **On-Demand Interactive Commands**:
   - `/deals` — Fetch current top deals for your saved PIN code immediately.
   - `/deals <pincode>` — Quick check deals for any other Indian PIN code.
   - `/mindiscount <pct>` — Set custom discount filter (e.g. `/mindiscount 70`).
   - `/settings` — View your active location and preferences.
   - `/pause` / `/resume` — Mute or unmute scheduled alert notifications.

---

## 🚀 Quick Setup & Deployment

### Step 1: Create Your Telegram Bot (1 minute)
1. Open Telegram and search for **`@BotFather`**.
2. Send `/newbot` and follow prompts to pick a name and username for your bot.
3. Copy the **HTTP API Token** provided by BotFather (e.g. `7123456789:AAH...`).

### Step 2: Set Token in `.env`
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set your `TELEGRAM_BOT_TOKEN`:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
   ```

### Step 3: Run the Interactive Bot
```bash
python bot.py
```
Your bot is now online! Open your bot on Telegram, send `/start`, and reply with your 6-digit delivery PIN code.

---

## 💻 24/7 Cloud Hosting (100% Free)

You can host `bot.py` 24/7 on free container services like **Render**, **Fly.io**, **Railway**, or **Koyeb**:

1. **Push your code to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "JioMart Interactive Bot"
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git push -u origin main
   ```
2. **Deploy on Render (or any free platform)**:
   - Create a new **Background Worker** or **Web Service** connected to your repo.
   - Set Build Command: `pip install -r requirements.txt`
   - Set Start Command: `python bot.py`
   - Add Environment Variable: `TELEGRAM_BOT_TOKEN` = `<your_bot_token>`

---

## 📱 Bot Commands Reference

| Command | Example | Description |
| :--- | :--- | :--- |
| `/start` | `/start` | Greets user and prompts for 6-digit delivery PIN code |
| `560045` or `/pincode 560045` | `/pincode 560045` | Validates and saves delivery location |
| `/deals` | `/deals` | Instantly fetches current top deals for your saved PIN |
| `/deals <pin>` | `/deals 400001` | On-demand deals lookup for any other PIN |
| `/mindiscount <pct>` | `/mindiscount 70` | Filter deals with minimum discount percentage |
| `/settings` | `/settings` | Displays your active PIN, city, discount threshold |
| `/pause` | `/pause` | Mutes automated 5x daily broadcasts |
| `/resume` | `/resume` | Resumes automated 5x daily broadcasts |
| `/help` | `/help` | Detailed command list and guidance |

---

## 🛠️ Standalone Scripts

- **`jiomart_fetcher.py`**: Pure CLI discount fetcher with rich color table output and CSV/JSON export.
- **`telegram_notifier.py`**: Single-run notifier script suitable for GitHub Actions cron or manual dry-run.
- **`bot.py`**: Interactive multi-user Telegram bot + 5x daily diffing scheduler.
- **`database.py`**: SQLite database layer for user profiles and product price history.
- **`deal_differ.py`**: Smart deal diffing engine.

---

## 📄 License
MIT License. Free for personal and non-commercial use.
