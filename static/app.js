'use strict';
const $ = s => document.querySelector(s);
const STORAGE_KEY = 'fiyat-avcisi-amazon-v3-filters';
const MAX_AGE = 23 * 3600;
const QUALITY_SENSORS = new Set(['PAW3311','PAW3315','PAW3333','PAW3335','PAW3370','PAW3395','PAW3399','PAW3950','PAW3955','PMW3360','PMW3366','PMW3389','HERO','HERO 2','FOCUS PRO','FOCUS PRO 30K','FOCUS PRO 35K']);
const emptyPrefs = () => ({category:'all',connection:'all',keyboardMax:'',mouseMax:'',sensor:'all',keyboardType:'all',color:'all',brand:'all',seller:'all',searchText:''});
let prefs=emptyPrefs(), products=[], status={}, refreshBusy=false;
try { prefs={...prefs,...JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}')}; } catch (_) {}
const safe=t=>String(t??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=n=>new Intl.NumberFormat('tr-TR',{maximumFractionDigits:2,minimumFractionDigits:Number(n)%1?2:0}).format(Number(n));
const dateText=s=>s ? new Intl.DateTimeFormat('tr-TR',{dateStyle:'short',timeStyle:'short'}).format(new Date(Number(s)*1000)):'Henüz yok';
const checkedAge=p=>Math.floor(Date.now()/1000)-Number(p.checked_at||0);
const validUrl=u=>{try {const x=new URL(u);return x.protocol==='https:'&&['www.amazon.com.tr','amazon.com.tr'].includes(x.hostname)?x.href:'';}catch(_){return '';}};
const validImage=u=>{try {const x=new URL(u);return x.protocol==='https:'&&['m.media-amazon.com','images-eu.ssl-images-amazon.com','images-na.ssl-images-amazon.com'].includes(x.hostname)?x.href:'';}catch(_){return '';}};
const limit=v=>{if(v===''||v===null||v===undefined)return Infinity;const n=Number(v);return Number.isFinite(n)&&n>0?n:Infinity;};
function keep(){try {localStorage.setItem(STORAGE_KEY,JSON.stringify(prefs));}catch(_){}}
function setTabs(name,value){for(const b of $(`#${name}`).querySelectorAll('button')){const current=b.dataset.category??b.dataset.connection;b.classList.toggle('selected',current===value);b.setAttribute('aria-pressed',String(current===value));}}
function syncControls(){
 setTabs('categoryTabs',prefs.category);setTabs('connectionTabs',prefs.connection);
 for(const id of ['keyboardMax','mouseMax','sensor','keyboardType','color','seller','searchText'])$("#"+id).value=String(prefs[id]??'');
 // Brand option may not exist until a feed has loaded.
 if([...$('#brand').options].some(o=>o.value===prefs.brand))$('#brand').value=prefs.brand;
 $('#keyboardMax').closest('label').classList.toggle('hidden',prefs.category==='mouse');
 $('#mouseMax').closest('label').classList.toggle('hidden',prefs.category==='keyboard');
 $('#sensor').closest('.field').classList.toggle('hidden',prefs.category==='keyboard');
 $('#keyboardType').closest('.field').classList.toggle('hidden',prefs.category==='mouse');
}
function isFresh(p){return status.demo || (p.source==='amazon-creators-api'&&checkedAge(p)>=0&&checkedAge(p)<MAX_AGE);}
function allAvailable(){
 const q=(prefs.searchText||'').trim().toLocaleLowerCase('tr-TR');
 return products.filter(p=>p&&isFresh(p)&&p.currency==='TRY'&&Number(p.price)>0&&
  (prefs.category==='all'||p.category===prefs.category)&&
  (p.category==='keyboard'?Number(p.price)<=limit(prefs.keyboardMax):Number(p.price)<=limit(prefs.mouseMax))&&
  (prefs.connection==='all'||p.connection===prefs.connection||p.connection==='both')&&
  (p.category!=='mouse'||prefs.sensor==='all'||(prefs.sensor==='quality'?QUALITY_SENSORS.has(p.sensor):p.sensor===prefs.sensor))&&
  (p.category!=='keyboard'||prefs.keyboardType==='all'||p.keyboard_type===prefs.keyboardType)&&
  (prefs.color==='all'||p.color===prefs.color)&&
  (prefs.brand==='all'||p.brand===prefs.brand)&&
  (prefs.seller==='all'||p.seller_type===prefs.seller)&&
  (!q||`${p.title||''} ${p.brand||''} ${p.sensor||''}`.toLocaleLowerCase('tr-TR').includes(q))
 ).sort((a,b)=>Number(a.price)-Number(b.price)||String(a.title).localeCompare(String(b.title),'tr'));
}
function tag(text,green=false){return `<span${green?' class="green"':''}>${safe(text)}</span>`;}
function card(p){
 const connection={wired:'Kablolu',wireless:'Kablosuz',both:'Kablolu + kablosuz'}[p.connection]||'Bağlantı bilinmiyor';
 const type={mechanical:'Mekanik',membrane:'Membran',hall:'Hall Effect'}[p.keyboard_type]||'';
 const tags=[tag(connection,p.connection==='wireless'),p.category==='keyboard'&&type?tag(type):'',p.category==='mouse'&&p.sensor?tag('◈ '+p.sensor,true):'',p.color!=='Bilinmiyor'?tag(p.color):''].filter(Boolean).join('');
 const url=validUrl(p.link), image=validImage(p.image);
 const art=image?`<img loading="lazy" referrerpolicy="no-referrer" src="${safe(image)}" alt="${safe(p.title)}">`:`<span class="fallback">${p.category==='mouse'?'🖱':'⌨'}</span>`;
 const seller=p.seller_type==='amazon'?'Amazon satıcısı':`Pazaryeri · ${p.seller||'Satıcı belirtilmemiş'}`;
 return `<article class="card"><div class="photo"><span class="kind">${p.category==='keyboard'?'KLAVYE':'MOUSE'}</span>${art}</div>
 <div class="card-body"><div class="seller-label" title="${safe(seller)}">● ${safe(seller)}</div><h3 title="${safe(p.title)}">${safe(p.title)}</h3>
 <div class="tags">${tags}</div><div class="price">${money(p.price)}<small>₺</small></div>
 <div class="checked">Fiyat kontrolü: ${safe(dateText(p.checked_at))}</div>
 ${url?`<a class="buy" target="_blank" rel="sponsored noopener noreferrer" href="${safe(url)}">Amazon'da görüntüle ↗</a>`:'<span class="buy disabled">Yalnızca örnek gösterim</span>'}</div></article>`;
}
function render(){
 const list=allAvailable();$('#resultCount').textContent=String(list.length);$('#heroCount').textContent=String(list.length);
 const el=$('#products');
 if(list.length)el.innerHTML=list.map(card).join('');
 else {
  let label='Bu filtrelere uygun ürün bulunamadı';
  let desc='Filtreleri genişletebilir veya ileride yeni taramaların katalogu büyütmesini bekleyebilirsin.';
  if(!status.configured&&!status.demo){label='Amazon API bağlantısı bekleniyor';desc='Resmî Creators API kimlik bilgileri tanımlanınca canlı ürünler burada görünür.';}
  else if(products.length===0){label='Amazon kataloğu henüz boş';desc='İlk başarılı ürün taramasından sonra gerçek sonuçlar listelenecek.';}
  else if(products.length>0&&!products.some(isFresh)){label='Fiyatların süresi doldu';desc='24 saatten eski Amazon ürün/fiyat içeriği otomatik gizlenir. Yeni başarılı taramayı bekle.';}
  el.innerHTML=`<div class="empty"><strong>${safe(label)}</strong><p>${safe(desc)}</p></div>`;
 }
 $('#lastSeen').textContent=status.demo?'Örnek veriler · Gerçek fiyat değil':`Son başarılı Amazon taraması: ${dateText(status.last_success)}`;
 const stale=products.length>0&&!products.some(isFresh);
 const enabled=status.configured&&!status.last_error&&!stale;
 $('#statusPill').classList.toggle('muted',!enabled);
 $('#statusText').textContent=status.demo?'ÖRNEK GÖRÜNÜM':!status.configured?'API BAĞLANTISI GEREKLİ':status.last_error?'TARAMA HATASI':stale?'VERİLER GÜNCEL DEĞİL':'AMAZON TAKİBİ AÇIK';
 $('#setupBanner').classList.toggle('hidden',status.configured||status.demo);
 $('#demoBanner').classList.toggle('hidden',!status.demo);
 $('#errorBanner').classList.toggle('hidden',!status.last_error);
 $('#errorBanner').textContent=status.last_error?`Amazon tarama uyarısı: ${status.last_error}`:'';
 $('#warningBanner').classList.toggle('hidden',!status.warning);
 $('#warningBanner').textContent=status.warning||'';
}
function reRender(){keep();syncControls();render();}
function rebuildBrandOptions(){
 const select=$('#brand');const brands=[...new Set(products.map(x=>x.brand).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'tr'));
 select.innerHTML='<option value="all">Tüm markalar</option>'+brands.map(x=>`<option value="${safe(x)}">${safe(x)}</option>`).join('');
 if(!brands.includes(prefs.brand))prefs.brand='all';
 // Additional sensor models are built from actually detected models, not made-up ones.
 const sensor=$('#sensor');const discovered=[...new Set(products.map(x=>x.sensor).filter(Boolean))].sort();
 sensor.innerHTML='<option value="all">Tüm sensörler (bilinmeyen dahil)</option><option value="quality">PAW3311 ve üzeri (doğrulanan)</option>'+discovered.map(s=>`<option value="${safe(s)}">${safe(s)}</option>`).join('');
 if(!['all','quality',...discovered].includes(prefs.sensor))prefs.sensor='all';
}
async function refresh(){
 if(refreshBusy)return; refreshBusy=true;$('#refresh').disabled=true;
 try{
  const response=await fetch(`./data/feed.json?ts=${Date.now()}`,{cache:'no-store'});
  if(!response.ok)throw new Error('Sunucu yanıtı '+response.status);
  const feed=await response.json();
  if(feed.schema!==3||!Array.isArray(feed.products)||typeof feed.status!=='object')throw new Error('v3 veri formatı bulunamadı.');
  status=feed.status;
  products=feed.products.filter(p=>p&&typeof p==='object'&&(status.demo||p.source==='amazon-creators-api'));
  rebuildBrandOptions();syncControls();render();
 }catch(e){
  status={configured:false,last_error:'Veri dosyası okunamadı: '+e.message};products=[];render();
 }finally{refreshBusy=false;$('#refresh').disabled=false;}
}
// Remove only ChatGPT's referral marker from display; keep Amazon referral URLs intact.
try{const u=new URL(location.href);if((u.searchParams.get('utm_source')||'').toLowerCase().includes('chatgpt')){u.searchParams.delete('utm_source');history.replaceState(null,'',u.pathname+u.search+u.hash);}}catch(_){}
$('#categoryTabs').addEventListener('click',e=>{const b=e.target.closest('button[data-category]');if(b){prefs.category=b.dataset.category;reRender();}});
$('#connectionTabs').addEventListener('click',e=>{const b=e.target.closest('button[data-connection]');if(b){prefs.connection=b.dataset.connection;reRender();}});
for(const id of ['keyboardMax','mouseMax','sensor','keyboardType','color','brand','seller','searchText']){
 $(`#${id}`).addEventListener(id==='keyboardMax'||id==='mouseMax'||id==='searchText'?'input':'change',e=>{prefs[id]=e.target.value;keep();render();});
}
$('#resetFilters').addEventListener('click',()=>{prefs=emptyPrefs();reRender();});
document.querySelectorAll('[data-budget]').forEach(button=>button.addEventListener('click',()=>{
 if(button.dataset.budget==='cheap'){prefs.keyboardMax='1100';prefs.mouseMax='1000';}
 else{prefs.keyboardMax='';prefs.mouseMax='';}
 reRender();
}));
$('#refresh').addEventListener('click',refresh);
$('#year').textContent=new Date().getFullYear();syncControls();refresh();setInterval(refresh,300000);
