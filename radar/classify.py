"""Kural tabanlı sınıflandırma: kategori, tür, kapsam, yerellik, son tarih, puan."""
from __future__ import annotations

import re
from datetime import date

from .util import CONFIG, fold, load_json, today

KW = load_json(CONFIG / "keywords.json", {})


def _compile(words):
    parts = []
    for w in words:
        f = fold(w).strip()
        if not f:
            continue
        end = r"(?![a-z0-9])" if w.endswith(" ") else ""
        parts.append(r"(?<![a-z0-9])" + re.escape(f) + end)
    return re.compile("|".join(parts)) if parts else None


CAT_RX = {k: _compile(v) for k, v in KW.get("cats", {}).items()}
KIND_RX = {k: _compile(v) for k, v in KW.get("kinds", {}).items()}
LOCAL_RX = {k: _compile(v) for k, v in KW.get("local", {}).items()}
TR_RX = _compile(KW.get("tr_signals", []))
BOOST_RX = _compile(KW.get("boost", []))
BLOCK_RX = _compile(KW.get("block", []))
CAMPUS_RX = _compile(["sakarya universitesi", "sau ", "subu", "sakarya uygulamali", "sau kariyer", "sau teknokent"])
ONLINE_RX = _compile(["online", "cevrim ici", "cevrimici", "uzaktan", "virtual", "remote", "hibrit", "hybrid"])

GROUP_CAT = {
    "Siber": "siber-guvenlik", "Savunma": "uzay-savunma", "Girişim": "girisim", "Kamu": "devlet",
    "Kariyer": "kariyer", "Akademik": "akademi", "Yapay zekâ": "yapay-zeka", "İslam": "islam-teknoloji",
    "Fintech": "islam-teknoloji", "Türkiye genel": "turkiye-ekonomi", "Global teknoloji": "buyuk-teknoloji",
    "Donanım": "buyuk-teknoloji", "Teknoloji politikası": "devlet", "Teknopark": "akademi", "Üniversite": "akademi",
}
GLOBAL_GROUPS = ("Global teknoloji", "Yapay zekâ: laboratuvarlar", "Teknoloji politikası", "Donanım ve çip")
TR_GROUPS = ("Türkiye", "Kamu", "Savunma", "Yerel", "Teknopark", "Üniversite", "Topluluk", "Kariyer", "Fintech", "İslam")
TECH_CATS = {"yapay-zeka", "siber-guvenlik", "yatirim", "girisim", "buyuk-teknoloji", "uzay-savunma", "akademi",
             "kariyer", "islam-teknoloji"}
LOCAL_GROUPS = ("Yerel", "Teknopark", "Üniversite", "Topluluk")
OPP_GROUPS = ("Etkinlik ve fırsat", "Kariyer, burs")

KIND_WEIGHT = {"hackathon": 5, "ilan": 5, "bootcamp": 4, "sertifika": 4, "etkinlik": 3,
               "akademik": 2, "acik-kaynak": 2, "makale": 1, "medya": 1, "haber": 1}
OPP_KINDS = {"hackathon", "ilan", "bootcamp", "sertifika", "etkinlik"}

MONTHS = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6, "temmuz": 7, "agustos": 8,
    "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
    "nov": 11, "dec": 12,
}
_MON = r"(ocak|subat|mart|nisan|mayis|haziran|temmuz|agustos|eylul|ekim|kasim|aralik|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
DATE_RX = re.compile(r"(?<!\d)(\d{1,2})\s*(?:-\s*\d{1,2}\s*)?" + _MON + r"(?:\s*(20\d\d))?")
DATE_EN_RX = re.compile(_MON + r"\s+(\d{1,2})(?:,?\s*(20\d\d))?")
DOT_RX = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](20\d\d)")
DEADLINE_CUE = re.compile(r"son basvuru|son gun|son tarih|basvuru(?:lar)?[^.]{0,40}(?:kadar|bitiyor|sona)|deadline|kadar basvur|apply by|registration closes|submissions? (?:close|due)")


def _mk(d, m, y=None):
    t = date.fromisoformat(today())
    try:
        if y:
            return date(int(y), m, int(d))
        cand = date(t.year, m, int(d))
        if (t - cand).days > 60:
            cand = date(t.year + 1, m, int(d))
        return cand
    except ValueError:
        return None


def find_dates(ft: str):
    out = []
    for m in DATE_RX.finditer(ft):
        d = _mk(m.group(1), MONTHS[m.group(2)], m.group(3))
        if d:
            out.append((m.start(), d))
    for m in DATE_EN_RX.finditer(ft):
        key = m.group(1)
        if key in MONTHS:
            d = _mk(m.group(2), MONTHS[key], m.group(3))
            if d:
                out.append((m.start(), d))
    for m in DOT_RX.finditer(ft):
        try:
            out.append((m.start(), date(int(m.group(3)), int(m.group(2)), int(m.group(1)))))
        except ValueError:
            pass
    return sorted(out)


def extract_deadline(ft: str):
    cue = DEADLINE_CUE.search(ft)
    if not cue:
        return None
    dates = find_dates(ft)
    if not dates:
        return None
    # İpucuna en yakın tarih
    pos, d = min(dates, key=lambda x: abs(x[0] - cue.start()))
    if abs(pos - cue.start()) > 120:
        return None
    return d.isoformat()


