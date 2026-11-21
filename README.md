# Fiyat Avcısı v2.0 — Tam Web Sitesi

**Amaç:** Siteye gir, uygun gaming klavye veya mouse var mı gör. Kullanıcı arama yapmaz.

**Görünüm:** Koyu arayüz, açık yeşil vurgular, iki ürün kategorisi ve üç bağlantı filtresi (**Tümü · Kablolu · Kablosuz**). Ürün kartında fotoğraf, fiyat, mağaza ve ürün bağlantısı bulunur. En ucuz ürünler önce gelir. Yeni ürün ve son 48 saatte doğrulanan fiyat düşüşü işaretlenir.

| Kategori | Maksimum fiyat | Kapsam |
|---|---:|---|
| Gaming klavyeler | **1.100 TL dahil** | Kablolu ve kablosuz |
| Gaming mouse | **1.000 TL dahil** | Kablolu ve kablosuz |

## En kısa yol: internette sürekli açık site

Tam kurulum adımları **`GITHUB-KURULUM.md`** dosyasında. Özet:

1. Proje dosyalarını GitHub'da **herkese açık** `fiyat-avcisi` adlı depoya yükle.
2. SerpApi hesabından aldığın API anahtarını GitHub **Actions secret** olarak `SERPAPI_KEY` adıyla ekle.
3. GitHub Pages kaynağını **GitHub Actions** seç.
4. **Actions → Fiyat Avcısı - Otomatik Tara ve Yayınla → Run workflow** ile ilk taramayı çalıştır.

Böylece site bilgisayar kapalıyken de 7/24 ziyaret edilebilir. Otomatik tarama **her akşam 21.23**, hafta içi ayrıca **sabah 09.23** (Türkiye saati) planlanmıştır. GitHub Actions görevleri bazen gecikebilir. Her tarama 4 Google Shopping sorgusu kullanır; bu takvim ayda en fazla yaklaşık 216 sorgu harcar. SerpApi ücretsiz planının Kasım 2026 itibarıyla aylık 250 sorgu limiti vardır; manuel taramalar ve push ile tetiklenen ilk kurulum taramaları da kotayı tüketir. Limit değişebilir.

**Tek seferlik dış hizmet kurulumu şarttır:** Github hesabı, herkese açık depo, Pages ayarı ve SerpApi anahtarı olmadan gerçek ürünler otomatik toplanamaz. Bunlar tamamlanmadan site örnek/uydurma fiyat göstermeyecektir.

## Bilgisayarda önizleme

- Python 3.10 veya üstünü yükle. `ORNEK_GORUNUM.bat` dosyasını çalıştır. Sadece tasarımı gösteren, açıkça **ÖRNEK** etiketli kurgu ürünler listelenir.
- Yerel gerçek tarama için `BASLAT.bat` dosyasını çalıştır, `http://127.0.0.1:8000` adresini aç ve SerpApi anahtarını gir. Yerel uygulama açıkken varsayılan tarama aralığı **24 saat**. Aynı anahtarla GitHub'da da tarama çalışıyorsa toplam kullanım ücretsiz kotayı aşabilir.
- Komut satırı: `python server.py --demo` veya `python server.py`.

## Dosyalar

- `.github/workflows/yayin.yml`: zamanlanan GitHub Actions taraması ve Pages yayını
- `cloud_publish.py`: gerçek fiyatları SerpApi'den çeker, önceki fiyat geçmişini korur, statik site için `feed.json` oluşturur
- `build_site.py`: yalnızca kamuya açık dosyaları `public/` klasörüne koyar
- `data/state.json`: fiyatların ve önceki taramaların kalıcı geçmişi; GitHub deposuna commit edilir; **API anahtarı içermez**
- `data/feed.json`: kullanıcı arayüzünün okuduğu, güncel ürün listesi
- `static/`: sade tasarım, mobil görünüm, Tümü/Kablolu/Kablosuz filtreleri
- `server.py`, `scanner.py`, `db.py`: Windows yerel çalışma seçeneği ve ürün tarayıcı
- `tests/`: internet bağlantısı ve API anahtarı gerektirmeyen testler

### Geliştirme/test

```shell
python -m unittest discover -s tests -v
python cloud_publish.py --no-scan
python build_site.py
python -m http.server 8080 --directory public
```

`--no-scan` canlı ürün üretmez. Gerçek veri almak için `SERPAPI_KEY` ortam değişkeni gereklidir ve `python cloud_publish.py` çalıştırılmalıdır. API anahtarını koda ya da GitHub depoya yazma.

## Bilinmesi gereken sınırlar

- Ürünler **Google Shopping (SerpApi)** sonuçlarından derlenir, mağazaların tamamı doğrudan taranmaz. Her mağaza, her fırsat, stok durumu veya kargo dahil nihai fiyat garanti edilemez.
- Bağlantı türü başlıktaki kablolu/kablosuz ifadelerinden sınıflandırılır. Emin olunamayan ürünler yalnızca **Tümü** sekmesinde görünür. Hem kablolu hem kablosuz olan cihazlar her ikisine de girer.
- Fiyat düşüşü etiketi, sitemizin **önceki kendi gözlemi** ile karşılaştırılır. İlk taramada geçmiş fiyat veya indirim kanıtı yoktur.
- Tarama başarısız olursa sitedeki önceki sonuçlar korunur ve hata/eski veri bildirimi görünür. Eski fiyatı güncelmiş gibi satın alma fiyatı sayma.
- Tasarım önizlemesindeki örnek ürünlerin tümü kurgusaldır. Gerçek API anahtarıyla yapılmış canlı tarama bu geliştirme ortamında doğrulanmadı.
- GitHub Pages statik bir sitedir. **Sitenin erişilebilir kalması, fiyatların sürekli gerçek zamanlı güncellendiği anlamına gelmez.** GitHub zamanlayıcısı gecikebilir; zamanlanmış görevler uzun süre hareketsiz kalan genel depolarda durdurulabilir.

Bu dosya ticari kullanıma açık fiyat veri erişimi veya üçüncü taraf mağazalara doğrudan scraping hakkı vermez. Kullanılan servislerin kullanım şartlarına dikkat et.
