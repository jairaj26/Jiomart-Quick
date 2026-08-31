# ⚡ JioMart Fast Ad-Free Deals & Interactive Telegram Bot

A high-performance, ad-free JioMart deal engine and interactive Telegram Bot. It queries JioMart's internal Vertex APIs directly, automatically resolves Quick Commerce delivery routing in real-time, supports **dynamic per-user location onboarding**, **clean compact deal formatting**, **live search**, and a **smart deal-diffing engine**.

---

## 🌟 Key Features

1. **📱 Interactive Multi-User Bot**:
   - Any user can start the bot (`/start`) and enter their 6-digit PIN code (e.g. `560045` or `/pincode 560045`).
   - All deals are personalized to their local store delivery routing.

2. **🧼 Clean, Compact Deal Formatting**:
   - Clean, uncluttered layout with direct **"Click here"** links.
   - Shows **only the `⏩ Next 15 Deals (/more)` button** below deals to keep messages tidy.

3. **📂 Instant Category Browsing (`/categories`)**:
   - Tap `/categories` to browse by dedicated categories:
     - 🌾 **Atta, Rice, Dal & Oil** *(Cooking oils, flours, grains, dals, spices, sugar, salt)*
     - 🥨 **Dry Fruits, Snacks & Dairy** *(Almonds, cashews, dates, biscuits, chocolates, tea/coffee)*
     - 🧼 **Kitchen, Cookware & Cleaning** *(Choppers, bottles, cookware, utensils, cleaners)*
     - 🧴 **Personal Care, Bath & Beauty** *(Soaps, shampoos, face wash, oral care, skincare)*
     - 🎧 **Electronics & Gadgets** *(Headphones, watches, small appliances, cables)*
     - 🎁 **Pooja, Seasonal & General** *(Festive specials, Rakhis, pooja needs)*

4. **⏩ `/more` Pagination & Keyword Search**:
   - Tap **"⏩ Next 15 Deals"** or type `/more` to browse pages 6–10, 11–15, etc.
   - Search any keyword in real-time: `/search ghee`, `/search almond`, `/search chopper`.

5. **🧠 Smart Deal Diffing (Zero Stale Spam)**:
   - Filters out permanent/fake 85% discount items.
   - **Two-Tier Alert Cycle**:
     - **12:05 AM IST (Daily Master Digest)**: Resets daily memory and broadcasts the full top categorized deals of the day.
     - **6 AM, 12 PM, 4 PM, 8 PM IST (Flash Alerts)**: Only sends alerts for fresh price drops, new items, or restocks today.

---

## 📱 Bot Commands & Shortcuts

| Command | Action |
| :--- | :--- |
| `/deals` | Top deals for your saved location (with `/more` button) |
| `/more` | Browse next 15 deals (Pages 6–10, 11–15...) |
| `/categories` | Show interactive category buttons |
| `/atta`, `/rice`, `/oil` | Filter for Atta, Rice, Dal & Oil deals |
| `/snacks`, `/dryfruits` | Filter for Dry Fruits, Snacks & Dairy deals |
| `/kitchen`, `/home` | Filter for Kitchen, Cookware & Cleaning deals |
| `/beauty`, `/personal` | Filter for Personal Care & Beauty deals |
| `/electronics` | Filter for Electronics & Gadgets |
| `/search <keyword>` | Search any product keyword (e.g. `/search almond`) |
| `/pincode <pin>` | Change delivery location (e.g. `/pincode 560045`) |
| `/mindiscount <pct>` | Filter by minimum discount (e.g. `/mindiscount 70`) |
| `/settings` | View current location, discount filter, and alert status |
| `/pause` / `/resume` | Mute or unmute scheduled alert notifications |

---

## 🚀 24/7 Cloud Deployment (Render + cron-job.org)

1. **Deploy on Render**:
   - Connect your GitHub repository as a **Free Web Service**.
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python bot.py`
   - Environment Variables: `TELEGRAM_BOT_TOKEN = <your_token>`

2. **Keep-Alive with cron-job.org**:
   - Create a free job on [cron-job.org](https://cron-job.org) that pings your Render URL (e.g. `https://your-app.onrender.com`) every **10 minutes**.
   - This ensures **zero cold starts** and guarantees the 5 daily broadcast intervals run accurately 24/7.

---

## 📄 License
MIT License. Free for personal and non-commercial use.
