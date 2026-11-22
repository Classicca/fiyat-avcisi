# Fiyat Avcısı v2.6 — Onaylı Mağaza Listesi ve Temiz Arayüz

Kullanıcı **arama yapmaz**. Site, Google Shopping/SerpApi ile otomatik ürün keşfeder ve **erişebildiği mağaza teklifleri arasında** en düşük fiyatlı olanı öne çıkarır. Aynı ürün modeli birden çok mağazada bulunduysa tek kart ve isteğe bağlı mağaza karşılaştırma listesi çıkar. **Tüm internet sitelerini tarama veya mutlak en ucuz fiyatı bulma garantisi yoktur.** Veriler güncellik, kapsam, mağaza katılımı ve kargo ücretine bağlıdır.

## Sadece seçilen 9 alışveriş platformu

**Amazon Türkiye, Trendyol, Hepsiburada, n11, Pazarama, idefix, İncehesap, İtopya, Gaming.Gen.TR.**

Tarayıcı, ancak ürün bağlantısının gerçek HTTPS alan adı bu dokuz platformdan birine aitse teklifi kabul eder. Google Shopping'in `source` alanına veya bir arama sonucunda yazan mağaza adına tek başına güvenmez. Fiyat karşılaştırma siteleri, yönlendirme linkleri ve taklit alan adları reddedilir. Eski kayıtlardaki izinsiz mağaza teklifleri de yayın akışında otomatik gizlenir.

**Bu dokuz mağazanın tamamını ayrı ayrı ve eksiksiz taramıyoruz.** Mevcut SerpApi/Google Shopping kaynağı yalnızca erişebildiği ürün ve mağaza tekliflerini döndürür; bu yüzden yeni sürüm daha güvenilir mağazalar gösterebilir ama ürün sayısı azalabilir. Pazaryerlerinin (Trendyol, n11 vb.) üçüncü taraf satıcılarını platformun kendisi gibi garantili saymayın; satıcının puanını ayrıca kontrol edin. Çok düşük/çelişkili fiyat alanları filtrelenir; gerçek mağaza fiyatı son kontrolde değişebilir.

**Arayüz:** Sol menü kaldırıldı; logo üst çubukta. Hepsi / Klavyeler / Mouse'lar, bağlantı türü, sensör ve fiyat ayarları sayfada kalır.

## Başlangıç ayarları

- Gaming klavye: **1.100 TL**; gaming mouse: **1.000 TL** (site üzerinde ayrı ayrı değiştirilebilir).
- Kategori: **Hepsi / Klavyeler / Mouse’lar**.
- Bağlantı: **Tümü / Kablolu / Kablosuz**.
- Mouse sensörü: **PAW3311 ve benzer veya üst sınıfı önceden doğrulanmış PixArt sensörleri**. Başlık/açıklamada sensör açıkça belirtilmiyorsa mouse sonuçlardan çıkarılır. Farklı sensör adlarını sadece numaraya bakarak sıralamıyoruz. İsteğe bağlı sensör seçimi de korunur.
- Aynı marka/modelin farklı mağazalardaki fiyatları (Google Product API `stores`) tek kartta ve ucuzdan pahalıya sunulur. Ayrıntı API çağrıları yalnızca **belirli sayıda ürün** için yapılır; eksiksiz mağaza kapsamı yoktur.
- Fiyat karşılaştırma siteleri birer satıcı olarak gösterilmez. Model kodları farklı ürünler birleştirilmez.
- Sonuçlar kategori içinde artan fiyata göre; ana veri kaynağı 24 saatte bir yenilenir.
- Dört genel aramaya ek olarak **her gece bir mouse ve bir klavye için marka/sensör/model araması** yapılarak önceki sürümlerde hiç görünmeyen ürünler de keşfedilmeye çalışılır. İlk aramada **James Donkey JDM11 PAW3311** ve **JDK99** özellikle kontrol edilir.
- Geçmişte keşfedilen ürünler, başka bir sorguda tekrar çıkmadı diye anında silinmez; ancak **10 günden eski mağaza fiyatları gizlenir**. İki günden eski fiyatlar kartta "son görülen fiyat" olarak belirtilir.

