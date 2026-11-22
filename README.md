# Fiyat Avcısı v3.0 — Amazon Türkiye

Sadece **Amazon.com.tr** ürünlerini gösteren koyu/yeşil tasarımlı bir GitHub Pages sitesi. Başka mağaza ve SerpApi kullanılmaz. Ürünler otomatik arka plan taramalarıyla bulunur; ziyaretçi önceden toplanmış katalogu anında filtreler. Site **tüm Amazon kataloğunu eksiksiz dökemez**: Creators API arama başına en fazla 10 ürün döndürür ve API erişimi şarttır.

## Filtreler

- Tümü / Klavyeler / Mouse'lar
- Tümü / Kablolu / Kablosuz
- Klavye ve mouse için **ayrı, isteğe bağlı fiyat üst limitleri**. İlk açılışta tüm fiyatlar görünür; hızlı bütçe düğmesi 1.100 TL ve 1.000 TL sınırlarını uygular.
- Mouse sensörü: Tümü, **PAW3311 ve üstü olarak önceden tanımlanmış doğrulanabilir sensör grubu**, eldeki katalogda bulunan tekil sensör modelleri
- Klavye: Mekanik / Membran / Hall Effect / Bilinmiyor
- Renk, marka, Amazon satıcısı / pazaryeri satıcısı, ürün adında arama
- Ürünler artan fiyata göre sıralanır; filtreler tarayıcıda saklanır.

Sensör ve bağlantı bilgisi Amazon API başlığı/özelliklerinden açıkça çıkarılabildiğinde gösterilir. Bilinmeyenleri yanlışlıkla belirli bir sensör veya bağlantı türüne atamayız. **PAW3311 ve üzeri**, model numarasından matematiksel üstünlük hesaplamak değil, seçilmiş uygun sensör aileleri listesidir; bütün sensörlerin kesin performans sıralaması değildir.

## Amazon Creators API kurulumu

Eski `SERPAPI_KEY` bu sürümde kullanılmaz. Amazon Associates/Creators API hesabı ve Türkiye için geçerli bir Partner Tag gerekir. Amazon Creators API erişimi onaylanmadıkça siteye gerçek ürün akmaz.

1. Amazon [Creators API kayıt adımları](https://affiliate-program.amazon.com/creatorsapi/docs/en-us/onboarding) ile erişim edin.
2. GitHub deposunda **Settings → Secrets and variables → Actions → New repository secret** bölümüne girin. Üç secret tanımlayın:
   - `AMAZON_CREATORS_CLIENT_ID`
   - `AMAZON_CREATORS_CLIENT_SECRET`
   - `AMAZON_ASSOCIATE_TAG` (amazon.com.tr için geçerli Associates takip kodu)
3. Mevcut GitHub Pages ayarının **Settings → Pages → Source: GitHub Actions** olduğundan emin olun.
4. **Actions → Fiyat Avcısı v3 - Amazon Türkiye → Run workflow** ile ilk taramayı başlatın. Tamamlanınca mevcut adresiniz `https://classicca.github.io/fiyat-avcisi/` açılır.

**Uyarı:** API anahtarını depodaki dosyalara veya ChatGPT sohbetine koymayın. Kurulum başarısız olduğunda sunucu sahte Amazon ürünü üretmez. Creators API erişimi başta ve sürekli satış uygunluk şartlarına bağlı olabilir. Ücretsiz GitHub altyapısının çalışma ve erişim limitleri bulunur.

## Katalog, fiyat ve lisans

- `data/amazon_catalog.json`: sadece ASIN kimlikleri, kategori ve tarama imleçleri; yeni modeller eklendikçe büyür (en fazla 1.500 kayıt).
- `data/feed.json`: Amazon'dan yeni çekilen başlık/fiyat/görsel/satıcı verileri. **23 saatten eski ürün içeriği hiçbir şekilde yayınlanmaz** (istemci de ayrıca süre kontrolü yapar). Eski Google/SerpApi verileri otomatik taşınmaz; `data/state.json` eski verisi değiştirilmez.
- **Her 6 saatte bir** yeni model araması ve mevcut ürün kimliklerinden en fazla 160 tanesinin fiyat tazelemesi planlanır. Kotalar ve API yanıtlarına göre eksik ürün olabilir. 1.500 ürünün tamamının her koşulda 24 saatte yenilendiği garanti edilmez.
- Amazon Gelir Ortaklığı politikalarındaki API veri önbellekleme ve bağlantı kullanımı kuralları gözetilmelidir. Son satış fiyatı ve stok Amazon ürün sayfasında geçerlidir. Fiyat geçmişi bu sürümde uzun süreli tutulmaz.
- Sadece API'nin `TRY` olarak sunduğu fiyat alınır, metin içinden fiyat okunmaz. Amazon Türkiye dışında adres veya para birimi kabul edilmez.
- Amazon'dan onaylı veri erişimi dışında otomatik Amazon HTML kazıması uygulanmaz.

## Mevcut Github Desktop projesini v3'e güncelleme

ZIP içindeki `.github`, `static`, `tests` klasörleri ve `amazon_api.py`, `catalog.py`, `cloud_publish.py`, `build_site.py`, `README.md`, `local_preview.py`, `ORNEK_GORUNUM.bat`, `.gitignore` dosyalarını **klonlanmış `fiyat-avcisi-github` deposunun kök dizinine** kopyala. `data/` klasörünü silme veya üzerine yazma. GitHub Desktop ile **Commit to main → Push origin** yap. Eski tarayıcı dosyaları depoda kalsa da yeni workflow bunları çalıştırmaz. İlk yeni yayında eski feed Amazon v3 verisine dönüştürülür ve eski Google verileri yeni sitede gösterilmez.

GitHub Actions ilk çalıştırma sırasında secret yoksa sahte veri üretmek yerine **"API bağlantısı bekleniyor"** mesajı yayınlar. API bağlandığında gerçek veriyi listeler.

## Yerel test

Python 3.10+ gereklidir. Üçüncü taraf Python paketi gerekmez.

```bash
python -m unittest discover -s tests -v
python cloud_publish.py            # Secret yoksa boş ve dürüst feed
python build_site.py
python -m http.server 8080 --directory public
```

Gerçek tarama için yukarıdaki üç ortam değişkenini Windows ortamında veya GitHub Secrets bölümünde tanımlayın.

Tasarımı gerçek ürün olmadan görmek için `ORNEK_GORUNUM.bat` / `python local_preview.py` çalıştırılır. Bu ayrı **örnek modudur** ve GitHub Pages'e yüklenen gerçek feed dosyasına eklenmez.

Not: Eski v2 test dosyaları depoda kaldıysa yeni GitHub Actions yalnızca `test_amazon.py` dosyasındaki v3 testlerini çalıştırır.