def _hits(rx, text):
    return len(rx.findall(text)) if rx else 0


def classify(entry: dict, src: dict | None = None) -> dict | None:
    """Ham girdiyi zenginleştirir; ilgisiz/yasaklıysa None döner."""
    src = src or {}
    group = src.get("group", "")
    title = entry.get("title", "")
    ft_title = fold(title)
    ft = fold(title + " " + entry.get("summary", ""))

    if BLOCK_RX and BLOCK_RX.search(ft_title):
        return None
    if len(title) < 20 or len(title.split()) < 4:
        return None  # "Sakarya Üniversitesi" gibi menü/başlık parçaları

    # Kategoriler (başlık eşleşmesi 2 kat ağırlıklı)
    scores = {}
    for c, rx in CAT_RX.items():
        s = 2 * _hits(rx, ft_title) + _hits(rx, ft)
        if s:
            scores[c] = s
    cats = [c for c, _ in sorted(scores.items(), key=lambda x: -x[1])][:3]
    if not cats:
        for k, v in GROUP_CAT.items():
            if group.startswith(k) or k in group:
                cats = [v]
                break

    # Tür
    kind = entry.get("kind")
    if not kind:
        for k in ("hackathon", "bootcamp", "ilan", "sertifika", "etkinlik"):
            rx = KIND_RX.get(k)
            if rx and rx.search(ft_title):
                kind = k
                break
    if not kind and any(group.startswith(g) for g in OPP_GROUPS):
        for k in ("hackathon", "bootcamp", "ilan", "sertifika", "etkinlik"):
            rx = KIND_RX.get(k)
            if rx and rx.search(ft):
                kind = k
                break
    hint = entry.get("kindHint")
    if not kind and hint and KIND_RX.get(hint) and KIND_RX[hint].search(ft):
        kind = hint
    if not kind and group.startswith("Akademik trend"):
        kind = "akademik"
    kind = kind or "haber"

    # Alakasız genel haberleri ele: haberin kendi metninde teknoloji/kariyer sinyali olmalı
    if kind == "haber":
        tech = set(scores) & TECH_CATS
        is_local_src = any(group.startswith(g) for g in LOCAL_GROUPS)
        if not tech and not (is_local_src and scores):
            if not (is_local_src and LOCAL_RX.get("Sakarya") and LOCAL_RX["Sakarya"].search(ft)):
                return None

    # Kapsam
    host = (entry.get("url") or "").split("/")[2] if "://" in (entry.get("url") or "") else ""
    scope = entry.get("scope")
    if not scope:
        if any(group.startswith(g) for g in GLOBAL_GROUPS):
            scope = "tr" if TR_RX and _hits(TR_RX, ft_title) else "global"
        elif any(group.startswith(g) for g in TR_GROUPS) or host.endswith(".tr") or entry.get("lang") == "tr" \
                or (TR_RX and TR_RX.search(ft)):
            scope = "tr"
        else:
            scope = "global"

    # Yerellik
    local_name = None
    for name, rx in LOCAL_RX.items():
        if rx and rx.search(ft):
            local_name = name
            break
    if not local_name and group.startswith("Yerel"):
        local_name = "Sakarya"
    campus = bool(CAMPUS_RX and CAMPUS_RX.search(ft))

    deadline = entry.get("deadline") or (extract_deadline(ft) if kind in OPP_KINDS else None)
    if deadline and deadline < today():
        if kind in ("hackathon", "bootcamp", "sertifika", "ilan"):
            return None  # süresi geçmiş fırsat
        deadline = None

    # Puan
    score = KIND_WEIGHT.get(kind, 1)
    score += {"Sakarya": 4, "Kocaeli": 2, "İstanbul": 1}.get(local_name, 0)
    score += 2 if campus else 0
    score += 1 if scope == "tr" else 0
    score += min(3, _hits(BOOST_RX, ft))
    score += min(2, len(cats))
    if src.get("freq") == "her-tarama":
        score += 1
    if deadline:
        left = (date.fromisoformat(deadline) - date.fromisoformat(today())).days
        score += 3 if left <= 7 else 1

    out = {k: v for k, v in entry.items() if k not in ("kindHint", "lang", "via")}
    out.update({
        "kind": kind, "cats": cats, "cat": cats[0] if cats else "", "scope": scope,
        "local": local_name in ("Sakarya", "Kocaeli") or campus, "city": local_name or "",
        "campus": campus, "score": score,
    })
    if deadline:
        out["deadline"] = deadline
    if kind in OPP_KINDS and not out.get("mode"):
        out["mode"] = "Online" if ONLINE_RX and ONLINE_RX.search(ft) else (local_name or "")
    if kind == "akademik" and not out.get("field"):
        out["field"] = academic_field(ft)
        out.setdefault("origin", "tr" if scope == "tr" else "global")
    return out


def academic_field(ft: str) -> str:
    if CAT_RX.get("siber-guvenlik") and CAT_RX["siber-guvenlik"].search(ft):
        return "siber"
    if re.search(r"(?<![a-z])(software|yazilim|code|program|test|devops|compiler|api)", ft):
        return "yazilim"
    if re.search(r"(?<![a-z])(distributed|dagitik|network|ag |cloud|bulut|gpu|hardware|donanim|kernel|database|veritaban|system)", ft):
        return "sistem"
    return "yz"
