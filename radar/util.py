"""Ortak yardımcılar: yollar, JSON, metin sadeleştirme, URL kanonikleştirme, tarih."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "docs" / "data"
STATE = ROOT / "state"


def load_json(path: Path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, obj, indent=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"))
    os.replace(tmp, path)


SETTINGS = load_json(CONFIG / "settings.json", {})
TZ = timezone(timedelta(hours=SETTINGS.get("timezone_offset_hours", 3)))


def now() -> datetime:
    return datetime.now(TZ)


def today() -> str:
    return now().strftime("%Y-%m-%d")


_TR = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g", "ü": "u", "Ü": "u",
                     "ö": "o", "Ö": "o", "ç": "c", "Ç": "c", "â": "a", "Â": "a", "î": "i", "û": "u"})


def fold(text: str) -> str:
    """Küçük harf + Türkçe karakter sadeleştirme + boşluk normalizasyonu."""
    t = (text or "").translate(_TR).lower()
    return " " + re.sub(r"\s+", " ", t) + " "


def clean_html(text: str, limit: int = 400) -> str:
    if not text:
        return ""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        cut = t[:limit].rsplit(" ", 1)[0]
        t = cut.rstrip(".,;: ") + "…"
    return t


_DROP_PARAMS = re.compile(r"^(utm_|fbclid|gclid|mc_|ref$|ref_|source$|cmpid|ocid|igshid|spm|_hs)", re.I)


def canonical_url(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url.strip()
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False) if not _DROP_PARAMS.match(k)]
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.").removeprefix("amp.")
    path = re.sub(r"/(amp|amp\.html)/?$", "/", p.path).rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(q)), ""))


def item_id(url: str, title: str = "") -> str:
    base = canonical_url(url) or fold(title)
    return "i" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def to_date(value) -> str | None:
    """feedparser struct_time / ISO string -> 'YYYY-MM-DD' (yerel saat)."""
    if not value:
        return None
    try:
        if hasattr(value, "tm_year"):
            dt = datetime(*value[:6], tzinfo=timezone.utc)
        else:
            s = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def days_between(a: str, b: str) -> int:
    return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days


def log(*a):
    print(f"[{now():%H:%M:%S}]", *a, flush=True)
