# Fiyat Avcısı v2.6 — GitHub Desktop güncellemesi

Bu sürümde yalnızca seçtiğin dokuz mağaza yayına alınır. Sol taraftaki gereksiz kategori menüsü de kaldırıldı. Fiyat geçmişini **silme**.

1. Bu ZIP'i bilgisayarına indir ve **Tümünü ayıkla**.
2. GitHub Desktop'ta **Current repository → fiyat-avcisi** seçili olsun. **Repository → Show in Explorer** ile yerel klonunu aç.
3. ZIP'in içindeki `.github`, `static`, `tests` klasörlerini ve diğer dosyaları **klon klasörünün içine** kopyala. Gelen değiştirme sorularını onayla.
4. ZIP'in içindeki **`merchants.py` yeni dosyadır**. Mutlaka projenin en üst seviyesinde (`scanner.py` ile yan yana) görünmeli.
5. **`data/` klasörünü değiştirme, silme veya ZIP ile üzerine yazma.** Bu güncelleme arşivinde `data/` yok.
6. GitHub Desktop'ta Summary alanına `Fiyat Avcısı v2.6 - Onaylı mağazalar` yaz, **Commit to main**, ardından **Push origin** yap.
7. GitHub → **Actions** bölümünde en yeni **Fiyat Avcısı - Otomatik Tara ve Yayınla** çalıştırmasının yeşil tikle bitmesini kontrol et. Sayfada `Ctrl+F5` yap.

## Değişiklikler

- İzin verilen siteler: Amazon Türkiye, Trendyol, Hepsiburada, n11, Pazarama, idefix, İncehesap, İtopya, Gaming.Gen.TR.
- Teklifin gerçek HTTPS adresi bu sitelerden değilse sonuç gösterilmeyecek; mağaza adı tek başına yeterli değil.
- Eski durum dosyasında bulunan bilinmeyen mağazalar da yeni yayında filtrelenecek.
- Çelişkili fiyat alanları kabul edilmeyecek; yalnızca bulunan **onaylı teklifler** ucuzdan pahalıya sıralanacak.
- Sol menü kaldırıldı; Hepsi / Klavye / Mouse filtreleri üstte kaldı.
- Var olan limitler (ilk açılışta klavye 1.100 TL, mouse 1.000 TL) ve sensör filtresi aynı.

**Önemli:** Bu güncelleme dokuz sitenin ürünlerini doğrudan ve eksiksiz tarayan yeni bir altyapı eklemez. Mevcut SerpApi sonuçlarını güvenilir alan adlarıyla sınırlar. Bu yüzden ürün sayısı azalabilir. Pazaryeri içindeki üçüncü taraf satıcıları ayrıca kontrol et. Gerçek API anahtarıyla canlı tarama, yalnızca GitHub'daki sonraki çalışma ile test edilebilir.
