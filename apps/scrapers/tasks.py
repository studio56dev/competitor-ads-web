import logging

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.ads.models import Ad
from apps.ads.services import detect_lang, parse_started_date, variant_count
from apps.catalog.models import Competitor

from .facebook import scrape_facebook_ad_library
from .models import ScrapeRun

logger = logging.getLogger(__name__)


def _ext_for_bytes(b: bytes) -> str:
    """Detect image format from magic bytes so we save with the right extension."""
    if not b:
        return "bin"
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return "png"  # safe fallback (Playwright screenshots are PNG by default)


@shared_task(bind=True)
def scrape_competitor_task(self, competitor_id: int, max_scrolls: int = 6):
    """Scrape a single competitor and update its Ad records."""
    try:
        competitor = Competitor.objects.select_related("set__brand__organization").get(
            pk=competitor_id
        )
    except Competitor.DoesNotExist:
        logger.error(f"Competitor {competitor_id} not found")
        return {"status": "failed", "error": "competitor_not_found"}

    if not competitor.source_url:
        logger.warning(f"{competitor} has no source_url, skipping")
        return {"status": "failed", "error": "no_source_url"}

    run = ScrapeRun.objects.create(
        competitor=competitor, status=ScrapeRun.STATUS_RUNNING
    )

    log_lines: list[str] = [f"[{timezone.now():%Y-%m-%d %H:%M:%S}] scrape start"]

    try:
        result = scrape_facebook_ad_library(
            competitor.source_url, max_scrolls=max_scrolls
        )
        log_lines.append(f"scraped {len(result.ads)} ad cards")
        if not result.ads and "Library ID" not in result.raw_text_sample:
            # Likely blocked / not logged in / page didn't load ads
            run.status = ScrapeRun.STATUS_BLOCKED
            run.error_message = "No Library IDs detected on page — likely blocked or rate-limited"
            log_lines.append("page text sample (first 500 chars):\n" + result.raw_text_sample[:500])
        else:
            new_count = 0
            thumbs_saved = 0
            scraped_lib_ids: set[str] = set()
            for ad_data in result.ads:
                lib_id = ad_data["libId"]
                scraped_lib_ids.add(lib_id)
                screenshot_bytes = ad_data.pop("_screenshot", None)
                body = ad_data.get("bodyCopy", "")
                defaults = {
                    "body_copy": body,
                    "headline": ad_data.get("headline", ""),
                    "cta": ad_data.get("cta", ""),
                    "started_text": ad_data.get("started", ""),
                    "started_date": parse_started_date(ad_data.get("started", "")),
                    "media_type": ad_data.get("mediaType") or "other",
                    "variant_text": ad_data.get("variant", ""),
                    "variant_count": variant_count(ad_data.get("variant", "")),
                    "language": detect_lang(body),
                    "is_active": True,
                }
                obj, created = Ad.objects.update_or_create(
                    competitor=competitor, lib_id=lib_id, defaults=defaults
                )
                if created:
                    new_count += 1
                # Only fill in a thumbnail when the Ad doesn't already have one
                # (this preserves richer legacy/imported screenshots).
                if screenshot_bytes and not obj.thumbnail:
                    ext = _ext_for_bytes(screenshot_bytes)
                    obj.thumbnail.save(
                        f"ad-{lib_id}.{ext}",
                        ContentFile(screenshot_bytes),
                        save=True,
                    )
                    thumbs_saved += 1

            removed = (
                Ad.objects.filter(competitor=competitor, is_active=True)
                .exclude(lib_id__in=scraped_lib_ids)
                .update(is_active=False)
            )
            run.status = ScrapeRun.STATUS_SUCCESS
            run.ads_found = len(result.ads)
            run.ads_new = new_count
            run.ads_removed = removed
            log_lines.append(
                f"saved: {len(result.ads)} found / {new_count} new / "
                f"{removed} marked inactive / {thumbs_saved} thumbnails added"
            )
    except Exception as exc:
        logger.exception(f"Scrape failed for competitor {competitor_id}")
        run.status = ScrapeRun.STATUS_FAILED
        run.error_message = f"{type(exc).__name__}: {exc}"
        log_lines.append(f"EXCEPTION: {run.error_message}")
    finally:
        run.finished_at = timezone.now()
        run.log = "\n".join(log_lines)[:8000]
        run.save()

    return {
        "status": run.status,
        "found": run.ads_found,
        "new": run.ads_new,
        "removed": run.ads_removed,
        "run_id": run.pk,
    }


@shared_task
def scrape_all_competitors_task():
    """Enqueue a scrape job for every competitor with a source_url."""
    qs = Competitor.objects.exclude(source_url="").values_list("id", flat=True)
    count = 0
    for cid in qs:
        scrape_competitor_task.delay(cid)
        count += 1
    return {"enqueued": count}
