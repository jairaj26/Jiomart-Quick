# ⚡ JioMart Fast Ad-Free Deals & Daily Telegram Broadcaster

A high-performance, ad-free tool that queries JioMart's internal Vertex APIs directly. It fetches and sorts products by discount, resolves Quick Commerce delivery routing in real-time, and can **automatically broadcast top deals to Telegram every day at 12:05 AM IST via GitHub Actions (100% Free)**.

---

## 🌟 Highlights

- **Pure Ad-Free Speed**: Bypasses heavy ad networks (`ads.jiomartjcp.com`), analytics scripts (`stelios`, `cctz0.de`), and tracking bloat for instant data retrieval.
- **Daily Automated Telegram Alerts**: Runs every midnight (12:05 AM IST) in the cloud via GitHub Actions and sends the top 20 discount deals to your personal Telegram or group/channel.
- **Zero Hardcoded Data**: Fully configurable via environment variables, `.env` file, GitHub Secrets, or CLI arguments.
- **Real-Time Logistics**: Automatically resolves Quick Commerce stores, polygon boundaries, and delivery status for any Indian PIN code.
- **Accurate Stock & Pricing**: Real in-stock verification, actual MRP vs. discounted price calculations, and direct clickable product links (`https://www.jiomart.com/product/{slug}`).
- **Rich Terminal UI & Exporting**: Colorized console table with savings summary, plus JSON and CSV exports.

---

## 🚀 Quick Setup: Daily Telegram Alerts via GitHub Actions

You can run this completely free in the cloud without leaving your computer on!

### Step 1: Create a Free Telegram Bot (1 minute)
1. Open Telegram and search for **`@BotFather`**.
2. Send `/newbot` and follow the prompts to choose a name and username for your bot.
3. BotFather will give you a **HTTP API Token** (e.g. `7123456789:AAH...`). Copy this token.

### Step 2: Get Your Telegram Chat ID
- **For Personal Alerts**: Search for **`@userinfobot`** or **`@raw_data_bot`** on Telegram and click Start. It will reply with your `id` (e.g. `123456789`).
- **For Channels or Groups**: Add your new bot as an Admin to your channel/group. Use the channel username (e.g. `@my_deals_channel`) or group chat ID.

### Step 3: Configure GitHub Repository Secrets
1. Push / Fork this repository on GitHub.
2. Go to your repository **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret** and add the following:
   - `TELEGRAM_BOT_TOKEN`: Paste the token from BotFather.
   - `TELEGRAM_CHAT_ID`: Paste your Chat ID.
   - `JIOMART_PINCODE`: Your 6-digit delivery PIN code (e.g. `560045`).

### Step 4: Enable & Test the GitHub Action
1. Go to the **Actions** tab in your repository.
2. Click **JioMart Daily Deals Telegram Alert** on the left.
3. Click **Run workflow** to test it instantly!
4. The workflow will automatically trigger every night at **12:05 AM IST** (`18:35 UTC`).

---

## 💻 Local Usage

### Requirements
- Python 3.8+
- `requests` library (`pip install -r requirements.txt`)

### 1. Telegram Notifier (`telegram_notifier.py`)

#### Local Dry-Run Preview (Test message format without sending):
```bash
python telegram_notifier.py --pincode 560045 --min-discount 60 --limit 10 --dry-run
```

#### Send Telegram Message using CLI flags:
```bash
python telegram_notifier.py --token <BOT_TOKEN> --chat-id <CHAT_ID> --pincode 560045 --min-discount 60 --limit 20
```

#### Send Telegram Message using `.env` file:
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Fill in your `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `JIOMART_PINCODE`.
3. Simply run:
   ```bash
   python telegram_notifier.py
   ```

---

### 2. Interactive Terminal Fetcher (`jiomart_fetcher.py`)

#### Basic Run with PIN Code & Minimum Discount:
```bash
python jiomart_fetcher.py --pincode 560045 --min-discount 60 --limit 20
```

#### Search for Specific Items (e.g. "atta", "almonds", "ghee"):
```bash
python jiomart_fetcher.py --pincode 560045 --query "atta" --limit 10
```

#### Browse Other Departments (Electronics, Fashion, Beauty):
```bash
python jiomart_fetcher.py --dept electronics --min-discount 50 --limit 15
```

#### Export Results to CSV or JSON:
```bash
# Export to CSV
python jiomart_fetcher.py --pincode 560045 --export csv --output top_deals.csv

# Export to JSON
python jiomart_fetcher.py --pincode 560045 --export json --output top_deals.json
```

---

## ⚙️ Configuration Reference

| Environment Variable | CLI Argument | Default | Description |
| :--- | :--- | :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | `--token` | None | Telegram Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | `--chat-id` | None | Target Telegram Chat ID or `@channel_name` |
| `JIOMART_PINCODE` | `--pincode`, `-p` | Auto-detect | 6-digit Indian delivery PIN code |
| `DEPARTMENT` | `--dept`, `-d` | `groceries` | Department: `groceries`, `electronics`, `fashion`, `beauty`, `home` |
| `MIN_DISCOUNT` | `--min-discount` | `60` | Minimum discount percentage threshold |
| `DEAL_LIMIT` | `--limit`, `-l` | `20` | Maximum number of deals to fetch/broadcast |
| `IN_STOCK_ONLY` | `--in-stock` | `True` | Filter for in-stock and sellable items |

---

## 📄 License
MIT License. Free for personal, non-commercial use.
