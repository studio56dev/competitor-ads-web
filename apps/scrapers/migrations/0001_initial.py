from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScrapeRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("blocked", "Blocked"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("ads_found", models.PositiveIntegerField(default=0)),
                ("ads_new", models.PositiveIntegerField(default=0)),
                ("ads_removed", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
                ("log", models.TextField(blank=True, help_text="Recent log lines / debug info")),
                (
                    "competitor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scrape_runs",
                        to="catalog.competitor",
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at"],
            },
        ),
        migrations.AddIndex(
            model_name="scraperun",
            index=models.Index(fields=["competitor", "-started_at"], name="scrapers_sc_compet_e3a1b9_idx"),
        ),
        migrations.AddIndex(
            model_name="scraperun",
            index=models.Index(fields=["status"], name="scrapers_sc_status_4f7d12_idx"),
        ),
    ]
