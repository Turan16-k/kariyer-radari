"""Kariyer Radarı toplayıcı.  Kullanım:  python -m radar [--slot auto|sabah|aksam|haftalik] [--dry-run] [--offline]"""
from __future__ import annotations

import argparse
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from rapidfuzz import fuzz, process

from . import collectors, fetch, llm, notify
from .classify import OPP_KINDS, classify
from .util import CONFIG, DATA, SETTINGS, STATE, canonical_url, fold, item_id, load_json, log, now, save_json, today

TR_MONTHS = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
ROTATION_NEXT: dict = {}
SLOT_TITLE = {"sabah": "Sabah özeti", "aksam": "Akşam özeti", "haftalik": "Haftalık tarama"}


def tr_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {TR_MONTHS[d.month]}"


def pick_slot(arg: str) -> str:
    if arg != "auto":
        return arg
    return "sabah" if now().hour < 13 else "aksam"


# ------------------------------------------------------------------ toplama
def build_jobs(slot: str, weekly: bool):
    sources = load_json(CONFIG / "sources.json", [])
    health = fetch.health()
    want = {"her-tarama", slot} | ({"haftalik"} if weekly else set())
    jobs = []
    for s in sources:
        if "atla" in s.get("name", "").lower() or s.get("disabled"):
            continue
        if s.get("freq", "haftalik") not in want:
            continue
        if health.get(s["id"], {}).get("fails", 0) >= 5 and not weekly:
            continue  # sürekli hata veren kaynak: yalnızca haftalık taramada yeniden denenir
        if s.get("rss"):
            jobs.append(("rss", s))
        elif s.get("url", "").startswith("http"):
            jobs.append(("page", s))
    return jobs, {s["id"]: s for s in sources}


def gnews_jobs(slot: str, weekly: bool):
    q = load_json(CONFIG / "queries.json", {})
    jobs = []
    for x in q.get("queries", []):
        if x.get("slot", "her") in ("her", slot) or (weekly and x.get("slot") == "haftalik"):
            jobs.append((x["q"], "sorgu", x.get("kind")))
    # Sakarya şirket/vakıf rotasyonu
    rot = q.get("rotation", {})
    pool = [c["name"] for c in load_json(CONFIG / "companies.json", []) if c.get("local")]
    pool += [v["name"] for v in load_json(CONFIG / "vakiflar.json", []) if v.get("local")]
    pool = sorted(set(pool))
    st = load_json(STATE / "rotation.json", {"i": 0})
    n = rot.get("per_run", 15)
    if pool:
        i = st.get("i", 0) % len(pool)
        chunk = (pool + pool)[i:i + min(n, len(pool))]
        for name in chunk:
            short = re.sub(r"\s*\(.*?\)", "", name).strip()
            jobs.append((f'"{short}" {rot.get("window", "when:14d")}', f"rotasyon:{short}", None))
        ROTATION_NEXT.update({"i": (i + n) % len(pool), "pool": len(pool)})
    # Takip edilen kişiler (haftalık)
    if weekly:
        names = q.get("people_watch", {}).get("names", [])
        names += [p["name"] for p in load_json(DATA / "people.json", []) if p.get("follow")]
        for nm in sorted(set(names))[:25]:
            jobs.append((f'"{nm}" when:7d', f"kişi:{nm}", None))
    return jobs


