"""Ağ olmadan uçtan uca test: tüm HTTP çağrıları sahte yanıtlarla değiştirilir.
Çalıştır:  python -m tests.test_offline   (repo kökünden)"""
import json, shutil, sys, tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp())
shutil.copytree(ROOT, tmp / "r", ignore=shutil.ignore_patterns(".git", "__pycache__"))
sys.path.insert(0, str(tmp / "r"))
shutil.rmtree(tmp / "r" / "state", ignore_errors=True)

from radar import fetch, util  # noqa: E402

T = date.fromisoformat(util.today())
D = lambda n: (T + timedelta(days=n))
rfc = lambda d: d.strftime("%a, %d %b %Y 08:00:00 +0300")
TRM = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

def rss(items):
    x = "".join(f"<item><title>{t}</title><link>{l}</link><description>{d}</description><pubDate>{rfc(p)}</pubDate>{s}</item>"
                for t, l, d, p, s in items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>{x}</channel></rss>'

dl = D(5)
FEEDS = {
 "webrazzi": rss([
   ("Sakarya merkezli yazılım girişimi 2 milyon dolar yatırım aldı", "https://webrazzi.com/2026/a-yatirim/?utm_source=rss", "Adapazarı'nda kurulan girişim tohum yatırım turunu tamamladı.", T, ""),
   ("Türkiye'de yapay zeka yatırımları rekor kırdı", "https://webrazzi.com/2026/yz-rekor", "Türk girişimleri yapay zeka alanında...", T, ""),
   ("Futbol transfer haberleri", "https://webrazzi.com/x", "", T, ""),
   ("Çok eski haber", "https://webrazzi.com/eski", "yapay zeka", D(-40), ""),
 ]),
 "gnews": rss([
   (f"Öğrencilere yönelik yapay zeka hackathonu başvuruları açıldı - Anadolu Ajansı", "https://news.google.com/rss/articles/abc1", f"Son başvuru {dl.day} {TRM[dl.month]}. Online yapılacak.", T, "<source url='https://aa.com.tr'>Anadolu Ajansı</source>"),
   (f"Türkiye'de yapay zeka yatırımları rekor kırdı! - Hürriyet", "https://news.google.com/rss/articles/abc2", "", T, "<source url='https://hurriyet.com.tr'>Hürriyet</source>"),
   ("Sakarya Üniversitesi siber güvenlik kampı düzenliyor - Sakarya Yenigün", "https://news.google.com/rss/articles/abc3", "SAÜ öğrencilerine ücretsiz bootcamp", T, "<source url='https://x'>Sakarya Yenigün</source>"),
 ]),
}
PAGE1 = '<html><body><main><a href="/haber/1">Sakarya Teknokent yeni kuluçka programı başvuruları başladı</a><a href="/login">Giriş</a></main></body></html>'
PAGE2 = PAGE1.replace('</main>', '<a href="/haber/2">Sakarya Teknokent firmaları yazılım stajyeri arıyor duyurusu</a></main>')
DEVPOST = {"hackathons": [{"title": "Global AI Agents Hackathon", "url": "https://ai-agents.devpost.com/", "displayed_location": {"location": "Online"},
            "prize_amount": "$<span>50,000</span>", "themes": [{"name": "Machine Learning/AI"}], "registrations_count": 4200,
            "submission_period_dates": f"Oct 01 - {D(20).strftime('%b %d, %Y')}"},
           {"title": "NYC Local Jam", "url": "https://n.devpost.com", "displayed_location": {"location": "New York"}, "registrations_count": 5}]}
HF = [{"paper": {"id": "2610.01234", "title": "Agentic Reasoning at Scale", "summary": "We present...", "upvotes": 88, "publishedAt": f"{T}T00:00:00Z"}}]
OA = {"results": [{"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/x", "title": "Intrusion detection with transformers", "publication_date": str(D(-30)),
       "cited_by_count": 12, "primary_location": {"source": {"display_name": "IEEE Access"}}, "authorships": [{"institutions": [{"display_name": "Sakarya University", "country_code": "TR"}]}]}]}

class R:
    def __init__(s, body, st=200): s.content = body.encode() if isinstance(body, str) else body; s.text = s.content.decode(); s.status_code = st; s.headers = {}
    def json(s): return json.loads(s.text)
    def raise_for_status(s): pass

calls = {"page": 0}
def fake_get(url, **kw):
    if "news.google.com" in url: return R(FEEDS["gnews"])
    if "webrazzi.com/feed" in url: return R(FEEDS["webrazzi"])
    if "devpost.com/api" in url: return R(json.dumps(DEVPOST if "page=1" in url else {"hackathons": []}))
    if "huggingface.co/api" in url: return R(json.dumps(HF))
    if "openalex.org" in url: return R(json.dumps(OA))
    if "sakaryateknokent" in url:
        calls["page"] += 1
        return R(PAGE1 if calls["page"] == 1 else PAGE2)
    raise ConnectionError("sahte: ağ yok " + url[:50])
fetch.get = fake_get

# Test için kaynak listesini küçült
cfg = tmp / "r" / "config" / "sources.json"
src = [{"id": "s1", "name": "Webrazzi", "group": "Türkiye teknoloji haberleri", "url": "https://webrazzi.com", "rss": "https://webrazzi.com/feed/", "freq": "her-tarama"},
       {"id": "s2", "name": "Sakarya Teknokent", "group": "Yerel (Sakarya/Kocaeli)", "url": "https://sakaryateknokent.com/duyurular", "freq": "her-tarama"},
       {"id": "s3", "name": "Kırık kaynak", "group": "Global teknoloji", "url": "https://broken.example", "rss": "https://broken.example/rss", "freq": "her-tarama"}]
cfg.write_text(json.dumps(src, ensure_ascii=False))

from radar import main as M  # noqa: E402
M.main(["--slot", "sabah", "--weekly", "--no-notify"])
d = tmp / "r" / "docs" / "data"
items = json.loads((d / "items.json").read_text())
new = [i for i in items if i.get("score") is not None]
by = {i["title"]: i for i in new}
print("\n--- YENİ KAYITLAR ---")
for i in new: print(f'{i["score"]:>2} {i["kind"]:<10} {i["scope"]:<6} {i.get("city",""):<8} {i.get("deadline",""):<10} {i["title"][:60]}  links={len(i.get("links",[]))}')

ok = lambda c, m: print(("✓ " if c else "✗ ") + m) or c
res = [
 ok("Futbol transfer haberleri" not in by, "engelli kelime elendi"),
 ok("Çok eski haber" not in by, "eski haber elendi"),
 ok(by.get("Sakarya merkezli yazılım girişimi 2 milyon dolar yatırım aldı", {}).get("city") == "Sakarya", "Sakarya yerelliği"),
 ok("yatirim" in by.get("Sakarya merkezli yazılım girişimi 2 milyon dolar yatırım aldı", {}).get("cats", []), "yatırım kategorisi"),
 ok(any(i["title"].startswith("Türkiye'de yapay zeka yatırımları rekor") and i.get("links") for i in new), "çapraz kaynak birleştirme (dedup)"),
 ok(by.get("Öğrencilere yönelik yapay zeka hackathonu başvuruları açıldı", {}).get("deadline") == str(dl), "son başvuru tarihi çıkarımı"),
 ok(by.get("Öğrencilere yönelik yapay zeka hackathonu başvuruları açıldı", {}).get("kind") == "hackathon", "hackathon türü"),
 ok("Agentic Reasoning at Scale" in by and by["Agentic Reasoning at Scale"]["kind"] == "akademik", "HF makalesi akademik"),
 ok(by.get("Intrusion detection with transformers", {}).get("origin") == "tr", "OpenAlex Türkiye makalesi"),
 ok("Sakarya Teknokent yeni kuluçka programı başvuruları başladı" not in by, "sayfa farkı: ilk çalıştırma taban çizgisi"),
]
health = json.loads((tmp / "r" / "state" / "health.json").read_text())
res.append(ok(health.get("s3", {}).get("fails") == 1, "kırık kaynak sağlık kaydına düştü"))
# 2. çalıştırma: sayfa farkı yeni bağlantıyı yakalamalı, tekrarlar eklenmemeli
n1 = len(items)
M.main(["--slot", "aksam", "--no-notify"])
items2 = json.loads((d / "items.json").read_text())
t2 = {i["title"] for i in items2}
res.append(ok("Sakarya Teknokent firmaları yazılım stajyeri arıyor duyurusu" in t2, "sayfa farkı: yeni duyuru yakalandı"))
res.append(ok(len(items2) - n1 in (1, 2), f"2. turda tekrar eklenmedi (+{len(items2)-n1})"))
res.append(ok("Global AI Agents Hackathon" in t2 and next(i for i in items2 if i["title"]=="Global AI Agents Hackathon").get("deadline")==str(D(20)), "Devpost (akşam) + son tarih"))
b = json.loads((d / "briefs.json").read_text())[0]
print("\nÖZET:", b["title"], b["when"]); [print(" •", h) for h in b["highlights"]]
print("\nSONUÇ:", sum(bool(r) for r in res), "/", len(res))
sys.exit(0 if all(res) else 1)
