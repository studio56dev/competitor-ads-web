"""Facebook Ad Library scraper — Faz 3b.

Each ad card is:
  1. Identified by JS (any DIV whose innerText matches 'Library ID: <digits>')
     and tagged with data-scrape-card="<idx>" so Playwright can find it.
  2. Iterated as a Locator → text + screenshot + media_type extracted.

Returned dicts have an extra '_screenshot' bytes key (consumed by tasks.py),
otherwise the shape matches the legacy data.json structure.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from playwright.sync_api import Browser, Page, sync_playwright

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
CTA_KEYWORDS = [
    # English
    "Book Now", "Learn More", "Shop Now", "Sign Up", "Contact Us",
    "Get Offer", "Reserve", "Discover", "Download", "Order Now",
    "Get Quote", "Apply Now", "Subscribe", "Get Directions",
    "Send Message", "Call Now", "Watch More", "Play Game",
    "Send WhatsApp Message", "Send Email", "View Menu", "Visit",
    "Buy Tickets", "Save", "Donate", "Listen Now", "Use App",
    "View Channel", "Get Promotions", "Request Time", "Get Showtimes",
    "See Menu", "View Pricing",
    # Turkish (frequent on TR ads)
    "Rezerve Et", "Hemen Rezerve Et", "Daha Fazla Bilgi", "Şimdi Al",
    "Şimdi Rezerve Et", "Hemen Satın Al", "Mesaj Gönder", "İletişime Geç",
    "Hemen Ara", "Sipariş Ver", "Keşfet", "Üye Ol", "Abone Ol",
    "Hemen İndir", "Daha Fazlasını Öğrenin", "Teklif Al",
]
META_LINE_MARKERS = (
    "Library ID", "Started running", "Sponsored", "ads use this",
    "Platforms", "Active", "Inactive", "Total active",
)


@dataclass
class ScrapeResult:
    ads: list[dict]
    raw_text_sample: str


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
    prev_height = 0
    for i in range(max_scrolls):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(settle_ms)
        try:
            curr = page.evaluate("document.body.scrollHeight")
        except Exception:
            curr = 0
        if curr and curr == prev_height:
            logger.info(f"Scroll {i+1}: page height stable at {curr}, stopping early")
            break
        prev_height = curr


def _find_and_mark_cards(page: Page) -> int:
    """Tag the smallest DIV containing each unique Library ID with data-scrape-card.

    Returns the number of unique cards marked.
    """
    return page.evaluate(
        """
() => {
  // Clear previous tags so re-runs are deterministic
  document.querySelectorAll('[data-scrape-card]').forEach(el => el.removeAttribute('data-scrape-card'));
  const seen = new Set();
  let idx = 0;
  const all = document.querySelectorAll('div');
  for (const el of all) {
    const t = el.innerText || '';
    const m = /library\\s+id:?\\s*(\\d+)/i.exec(t);
    if (!m) continue;
    const libId = m[1];
    if (seen.has(libId)) continue;
    if (t.length > 5000) continue;            // skip wrappers containing many cards
    const r = el.getBoundingClientRect();
    if (r.width < 200 || r.height < 100) continue;
    // Skip if a descendant already got the libId (we want smallest container)
    if (el.querySelector('[data-scrape-card]')) continue;
    seen.add(libId);
    el.setAttribute('data-scrape-card', idx.toString());
    idx += 1;
  }
  return idx;
}
        """
    )


def _parse_card_text(text: str) -> dict | None:
    m = LIB_ID_RE.search(text)
    if not m:
        return None
    lib_id = m.group(1)

    s = STARTED_RE.search(text)
    started = s.group(1).strip() if s else ""

    v = VARIANT_RE.search(text)
    variant = v.group(1).strip() if v else ""

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    body_candidates = [
        ln for ln in lines
        if len(ln) > 25 and not any(m in ln for m in META_LINE_MARKERS)
    ]
    body = max(body_candidates, key=len, default="")

    headline = ""
    if body and body in lines:
        idx = lines.index(body)
        for j in range(idx - 1, max(idx - 4, -1), -1):
            cand = lines[j]
            if 4 <= len(cand) <= 80 and not any(m in cand for m in META_LINE_MARKERS):
                headline = cand
                break

    cta = ""
    lowered = text.lower()
    for keyword in CTA_KEYWORDS:
        if keyword.lower() in lowered:
            cta = keyword
            break

    return {
        "libId": lib_id,
        "bodyCopy": body,
        "headline": headline,
        "cta": cta,
        "started": started,
        "variant": variant,
        "active": True,
    }


def _detect_media_type(card_locator) -> str:
    """video > image > other, based on what's actually rendered inside the card."""
    try:
        if card_locator.locator("video").count() > 0:
            return "video"
        if card_locator.locator('img[src*="scontent"], img[src*="fbcdn"]').count() > 0:
            return "image"
        # Fallback: any non-emoji image counts as image
        if card_locator.locator('img:not([src*="emoji"])').count() > 0:
            return "image"
    except Exception:
        pass
    return "other"


def _largest_media_locator(card_locator):
    """Return the locator for the largest creative img/video inside the card.

    Filters:
      - Skip avatars / icons / emoji (area < 40k or any side < 200)
      - Skip FB UI sprites (src contains '/emoji/', 'rsrc.php')
      - For carousels FB shows multiple imgs; we pick the largest visible one
    """
    try:
        elements = card_locator.locator("img, video").all()
    except Exception:
        return None
    largest = None
    largest_area = 0
    for el in elements:
        try:
            box = el.bounding_box()
        except Exception:
            continue
        if not box:
            continue
        area = box["width"] * box["height"]
        if area < 40_000 or box["width"] < 200 or box["height"] < 200:
            continue
        try:
            src = (el.get_attribute("src") or "").lower()
        except Exception:
            src = ""
        if any(skip in src for skip in ("/emoji/", "rsrc.php", "/static_map.php")):
            continue
        if area > largest_area:
            largest = el
            largest_area = area
    return largest