def collect(slot: str, weekly: bool):
    jobs, src_by_id = build_jobs(slot, weekly)
    gjobs = gnews_jobs(slot, weekly)
    extra = SETTINGS.get("sources_extra", {})
    raw = []  # (entry, src)
    t0 = time.time()

    def run(kind, payload):
        if kind == "rss":
            return collectors.rss(payload), payload
        if kind == "page":
            return collectors.pagediff(payload), payload
        if kind == "gnews":
            q, label, k = payload
            return collectors.gnews(q, label, k), {"id": "gnews", "name": label, "group": "Google Haberler", "freq": "her-tarama"}
        if kind == "devpost":
            return collectors.devpost(), {"id": "devpost", "group": "Etkinlik ve fırsat platformları"}
        if kind == "hf":
            return collectors.hf_papers(), {"id": "hf-papers", "group": "Akademik trend"}
        if kind == "openalex":
            return collectors.openalex(), {"id": "openalex", "group": "Akademik trend"}
        raise ValueError(kind)

    tasks = [(k, s) for k, s in jobs] + [("gnews", g) for g in gjobs]
    if extra.get("devpost", True) and slot == "aksam":
        tasks.append(("devpost", None))
    if extra.get("hf_papers", True) and slot == "sabah":
        tasks.append(("hf", None))
    if extra.get("openalex", True) and weekly:
        tasks.append(("openalex", None))

    errors = 0
    with ThreadPoolExecutor(max_workers=SETTINGS.get("workers", 16)) as ex:
        futs = {ex.submit(run, k, p): (k, p) for k, p in tasks}
        for f in as_completed(futs):
            k, p = futs[f]
            try:
                entries, src = f.result()
                raw.extend((e, src) for e in entries)
            except Exception as e:  # noqa: BLE001
                errors += 1
                if k in ("rss", "page"):
                    fetch.mark(p["id"], p["name"], False, err=f"{type(e).__name__}: {e}")
                elif k == "gnews":
                    fetch.mark("gnews", "Google Haberler RSS", False, err=str(e))
                else:
                    fetch.mark(k, k, False, err=str(e))
    log(f"{len(tasks)} iş, {len(raw)} ham kayıt, {errors} hata, {time.time() - t0:.0f} sn")
    return raw, src_by_id, len(tasks), errors


# ------------------------------------------------------------------ işleme
def process_entries(raw, items):
    max_age = SETTINGS.get("max_age_days_on_ingest", 10)
    cutoff = (date.fromisoformat(today()) - timedelta(days=max_age)).isoformat()
    by_id = {i["id"]: i for i in items}
    by_url = {canonical_url(i.get("url", "")): i for i in items if i.get("url")}
    recent = [i for i in items if (i.get("addedAt") or "") >= (date.fromisoformat(today()) - timedelta(days=21)).isoformat()]
    titles = [fold(i["title"]).strip() for i in recent]
    thr = SETTINGS.get("dedup_threshold", 87)

    new, merged = [], 0
    for e, src in raw:
        if not e.get("title") or not e.get("url"):
            continue
        if e.get("kind") != "akademik" and (e.get("date") or today()) < cutoff:
            continue
        it = classify(e, src)
        if not it or it["score"] < SETTINGS.get("min_score_to_keep", 1):
            continue
        it["id"] = item_id(it["url"], it["title"])
        cu = canonical_url(it["url"])
        dup = by_id.get(it["id"]) or by_url.get(cu)
        ft = fold(it["title"]).strip()
        if not dup and titles and len(ft) > 18:
            m = process.extractOne(ft, titles, scorer=fuzz.token_sort_ratio, score_cutoff=thr)
            if m:
                dup = recent[m[2]]
        if dup:
            if dup.get("source") != it["source"] and all(l.get("u") != it["url"] for l in dup.get("links", [])) \
                    and dup.get("url") != it["url"]:
                dup.setdefault("links", []).append({"t": it["source"], "u": it["url"]})
                dup["xs"] = len(dup["links"]) + 1
                merged += 1
            continue
        it["addedAt"] = today()
        it["status"] = ""
        it.pop("sourceId", None)
        it.pop("popularity", None)
        new.append(it)
        by_id[it["id"]] = it
        by_url[cu] = it
        recent.append(it)
        titles.append(ft)
    return new, merged


