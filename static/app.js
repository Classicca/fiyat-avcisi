/* Fiyat Avcısı: sade günlük fırsat ekranı. Gerçek modda yalnızca API verileri gösterilir. */
'use strict';
const $ = (selector) => document.querySelector(selector);
const DEFAULT_LIMITS = { keyboard: 1100, mouse: 1000 };
const PREFS_KEY = 'fiyat-avcisi-pref-v24';
const ALLOWED_SENSORS = new Set(['PAW3311','PAW3315','PAW3333','PAW3335','PAW3370','PAW3395','PAW3399','PAW3950','PAW3955','PMW3360','PMW3366','PMW3389','PMW3391','PMW3399']);
const state = { products: [], status: null, busy: false, connection: 'all', category: 'all', limits: { ...DEFAULT_LIMITS }, sensors: [] };
function normalizedSensor(value) { return String(value ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[^A-Z0-9]/g, ''); }
function displaySensor(value) { return String(value ?? '').trim().toUpperCase().replace(/\s+/g, ' ').slice(0, 35); }
function sanitizeLimit(value, fallback) {
  const n = Number(value);
  return Number.isSafeInteger(n) && n >= 1 && n <= 999999 ? n : fallback;
}
function restorePreferences() {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
    state.category = ['all', 'keyboard', 'mouse'].includes(raw.category) ? raw.category : 'all';
    state.connection = ['all', 'wired', 'wireless'].includes(raw.connection) ? raw.connection : 'all';
    state.limits.keyboard = sanitizeLimit(raw.keyboardLimit, DEFAULT_LIMITS.keyboard);
    state.limits.mouse = sanitizeLimit(raw.mouseLimit, DEFAULT_LIMITS.mouse);
    if (Array.isArray(raw.sensors)) state.sensors = [...new Set(raw.sensors.filter(x => typeof x === 'string').map(displaySensor).filter(x => ALLOWED_SENSORS.has(normalizedSensor(x))))].slice(0, 8);
  } catch (_ignored) { /* Storage may be disabled; filters still work for this visit. */ }
}
function savePreferences() {
  try { localStorage.setItem(PREFS_KEY, JSON.stringify({ category: state.category, connection: state.connection, keyboardLimit: state.limits.keyboard, mouseLimit: state.limits.mouse, sensors: state.sensors })); }
  catch (_ignored) { /* Private browsing / blocked storage. */ }
}
function updateTabs(id, dataKey, current) {
  for (const button of document.querySelectorAll(`#${id} button`)) {
    const active = button.dataset[dataKey] === current;
    button.classList.toggle('selected', active);
    button.setAttribute('aria-pressed', String(active));
  }
}
function drawSensorChips() {
  $('#sensorChips').innerHTML = state.sensors.length
    ? state.sensors.map((s, i) => `<button class="sensor-chip" data-sensor-index="${i}" type="button" title="Sensörü kaldır">${safe(s)} <span aria-hidden="true">×</span><span class="sr-only">kaldır</span></button>`).join('')
    : '<span class="sensor-muted">PAW3311 ve üzeri sensörler gösterilir. İstersen model seç.</span>';
}
function updateControls() {
  updateTabs('categoryFilter', 'category', state.category);
  updateTabs('connectivityFilter', 'connection', state.connection);
  $('#keyboardLimit').value = state.limits.keyboard;
  $('#mouseLimit').value = state.limits.mouse;
  $('#keyboardLimitLabel').textContent = `En fazla ${money(state.limits.keyboard)} TL`;
  $('#mouseLimitLabel').textContent = `En fazla ${money(state.limits.mouse)} TL`;
  $('#sensorFilterBox').classList.toggle('hidden', state.category === 'keyboard');
  $('#keyboardSection').classList.toggle('hidden', state.category === 'mouse');
  $('#mouseSection').classList.toggle('hidden', state.category === 'keyboard');
  drawSensorChips();
}
function matchesSensor(product) {
  if (product.category !== 'mouse' || state.sensors.length === 0) return true;
  const searchable = normalizedSensor(`${product.sensor || ''} ${product.title || ''}`);
  return state.sensors.some(sensor => searchable.includes(normalizedSensor(sensor)));
}
// Only remove ChatGPT's attribution parameter from the visible page address.
try {
  const url = new URL(window.location.href);
  if (/chatgpt/i.test(url.searchParams.get('utm_source') || '')) {
    url.searchParams.delete('utm_source');
    window.history.replaceState(null, '', url.pathname + url.search + url.hash);
  }
} catch (_ignored) {}