def _download_creative_via_page(page: Page, media_locator) -> bytes | None:
    """Download the actual creative bytes from FB CDN using the page's session.

    For <img>: use src.
    For <video>: prefer poster, fall back to first <source>.
    Returns the raw bytes or None.
    """
    if media_locator is None:
        return None
    try:
        tag = (media_locator.evaluate("e => e.tagName") or "").upper()
    except Exception:
        return None
    src = None
    try:
        if tag == "VIDEO":
            src = media_locator.get_attribute("poster")
            if not src:
                inner_source = media_locator.locator("source").first
                if inner_source.count() > 0:
                    src = inner_source.get_attribute("src")
        else:
            src = media_locator.get_attribute("src")
    except Exception:
        return None
    if not src or src.startswith("data:") or src.startswith("blob:"):
        return None
    try:
        resp = page.request.get(src, timeout=10_000)
    except Exception:
        return None
    if not resp.ok:
        return None
    try:
        body = resp.body()
    except Exception:
        return None
    # Sanity check: at least a few KB
    if len(body) < 1_000:
        return None
    return body


URL_LIKE_RE = re.compile(
    r"^(https?://|www\.)", re.I
)
DOMAIN_LIKE_RE = re.compile(
    r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.I
)
SKIP_BUTTON_TEXTS = (
    "See ad details", "See summary details", "See more", "See less",
    "Reklam ayrıntılarını", "Daha fazla", "details",
)


def _looks_like_url(txt: str) -> bool:
    s = txt.strip().strip(".,/")
    if URL_LIKE_RE.search(s):
        return True
    if DOMAIN_LIKE_RE.match(s):
        return True
    # All caps + contains a dot is typical of FB's displayed link domain
    if "." in s and s.upper() == s and any(c.isalpha() for c in s):
        return True
    return False


def _extract_cta_from_dom(card_locator) -> str:
    """Find a CTA button inside the card and return its text.

    FB renders the ad's CTA as a button-styled link near the bottom. We
    filter out:
    - URL/domain text (FB also shows the destination URL as a link)
    - 'See ad details' and similar housekeeping buttons
    - Multi-line text
    """
    try:
        candidates = card_locator.locator('[role="button"], a[role="link"]').all()
    except Exception:
        return ""
    for el in candidates:
        try:
            txt = el.inner_text(timeout=500).strip()
        except Exception:
            continue
        if not txt or "\n" in txt:
            continue
        if any(skip.lower() in txt.lower() for skip in SKIP_BUTTON_TEXTS):
            continue
        if _looks_like_url(txt):
            continue
        # CTAs are typically 2-35 chars, 1-4 words
        if 2 <= len(txt) <= 35 and len(txt.split()) <= 4:
            return txt
    return ""


def _extract_ads_from_page(page: Page) -> list[dict]:
    """Tag every card, then iterate over them as locators to get text + screenshot."""
    marked = _find_and_mark_cards(page)
    logger.info(f"Marked {marked} card candidates")
    if marked == 0:
        return []

    # Bring cards into viewport progressively so screenshots are stable
    ads: list[dict] = []
    for i in range(marked):
        card = page.locator(f'[data-scrape-card="{i}"]')
        if card.count() == 0:
            continue
        try:
            text = card.inner_text(timeout=2000)
        except Exception as exc:
            logger.warning(f"Card {i}: inner_text failed: {exc}")
            continue

        parsed = _parse_card_text(text)
        if not parsed:
            continue

        parsed["mediaType"] = _detect_media_type(card)

        # CTA: keyword scan from card text already ran in _parse_card_text.
        # Use DOM scan only as a fallback when the text scan missed it.
        if not parsed.get("cta"):
            parsed["cta"] = _extract_cta_from_dom(card)

        # Capture creative bytes — prefer downloading the actual file from FB CDN
        # (cleanest, looks identical to legacy thumbnails). Fall back to
        # media-element screenshot, then full-card screenshot as last resort.
        screenshot_bytes = None
        try:
            card.scroll_into_view_if_needed(timeout=2000)
            page.wait_for_timeout(150)
            media_el = _largest_media_locator(card)

            # 1) Try real CDN download via page.request (uses browser cookies)
            if media_el is not None:
                screenshot_bytes = _download_creative_via_page(page, media_el)

            # 2) Fall back: screenshot of just the media element
            if screenshot_bytes is None and media_el is not None:
                try:
                    screenshot_bytes = media_el.screenshot(timeout=5000)
                except Exception as exc:
                    logger.warning(
                        f"Card {i} ({parsed['libId']}): media screenshot failed: {exc}"
                    )

            # 3) Last resort: full card screenshot (noisy but better than nothing)
            if screenshot_bytes is None:
                screenshot_bytes = card.screenshot(timeout=5000)
        except Exception as exc:
            logger.warning(f"Card {i} ({parsed['libId']}): screenshot failed: {exc}")
        parsed["_screenshot"] = screenshot_bytes

        ads.append(parsed)

    # Dedupe by libId (the data-scrape-card marking already dedupes, defensive)
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
