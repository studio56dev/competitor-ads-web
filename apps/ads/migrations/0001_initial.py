from django.db import migrations, models
import django.db.models.deletion
import apps.ads.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Ad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lib_id", models.CharField(help_text="Facebook Ad Library id", max_length=64)),
                ("headline", models.CharField(blank=True, max_length=500)),
                ("body_copy", models.TextField(blank=True)),
                ("cta", models.CharField(blank=True, max_length=100)),
                ("started_text", models.CharField(blank=True, max_length=200)),
                ("started_date", models.DateField(blank=True, null=True)),
                (
                    "media_type",
                    models.CharField(
                        blank=True,
                        choices=[("video", "Video"), ("image", "Image"), ("other", "Other")],
                        default="other",
                        max_length=20,
                    ),
                ),
                ("variant_text", models.CharField(blank=True, max_length=200)),
                ("variant_count", models.PositiveIntegerField(default=1)),
                (
                    "language",
                    models.CharField(
                        choices=[("EN", "English"), ("TR", "Turkish"), ("AR", "Arabic"), ("XX", "Other")],
                        default="XX",
                        max_length=4,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "thumbnail",
                    models.ImageField(blank=True, null=True, upload_to=apps.ads.models.ad_thumbnail_path),
                ),
                ("first_seen", models.DateTimeField(auto_now_add=True)),
                ("last_seen", models.DateTimeField(auto_now=True)),
                (
                    "competitor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ads",
                        to="catalog.competitor",
                    ),
                ),
            ],
            options={
                "ordering": ["-first_seen"],
            },
        ),
        migrations.AddConstraint(
            model_name="ad",
            constraint=models.UniqueConstraint(
                fields=("competitor", "lib_id"), name="ad_unique_per_competitor"
            ),
        ),
        migrations.AddIndex(
            model_name="ad",
            index=models.Index(
                fields=["competitor", "is_active"], name="ads_ad_compet_b9c8e8_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="ad",
            index=models.Index(fields=["language"], name="ads_ad_languag_5e3c12_idx"),
        ),
    ]
