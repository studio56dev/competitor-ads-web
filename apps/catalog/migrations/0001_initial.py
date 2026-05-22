from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Brand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=200)),
                ("industry", models.CharField(blank=True, max_length=200)),
                ("city", models.CharField(blank=True, max_length=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="brands",
                        to="organizations.organization",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CompetitorSet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "subtype",
                    models.CharField(
                        choices=[
                            ("local", "Local"),
                            ("international", "International"),
                            ("inspiration", "Inspiration"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "brand",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sets",
                        to="catalog.brand",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Competitor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=200)),
                ("industry", models.CharField(blank=True, max_length=200)),
                ("page_id", models.CharField(blank=True, help_text="Facebook page id", max_length=100)),
                ("source_url", models.URLField(blank=True, max_length=1000)),
                ("country", models.CharField(blank=True, max_length=5)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="competitors",
                        to="catalog.competitorset",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddConstraint(
            model_name="brand",
            constraint=models.UniqueConstraint(
                fields=("organization", "slug"), name="brand_slug_unique_per_org"
            ),
        ),
        migrations.AddConstraint(
            model_name="competitorset",
            constraint=models.UniqueConstraint(
                fields=("brand", "slug"), name="set_slug_unique_per_brand"
            ),
        ),
        migrations.AddConstraint(
            model_name="competitor",
            constraint=models.UniqueConstraint(
                fields=("set", "slug"), name="competitor_slug_unique_per_set"
            ),
        ),
    ]
