"""Import the original file-based competitor-ads/ tree into the database.

Usage:
    python manage.py import_legacy_data /path/to/competitor-ads/ \\
        --organization "Studio Fifty Six" --org-slug studio56

If --organization isn't provided, defaults to "Default Organization" / "default".

Tree expected:
    <root>/<brand-slug>/meta.json  (type: brand)
                       /<set-slug>/meta.json  (type: set)
                                  /<comp-slug>/meta.json  (type: competitor)
                                              /data.json
                                              /screenshots/ad-<libId>.jpg
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.ads.models import Ad, ad_thumbnail_path
from apps.ads.services import clean_copy, detect_lang, parse_started_date, variant_count
from apps.catalog.models import Brand, Competitor, CompetitorSet
from apps.organizations.models import Organization


class Command(BaseCommand):
    help = "Import the file-based competitor-ads/ tree into the database."

    def add_arguments(self, parser):
        parser.add_argument("root", help="Path to the competitor-ads/ root directory")
        parser.add_argument(
            "--organization", default="Default Organization",
            help="Display name of the organization to attach imported brands to",
        )
        parser.add_argument(
            "--org-slug", default="default",
            help="Slug for the organization",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Parse and report without writing to DB",
        )

    def handle(self, *args, **opts):
        root = Path(opts["root"]).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise CommandError(f"Path not found or not a directory: {root}")

        dry = opts["dry_run"]
        org_name = opts["organization"]
        org_slug = opts["org_slug"]

        if dry:
            self.stdout.write(self.style.WARNING("DRY RUN — no DB writes."))

        if not dry:
            org, _ = Organization.objects.get_or_create(
                slug=org_slug, defaults={"name": org_name}
            )
            self.stdout.write(f"Organization: {org} (id={org.pk})")
        else:
            org = None

        totals = {"brands": 0, "sets": 0, "competitors": 0, "ads": 0, "thumbs": 0}

        for brand_dir in sorted(root.iterdir()):
            if not self._is_data_dir(brand_dir):
                continue
            brand_meta = self._load_meta(brand_dir, expected_type="brand")
            if not brand_meta:
                continue
            slug = brand_meta.get("slug") or slugify(brand_dir.name)
            self.stdout.write(self.style.SUCCESS(f"\nBRAND: {brand_meta['displayName']} ({slug})"))
            totals["brands"] += 1

            brand = None
            if not dry:
                brand, _ = Brand.objects.update_or_create(
                    organization=org, slug=slug,
                    defaults={
                        "name": brand_meta["displayName"],
                        "industry": brand_meta.get("industry", ""),
                        "city": brand_meta.get("city", ""),
                    },
                )

            for set_dir in sorted(brand_dir.iterdir()):
                if not self._is_data_dir(set_dir):
                    continue
                set_meta = self._load_meta(set_dir, expected_type="set")
                if not set_meta:
                    continue
                set_slug = set_meta.get("slug") or slugify(set_dir.name)
                self.stdout.write(f"  SET: {set_meta['displayName']} ({set_slug})")
                totals["sets"] += 1

                cs = None
                if not dry:
                    cs, _ = CompetitorSet.objects.update_or_create(
                        brand=brand, slug=set_slug,
                        defaults={
                            "name": set_meta["displayName"],
                            "description": set_meta.get("description", ""),
                            "subtype": set_meta.get("subtype", "other"),
                        },
                    )

                for comp_dir in sorted(set_dir.iterdir()):
                    if not self._is_data_dir(comp_dir):
                        continue
                    comp_meta = self._load_meta(comp_dir, expected_type="competitor")
                    if not comp_meta:
                        continue
                    comp_slug = comp_meta.get("slug") or slugify(comp_dir.name)
                    self.stdout.write(f"    COMP: {comp_meta['displayName']} ({comp_slug})")
                    totals["competitors"] += 1

                    competitor = None
                    if not dry:
                        competitor, _ = Competitor.objects.update_or_create(
                            set=cs, slug=comp_slug,
                            defaults={
                                "name": comp_meta["displayName"],
                                "industry": comp_meta.get("industry", ""),
                                "page_id": comp_meta.get("pageId", ""),
                                "source_url": comp_meta.get("sourceUrl", ""),
                                "country": comp_meta.get("country", ""),
                            },
                        )

                    data_path = comp_dir / "data.json"
                    if not data_path.exists():
                        self.stdout.write(self.style.WARNING("      (no data.json)"))
                        continue
                    ads_data = json.loads(data_path.read_text())
                    screenshots_dir = comp_dir / "screenshots"

                    for ad in ads_data:
                        body = clean_copy(ad.get("bodyCopy", ""), ad.get("headline", ""))
                        lang = detect_lang(body or ad.get("bodyCopy", ""))
                        thumb_src = screenshots_dir / f"ad-{ad['libId']}.jpg"

                        if dry:
                            totals["ads"] += 1
                            if thumb_src.exists():
                                totals["thumbs"] += 1
                            continue

                        defaults = {
                            "headline": ad.get("headline", "") or "",
                            "body_copy": body,
                            "cta": ad.get("cta", "") or "",
                            "started_text": ad.get("started", "") or "",
                            "started_date": parse_started_date(ad.get("started", "")),
                            "media_type": ad.get("mediaType", "") or "other",
                            "variant_text": ad.get("variant", "") or "",
                            "variant_count": variant_count(ad.get("variant", "")),
                            "language": lang,
                            "is_active": bool(ad.get("active", False)),
                        }
                        obj, created = Ad.objects.update_or_create(
                            competitor=competitor, lib_id=ad["libId"],
                            defaults=defaults,
                        )
                        totals["ads"] += 1

                        if thumb_src.exists() and not obj.thumbnail:
                            with thumb_src.open("rb") as f:
                                obj.thumbnail.save(f"ad-{ad['libId']}.jpg", File(f), save=True)
                            totals["thumbs"] += 1

        self.stdout.write("\n" + self.style.SUCCESS("=== Import summary ==="))
        for k, v in totals.items():
            self.stdout.write(f"  {k}: {v}")

    def _is_data_dir(self, p: Path) -> bool:
        return p.is_dir() and not p.name.startswith((".", "_"))

    def _load_meta(self, d: Path, expected_type: str | None = None) -> dict | None:
        meta_path = d / "meta.json"
        if not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError as e:
            self.stderr.write(f"Bad JSON in {meta_path}: {e}")
            return None
        if expected_type and meta.get("type") != expected_type:
            return None
        return meta
