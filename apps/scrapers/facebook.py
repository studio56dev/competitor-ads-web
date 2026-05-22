"""Facebook Ad Library scraper — MVP.

This is a starting point. FB DOM changes frequently; selectors below are
best-effort heuristics. Test with `manage.py scrape_now <competitor-slug>`
and iterate. Returns a list of dicts compatible with the legacy data.json
shape so apps.ads.services / Ad model can consume them.

dict keys produced:
    libId       — required, Facebook Ad Library numeric ID
    bodyCopy    — main ad text (best-effort, may include extra lines)
    headline    — short headline text if detected
    cta         — call-to-action button text
    started     — "Started running on …" raw text
    mediaType   — 'video' | 'image' | 'other'
    variant     — multi-variant indicator text (best-effort)
    active      — True (we only see active ads via the public URL anyway)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from playwright.sync_api import Browser, Page, TimeoutError as PWTimeout, sync_playwright

logger = logging.getLogger(__name__)

LIB_ID_RE = re.compile(r"Library\s+ID:?\s*(\d+)", re.I)
STARTED_RE = re.compile(r"(Started\s+running\s+on[^\n]+)", re.I)
VARIANT_RE = re.compile(r"(\d+\s+ads?\s+use\s+this\s+creative[^\n]*)", re.I)
COOKIE_BUTTON_TEXTS = [
    "Allow all cookies",
    "Tümünü kabul et",
    "Tümüne izin ver",
    "Tümü kabul et",
    "Accept all",
    "Allow essential and optional cookies",
]


@dataclass
class ScrapeResult:
    ads: list[dict]
    raw_text_sample: str
    screenshots_taken: int = 0


def _dismiss_cookies(page: Page) -> None:
    for text in COOKIE_BUTTON_TEXTS:
        try:
            btn = page.get_by_role("button", name=re.compile(re.escape(text), re.I))
            if btn.first.is_visible(timeout=500):
                btn.first.click()
                page.wait_for_timeout(800)
                return
        except Exception:
            continue


def _scroll_to_load(page: Page, max_scrolls: int = 6, settle_ms: int = 1800) -> None:
    """Scroll viewport repeatedly so FB lazy-loads more ad cards."""
    prev_height = 0
    for i in range(max_scrolls):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(settle_ms)
        try:
            curr = page.evaluate("document.body.scrollHeight")
        except Exception:
            curr = 0
        if curr and curr == prev_height:
            logger.info(f"Scroll {i+1}: page height stable at {curr}, stopping")
            break
        prev_height = curr


def _extract_ads_from_page(page: Page) -> list[dict]:
    """Extract one dict per ad card found on the page.

    Strategy: find every element whose innerText mentions 'Library ID',
    treat the smallest such container as a card. Parse text heuristically.
    """
    # JS evaluates within the page context, returns plain list of strings (one per card)
    card_texts = page.evaluate(
        """
() => {
  const out = [];
  const all = document.querySelectorAll('div');
  const seen = new Set();
  for (const el of all) {
    const t = el.innerText || '';
    if (!t || !/library\\s+id:?\\s*\\d+/i.test(t)) continue;
    // Pick the smallest container that still has the library id
    // (skip large wrappers that contain multiple cards)
    if (t.length > 5000) continue;
    if (seen.has(t)) continue;
    seen.add(t);
    out.push(t);
  }
  return out;
}
        """
    )
    logger.info(f"Found {len(card_texts)} candidate ad text blocks")

    ads: list[dict] = []
    for text in card_texts:
        m = LIB_ID_RE.search(text)
        if not m:
            continue
        lib_id = m.group(1)

        # Find started date
        s = STARTED_RE.search(text)
        started = s.group(1).strip() if s else ""

        # Find variant text
        v = VARIANT_RE.search(text)
        variant = v.group(1).strip() if v else ""

        # Body: longest line that isn't meta
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        meta_markers = ("Library ID", "Started running", "Sponsored", "ads use this", "Platforms", "Active", "Inactive")
        body_candidates = [
            ln for ln in lines
            if len(ln) > 25 and not any(m in ln for m in meta_markers)
        ]
        body = max(body_candidates, key=len, default="")

        # Headline: short line just above body (best-effort)
        headline = ""
        if body and body in lines:
            idx = lines.index(body)
            for j in range(idx - 1, max(idx - 4, -1), -1):
                cand = lines[j]
                if 4 <= len(cand) <= 80 and not any(m in cand for m in meta_markers):
                    headline = cand
                    break

        # CTA: usually one of a small list, single line ALL CAPS or Title Case
        cta = ""
        for keyword in ("Book Now", "Learn More", "Shop Now", "Sign Up", "Contact Us", "Get Offer", "Reserve", "Discover"):
            if keyword.lower() in text.lower():
                cta = keyword
                break

        media_type = "video" if "▶" in text or "Play" in text else ("image" if "image" in text.lower() else "other")

        ads.append({
            "libId": lib_id,
            "bodyCopy": body,
            "headline": headline,
            "cta": cta,
            "started": started,
            "mediaType": media_type,
            "variant": variant,
            "active": True,
        })

    # Dedupe by libId
    seen = set()
    unique = []
    for ad in ads:
        if ad["libId"] in seen:
            continue
        seen.add(ad["libId"])
        unique.append(ad)
    return unique


def scrape_facebook_ad_library(
    url: str,
    max_scrolls: int = 6,
    timeout_ms: int = 60_000,
    headless: bool = True,
) -> ScrapeResult:
    """Open URL, scroll, parse ads. Returns ScrapeResult with ads list + sample text."""
    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
                locale="en-US",
            )
            page = context.new_page()
            logger.info(f"Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(2500)
            _dismiss_cookies(page)
            page.wait_for_timeout(1500)
            _scroll_to_load(page, max_scrolls=max_scrolls)

            ads = _extract_ads_from_page(page)
            sample = ""
            try:
                sample = page.inner_text("body", timeout=2000)[:2000]
            except Exception:
                pass
            return ScrapeResult(ads=ads, raw_text_sample=sample)
        finally:
            browser.close()