## Neden tüm mağazaları her an kontrol etmiyor?

SerpApi ücretsiz paketi şu an **250 arama/ay**. Bir gece taraması 4 genel sorgu, 2 dönüşümlü model/sensör/marka sorgusu, 1 mağaza karşılaştırma sorgusu kullanabilir. 31 günde teorik azami **217** arama (ek/manuel ve yeniden başlatmalar hariç). Kullanılabilir kota azsa ek sorgular atlanır. API anahtarı olmadan güncel fiyat doğrulanamaz. Mağazaların Google Shopping verisine katılması, model ayrıştırma doğruluğu ve sağlayıcı fiyatlarının tazeliği sonucu belirler.

## GitHub'da zaten yayınlanan siteyi güncelleme

**`Fiyat-Avcisi-v2.6-Magaza-Dogrulama-Guncelleme.zip`** dosyasını kullan; içindeki klasörleri ve dosyaları **mevcut depo kök dizinine** doğru yolları koruyarak kopyala. Özellikle `.github/workflows/yayin.yml`, `static/`, `scanner.py`, `cloud_publish.py`, **`discovery.py` ve yeni `merchants.py`** güncellenecek. `data/state.json` ve `data/feed.json` ZIP'e konulmadı; mevcut fiyat geçmişini silme.

En güvenilir yöntem: **GitHub Desktop** → File → Clone repository (mevcut fiyat-avcisi) → güncelleme ZIP'inin içindeki dosyaları bu yerel klonun üzerine kopyala → Commit to main → Push origin. Ardından GitHub Actions sonucuna bak. İnternet sayfası yayımlandığı anda ilk geçerli taramada değişiklikler yansır. Adımlar `GITHUB-GUNCELLEME-v2.6.md` içinde.

Mevcut SerpApi Secret `SERPAPI_KEY` aynen kalır. Fiyat geçmişini korumak için önceki `data/` içeriğini silme ve ZIP'teki herhangi bir örnek/önizleme verisini yükleme.

## Test/yerel görüntüleme

```bash
python -m unittest discover -s tests -v
python cloud_publish.py --no-scan
python build_site.py
python -m http.server 8080 --directory public
```

Gerçek tarama için `SERPAPI_KEY` ortam değişkeni ve `python cloud_publish.py` gerekir. Windows'ta `ORNEK_GORUNUM.bat` tasarım önizlemesi (kurgu veri), `BASLAT.bat` yerel gerçek tarama içindir.

**Sınırlamalar:** Fiyatlar kargo/üyelik/kupon dahil nihai kasa fiyatı olmak zorunda değildir. Alışveriş yapmadan önce mağazadaki stok, kargo ve toplam tutarı doğrula. Bulunamayan satıcılar, tutarsız ürün isimleri veya eksik sensör bilgisi nedeniyle sonuçlar eksik kalabilir. PAW3311 ve üzeri filtresi kapsamı daraltır. İş akışının yeşil olması, tüm mağazalarda en ucuz fiyatın bulunduğunu kanıtlamaz.

## Doğruluk sınırları

Her internet mağazasını listeleyen ücretsiz ve eksiksiz bir API yok. Google Shopping'in kapsamı sınırlıdır, mevcut Google Shopping API sayfalaması da ilk sonuç penceresi ötesine geçemeyebilir. Bu yüzden "piyasadaki mutlak en ucuz fiyat" iddiası yerine **"bulunan mağazalar arasında en ucuz fiyat"** gösterilir. Kargo, kupon, stok durumu ve fiyat değişikliği için alışveriş sayfasını kontrol etmek gerekir. Bu sürüm çevrimiçi API anahtarıyla canlı test edilmedi; yerel testler sentetik verilerdir.
