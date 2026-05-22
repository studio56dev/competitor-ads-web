from django.db import models


def ad_thumbnail_path(instance: "Ad", filename: str) -> str:
    return (
        f"competitors/{instance.competitor.set.brand.slug}/"
        f"{instance.competitor.set.slug}/{instance.competitor.slug}/"
        f"ad-{instance.lib_id}.jpg"
    )


class Ad(models.Model):
    LANG_CHOICES = [("EN", "English"), ("TR", "Turkish"), ("AR", "Arabic"), ("XX", "Other")]
    MEDIA_CHOICES = [("video", "Video"), ("image", "Image"), ("other", "Other")]

    competitor = models.ForeignKey(
        "catalog.Competitor", on_delete=models.CASCADE, related_name="ads"
    )
    lib_id = models.CharField(max_length=64, help_text="Facebook Ad Library id")
    headline = models.CharField(max_length=500, blank=True)
    body_copy = models.TextField(blank=True)
    cta = models.CharField(max_length=100, blank=True)
    started_text = models.CharField(max_length=200, blank=True)
    started_date = models.DateField(null=True, blank=True)
    media_type = models.CharField(
        max_length=20, choices=MEDIA_CHOICES, default="other", blank=True
    )
    variant_text = models.CharField(max_length=200, blank=True)
    variant_count = models.PositiveIntegerField(default=1)
    language = models.CharField(max_length=4, choices=LANG_CHOICES, default="XX")
    is_active = models.BooleanField(default=True)
    thumbnail = models.ImageField(upload_to=ad_thumbnail_path, blank=True, null=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-first_seen"]
        constraints = [
            models.UniqueConstraint(
                fields=["competitor", "lib_id"], name="ad_unique_per_competitor"
            )
        ]
        indexes = [
            models.Index(fields=["competitor", "is_active"]),
            models.Index(fields=["language"]),
        ]

    def __str__(self) -> str:
        return f"{self.competitor.name} · {self.lib_id}"

    @property
    def facebook_url(self) -> str:
        return f"https://www.facebook.com/ads/library/?id={self.lib_id}"
