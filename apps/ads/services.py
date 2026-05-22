"""Ad copy analysis utilities — ported from original build.py."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from typing import Iterable

ARABIC_RE = re.compile(r"[؀-ۿ]")
TURKISH_CHARS = set("şğıöüçŞĞİÖÜÇ")
VIDEO_DURATION_RE = re.compile(r"^\s*\d+:\d+\s*/\s*\d+:\d+\s*$", re.MULTILINE)
VARIANT_RE = re.compile(r"(\d+)\s+ads?\s+use")


def detect_lang(text: str) -> str:
    if not text:
        return "XX"
    if ARABIC_RE.search(text):
        return "AR"
    if any(c in text for c in TURKISH_CHARS):
        return "TR"
    return "EN"


def clean_copy(text: str, headline: str = "") -> str:
    if not text:
        return ""
    lines = [ln for ln in text.split("\n") if not VIDEO_DURATION_RE.fullmatch(ln)]
    if headline and lines and lines[-1].strip() == headline.strip():
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_started_date(s: str) -> date | None:
    """Parse strings like 'on Apr 7, 2026' or 'on May 10, 2026 · Total active time …'."""
    if not s:
        return None
    cleaned = s.strip().lstrip("on ").split("·")[0].strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def variant_count(variant_text: str) -> int:
    if not variant_text:
        return 1
    m = VARIANT_RE.match(variant_text)
    if m:
        return int(m.group(1))
    return 1


def _normalize_for_clustering(text: str) -> str:
    key = re.sub(r"\s+", " ", text.lower())
    return re.sub(r"[^a-z0-9؀-ۿşğıöüçа-яё]+", "", key)


def cluster_by_copy(ads: Iterable[dict]) -> list[dict]:
    """Group ads with effectively identical body copy.

    Each ad dict expects keys: bodyCopy, headline, variant.
    Returns clusters sorted by total active variants desc.
    """
    groups: dict[str, dict] = {}
    for ad in ads:
        cleaned = clean_copy(ad.get("bodyCopy", ""), ad.get("headline", ""))
        key = _normalize_for_clustering(cleaned)
        bucket = groups.setdefault(
            key,
            {
                "sample": cleaned,
                "lang": detect_lang(cleaned),
                "ads": [],
                "headlines": set(),
                "variant_total": 0,
            },
        )
        bucket["ads"].append(ad)
        if ad.get("headline"):
            bucket["headlines"].add(ad["headline"])
        bucket["variant_total"] += variant_count(ad.get("variant", ""))
    out = []
    for b in groups.values():
        b["headlines"] = sorted(b["headlines"])
        out.append(b)
    out.sort(key=lambda g: -g["variant_total"])
    return out


def summarize_ads(ads: list) -> dict:
    """Compute aggregate stats for a Competitor's queryset of Ad records.

    Designed to work on either Ad model instances or dicts with matching keys.
    """

    def g(obj, *keys):
        for k in keys:
            if hasattr(obj, k):
                return getattr(obj, k)
            if isinstance(obj, dict) and k in obj:
                return obj[k]
        return None

    n = len(ads)
    if n == 0:
        return {
            "unique_creatives": 0,
            "total_active": 0,
            "video_count": 0,
            "image_count": 0,
            "languages": {},
            "ctas": {},
            "date_range": "—",
        }

    n_video = sum(1 for a in ads if g(a, "media_type", "mediaType") == "video")
    n_image = sum(1 for a in ads if g(a, "media_type", "mediaType") == "image")
    total_variants = sum(int(g(a, "variant_count") or 1) for a in ads)
    lang_counts = Counter(g(a, "language") or detect_lang(g(a, "body_copy", "bodyCopy") or "") for a in ads)
    dates = [g(a, "started_date") for a in ads if g(a, "started_date")]
    earliest = min(dates).strftime("%b %d, %Y") if dates else "—"
    latest = max(dates).strftime("%b %d, %Y") if dates else "—"
    ctas = Counter((g(a, "cta") or "").strip().lower() for a in ads if g(a, "cta"))

    return {
        "unique_creatives": n,
        "total_active": total_variants,
        "video_count": n_video,
        "image_count": n_image,
        "languages": dict(lang_counts),
        "ctas": dict(ctas.most_common(5)),
        "date_range": f"{earliest} → {latest}",
    }
