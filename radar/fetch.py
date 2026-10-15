"""HTTP katmanı: yeniden deneme, koşullu GET (ETag/Last-Modified), kaynak sağlık kaydı."""
from __future__ import annotations

import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .util import SETTINGS, STATE, load_json, save_json, today

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 KariyerRadari/2.0 (+https://github.com)")
TIMEOUT = SETTINGS.get("http_timeout", 20)

_local = threading.local()
_lock = threading.Lock()
_cache = load_json(STATE / "http_cache.json", {}) or {}
_health = load_json(STATE / "health.json", {}) or {}


def session() -> requests.Session:
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        retry = Retry(total=2, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), respect_retry_after_header=True)
        s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
        s.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
        s.headers.update({"User-Agent": UA, "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"})
        _local.s = s
    return s


class NotModified(Exception):
    pass


def get(url: str, *, conditional: bool = True, accept: str | None = None, timeout: int | None = None) -> requests.Response:
    headers = {}
    if accept:
        headers["Accept"] = accept
    c = _cache.get(url) if conditional else None
    if c:
        if c.get("etag"):
            headers["If-None-Match"] = c["etag"]
        if c.get("lm"):
            headers["If-Modified-Since"] = c["lm"]
    r = session().get(url, headers=headers, timeout=timeout or TIMEOUT, allow_redirects=True)
    if r.status_code == 304:
        raise NotModified(url)
    r.raise_for_status()
    if conditional:
        with _lock:
            _cache[url] = {k: v for k, v in (("etag", r.headers.get("ETag")), ("lm", r.headers.get("Last-Modified"))) if v}
    return r


def mark(key: str, name: str, ok: bool, n: int = 0, err: str = "") -> None:
    """Kaynak sağlığı: art arda hata sayısı, son başarı, son hata."""
    with _lock:
        h = _health.setdefault(key, {"name": name, "fails": 0})
        h["name"] = name
        h["lastRun"] = today()
        if ok:
            h["fails"] = 0
            h["lastOk"] = today()
            h["lastCount"] = n
            h.pop("lastError", None)
        else:
            h["fails"] = h.get("fails", 0) + 1
            h["lastError"] = err[:160]


def health() -> dict:
    return _health


def persist() -> None:
    save_json(STATE / "http_cache.json", _cache)
    save_json(STATE / "health.json", _health, indent=1)


def polite_sleep(sec: float = 0.4) -> None:
    time.sleep(sec)
