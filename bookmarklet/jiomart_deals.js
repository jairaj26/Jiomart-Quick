/**
 * =============================================================================
 * ⚡ JioMart 70%+ Super Deals Hunter - Browser Bookmarklet
 * =============================================================================
 * Directly queries JioMart's Vertex API from inside jiomart.com.
 * Features:
 * - Auto-detects active PIN code / store delivery promise
 * - Filter by discount (70%+, 75%+, 80%+, 85%+)
 * - Instant Category Tabs (Staples, Snacks, Kitchen, Personal Care, Electronics, etc.)
 * - Instant Real-Time Search
 * - Responsive Slide-Over Drawer (Desktop & Mobile)
 * =============================================================================
 */

(function () {
  'use strict';

  // Toggle existing drawer if already present
  if (window.__JIOMART_DEALS_ACTIVE__) {
    const existing = document.getElementById('jm-deals-drawer');
    if (existing) {
      existing.style.display = existing.style.display === 'none' ? 'flex' : 'none';
      return;
    }
  }

  // Ensure user is on JioMart
  if (!window.location.hostname.includes('jiomart.com')) {
    const proceed = confirm(
      '⚡ JioMart Deals Hunter must be opened on https://www.jiomart.com.\n\nWould you like to open JioMart now?'
    );
    if (proceed) {
      window.location.href = 'https://www.jiomart.com';
    }
    return;
  }

  window.__JIOMART_DEALS_ACTIVE__ = true;

  // --- Configuration ---
  const AUTH_BEARER = 'Bearer Njg1OTQ1ZjQ2YzhjN2FlZTNmM2FmNjA1OlRwS3c3d0Q5aA==';
  const DEFAULT_PINCODE = '560045';

  const CATEGORIES = [
    { id: 'all', name: '🔥 All Deals', keywords: [] },
    { id: 'staples', name: '🌾 Atta, Rice & Oil', keywords: ['atta', 'rice', 'dal', 'oil', 'ghee', 'flour', 'pulse', 'grain', 'salt', 'sugar'] },
    { id: 'snacks', name: '🥨 Snacks & Dry Fruits', keywords: ['dry fruit', 'almond', 'cashew', 'snack', 'biscuit', 'chocolate', 'tea', 'coffee', 'dairy', 'milk', 'butter', 'dates'] },
    { id: 'kitchen', name: '🧼 Kitchen & Home', keywords: ['cookware', 'bottle', 'container', 'pan', 'cleaning', 'utensil', 'chopper', 'dish', 'tiffin', 'box'] },
    { id: 'personal', name: '🧴 Personal Care', keywords: ['soap', 'shampoo', 'facewash', 'toothpaste', 'cream', 'lotion', 'bodywash', 'skin', 'hair', 'deodorant'] },
    { id: 'electronics', name: '🎧 Electronics', keywords: ['headphone', 'watch', 'gadget', 'cable', 'charger', 'speaker', 'earbuds', 'trimmer'] },
    { id: 'pooja', name: '🎁 Pooja & Festive', keywords: ['pooja', 'rakhi', 'festival', 'agarbatti', 'diya', 'camphor', 'dhoop'] }
  ];

  // --- State ---
  let state = {
    pincode: DEFAULT_PINCODE,
    city: 'Bengaluru',
    stateName: 'Karnataka',
    minDiscount: 70,
    selectedCategory: 'all',
    searchQuery: '',
    products: [],
    loading: false,
    deliveryInfo: null
  };

  // --- Auto-Detect PIN code from JioMart DOM / Storage ---
  function detectInitialPincode() {
    try {
      const stored = localStorage.getItem('__jm_deals_pin') ||
                     localStorage.getItem('pincode') ||
                     localStorage.getItem('user_pincode') ||
                     localStorage.getItem('delivery_pincode');
      if (stored && /^\d{6}$/.test(stored.trim())) {
        return stored.trim();
      }

      // Check cookies
      const match = document.cookie.match(/(?:^|;\s*)(?:pincode|nms_mgo_pincode)=(\d{6})/);
      if (match && match[1]) {
        return match[1];
      }

      // Check header DOM elements for 6-digit pin
      const headerText = document.querySelector('header')?.innerText || '';
      const docMatch = headerText.match(/\b([1-9][0-9]{5})\b/);
      if (docMatch && docMatch[1]) {
        return docMatch[1];
      }
    } catch (e) {
      console.warn('[JioMart Deals] Could not auto-detect PIN:', e);
    }
    return DEFAULT_PINCODE;
  }

  state.pincode = detectInitialPincode();

  // --- Styles ---
  const styleEl = document.createElement('style');
  styleEl.id = 'jm-deals-styles';
  styleEl.textContent = `
    #jm-deals-drawer {
      position: fixed;
      top: 0;
      right: 0;
      width: 450px;
      max-width: 100vw;
      height: 100vh;
      background: #0f172a;
      color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      z-index: 2147483647;
      box-shadow: -8px 0 32px rgba(0, 0, 0, 0.45);
      display: flex;
      flex-direction: column;
      border-left: 1px solid #1e293b;
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
      box-sizing: border-box;
    }
    #jm-deals-drawer * {
      box-sizing: border-box;
    }
    .jm-header {
      padding: 16px 20px;
      background: #1e293b;
      border-bottom: 1px solid #334155;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .jm-title-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .jm-logo {
      font-size: 22px;
    }
    .jm-title {
      font-size: 17px;
      font-weight: 700;
      color: #f8fafc;
      letter-spacing: -0.3px;
    }
    .jm-subtitle {
      font-size: 11px;
      color: #94a3b8;
    }
    .jm-close-btn {
      background: #334155;
      border: none;
      color: #cbd5e1;
      width: 32px;
      height: 32px;
      border-radius: 8px;
      font-size: 18px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s, color 0.15s;
    }
    .jm-close-btn:hover {
      background: #ef4444;
      color: #fff;
    }
    .jm-location-bar {
      padding: 10px 20px;
      background: #1e293b;
      border-bottom: 1px solid #334155;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 13px;
    }
    .jm-location-info {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #e2e8f0;
      font-weight: 500;
    }
    .jm-pin-input-wrap {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .jm-pin-input {
      width: 80px;
      padding: 4px 8px;
      background: #0f172a;
      border: 1px solid #475569;
      border-radius: 6px;
      color: #f8fafc;
      font-size: 13px;
      font-weight: 600;
      text-align: center;
    }
    .jm-pin-btn {
      padding: 4px 10px;
      background: #2563eb;
      color: #fff;
      border: none;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .jm-pin-btn:hover {
      background: #1d4ed8;
    }
    .jm-controls {
      padding: 14px 20px 8px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      border-bottom: 1px solid #1e293b;
    }
    .jm-discount-chips {
      display: flex;
      align-items: center;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 2px;
    }
    .jm-chip-label {
      font-size: 12px;
      font-weight: 600;
      color: #94a3b8;
      margin-right: 4px;
    }
    .jm-chip {
      padding: 5px 12px;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 20px;
      color: #cbd5e1;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .jm-chip.active {
      background: #10b981;
      border-color: #10b981;
      color: #022c22;
      font-weight: 700;
    }
    .jm-category-chips {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 4px;
      scrollbar-width: thin;
    }
    .jm-cat-btn {
      padding: 6px 12px;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      color: #cbd5e1;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.15s;
    }
    .jm-cat-btn.active {
      background: #3b82f6;
      border-color: #3b82f6;
      color: #fff;
      font-weight: 600;
    }
    .jm-search-box {
      width: 100%;
      padding: 8px 12px;
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      color: #f8fafc;
      font-size: 13px;
      outline: none;
    }
    .jm-search-box:focus {
      border-color: #3b82f6;
    }
    .jm-products-list {
      flex: 1;
      overflow-y: auto;
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .jm-product-card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 12px;
      display: flex;
      gap: 14px;
      align-items: center;
      transition: transform 0.15s, border-color 0.15s;
      text-decoration: none;
      color: inherit;
    }
    .jm-product-card:hover {
      transform: translateY(-2px);
      border-color: #475569;
    }
    .jm-product-img {
      width: 76px;
      height: 76px;
      object-fit: contain;
      background: #fff;
      border-radius: 8px;
      padding: 4px;
      flex-shrink: 0;
    }
    .jm-product-details {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .jm-product-brand {
      font-size: 11px;
      font-weight: 600;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.4px;
    }
    .jm-product-name {
      font-size: 13px;
      font-weight: 600;
      color: #f8fafc;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .jm-product-qty {
      font-size: 11px;
      color: #cbd5e1;
    }
    .jm-price-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 4px;
    }
    .jm-price-eff {
      font-size: 16px;
      font-weight: 700;
      color: #10b981;
    }
    .jm-price-mrp {
      font-size: 12px;
      color: #94a3b8;
      text-decoration: line-through;
    }
    .jm-badge-disc {
      padding: 2px 7px;
      background: #dc2626;
      color: #fff;
      font-size: 11px;
      font-weight: 700;
      border-radius: 6px;
    }
    .jm-empty-state {
      text-align: center;
      padding: 40px 20px;
      color: #94a3b8;
    }
    .jm-empty-icon {
      font-size: 36px;
      margin-bottom: 8px;
    }
    .jm-spinner {
      width: 28px;
      height: 28px;
      border: 3px solid #334155;
      border-top-color: #10b981;
      border-radius: 50%;
      animation: jm-spin 0.8s linear infinite;
      margin: 40px auto;
    }
    @keyframes jm-spin {
      to { transform: rotate(360deg); }
    }
    .jm-footer {
      padding: 12px 20px;
      background: #1e293b;
      border-top: 1px solid #334155;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: #94a3b8;
    }
    .jm-footer a {
      color: #38bdf8;
      text-decoration: none;
    }
  `;
  document.head.appendChild(styleEl);

  // --- Create Drawer Container ---
  const drawer = document.createElement('div');
  drawer.id = 'jm-deals-drawer';
  document.body.appendChild(drawer);

  // --- API Services ---
  async function resolveLogistics(pincode) {
    try {
      const res = await fetch(`https://www.jiomart.com/api/service/application/logistics/v1.0/pincode/${pincode}`, {
        headers: {
          'accept': 'application/json, text/plain, */*',
          'authorization': AUTH_BEARER,
          'x-currency-code': 'INR'
        }
      });
      const data = await res.json();
      if (data && data.data && data.data[0]) {
        const item = data.data[0];
        const coords = item.lat_long?.coordinates || [77.6226, 13.036];
        let city = 'Bengaluru', stateName = 'Karnataka';
        for (const p of item.parents || []) {
          if (p.sub_type === 'city') city = p.name;
          if (p.sub_type === 'state') stateName = p.name;
        }
        return {
          pincode,
          longitude: coords[0],
          latitude: coords[1],
          city,
          state: stateName
        };
      }
    } catch (e) {
      console.warn('[JioMart Deals] Logistics error:', e);
    }
    return { pincode, longitude: 77.6226, latitude: 13.036, city: 'Bengaluru', state: 'Karnataka' };
  }

  async function fetchDeliveryPromise(loc) {
    try {
      const res = await fetch('https://www.jiomart.com/api/service/application/logistics/v1.0/delivery-promise', {
        headers: {
          'accept': 'application/json, text/plain, */*',
          'authorization': AUTH_BEARER,
          'x-currency-code': 'INR',
          'x-geolocation': JSON.stringify({ latitude: String(loc.latitude), longitude: String(loc.longitude) }),
          'x-location-detail': JSON.stringify({
            country: 'INDIA', country_iso_code: 'IN',
            city: loc.city, pincode: loc.pincode, state: loc.state
          })
        }
      });
      const data = await res.json();
      const storeIds = data?.query_params?.store_ids || [];
      const polygonIds = [];
      for (const it of data?.items || []) {
        for (const jp of it.journey_wise_promise || []) {
          const poly = jp.meta?.polygon_id;
          if (poly && !polygonIds.includes(poly)) polygonIds.push(poly);
        }
      }
      return { storeIds, polygonIds };
    } catch (e) {
      console.warn('[JioMart Deals] Delivery promise error:', e);
      return { storeIds: [], polygonIds: [] };
    }
  }

  async function fetchDeals() {
    state.loading = true;
    render();

    try {
      const loc = await resolveLogistics(state.pincode);
      state.city = loc.city;
      state.stateName = loc.state;

      const delivery = await fetchDeliveryPromise(loc);
      state.deliveryInfo = delivery;

      const storeFilter = delivery.storeIds.slice(0, 10).join('||');
      const fParts = ['department:groceries'];
      if (storeFilter) {
        fParts.push('journey:quickcommerce');
        fParts.push(`store_ids:${storeFilter}`);
      }

      const allFetched = [];
      // Fetch 3 pages (150 items) for rich selection
      for (let p = 1; p <= 3; p++) {
        const params = new URLSearchParams({
          f: fParts.join(':::'),
          page_size: '50',
          sort_on: 'discount_dsc',
          page_no: String(p),
          page_type: 'number'
        });

        const res = await fetch(`https://www.jiomart.com/ext/vertex/application/api/v1.0/products?${params.toString()}`, {
          headers: {
            'accept': 'application/json, text/plain, */*',
            'authorization': AUTH_BEARER,
            'x-currency-code': 'INR',
            'x-geolocation': JSON.stringify({
              latitude: String(loc.latitude),
              longitude: String(loc.longitude),
              polygon_ids: delivery.polygonIds
            }),
            'x-location-detail': JSON.stringify({
              country: 'INDIA', country_iso_code: 'IN',
              city: loc.city, pincode: loc.pincode, state: loc.state
            })
          }
        });

        if (!res.ok) break;
        const data = await res.json();
        const items = data?.items || [];
        if (!items.length) break;

        for (const it of items) {
          const effectivePrice = it.price?.effective?.max ?? it.price?.marked?.max ?? 0;
          const markedPrice = it.price?.marked?.max ?? effectivePrice;
          const discountPct = (markedPrice > 0) ? Math.round(((markedPrice - effectivePrice) / markedPrice) * 100) : 0;
          const savings = Math.max(0, markedPrice - effectivePrice);

          const sellable = it.sellable ?? true;
          const instockSizes = it.instock_variants?.sizes;
          const inStock = sellable && Array.isArray(instockSizes) && instockSizes.length > 0;

          const image = it.medias?.[0]?.url || 'https://www.jiomart.com/assets/version1717658742/smartweb/images/jiomart-default-product.svg';
          const brand = (typeof it.brand === 'object' ? it.brand?.name : it.brand_name) || 'JioMart';
          const name = it.name || 'Product';
          const slug = it.slug || '';
          const productUrl = slug ? `https://www.jiomart.com/product/${slug}` : '#';

          allFetched.push({
            uid: it.uid,
            name,
            brand,
            effectivePrice,
            markedPrice,
            discountPct,
            savings,
            inStock,
            image,
            url: productUrl,
            rawCategories: (it.categories || []).map(c => c.name || '')
          });
        }

        if (!data?.page?.has_next) break;
      }

      state.products = allFetched;
    } catch (err) {
      console.error('[JioMart Deals] Fetch error:', err);
    } finally {
      state.loading = false;
      render();
    }
  }

  // --- Filtering Logic ---
  function getFilteredProducts() {
    let list = state.products.filter(p => p.discountPct >= state.minDiscount);

    // Filter by Category
    if (state.selectedCategory !== 'all') {
      const catObj = CATEGORIES.find(c => c.id === state.selectedCategory);
      if (catObj && catObj.keywords.length) {
        list = list.filter(p => {
          const text = `${p.name} ${p.brand} ${p.rawCategories.join(' ')}`.toLowerCase();
          return catObj.keywords.some(kw => text.includes(kw));
        });
      }
    }

    // Filter by Search Query
    if (state.searchQuery.trim()) {
      const q = state.searchQuery.toLowerCase().trim();
      list = list.filter(p => `${p.name} ${p.brand}`.toLowerCase().includes(q));
    }

    // Sort by highest discount descending
    return list.sort((a, b) => b.discountPct - a.discountPct);
  }

  // --- Render UI ---
  function render() {
    const filtered = getFilteredProducts();

    drawer.innerHTML = `
      <!-- Header -->
      <div class="jm-header">
        <div class="jm-title-wrap">
          <span class="jm-logo">⚡</span>
          <div>
            <div class="jm-title">JioMart 70%+ Deals</div>
            <div class="jm-subtitle">${state.products.length} live deals fetched</div>
          </div>
        </div>
        <button class="jm-close-btn" id="jm-close-btn" title="Close (Esc)">✕</button>
      </div>

      <!-- Location Bar -->
      <div class="jm-location-bar">
        <div class="jm-location-info">
          <span>📍</span>
          <span>${state.city} (${state.pincode})</span>
        </div>
        <div class="jm-pin-input-wrap">
          <input type="text" id="jm-pin-input" class="jm-pin-input" value="${state.pincode}" maxlength="6" placeholder="PIN" />
          <button id="jm-pin-save" class="jm-pin-btn">Update</button>
        </div>
      </div>

      <!-- Controls -->
      <div class="jm-controls">
        <!-- Min Discount Selector -->
        <div class="jm-discount-chips">
          <span class="jm-chip-label">Min Off:</span>
          ${[70, 75, 80, 85].map(d => `
            <button class="jm-chip ${state.minDiscount === d ? 'active' : ''}" data-disc="${d}">${d}%+</button>
          `).join('')}
        </div>

        <!-- Category Selector -->
        <div class="jm-category-chips">
          ${CATEGORIES.map(c => `
            <button class="jm-cat-btn ${state.selectedCategory === c.id ? 'active' : ''}" data-cat="${c.id}">${c.name}</button>
          `).join('')}
        </div>

        <!-- Search Box -->
        <input type="text" id="jm-search-input" class="jm-search-box" placeholder="🔍 Search deal title or brand..." value="${state.searchQuery}" />
      </div>

      <!-- Products Feed -->
      <div class="jm-products-list">
        ${state.loading ? `
          <div class="jm-spinner"></div>
          <div style="text-align:center; color:#94a3b8; font-size:13px;">Scanning JioMart deals for PIN ${state.pincode}...</div>
        ` : filtered.length === 0 ? `
          <div class="jm-empty-state">
            <div class="jm-empty-icon">🔍</div>
            <div style="font-weight:600; color:#f8fafc; margin-bottom:4px;">No matching deals found</div>
            <div style="font-size:12px;">Try selecting "🔥 All Deals" or lowering the discount threshold to 70%+.</div>
          </div>
        ` : filtered.map(p => `
          <a class="jm-product-card" href="${p.url}" target="_blank" rel="noopener noreferrer">
            <img class="jm-product-img" src="${p.image}" alt="${p.name}" loading="lazy" />
            <div class="jm-product-details">
              <span class="jm-product-brand">${p.brand}</span>
              <div class="jm-product-name" title="${p.name}">${p.name}</div>
              <div class="jm-price-row">
                <span class="jm-price-eff">₹${p.effectivePrice}</span>
                <span class="jm-price-mrp">₹${p.markedPrice}</span>
                <span class="jm-badge-disc">${p.discountPct}% OFF</span>
              </div>
            </div>
          </a>
        `).join('')}
      </div>

      <!-- Footer -->
      <div class="jm-footer">
        <span>Showing ${filtered.length} deals</span>
        <button id="jm-refresh-btn" style="background:transparent; border:none; color:#38bdf8; font-size:12px; cursor:pointer; font-weight:600;">🔄 Refresh Deals</button>
      </div>
    `;

    // --- Attach Listeners ---
    document.getElementById('jm-close-btn').onclick = () => {
      drawer.style.display = 'none';
    };

    document.getElementById('jm-pin-save').onclick = () => {
      const input = document.getElementById('jm-pin-input').value.trim();
      if (/^\d{6}$/.test(input)) {
        state.pincode = input;
        localStorage.setItem('__jm_deals_pin', input);
        fetchDeals();
      } else {
        alert('Please enter a valid 6-digit PIN code.');
      }
    };

    document.querySelectorAll('.jm-chip').forEach(btn => {
      btn.onclick = () => {
        state.minDiscount = parseInt(btn.getAttribute('data-disc'), 10);
        render();
      };
    });

    document.querySelectorAll('.jm-cat-btn').forEach(btn => {
      btn.onclick = () => {
        state.selectedCategory = btn.getAttribute('data-cat');
        render();
      };
    });

    const searchInput = document.getElementById('jm-search-input');
    searchInput.oninput = (e) => {
      state.searchQuery = e.target.value;
      render();
      // Keep focus in input
      const newInp = document.getElementById('jm-search-input');
      newInp.focus();
      newInp.selectionStart = newInp.selectionEnd = newInp.value.length;
    };

    document.getElementById('jm-refresh-btn').onclick = () => {
      fetchDeals();
    };
  }

  // Keyboard shortcut: Esc to close
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && drawer.style.display !== 'none') {
      drawer.style.display = 'none';
    }
  });

  // Initial Fetch
  fetchDeals();
})();
