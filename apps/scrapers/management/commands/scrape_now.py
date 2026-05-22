"""Manual scraper test command.

Usage:
    # Async via Celery (production-style)
    python manage.py scrape_now four-seasons-bosphorus

    # Sync — run scraper inline in current process (for debugging selectors)
    python manage.py scrape_now four-seasons-bosphorus --sync

    # Scroll fewer times for faster iteration
    python manage.py scrape_now peninsula --sync --scrolls 2
"""
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Competitor


class Command(BaseCommand):
    help = "Trigger a scrape for one competitor (by slug)."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Competitor slug, e.g. 'four-seasons-bosphorus'")
        parser.add_argument(
            "--sync", action="store_true",
            help="Run scraper inline (don't enqueue via Celery). Best for debugging.",
        )
        parser.add_argument(
            "--scrolls", type=int, default=6,
            help="Number of scroll-downs to load lazy content (default 6).",
        )

    def handle(self, *args, **opts):
        slug = opts["slug"]
        try:
            competitor = Competitor.objects.get(slug=slug)
        except Competitor.DoesNotExist:
            raise CommandError(f"Competitor with slug '{slug}' not found")

        self.stdout.write(f"Competitor: {competitor} (id={competitor.pk})")
        self.stdout.write(f"URL: {competitor.source_url or '(none — will fail)'}")

        if opts["sync"]:
            from apps.scrapers.tasks import scrape_competitor_task
            self.stdout.write(self.style.WARNING("Running synchronously (no Celery)…"))
            result = scrape_competitor_task.apply(
                args=(competitor.pk,), kwargs={"max_scrolls": opts["scrolls"]}
            ).get()
            self.stdout.write(self.style.SUCCESS(f"Result: {result}"))
        else:
            from apps.scrapers.tasks import scrape_competitor_task
            async_result = scrape_competitor_task.delay(
                competitor.pk, max_scrolls=opts["scrolls"]
            )
            self.stdout.write(self.style.SUCCESS(f"Enqueued — task id: {async_result.id}"))
            self.stdout.write("Tail the worker container to watch:")
            self.stdout.write("  docker compose logs -f worker")
