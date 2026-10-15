# Kariyer Radarı (ücretsiz sürüm)

GitHub Actions günde iki kez yaklaşık 280 kaynağı tarar: 07:30 ve 19:30 (Türkiye saati). Bulduklarını sınıflandırır ve puanlar. Sonra panoyu GitHub Pages'te günceller, önemli fırsatları da Telegram'dan gönderir. Bunun hiçbir parçası ücret istemez.

```
config/        ← senin düzenleyeceğin ayarlar (kaynaklar, sorgular, anahtar kelimeler)
radar/         ← toplayıcı kodu (Python)
docs/          ← pano (GitHub Pages buradan yayınlanır) + docs/data/*.json veriler
state/         ← botun hafızası (sağlık kaydı, sayfa farkları, rotasyon) — elle dokunma
.github/workflows/radar.yml   ← zamanlayıcı
.github/workflows/kontrol.yml ← ayar dosyalarını bozarsan seni uyaran test
```

---

## Kurulum (yaklaşık 20 dakika)

### 1. Repoyu oluştur ve dosyaları yükle
1. GitHub'da **New repository** butonuna bas. Adı `kariyer-radari` olsun ve **Public** seç. Actions dakikaları ve Pages yalnızca herkese açık repoda sınırsız ve ücretsiz.
2. Zip'i bilgisayarında aç.
3. Repo sayfasında **Add file → Upload files** yolunu izle. Klasörün *içindekilerin hepsini* sürükle, `.github` klasörü dahil. Gizli klasörler görünmüyorsa:
   - **Mac:** Finder'da `Cmd+Shift+.`
   - **Windows:** Gezgin'de Görünüm → Gizli öğeler
4. **Commit changes** de.

> Git kullanıyorsan: `git init && git add . && git commit -m ilk && git branch -M main && git remote add origin https://github.com/KULLANICIADI/kariyer-radari.git && git push -u origin main`

### 2. Actions'a yazma izni ver
**Settings → Actions → General → Workflow permissions** altında **Read and write permissions** seç ve Save de.

### 3. Panoyu yayınla (GitHub Pages)
1. **Settings → Pages → Build and deployment** bölümünü aç.
2. Source olarak **Deploy from a branch**, Branch olarak **main**, klasör olarak **/docs** seç ve Save de.
3. 1–2 dakika içinde adresin hazır olur: `https://KULLANICIADI.github.io/kariyer-radari/`
4. Bu adresi `config/settings.json` içindeki `pano_url` alanına yaz. Telegram mesajlarındaki "Panoyu aç" bağlantısı bu adresi kullanır.

### 4. Telegram bildirimi (önerilir, 3 dakika)
1. Telegram'da **@BotFather** ile konuşma başlat, `/newbot` yaz ve bir isim ver. Sana bir **token** verir, onu sakla.
2. Yeni botunla konuşma başlat ve **/start** yaz.
3. Tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini aç. Çıkan metinde `"chat":{"id":123456789` gibi bir sayı göreceksin; bu senin **chat id**'n.
4. Repoda **Settings → Secrets and variables → Actions → New repository secret** yolunu izleyip iki secret ekle:
   - `TELEGRAM_BOT_TOKEN` → BotFather'ın verdiği token
   - `TELEGRAM_CHAT_ID` → bulduğun sayı

### 5. Yapay zekâ özetleri (isteğe bağlı ama kaliteyi belirgin artırır)
Yapay zekâ özetleri açıkken şunlar değişir:
- Özetler Türkçe ve 1–2 cümle olur.
- Kategori ve tür daha isabetli seçilir.
- Metindeki son başvuru tarihi daha iyi yakalanır.
- Sabah ve akşam özetleri editör gibi yazılır.

Anahtarı şöyle eklersin:
- **Gemini:** https://aistudio.google.com/apikey adresinden ücretsiz anahtar al ve `GEMINI_API_KEY` adıyla secret olarak ekle.
- **Yedek (Groq):** https://console.groq.com/keys adresinden anahtar al ve `GROQ_API_KEY` adıyla ekle. Gemini düşerse Groq'a geçilir.

Anahtar hiç yoksa sistem kural tabanlı modda çalışmaya devam eder, hiçbir şey kırılmaz.

### 6. İlk çalıştırma
**Actions → Kariyer Radarı → Run workflow** yolunu izle ve `auto` seçip çalıştır. 2–4 dakika sürer. Yeşil tik görürsen panoyu yenile.

> İlk çalıştırmada RSS'i olmayan sayfalar yalnızca "taban çizgisi" kaydeder. Bu sayede eski duyurular yeni gibi gelmez. Bu sayfalardaki yeni duyurular ikinci taramadan itibaren gelir.

---

## Günlük kullanım

