# Kariyer Radarı https://turan16-k.github.io/kariyer-radari/
### 5. Yapay zekâ özetleri
Yapay zekâ özetleri açıkken şunlar değişir:
- Özetler Türkçe ve 1–2 cümle olur.
- Kategori ve tür daha isabetli seçilir.
- Metindeki son başvuru tarihi daha iyi yakalanır.
- Sabah ve akşam özetleri editör gibi yazılır.
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

1. **Repo herkese açık kalmalı.** Böylece her şey ücretsiz olur. Buna karşılık:
   - Repoya şifre ya da anahtar **asla** yazma, hepsi Secrets'a girer.
   - Panodaki işaretlerin repoya değil kendi tarayıcına yazılır, yani kimse göremez.
2. **60 gün kuralı:** GitHub, 60 gün hiç değişmeyen repolarda zamanlayıcıyı kapatır. Bot her taramada veri commit ettiği için bu pratikte olmaz. Yine de bir gün tarama durursa **Actions** sekmesinde "Enable workflow" de.
3. **Ücretsiz yapay zekâ katmanının sınırları değişebilir.** Ücretsiz katmanda gönderilen metin, sağlayıcının modelini geliştirmek için kullanılabilir. Buraya giden şey yalnızca herkese açık haber başlıkları ve özetler, kişisel verin değil. Sınır aşılırsa o tarama kural tabanlı modla tamamlanır.