def balance(new):
    """Türkiye ağırlığını koru: global haberler, Türkiye kayıtlarının yarısını (en az 12) geçmesin."""
    tr = [i for i in new if i["scope"] == "tr"]
    gl = sorted([i for i in new if i["scope"] != "tr"], key=lambda x: -x["score"])
    keep_gl = [i for i in gl if i["kind"] in OPP_KINDS or i["kind"] == "akademik"]
    rest = [i for i in gl if i not in keep_gl][: max(12, len(tr) // 2)]
    return tr + keep_gl + rest


def retain(items):
    days = SETTINGS.get("retention_days", 45)
    cutoff = (date.fromisoformat(today()) - timedelta(days=days)).isoformat()
    keep, old = [], []
    for i in items:
        alive = (i.get("deadline") or "") >= today()
        saved = SETTINGS.get("keep_saved_forever", True) and i.get("status") in ("interested", "applied")
        if (i.get("addedAt") or today()) >= cutoff or alive or saved:
            keep.append(i)
        else:
            old.append(i)
    if old:
        by_month = {}
        for i in old:
            by_month.setdefault((i.get("addedAt") or today())[:7], []).append(i)
        for m, lst in by_month.items():
            p = DATA / "gecmis" / f"{m}.json"
            prev = load_json(p, [])
            ids = {x["id"] for x in prev}
            save_json(p, prev + [x for x in lst if x["id"] not in ids])
    return keep, len(old)


# ------------------------------------------------------------------ özet ve bildirim
def build_brief(slot, new, items, health_bad):
    t = today()
    soon_limit = (date.fromisoformat(t) + timedelta(days=3)).isoformat()
    soon = sorted([i for i in items if t <= (i.get("deadline") or "") <= soon_limit], key=lambda x: x["deadline"])
    opps = sorted([i for i in new if i["kind"] in OPP_KINDS], key=lambda x: -x["score"])
    local = sorted([i for i in new if i.get("local")], key=lambda x: -x["score"])
    news = sorted([i for i in new if i["kind"] == "haber" and i["scope"] == "tr"],
                  key=lambda x: (-(x.get("xs") or 1), -x["score"]))
    glob = sorted([i for i in new if i["kind"] == "haber" and i["scope"] != "tr"], key=lambda x: -x["score"])
    acad = sorted([i for i in new if i["kind"] == "akademik"], key=lambda x: -x["score"])

    def names(lst, n, with_dl=False):
        return "; ".join(f"{i['title']}" + (f" ({tr_date(i['deadline'])})" if with_dl and i.get("deadline") else "")
                         for i in lst[:n])

    hl = [f"Bu taramada {len(new)} yeni kayıt: {len(opps)} fırsat, {len(local)} Sakarya/Kocaeli, "
          f"{sum(1 for i in new if i['scope'] == 'tr')} Türkiye, {len(glob)} global."]
    if soon:
        hl.append("3 gün içinde kapanıyor: " + names(soon, 6, True) + ".")
    if opps:
        hl.append("Yeni fırsatlar: " + names(opps, 5, True) + ".")
    if local:
        hl.append("Yakınında: " + names(local, 4) + ".")
    if news:
        hl.append("Türkiye gündemi: " + names(news, 4) + ".")
    if glob:
        hl.append("Dünyada: " + names(glob, 3) + ".")
    if acad:
        hl.append("Akademi: " + names(acad, 3) + ".")
    if health_bad:
        hl.append(f"Kaynak sağlığı: {len(health_bad)} kaynak art arda hata veriyor ({', '.join(health_bad[:4])}…). Kaynaklar sekmesinden bak.")

    ai = llm.write_brief(SLOT_TITLE.get(slot, "").lower(), new)
    if ai:
        hl = hl[:1] + ([hl[1]] if soon else []) + ai + ([hl[-1]] if health_bad else [])
    n = now()
    return {
        "id": f"b-{t}-{slot}", "createdAt": n.isoformat(timespec="seconds"), "slot": slot,
        "title": SLOT_TITLE.get(slot, "Özet"), "when": f"{n.day} {TR_MONTHS[n.month]} {n.year} · {n:%H:%M}",
        "highlights": hl,
    }


def send_notifications(slot, new, items):
    cfg = SETTINGS.get("notify", {})
    warned = load_json(STATE / "warned.json", {})
    t = today()
    picks = [i for i in new if i["score"] >= cfg.get("min_score", 6)
             or (i["kind"] in cfg.get("always_kinds", []) and (i["scope"] == "tr" or i.get("mode") == "Online"))]
    picks.sort(key=lambda x: -x["score"])
    picks = picks[: cfg.get("max_per_run", 12)]
    lim = (date.fromisoformat(t) + timedelta(days=cfg.get("deadline_warn_days", 3))).isoformat()
    closing = [i for i in items if t <= (i.get("deadline") or "") <= lim and i["id"] not in warned
               and i.get("status") != "hidden"]
    for i in closing:
        warned[i["id"]] = t
    save_json(STATE / "warned.json", {k: v for k, v in warned.items() if v >= (date.fromisoformat(t) - timedelta(days=30)).isoformat()})
    if not picks and not closing:
        return False
    url = SETTINGS.get("pano_url", "")
    msg = notify.digest(f"Kariyer Radarı · {SLOT_TITLE.get(slot, '')}",
                        [("⏰ Kapanmak üzere", closing[:8]), ("Yeni ve önemli", picks)],
                        f'<a href="{url}">Panoyu aç</a>' if url else "")
    return notify.send(msg)


# ------------------------------------------------------------------ ana akış
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="auto", choices=["auto", "sabah", "aksam", "haftalik"])
    ap.add_argument("--weekly", action="store_true", help="haftalık kaynakları da tara")
    ap.add_argument("--dry-run", action="store_true", help="dosya yazma, bildirim gönderme")
    ap.add_argument("--no-notify", action="store_true")
    a = ap.parse_args(argv)

    t0 = time.time()
    slot = pick_slot(a.slot)
    weekly = a.weekly or slot == "haftalik" or (now().weekday() == 0 and slot == "sabah")
    if slot == "haftalik":
        slot = "sabah"
    log(f"Slot: {slot}{' + haftalık' if weekly else ''}")

    items = load_json(DATA / "items.json", [])
    raw, src_by_id, n_jobs, n_err = collect(slot, weekly)
    new, merged = process_entries(raw, items)
    new = balance(new)
    if llm.available():
        log(f"LLM zenginleştirme: {llm.enrich(new)} kayıt")
    new = [i for i in new if not i.pop("_drop", False)]
    items = new + items
    items, archived = retain(items)
    items.sort(key=lambda x: (x.get("addedAt", ""), x.get("score", 0)), reverse=True)

    health = fetch.health()
    bad = [h["name"] for h in health.values() if h.get("fails", 0) >= 3]
    brief = build_brief(slot, new, items, bad)
    log(f"Yeni {len(new)}, birleşen {merged}, arşivlenen {archived}, toplam {len(items)}")
    for h in brief["highlights"]:
        log("  •", h[:160])

    if a.dry_run:
        return 0

    save_json(DATA / "items.json", items)
    briefs = [brief] + [b for b in load_json(DATA / "briefs.json", []) if b.get("id") != brief["id"]]
    briefs.sort(key=lambda b: b.get("createdAt", ""), reverse=True)
    save_json(DATA / "briefs.json", briefs[:60])
    # Pano için yapılandırmaların kopyası (+ sağlık durumu)
    srcs = load_json(CONFIG / "sources.json", [])
    for s in srcs:
        h = health.get(s["id"])
        if h:
            s["health"] = {"fails": h.get("fails", 0), "lastOk": h.get("lastOk"), "lastCount": h.get("lastCount")}
    save_json(DATA / "sources.json", srcs)
    for name in ("companies", "vakiflar"):
        save_json(DATA / f"{name}.json", load_json(CONFIG / f"{name}.json", []))
    fetch.persist()
    if ROTATION_NEXT:
        save_json(STATE / "rotation.json", ROTATION_NEXT)
    meta = {"lastRun": now().isoformat(timespec="seconds"), "slot": slot, "weekly": weekly, "jobs": n_jobs,
            "errors": n_err, "new": len(new), "merged": merged, "total": len(items), "llm": llm.available(),
            "seconds": round(time.time() - t0)}
    save_json(DATA / "meta.json", meta, indent=1)
    if not a.no_notify:
        sent = send_notifications(slot, new, items)
        log("Telegram:", "gönderildi" if sent else "gönderilmedi/kapalı")
    log(f"Bitti: {meta['seconds']} sn")
    if n_jobs and n_err / n_jobs > 0.6:
        notify.send(f"⚠️ Kariyer Radarı: {n_err}/{n_jobs} kaynak hata verdi. Ağ ya da GitHub Actions sorunu olabilir; "
                    "Actions sekmesindeki kaydı kontrol et.")
        log("Hataların oranı çok yüksek; iş başarısız sayılıyor.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
