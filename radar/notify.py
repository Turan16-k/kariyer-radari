"""Telegram bildirimi (ücretsiz). TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID secret'ları yoksa atlanır."""
from __future__ import annotations

import html
import os

import requests

from .util import log

KIND_ICON = {"hackathon": "🏁", "ilan": "💼", "bootcamp": "🎓", "sertifika": "📜", "etkinlik": "📅",
             "akademik": "📄", "haber": "📰"}


def enabled() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send(text: str) -> bool:
    if not enabled():
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
            json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text[:4000], "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20,
        )
        r.raise_for_status()
        return True
    except Exception as ex:  # noqa: BLE001
        log("Telegram gönderilemedi:", str(ex)[:120])
        return False


def line(it: dict) -> str:
    icon = KIND_ICON.get(it.get("kind"), "•")
    extra = []
    if it.get("deadline"):
        extra.append(f"son: {it['deadline'][8:10]}.{it['deadline'][5:7]}")
    if it.get("city"):
        extra.append(it["city"])
    tail = f" <i>({', '.join(extra)})</i>" if extra else ""
    return f'{icon} <a href="{html.escape(it["url"], quote=True)}">{html.escape(it["title"][:140])}</a>{tail}'


def digest(title: str, sections: list[tuple[str, list[dict]]], footer: str = "") -> str:
    parts = [f"<b>{html.escape(title)}</b>"]
    for head, items in sections:
        if items:
            parts.append(f"\n<b>{html.escape(head)}</b>")
            parts.extend(line(i) for i in items)
    if footer:
        parts.append("\n" + footer)
    return "\n".join(parts)
