"""İsteğe bağlı ücretsiz LLM zenginleştirme (Gemini / Groq). Anahtar yoksa ya da hata olursa sessizce atlanır."""
from __future__ import annotations

import json
import os
import re

import requests

from .util import SETTINGS, log, today

CFG = SETTINGS.get("llm", {})
VALID_KINDS = {"haber", "hackathon", "bootcamp", "ilan", "sertifika", "etkinlik", "akademik", "makale", "acik-kaynak"}
VALID_CATS = {"yapay-zeka", "siber-guvenlik", "yatirim", "girisim", "buyuk-teknoloji", "devlet", "turkiye-ekonomi",
              "uzay-savunma", "akademi", "islam-teknoloji", "kariyer"}

PROMPT = """Sen Sakarya'da yaşayan bir bilgisayar mühendisliği öğrencisi için teknoloji/kariyer haberi editörüsün.
Bugün: {today}. Aşağıdaki her kayıt için JSON üret. Sadece JSON döndür: {{"items":[...]}}
Her öğe: {{"id": "...", "summary": "Türkçe, en fazla 2 cümle, somut (kim, ne, rakam, tarih)",
"kind": "{kinds}", "cats": [en fazla 3: {cats}],
"deadline": "YYYY-MM-DD veya null (yalnızca başvuru son tarihi)", "eventDate": "etkinlik tarihi metni veya null",
"mode": "Online / şehir adı veya null", "relevance": 0-3 (öğrenci için önemi; 0=alakasız)}}
Uydurma bilgi ekleme; metinde yoksa null yaz.

KAYITLAR:
{items}"""


def available() -> bool:
    return CFG.get("enabled", True) and bool(os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY"))


def _gemini(prompt: str) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("anahtar yok")
    model = CFG.get("gemini_model", "gemini-2.5-flash")
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(prompt: str) -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("anahtar yok")
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": CFG.get("groq_model", "llama-3.3-70b-versatile"), "temperature": 0.2,
              "response_format": {"type": "json_object"},
              "messages": [{"role": "user", "content": prompt}]},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


PROVIDERS = {"gemini": _gemini, "groq": _groq}


def _ask(prompt: str) -> dict | None:
    for name in CFG.get("provider_order", ["gemini", "groq"]):
        try:
            txt = PROVIDERS[name](prompt)
            txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M)
            return json.loads(txt)
        except Exception as ex:  # noqa: BLE001
            log(f"LLM {name} başarısız: {str(ex)[:120]}")
    return None


def enrich(items: list[dict]) -> int:
    """Puanı yüksek yeni kayıtları toplu olarak özetler/sınıflandırır. Değiştirilen kayıt sayısını döndürür."""
    if not available() or not items:
        return 0
    pool = sorted([i for i in items if i.get("score", 0) >= CFG.get("min_score_for_llm", 3)],
                  key=lambda x: -x["score"])[: CFG.get("max_items_per_run", 40)]
    bs = CFG.get("batch_size", 10)
    changed = 0
    for k in range(0, len(pool), bs):
        batch = pool[k:k + bs]
        payload = "\n".join(json.dumps({"id": i["id"], "title": i["title"], "text": (i.get("summary") or "")[:600],
                                        "source": i.get("source")}, ensure_ascii=False) for i in batch)
        res = _ask(PROMPT.format(today=today(), kinds="|".join(sorted(VALID_KINDS)),
                                 cats=", ".join(sorted(VALID_CATS)), items=payload))
        if not res:
            break  # sağlayıcılar düştüyse kalan partileri deneme
        by_id = {i["id"]: i for i in batch}
        for r in res.get("items", []):
            it = by_id.get(r.get("id"))
            if not it:
                continue
            if r.get("summary"):
                it["summary"] = str(r["summary"])[:420]
            if r.get("kind") in VALID_KINDS and it.get("kind") in ("haber", None):
                it["kind"] = r["kind"]
            cats = [c for c in (r.get("cats") or []) if c in VALID_CATS]
            if cats:
                it["cats"], it["cat"] = cats, cats[0]
            dl = r.get("deadline")
            if isinstance(dl, str) and re.fullmatch(r"20\d\d-\d\d-\d\d", dl) and dl >= today():
                it["deadline"] = dl
            for f in ("eventDate", "mode"):
                if r.get(f) and not it.get(f):
                    it[f] = str(r[f])[:80]
            rel = r.get("relevance")
            if isinstance(rel, int):
                it["score"] = it.get("score", 0) + (rel - 1) * 2
                if rel == 0:
                    it["_drop"] = True
            it["ai"] = True
            changed += 1
    return changed


BRIEF_PROMPT = """Sakarya'da okuyan bir bilgisayar mühendisliği öğrencisi için kısa bir {slot} özeti yaz.
Aşağıdaki yeni kayıtlardan en önemlilerini seç. 5-7 madde, her madde tek cümle, Türkçe, somut (kurum, rakam, tarih).
Önce kapanmak üzere olan fırsatlar, sonra Sakarya/Kocaeli, sonra Türkiye gündemi, en son dünya ve akademi.
Sadece JSON döndür: {{"highlights": ["...", "..."]}}

KAYITLAR:
{items}"""


def write_brief(slot: str, new: list[dict]) -> list[str] | None:
    if not available() or not new:
        return None
    top = sorted(new, key=lambda x: -x.get("score", 0))[:35]
    payload = "\n".join(json.dumps({k: i.get(k) for k in ("title", "summary", "kind", "deadline", "city", "scope")},
                                   ensure_ascii=False) for i in top)
    res = _ask(BRIEF_PROMPT.format(slot=slot, items=payload))
    hl = (res or {}).get("highlights")
    if isinstance(hl, list) and hl and all(isinstance(h, str) for h in hl):
        return [h.strip()[:400] for h in hl[:8]]
    return None
