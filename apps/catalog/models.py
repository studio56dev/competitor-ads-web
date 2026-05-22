from django.db import models
from django.urls import reverse


class Brand(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="brands",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    industry = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "slug"], name="brand_slug_unique_per_org"
            )
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("brand-detail", args=[self.slug])


class CompetitorSet(models.Model):
    """A grouping of competitors under a brand (e.g. 'Local competitors')."""

    SUBTYPE_CHOICES = [
        ("local", "Local"),
        ("international", "International"),
        ("inspiration", "Inspiration"),
        ("other", "Other"),
    ]

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="sets")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField(blank=True)
    subtype = models.CharField(max_length=30, choices=SUBTYPE_CHOICES, default="other")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["brand", "slug"], name="set_slug_unique_per_brand"
            )
        ]

    def __str__(self) -> str:
        return f"{self.brand.name} · {self.name}"

    def get_absolute_url(self) -> str:
        return reverse("set-detail", args=[self.brand.slug, self.slug])


class Competitor(models.Model):
    set = models.ForeignKey(
        CompetitorSet, on_delete=models.CASCADE, related_name="competitors"
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    industry = models.CharField(max_length=200, blank=True)
    page_id = models.CharField(max_length=100, blank=True, help_text="Facebook page id")
    source_url = models.URLField(blank=True, max_length=1000)
    country = models.CharField(max_length=5, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["set", "slug"], name="competitor_slug_unique_per_set"
            )
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse(
            "competitor-detail",
            args=[self.set.brand.slug, self.set.slug, self.slug],
        )
