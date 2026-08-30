# ⚡ JioMart Fast Ad-Free Deals & Interactive Telegram Bot

A high-performance, ad-free JioMart deal engine and interactive Telegram Bot. It queries JioMart's internal Vertex APIs directly, automatically resolves Quick Commerce delivery routing in real-time, supports **dynamic per-user location onboarding**, **clickable category buttons**, **live search**, and a **smart deal-diffing engine**.

---

## 🌟 Key Features

1. **🔘 Clickable Category Buttons (Inline Keyboard)**:
   - Users don't need to type commands—tap buttons directly under the message to browse by category!
   - 🌾 **Atta, Rice, Dal & Oil** *(Cooking oils, flours, grains, dals, spices, sugar, salt)*
   - 🥨 **Dry Fruits, Snacks & Dairy** *(Almonds, cashews, dates, biscuits, chocolates, tea/coffee)*
   - 🧼 **Kitchen, Cookware & Cleaning** *(Choppers, bottles, cookware, utensils, cleaners)*
   - 🧴 **Personal Care, Bath & Beauty** *(Soaps, shampoos, face wash, oral care, skincare)*
   - 🎧 **Electronics & Gadgets** *(Headphones, watches, small appliances, cables)*
   - 🎁 **Pooja, Seasonal & General** *(Festive specials, Rakhis, pooja needs)*

2. **⏩ `/more` Pagination & Keyword Search**:
   - Tap **"⏩ Next 15 Deals"** or type `/more` to traverse pages 6–10, 11–15, etc.
   - Search any keyword in real-time: `/search ghee`, `/search almond`, `/search chopper`.

3. **🧠 Smart Deal Diffing (Zero Stale Spam)**:
   - Eliminates permanent/fake 85% discount items.
   - **Two-Tier Alert Cycle**:
     - **12:05 AM IST (Daily Master Digest)**: Resets daily memory and broadcasts the full top categorized deals of the day.
     - **6 AM, 12 PM, 4 PM, 8 PM IST (Flash Alerts)**: Only sends alerts for fresh price drops, new items, or restocks today.

4. **📍 Dynamic Multi-User Pincode Support**:
   - Any user can send `/start` and enter their 6-digit delivery PIN code (e.g. `560045` or `/pincode 400001`).
   - Deals are 100% personalized to their local store delivery routing.

---

## 📱 Bot Commands & Shortcuts

| Command | Action |
| :--- | :--- |
| `/deals` | Top deals with interactive category buttons (resets to Page 1) |
| `/more` | Browse next 15 deals (Pages 6–10, 11–15...) |
| `/atta`, `/rice`, `/oil` | Filter for Atta, Rice, Dal & Oil deals |
| `/snacks`, `/dryfruits` | Filter for Dry Fruits, Snacks & Dairy deals |
| `/kitchen`, `/home` | Filter for Kitchen, Cookware & Cleaning deals |
| `/beauty`, `/personal` | Filter for Personal Care & Beauty deals |
| `/electronics` | Filter for Electronics & Gadgets |
| `/categories` | Opens the Category selection buttons |
| `/search <keyword>` | Search any product keyword (e.g. `/search almond`) |
| `/pincode <pin>` | Change delivery location (e.g. `/pincode 560045`) |
| `/mindiscount <pct>` | Filter by minimum discount (e.g. `/mindiscount 70`) |
| `/settings` | View current location, discount filter, and alert status |
| `/pause` / `/resume` | Mute or unmute scheduled alert notifications |

---

## 🚀 Setup & Hosting

1. Set your `TELEGRAM_BOT_TOKEN` in `.env` (or in Render environment variables).
2. Run locally:
   ```bash
   python bot.py
   ```
   Or deploy as a **Free Web Service** on [Render](https://render.com) for 24/7 cloud hosting!

---

## 📄 License
MIT License. Free for personal and non-commercial use.
