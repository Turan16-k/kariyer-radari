# Claude haftalık analiz görevi (isteğe bağlı)

Bu görev Claude'da "zamanlanmış görev" olarak haftada bir kez çalışır. Yeniden tarama yapmaz; GitHub'daki hazır veriyi okuyup yorumlar. Bu yüzden maliyeti düşüktür.
Kurmak istersen Claude'a şunu yaz: "Haftalık görevimi CLAUDE_HAFTALIK.md'deki gibi güncelle, repo adresim: https://github.com/KULLANICIADI/kariyer-radari"

## Görev metni

Kariyer Radarı haftalık analizi. Tarama YAPMA. Şu dosyaları oku:
- https://raw.githubusercontent.com/KULLANICIADI/kariyer-radari/main/docs/data/items.json (son 7 gün: addedAt)
- https://raw.githubusercontent.com/KULLANICIADI/kariyer-radari/main/docs/data/briefs.json
- https://raw.githubusercontent.com/KULLANICIADI/kariyer-radari/main/state/health.json

Bunlardan şunları çıkar:
1. Haftanın 5 önemli gelişmesi: Türkiye ağırlıklı, en az 2/3'ü Türkiye olsun.
2. Önümüzdeki 14 günde kapanan fırsatlar.
3. Akademik trend özeti: yz, siber, yazılım ve sistem alanları; global ve Türkiye ayrı.
4. Bir "haftanın becerisi" önerisi.
5. 3 taramadır yanıt vermeyen kaynaklar için yerine geçebilecek alternatifler.

Sonucu Kariyer Radarı Claude panosundaki (https://claude.ai/artifact/9bdwMmjALYQHfDEXagz1Zj) insights koleksiyonuna yeni bir belge olarak yaz. Kullanıcıya soru sorma.
