# Fiyat Avcısı v2.7 – eksik sonuç onarımı

**Bu paket, site görünümünü değiştirmez.** v2.6'nın onaylı dokuz mağaza kısıtlaması, sensör alt sınırı, fiyat kontrolleri ve mevcut GitHub Pages yayını korunur.

## Düzeltilen akış

- Google Shopping bazen mağaza yerine Google ürün sayfası bağlantısı verir. Bu ürünler doğrudan yayınlanmaz; geçerli Google ürün kimliği varsa *mağaza tekliflerini doğrulamak için* sıraya alınır.
- SerpApi Google Product ayrıntı sonucundan **doğrudan HTTPS mağaza bağlantısı ve ürün fiyatı doğrulanan** teklifler ekrana alınır. Diğer mağazalar ve sahte/Google bağlantıları elenir.
- James Donkey JDM11 ve MageGee Scout için açıkça doğrulanmış PAW3311 sensörü, başlıkta sensör yazmadığında da tanınır. Diğer modeller için tahmin yapılmaz. Ayrıntı sayfasında yazılı ve modelle eşleşen sensör bilgisi de kullanılabilir.
- Satıcı başlığı kısaysa ama marka + model kesin eşleşiyorsa ürün adı güvenilir tam başlıkla gösterilebilir.
- GitHub Actions kayıtlarında, kaç ham ürün bulunduğu, kaçının doğrudan mağaza bağlantısıyla kabul edildiği, kaçının ayrıntılı teklif sorgusuna aday olduğu gibi tanı sayıları yazdırılır.

## Mevcut depona nasıl yüklersin?

1. Paket içindeki `scanner.py` ve `cloud_publish.py` dosyalarını klonlanmış `fiyat-avcisi` klasörünün köküne kopyalayıp mevcut dosyaları değiştir.
2. `tests/test_recovery.py` dosyasını projenin `tests/` klasörüne kopyala.
3. `data` klasörüne **dokunma**. GitHub Desktop'ta Summary alanına `Fiyat Avcısı v2.7 - Eksik ürün tarama düzeltmesi` yaz; **Commit to main**, ardından **Push origin** yap.
4. GitHub → Actions → Fiyat Avcısı - Otomatik Tara ve Yayınla → **Run workflow** ile test et. `Ürünleri tara ve JSON verisini oluştur` adımında `Tarama tanisi` satırı görünür.
5. Sitede Ctrl+F5 ile yenile. Sonuçları mutlaka mağazaların gerçek ürün sayfasındaki fiyatla karşılaştır.

## Önemli sınırlamalar

Bu düzeltme arama kapsamasını genişletir ancak **tüm modelleri ve mutlak en düşük fiyatı garanti etmez**. SerpApi'nin Google Shopping aramalarında kaynaklar eksik olabilir; ürünün sensörü doğrulanamaz veya onaylı mağazadan doğrudan teklif bağlantısı alınamazsa ürün yayınlanmaz. Ücretsiz kota nedeniyle günde en fazla bir ek mağaza ayrıntı sorgusu yapılır; sonuçların birikmesi zaman alabilir. Yeni taramalar kota tüketir. API anahtarı ZIP içinde bulunmaz, GitHub Secrets'ta kalır.

39 yerel test geçti. **Gerçek SerpApi API anahtarıyla uçtan uca canlı doğrulama yapılmadı.**
