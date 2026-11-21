# Fiyat Avcısı — GitHub'a Yükle, Sürekli Açık Tut

Bir kez kuracaksın. Sonra siteyi açıp klavye/mouse fırsatlarına bakacaksın.

## 1) Ücretsiz GitHub deposu aç

1. [GitHub](https://github.com/) hesabına giriş yap.
2. Sağ üst **+ → New repository**.
3. Ad: **`fiyat-avcisi`**. **Public** seç, **Create repository**.
4. GitHub'ın **uploading an existing file** bağlantısını kullan.
5. Bu ZIP'i çıkardıktan sonra, `Fiyat-Avcisi` klasörünün **İÇİNDEKİ** tüm dosya ve klasörleri yükle. `.github` klasörünün de yüklendiğini kontrol et (zamanlayıcı burada). Bir üst klasörü tek başına yükleme.
6. Değişiklikleri `main` dalına **Commit changes** ile kaydet.

`main` dışında dal açtıysan `.github/workflows/yayin.yml` içindeki `branches: [main]` değerini kendi ana dalınla eşleştirmen gerekir.

## 2) SerpApi anahtarını gizli ekle

1. [SerpApi](https://serpapi.com/users/sign_up) hesabı açıp API anahtarını al.
2. GitHub deponda **Settings → Secrets and variables → Actions → New repository secret**.
3. Name: **`SERPAPI_KEY`** (tam olarak böyle, büyük harf).
4. Secret bölümüne anahtarı yapıştır; **Add secret**.

**API anahtarını README'ye, HTML'e, JSON dosyalarına veya GitHub'a doğrudan yapıştırma.** Anahtarı sadece Actions secret tutar.

## 3) GitHub Pages'i etkinleştir

1. Depoda **Settings → Pages**.
2. **Build and deployment → Source: GitHub Actions** seç.
3. Depoda **Settings → Actions → General** bölümünde Workflow permissions için **Read and write permissions** seçeneğine izin ver; veriyi `data/` klasörüne geri yazmak için gerekir. Kurum politikası engellerse depo yöneticisinin izin vermesi gerekir.

## 4) İlk gerçek taramayı yap

1. Depoda **Actions** bölümünü aç.
2. Solda **Fiyat Avcısı - Otomatik Tara ve Yayınla** iş akışını seç.
3. **Run workflow → Run workflow** ile başlat.
4. İş akışında `tara-ve-yayinla` çalışmasının yeşil tamamlandığını kontrol et.
5. Yayın adresini **Settings → Pages** sayfasında göreceksin. Genellikle `https://KULLANICI.github.io/fiyat-avcisi/` biçimindedir.

**İlk yüklemede API secret olmadan iş akışı çalışmışsa**, anahtarı ekledikten sonra yukarıdaki **Run workflow** adımını yeniden uygula.

## Bundan sonra nasıl çalışır?

- **Her gün 21.23**, **hafta içi ayrıca 09.23** Türkiye saatinde otomatik dört sorgu yapılır (planlanan saat; gecikebilir).
- Gerçek sonuçlar ve gözlem geçmişi `data/` altında tutulur, site otomatik yeniden yayınlanır.
- Senin bilgisayarın kapalı olabilir; telefondan da açabilirsin.
- Sağ üst yenile düğmesi yalnızca yayınlanmış ürün listesini tekrar okur; yeni ücretli API sorgusu başlatmaz.
- Fiyat sınırları: **klavye 1.100 TL**, **mouse 1.000 TL** (ikisi de dahil). **Tümü / Kablolu / Kablosuz** filtresi mevcut.

## Sorun çıkarsa

| Durum | Çözüm |
|---|---|
| Ekranda «İlk tarama bekleniyor» | Actions'da ilk gerçek taramayı çalıştır, API secret ekli mi kontrol et |
| Son taramada hata / eski sonuçlar | Actions kaydını incele, SerpApi bakiyesini ve kota durumunu doğrula |
| GitHub Pages 404 | Settings → Pages → Source = GitHub Actions; Actions dağıtım adımı tamamlanmış mı bak |
| Ürün sayısı sıfır | Bu, şu anki sorgularda koşullara uyan sonuç olmadığını da gösterebilir; otomatik tarama her mağazayı kapsamaz |
| Commit sırasında 403 | Actions → General → Workflow permissions = Read and write |
| Zamanlanmış taramalar durdu | GitHub Actions'ta iş akışı devre dışı mı kontrol et; halka açık ve 60 gündür etkinlik olmayan depolarda zamanlayıcı durdurulabilir |

**Kota hesabı:** Dört sorgu × her gün akşam + hafta içi sabah = 31 günlük ayda en çok yaklaşık **216 sorgu**. SerpApi'nin Kasım 2026 ücretsiz limiti **250/ay** olarak listelenir; manuel tarama ve kaynak koda yapılan push'lar ilave sorgu harcar. Bu limit değişebilir.

**Önemli:** GitHub Pages'i gerçek zamanlı bir sunucuya dönüştürmüyoruz. Sayfa 7/24 erişilebilir, ancak fiyatlar yalnızca planlı tarama başarıyla tamamlanınca güncellenir. Canlı tarama API anahtarı olmadan yapılamaz.