const money = (value) => new Intl.NumberFormat('tr-TR', { minimumFractionDigits: Number(value) % 1 ? 2 : 0, maximumFractionDigits: 2 }).format(Number(value) || 0);
const safe = (str) => String(str ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const safeUrl = (url) => /^https?:\/\//i.test(String(url || '').trim()) ? safe(String(url).trim()) : '';
const dateFormat = (unix) => unix ? new Intl.DateTimeFormat('tr-TR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(unix * 1000)) : '';
function ago(unix) {
  if (!unix) return 'Henüz kontrol edilmedi';
  const diff = Math.max(0, Date.now() / 1000 - unix);
  if (diff < 60) return 'Az önce kontrol edildi';
  if (diff < 3600) return `${Math.floor(diff / 60)} dk önce kontrol edildi`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} saat önce kontrol edildi`;
  return `Son kontrol: ${dateFormat(unix)}`;
}
function toast(message) {
  const el = $('#toast'); el.textContent = message; el.classList.remove('hidden');
  window.clearTimeout(toast.timer); toast.timer = window.setTimeout(() => el.classList.add('hidden'), 5000);
}
function keyboardIllustration() {
  return `<div class="art-keyboard" aria-hidden="true">${Array.from({ length: 52 }, (_, i) => `<span class="art-key${[3, 7, 11, 18, 25, 32, 39, 44, 50].includes(i) ? ' lit' : ''}"></span>`).join('')}</div>`;
}
function mouseIllustration() {
  return '<div class="art-mouse" aria-hidden="true"><span></span></div>';
}
function productCard(product) {
  const badge = product.drop_amount > 0 ? '<span class="product-badge drop">↘ FİYATI DÜŞTÜ</span>' : product.is_new ? '<span class="product-badge">✦ YENİ</span>' : '';
  const imgUrl = safeUrl(product.image);
  const img = imgUrl ? `<img src="${imgUrl}" alt="${safe(product.title)}" loading="lazy" referrerpolicy="no-referrer">` : '';
  const old = product.original_price > product.price ? `<span class="old-price">${money(product.original_price)} TL</span>` : '';
  const seenTime = Number(product.price_checked_at || product.last_seen || 0);
  const daysOld = seenTime ? (Date.now() / 1000 - seenTime) / 86400 : 0;
  const checkedNote = daysOld >= 2 ? `<div class="product-connection">Fiyat ${safe(dateFormat(seenTime))} tarihinde görüldü</div>` : '';
  const productUrl = safeUrl(product.link);
  const isComparison = (() => { try { const host = new URL(product.link).hostname; return host.includes('google.'); } catch (_) { return false; } })();
  const link = productUrl ? `<a class="product-link" href="${productUrl}" target="_blank" rel="noopener noreferrer">${isComparison ? 'Teklifleri karşılaştır' : 'Bulunan en ucuz mağazaya git'} ↗</a>` : '<span class="product-link disabled" aria-disabled="true">Örnek ürün</span>';
  const options = Array.isArray(product.offers) ? product.offers : [];
  const compare = options.length > 1 ? `<details class="merchant-offers"><summary>${options.length} mağazanın bulunan fiyatı</summary><div class="merchant-list">${options.map(o => `<a href="${safeUrl(o.link)}" target="_blank" rel="noopener noreferrer"><span>${safe(o.store)}</span><strong>${money(o.price)} TL ↗</strong></a>`).join('')}</div></details>` : '';
  return `<article class="product-card">
    <div class="product-visual">${product.category === 'mouse' ? mouseIllustration() : keyboardIllustration()}${img}<div class="product-badges">${badge}</div></div>
    <div class="product-info"><div class="product-store"><span class="store-tick"></span>${safe(product.store)}</div>
      ${product.connectivity === 'wired' ? '<div class="product-connection">⌁ Kablolu</div>' : product.connectivity === 'wireless' ? '<div class="product-connection">⌁ Kablosuz</div>' : product.connectivity === 'both' ? '<div class="product-connection">⌁ Kablolu + Kablosuz</div>' : ''}
      ${product.category === 'mouse' && product.sensor ? `<div class="product-connection">◈ Sensör: ${safe(product.sensor)}</div>` : ''}
      <h3 class="product-title" title="${safe(product.title)}">${safe(product.title)}</h3>
      ${checkedNote}
      <div class="price-area"><div class="product-price">${money(product.price)}<span class="money-symbol">₺</span></div>${old}</div>
      ${compare}
      <div class="product-footer">${link}</div>
    </div>
  </article>`;
}
function availableProducts() {
  return state.products.filter(p => Object.hasOwn(state.limits, p.category) &&
      (state.category === 'all' || p.category === state.category) &&
      Number.isFinite(Number(p.price)) && Number(p.price) > 0 && Number(p.price) <= state.limits[p.category] &&
      (state.connection === 'all' || p.connectivity === state.connection || p.connectivity === 'both') &&
      matchesSensor(p))
    .sort((a, b) => Number(a.price) - Number(b.price));
}
function renderProducts() {
  const items = availableProducts();
  $('#resultCount').textContent = items.length;
  for (const [category, target, counter, label] of [
    ['keyboard', '#keyboardProducts', '#keyboardCount', 'klavye'],
    ['mouse', '#mouseProducts', '#mouseCount', 'gaming mouse'],
  ]) {
    const found = items.filter(p => p.category === category);
    $(counter).textContent = found.length;
    if (found.length) { $(target).innerHTML = found.map(productCard).join(''); continue; }
    const configured = state.status?.configured;
    const scanning = state.status?.scanning;
    let title = 'Henüz ürün bulunamadı', desc = 'Takip başladığında uygun ürünleri burada göreceksin.';
    if (configured && scanning) { title = 'Ürünler taranıyor'; desc = 'Sonuçlar otomatik güncellenecek.'; }
    else if (!state.status?.last_success && !state.status?.demo) { title = 'İlk fiyat taraması bekleniyor'; desc = 'Canlı veri bağlandığında ürünler otomatik görünecek.'; }
    else if (configured) { title = `Bu filtrelerde uygun ${label} yok`; desc = 'Fiyatı veya filtreleri değiştirerek tekrar bakabilirsin.'; }
    $(target).innerHTML = `<div class="empty"><div class="empty-symbol">⌁</div><strong>${safe(title)}</strong><p>${safe(desc)}</p></div>`;
  }
}
function renderStatus() {
  const status = state.status;
  if (!status) return;
  const items = availableProducts();
  const count = items.length;
  const title = $('#heroTitle');
  if (status.scanning && count === 0) title.innerHTML = 'Fırsatlar<br><em>aranıyor.</em>';
  else if (!status.last_success && !status.demo && status.public_site) title.innerHTML = 'İlk tarama<br><em>bekleniyor.</em>';
  else if (!status.configured && !status.demo) title.innerHTML = 'Fırsatları<br><em>takip edelim.</em>';
  else if (count > 0) title.innerHTML = `${count} uygun ürün<br><em>bulundu.</em>`;
  else if (!status.last_success && !status.demo && !status.last_error) title.innerHTML = 'İlk tarama<br><em>bekleniyor.</em>';
  else title.innerHTML = 'Şimdilik uygun<br><em>ürün yok.</em>';
  $('#lastScan').textContent = status.demo ? 'Örnek ürünler gösteriliyor' : ago(status.last_success);
  $('#lastScan').title = status.last_success ? `Son başarılı tarama: ${dateFormat(status.last_success)}` : '';
  const isStale = Boolean(status.last_success && Date.now() / 1000 - status.last_success > 36 * 3600);
  const label = status.demo ? 'ÖRNEK MOD' : status.scanning ? 'TARANIYOR' :
    status.public_site ? (!status.configured ? 'KURULUM BEKLİYOR' : status.last_error ? 'SON TARAMA HATASI' : isStale ? 'SONUÇLAR ESKİ' : 'OTOMATİK TAKİP AÇIK') :
    status.configured ? (status.last_error ? 'TARAMA HATASI' : 'OTOMATİK TAKİP AÇIK') : 'KURULUM GEREKLİ';
  $('#liveLabel').textContent = label;
  $('#livePill').className = 'status-pill' + (!status.configured || status.last_error || status.demo || isStale ? ' off' : '') + (status.scanning ? ' running' : '');
  $('#demoBanner').classList.toggle('hidden', !status.demo);
  $('#setupPanel').classList.toggle('hidden', status.configured || Boolean(status.public_site));
  $('#errorBanner').classList.toggle('hidden', !status.last_error);
  $('#warnBanner').classList.toggle('hidden', !status.warning || !!status.last_error);
  $('#errorText').textContent = status.last_error || '';
  $('#warnText').textContent = status.warning || '';
}
async function readData() {
  // GitHub Pages uses pre-generated public JSON; local Python app uses API.
  // Relative URLs work at both a root domain and /repository-name/.
  try {
    const response = await fetch(`./data/feed.json?ts=${Date.now()}`, { cache: 'no-store' });
    if (response.ok) {
      const feed = await response.json();
      if (feed && feed.schema === 1 && feed.status && Array.isArray(feed.products)) {
        return { status: feed.status, products: feed.products };
      }
    }
  } catch (_ignored) { /* Local app has no static feed endpoint. */ }
  const [statusResp, productResp] = await Promise.all([
    fetch('./api/status', { cache: 'no-store' }),
    fetch('./api/products', { cache: 'no-store' })
  ]);
  if (!statusResp.ok || !productResp.ok) throw new Error('Sunucudan bilgi alınamadı.');
  const status = await statusResp.json();
  const result = await productResp.json();
  return { status, products: Array.isArray(result.products) ? result.products : [] };
}
async function loadAll() {
  if (state.busy) return;
  state.busy = true;
  $('#refreshButton').classList.add('busy');
  try {
    const data = await readData();
    state.status = data.status;
    state.products = data.products;
    renderStatus(); renderProducts();
  } catch (error) {
    toast(`Bağlantı hatası: ${error.message}`);
    if (!state.status) for (const target of ['#keyboardProducts', '#mouseProducts']) $(target).innerHTML = '<div class="empty"><strong>Veri yüklenemedi</strong><p>Biraz sonra yeniden dene.</p></div>';
  } finally {
    state.busy = false;
    $('#refreshButton').classList.remove('busy');
  }
}
async function post(url, body) {
  const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Local-Action': '1' }, body: JSON.stringify(body) });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || data.message || 'İşlem başarısız.');
  return data;
}
async function saveApiKey(event) {
  event.preventDefault();
  $('#setupError').classList.add('hidden');
  const key = $('#apiKey').value.trim();
  const btn = $('#saveKeyButton'); btn.disabled = true;
  try {
    const result = await post('/api/configure', { api_key: key });
    $('#apiKey').value = '';
    toast(result.message);
    await loadAll();
  } catch (error) {
    $('#setupError').textContent = error.message;
    $('#setupError').classList.remove('hidden');
  } finally { btn.disabled = false; }
}
$('#year').textContent = new Date().getFullYear();
restorePreferences();
updateControls();
$('#categoryFilter').addEventListener('click', event => {
  const button = event.target.closest('button[data-category]');
  if (!button || !$('#categoryFilter').contains(button)) return;
  state.category = button.dataset.category;
  savePreferences(); updateControls(); renderProducts(); renderStatus();
});
$('#connectivityFilter').addEventListener('click', (event) => {
  const button = event.target.closest('button[data-connection]');
  if (!button || !$('#connectivityFilter').contains(button)) return;
  state.connection = button.dataset.connection;
  savePreferences();
  updateTabs('connectivityFilter', 'connection', state.connection);
  renderProducts();
  renderStatus();
});
for (const kind of ['keyboard', 'mouse']) {
  $(`#${kind}Limit`).addEventListener('change', event => {
    state.limits[kind] = sanitizeLimit(event.target.value, state.limits[kind]);
    savePreferences(); updateControls(); renderProducts(); renderStatus();
  });
}
function addSensor() {
  const value = displaySensor($('#sensorInput').value);
  if (!ALLOWED_SENSORS.has(normalizedSensor(value))) { toast('Yalnızca PAW3311 ve üzeri doğrulanmış sensör modelleri seçilebilir.'); return; }
  if (state.sensors.some(item => normalizedSensor(item) === normalizedSensor(value))) { $('#sensorInput').value = ''; return; }
  if (state.sensors.length >= 8) { toast('En fazla 8 sensör eklenebilir.'); return; }
  state.sensors.push(value);
  $('#sensorInput').value = '';
  savePreferences(); drawSensorChips(); renderProducts(); renderStatus();
}
$('#addSensorButton').addEventListener('click', addSensor);
$('#sensorInput').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); addSensor(); } });
$('#sensorChips').addEventListener('click', event => {
  const button = event.target.closest('button[data-sensor-index]');
  if (!button) return;
  state.sensors.splice(Number(button.dataset.sensorIndex), 1);
  savePreferences(); drawSensorChips(); renderProducts(); renderStatus();
});
$('#refreshButton').addEventListener('click', loadAll);
$('#setupForm').addEventListener('submit', saveApiKey);
for (const target of ['#keyboardProducts', '#mouseProducts']) $(target).addEventListener('error', event => { if (event.target.tagName === 'IMG') event.target.remove(); }, true);
loadAll();
window.setInterval(loadAll, 300000); // Sayfa açıkken 5 dakikada bir güncel veriyi kontrol et.
