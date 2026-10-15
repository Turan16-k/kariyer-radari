"""Toplayıcılar. Her biri ham girdi listesi döndürür:
{title, url, summary, date, source, sourceId, [kind, deadline, scope, field, origin, venue, eventDate, mode]}
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from urllib.parse import quote, quote_plus, urljoin, urlsplit

import feedparser
from bs4 import BeautifulSoup

from . import fetch
from .util import SETTINGS, STATE, clean_html, load_json, log, save_json, to_date, today

MAX_PER_SOURCE = SETTINGS.get("max_items_per_source", 25)


# ---------- RSS / Atom ----------
def rss(src: dict) -> list[dict]:
    url = src["rss"]
    try:
        r = fetch.get(url, accept="application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8")
    except fetch.NotModified:
        fetch.mark(src["id"], src["name"], True, 0)
        return []
    return _feed_entries(feedparser.parse(r.content), src)


def _feed_entries(feed, src: dict) -> list[dict]:
    if feed.bozo and not feed.entries:
        raise ValueError(f"RSS çözülemedi: {feed.bozo_exception!r}"[:150])
    limit = SETTINGS.get("max_items_per_academic_feed", 6) if src.get("group", "").startswith("Akademik") else MAX_PER_SOURCE
    out = []
    for e in feed.entries[:limit]:
        link = e.get("link") or ""
        title = clean_html(e.get("title", ""), 220)
        if not title or not link:
            continue
        summary = e.get("summary") or (e.get("content") or [{}])[0].get("value", "")
        out.append({
            "title": title, "url": link, "summary": clean_html(summary, 420),
            "date": to_date(e.get("published_parsed") or e.get("updated_parsed")) or today(),
            "source": src["name"], "sourceId": src["id"],
        })
    fetch.mark(src["id"], src["name"], True, len(out))
    return out


# ---------- Google News RSS arama ----------
def gnews(query: str, label: str, kind: str | None = None, limit: int = 12) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=tr&gl=TR&ceid=TR:tr"
    r = fetch.get(url, conditional=False)
    feed = feedparser.parse(r.content)
    out = []
    for e in feed.entries[:limit]:
        title = clean_html(e.get("title", ""), 240)
        publisher = (e.get("source") or {}).get("title") or ""
        if publisher and title.endswith(" - " + publisher):
            title = title[: -len(publisher) - 3]
        summary = clean_html(e.get("summary", ""), 300)
        if summary.startswith(title[:40]):
            summary = ""
        item = {"title": title, "url": e.get("link", ""), "summary": summary,
                "date": to_date(e.get("published_parsed")) or today(),
                "source": publisher or "Google Haberler", "sourceId": "gnews", "via": label}
        if kind:
            item["kindHint"] = kind
        if re.search(r"[ğşıİĞŞ]", title):
            item["lang"] = "tr"
        out.append(item)
    fetch.mark("gnews", "Google Haberler RSS", True, len(out))
    return out


# ---------- RSS'i olmayan sayfalar: sayfa farkı ----------
_NAV = re.compile(r"(giris|login|kayit ol|iletisim|hakkimizda|cerez|kvkk|gizlilik|privacy|cookie|facebook|twitter|instagram|linkedin|youtube|whatsapp|#|javascript:|mailto:|tel:)", re.I)


def pagediff(src: dict) -> list[dict]:
    """Sayfadaki bağlantıları önceki taramayla karşılaştırır; yeni çıkanları döndürür.
    İlk çalıştırmada yalnızca taban çizgisi kaydeder (eski içerik bildirim yağmuru yapmasın)."""
    url = src["url"]
    path = STATE / "pages" / (hashlib.md5(url.encode()).hexdigest()[:16] + ".json")
    seen = load_json(path, None)
    try:
        r = fetch.get(url)
    except fetch.NotModified:
        fetch.mark(src["id"], src["name"], True, 0)
        return []
    head = r.content[:400].lstrip().lower()
    if b"<rss" in head or b"<feed" in head or b"<?xml" in head or "xml" in r.headers.get("Content-Type", ""):
        return _feed_entries(feedparser.parse(r.content), src)  # aslında RSS
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["nav", "footer", "header", "script", "style", "aside", "form"]):
        tag.decompose()
    host = urlsplit(url).netloc
    links = {}
    for a in soup.find_all("a", href=True):
        text = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        href = urljoin(url, a["href"]).split("#")[0]
        if len(text) < 22 or len(text) > 220 or _NAV.search(href) or _NAV.search(text[:20]):
            continue
        if urlsplit(href).netloc and host.split(".")[-2] not in urlsplit(href).netloc:
            continue  # dış bağlantıları alma
        links.setdefault(href, text)
    if not links:
        raise ValueError("Sayfada bağlantı bulunamadı (JS ile yükleniyor olabilir)")
    if seen is None:
        save_json(path, {"url": url, "links": sorted(links)[:600], "since": today()})
        fetch.mark(src["id"], src["name"], True, 0)
        return []
    old = set(seen.get("links", []))
    new = [(h, t) for h, t in links.items() if h not in old][:10]
    save_json(path, {"url": url, "links": sorted(set(links) | old)[-800:], "since": seen.get("since")})
    out = [{"title": t, "url": h, "summary": "", "date": today(), "source": src["name"], "sourceId": src["id"]}
           for h, t in new]
    fetch.mark(src["id"], src["name"], True, len(out))
    return out


# ---------- Devpost (online hackathonlar) ----------
def _devpost_deadline(s: str):
    # "Oct 01 - Nov 12, 2026" / "Sep 20 - 22, 2026"
    m = re.search(r"([A-Z][a-z]{2})\s+(\d{1,2}),\s*(20\d\d)\s*$", s or "")
    m2 = re.search(r"-\s*(\d{1,2}),\s*(20\d\d)\s*$", s or "")
    try:
        if m:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").date().isoformat()
        if m2:
            mon = re.match(r"([A-Z][a-z]{2})", s).group(1)
            return datetime.strptime(f"{mon} {m2.group(1)} {m2.group(2)}", "%b %d %Y").date().isoformat()
    except (ValueError, AttributeError):
        return None
    return None


def devpost() -> list[dict]:
    out = []
    for page in (1, 2):
        r = fetch.get(f"https://devpost.com/api/hackathons?status[]=upcoming&status[]=open&page={page}", conditional=False,
                      accept="application/json")
        for h in r.json().get("hackathons", []):
            loc = (h.get("displayed_location") or {}).get("location", "")
            if "online" not in loc.lower() and "turk" not in loc.lower():
                continue
            prize = clean_html(h.get("prize_amount", ""), 40)
            themes = ", ".join(t.get("name", "") for t in h.get("themes", [])[:3])
            regs = h.get("registrations_count", 0)
            out.append({
                "title": h.get("title", ""), "url": h.get("url", ""), "kind": "hackathon", "scope": "global",
                "summary": f"Online hackathon · Ödül: {prize or '—'} · Konular: {themes or '—'} · {regs} kayıt · {h.get('submission_period_dates', '')}",
                "deadline": _devpost_deadline(h.get("submission_period_dates", "")), "mode": "Online",
                "date": today(), "source": "Devpost", "sourceId": "devpost", "popularity": regs,
            })
    out.sort(key=lambda x: -x.get("popularity", 0))
    fetch.mark("devpost", "Devpost API", True, len(out))
    return out[:15]


# ---------- Hugging Face Daily Papers ----------
def hf_papers() -> list[dict]:
    r = fetch.get("https://huggingface.co/api/daily_papers?limit=50", conditional=False, accept="application/json")
    papers = r.json()
    papers.sort(key=lambda p: -(p.get("paper", {}).get("upvotes", 0)))
    out = []
    for p in papers[:10]:
        pp = p.get("paper", {})
        pid = pp.get("id", "")
        out.append({
            "title": clean_html(pp.get("title") or p.get("title", ""), 220),
            "url": f"https://huggingface.co/papers/{pid}", "summary": clean_html(pp.get("summary", ""), 420),
            "kind": "akademik", "field": "yz", "origin": "global", "scope": "global",
            "venue": f"HF Daily Papers · {pp.get('upvotes', 0)} oy", "date": to_date(pp.get("publishedAt")) or today(),
            "source": "Hugging Face Daily Papers", "sourceId": "hf-papers",
            "links": [{"t": "arXiv", "u": f"https://arxiv.org/abs/{pid}"}] if pid else [],
        })
    fetch.mark("hf-papers", "Hugging Face Daily Papers API", True, len(out))
    return out


# ---------- OpenAlex: alana göre çok atıf alan yeni makaleler (global + Türkiye) ----------
OA_FIELDS = {
    "yz": "primary_topic.subfield.id:1702",
    "yazilim": "primary_topic.subfield.id:1712",
    "sistem": "primary_topic.subfield.id:1705|1708",
    "siber": "primary_topic.field.id:17,title_and_abstract.search:security OR malware OR intrusion OR cyberattack",
}


def openalex() -> list[dict]:
    out = []
    since = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
    mail = SETTINGS.get("contact_email") or "radar@example.com"
    for field, flt in OA_FIELDS.items():
        for origin in ("tr", "global"):
            f = f"{flt},from_publication_date:{since},type:article|preprint"
            if origin == "tr":
                f += ",authorships.institutions.country_code:TR"
            url = (f"https://api.openalex.org/works?filter={quote(f, safe=':,|.-')}&sort=cited_by_count:desc&per-page=5"
                   f"&select=id,doi,title,publication_date,cited_by_count,primary_location,authorships&mailto={mail}")
            try:
                r = fetch.get(url, conditional=False, accept="application/json")
            except Exception as ex:  # noqa: BLE001
                log("openalex", field, origin, ex)
                continue
            for w in r.json().get("results", []):
                loc = w.get("primary_location") or {}
                venue = ((loc.get("source") or {}).get("display_name")) or ""
                insts = []
                for a in w.get("authorships", [])[:6]:
                    for i in a.get("institutions", []):
                        if origin == "tr" and i.get("country_code") != "TR":
                            continue
                        if i.get("display_name") and i["display_name"] not in insts:
                            insts.append(i["display_name"])
                out.append({
                    "title": clean_html(w.get("title") or "", 240),
                    "url": w.get("doi") or loc.get("landing_page_url") or w.get("id"),
                    "summary": f"{w.get('cited_by_count', 0)} atıf · {', '.join(insts[:3])}",
                    "kind": "akademik", "field": field, "origin": origin, "scope": "tr" if origin == "tr" else "global",
                    "venue": venue, "date": w.get("publication_date") or today(),
                    "source": "OpenAlex", "sourceId": "openalex",
                })
            fetch.polite_sleep(0.2)
    seen, uniq = set(), []
    for x in out:  # aynı makale iki listede varsa Türkiye kaydı kalır
        if x["title"] and x["url"] not in seen:
            seen.add(x["url"])
            uniq.append(x)
    fetch.mark("openalex", "OpenAlex API", True, len(uniq))
    return uniq


# ---------- Sessionize: konuşmacılar ----------
def sessionize(event_id: str, event_name: str) -> list[dict]:
    r = fetch.get(f"https://sessionize.com/api/v2/{event_id}/view/Speakers", conditional=False, accept="application/json")
    people = []
    for s in r.json():
        people.append({"name": s.get("fullName", ""), "role": s.get("tagLine", ""),
                       "event": event_name, "url": f"https://sessionize.com/api/v2/{event_id}/view/Speakers"})
    fetch.mark(f"sessionize-{event_id}", f"Sessionize {event_name}", True, len(people))
    return people
