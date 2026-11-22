# Fiyat Avcısı v3.0 kurulumu (mevcut GitHub sitesi)

**Eski GitHub deposunu veya geçmiş Actions kayıtlarını silme.** Aynı adres üzerinde yeni sürüm yayınlanır.

1. Bu ZIP'i aç. İçindeki `.github`, `static`, `tests` klasörleriyle `.py` ve diğer dosyaları GitHub Desktop üzerinden klonlanmış `fiyat-avcisi-github` dizininin köküne kopyala. Soru gelirse aynı adlı dosyaları değiştir.
2. **`data` klasörüne dokunma.** Eski v2 `data/state.json` silinmeyecek; fakat v3 Amazon sitesinde eski Google sonuçları kullanılmayacak.
3. GitHub Desktop → Summary: `Fiyat Avcısı v3.0 - Amazon Türkiye ürün kataloğu` → **Commit to main** → **Push origin**.
4. GitHub → Settings → Secrets and variables → Actions bölümüne Creators API erişimin varsa şu üç secret'ı ekle:
   - `AMAZON_CREATORS_CLIENT_ID`
   - `AMAZON_CREATORS_CLIENT_SECRET`
   - `AMAZON_ASSOCIATE_TAG` (Türkiye Amazon Gelir Ortaklığı takip kodu)
5. GitHub → Settings → Pages bölümünde **Source = GitHub Actions** seçili kalsın.
6. GitHub → Actions → **Fiyat Avcısı v3 - Amazon Türkiye** → **Run workflow**. Test, tarama ve yayınlama adımları yeşil olursa site aynı adreste güncellenir.

**Gerçek ürünler görünmüyorsa:** Credentials olmadan veya API izni olmadan v3 gerçek Amazon verisi çekemez. Eski SerpApi anahtarı bu yeni sürümde hiçbir işlev görmez. Amazon için "API bağlantısı bekleniyor" gösterilmesi beklenen ve güvenli davranıştır.

**Ücretsiz Amazon erişimi konusunda:** Amazon Associates'e ücretsiz kayıt olunabilir; Creators API kullanım hakkı ve sürekliliği Amazon uygunluk şartlarına bağlıdır. Bütün Amazon ürünlerini döken ücretsiz, sınırsız bir API garantisi yoktur.

**Denemek için:** Windows'ta `ORNEK_GORUNUM.bat` dosyasını aç. Bu yalnızca tasarım ve filtre testidir; fiyatlar örnektir. Bu örnekler yayımlanan siteye karışmaz.
