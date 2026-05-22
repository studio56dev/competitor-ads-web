from django.db import models


class ScrapeRun(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_BLOCKED = "blocked"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_BLOCKED, "Blocked"),
    ]

    competitor = models.ForeignKey(
        "catalog.Competitor",
        on_delete=models.CASCADE,
        related_name="scrape_runs",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ads_found = models.PositiveIntegerField(default=0)
    ads_new = models.PositiveIntegerField(default=0)
    ads_removed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    log = models.TextField(blank=True, help_text="Recent log lines / debug info")

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["competitor", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"{self.competitor.name} · {self.status} · {self.started_at:%Y-%m-%d %H:%M}"

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
