# Fiyat Avcısı v2.5 — GitHub'a tek seferde güncelleme

> Bu paket, şu anda yayındaki v2.0 siteyi bile v2.5'e yükseltecek kaynak dosyalarını içerir. GitHub'daki `data/` dosyalarını değiştirme.

## Önerilen yol: GitHub Desktop

1. [GitHub Desktop](https://desktop.github.com/) uygulamasını kur ve GitHub hesabına giriş yap.
2. **File → Clone repository** kısmında `Classicca/fiyat-avcisi` deposunu seçip **Clone** de.
3. `Fiyat-Avcisi-v2.5-Guncelleme.zip` arşivini çıkar. **ZIP içindeki bütün dosyaları ve klasörleri**, bilgisayardaki klon klasörünün **içine** (üst düzey klasör oluşturmayacak şekilde) kopyala. Windows değiştirme onayı çıkarsa kabul et.
4. `.github/workflows/yayin.yml`, `static/index.html`, `static/app.js`, `scanner.py`, `cloud_publish.py`, `discovery.py` konumlarını kontrol et. **Mevcut `data/` klasörünü silme/değiştirme**.
5. GitHub Desktop'ta değişen dosyaları gör. Summary'ye `Fiyat Avcısı v2.5` yaz; **Commit to main**, sonra **Push origin**.
6. GitHub → Actions → **Fiyat Avcısı - Otomatik Tara ve Yayınla** → yeşil tik olup olmadığını kontrol et. Ardından sitenin sayfasını `Ctrl+F5` ile yenile.

## Sadece web tarayıcısı ile yükleme

Deponun **Code → Add file → Upload files** sayfasına gir. ZIP içindeki `.github`, `static`, `tests` klasörlerini ve kökteki Python dosyalarını **dosya yollarını bozmadan** yükle; değişen yolları kontrol ederek **Commit changes** yap. Github web arayüzü dosya üzerine yazmayı veya gizli klasörleri beklediğin şekilde işlemeyebilir; başarısız olursa GitHub Desktop yolunu kullan. `.github` klasörü yüklenmezse GitHub'da doğrudan `.github/workflows/yayin.yml` dosyasını açıp içeriğini yenisiyle değiştir.

## İlk kontrolde

- Başlangıç fiyatları: klavye 1.100 TL, mouse 1.000 TL. Üst sınırlar site içinde değiştirilebilir.
- Mouse'larda yalnızca PAW3311 ve üst sınıfı onaylı sensör listesi; sensörü bilinmeyenler görünmez.
- Tek kartta **en ucuz bulunan mağaza** ve başka teklifler varsa genişletilebilir fiyat listesi.
- Gecelik tarama: Türkiye saati 21.23. Eskiden hafta içi sabah yapılan tarama, ücretsiz API sorgu kotasını mağaza karşılaştırmasına ayırmak için kaldırıldı.
- `data/state.json` ve `data/feed.json` **korunduğunda** eski fiyat geçmişi silinmez.
- Mağazalarda listelenmeyen ürünlerin ve fiyatların eksik kalması mümkündür; ürün sayfasındaki güncel fiyatı son kez kontrol et.

> **Önemli:** Güncelleme sırasında `discovery.py` dosyasını repo köküne koymayı unutma. Bu dosya olmadan GitHub Actions içindeki testler başarısız olur. `.github/workflows/yayin.yml` dosyasını da güncelle.