| Ne zaman | Ne olur |
|---|---|
| 07:30 | Sabah taraması. Her taramada bakılan kaynaklar, sabah kaynakları, Google Haberler sorguları, 15 Sakarya şirketi/vakfı (sırayla) ve HF Daily Papers taranır. |
| Pazartesi 07:30 | Sabah taramasına ek olarak haftalık kaynaklar, OpenAlex akademik trendler (global + Türkiye, 4 alan) ve takip ettiğin kişiler de taranır. Sürekli hata veren kaynaklar da bu taramada yeniden denenir. |
| 19:30 | Akşam taraması. Devpost'taki online hackathonlar da eklenir. |
| Son başvuruya 3 gün kala | Telegram'a "⏰ Kapanmak üzere" uyarısı gelir, her fırsat için bir kez. |

GitHub'ın zamanlayıcısı yoğun saatlerde 5–30 dakika gecikebilir, bu normal.

**Panoda** "İlgileniyorum", "Başvurdum", "Gizle" ve yıldız gibi işaretler **o tarayıcıda** saklanır. Telefona taşımak için alttaki **Yedekle** düğmesiyle dosya indir, öbür cihazda **Yedeği yükle** ile aç. Kaydettiğin fırsatlar 45 gün sonra arşive düşse bile panoda kalır.

---

## Ayarları değiştirme (kod bilmeden)

GitHub'da dosyayı aç, kalem simgesine bas, düzenle ve Commit de. Sonra **Kontrol** testi çalışır. Kırmızı çıkarsa büyük ihtimalle bir virgül ya da tırnak eksiktir.

| İstediğin | Dosya | Örnek |
|---|---|---|
| Yeni kaynak eklemek | `config/sources.json` | `{"id":"src-300","name":"X Blog","group":"Türkiye teknoloji haberleri","url":"https://x.com","rss":"https://x.com/feed","freq":"aksam"}` <br>`freq` değeri `her-tarama`, `sabah`, `aksam` ya da `haftalik` olabilir. RSS yoksa `rss` alanını boş bırak; sayfa farkı ile takip edilir. |
| Kaynağı kapatmak | `config/sources.json` | Kaynağa `"disabled": true` ekle |
| Yeni arama konusu | `config/queries.json` | `{"q":"\"Siber Vatan\" başvuru when:7d","slot":"haftalik","kind":"sertifika"}` |
| Bir kişiyi izlemek | `config/queries.json` → `people_watch.names` | `["Selçuk Bayraktar"]` |
| Sakarya şirketi eklemek | `config/companies.json` | `"local": true` olanlar rotasyona otomatik girer |
| Kelime ile filtre | `config/keywords.json` | `block` listesindeki kelimeler başlıkta geçerse kayıt atılır. `boost` listesindekiler puanı artırır. |
| Bildirim yoğunluğu | `config/settings.json` → `notify` | `min_score` değerini yükseltirsen daha az bildirim alırsın |
| Saklama süresi | `config/settings.json` → `retention_days` | Varsayılan 45 gün. Eskiyen kayıtlar `docs/data/gecmis/AAAA-AA.json` dosyasına taşınır. |
| Yapay zekâ modeli | `config/settings.json` → `llm` | Google model adını değiştirirse buradan güncelle |

**Kaynak sağlığı:** Bir kaynak 3 taramadır yanıt vermiyorsa iki yerde görünür:
- Panonun Kaynaklar sekmesinde adının yanında ⚠ çıkar.
- Özetin sonunda uyarı olarak yer alır.

5 kez üst üste hata veren kaynak yalnızca haftalık taramada denenir. Ayrıntılar `state/health.json` dosyasında.

---

## Bilmen gereken 3 şey

1. **Repo herkese açık kalmalı.** Böylece her şey ücretsiz olur. Buna karşılık:
   - Repoya şifre ya da anahtar **asla** yazma, hepsi Secrets'a girer.
   - Panodaki işaretlerin repoya değil kendi tarayıcına yazılır, yani kimse göremez.
2. **60 gün kuralı:** GitHub, 60 gün hiç değişmeyen repolarda zamanlayıcıyı kapatır. Bot her taramada veri commit ettiği için bu pratikte olmaz. Yine de bir gün tarama durursa **Actions** sekmesinde "Enable workflow" de.
3. **Ücretsiz yapay zekâ katmanının sınırları değişebilir.** Ücretsiz katmanda gönderilen metin, sağlayıcının modelini geliştirmek için kullanılabilir. Buraya giden şey yalnızca herkese açık haber başlıkları ve özetler, kişisel verin değil. Sınır aşılırsa o tarama kural tabanlı modla tamamlanır.

---

## Bilgisayarında denemek (isteğe bağlı)

```bash
pip install -r requirements.txt
python -m tests.test_offline          # ağsız uçtan uca test (14 kontrol)
python -m radar --slot sabah --dry-run   # gerçek tarama, dosya yazmadan
python -m http.server -d docs 8000    # panoyu http://localhost:8000 adresinde aç
```
