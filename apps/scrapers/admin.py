from django.contrib import admin
from django.utils.html import format_html

from .models import ScrapeRun


@admin.register(ScrapeRun)
class ScrapeRunAdmin(admin.ModelAdmin):
    list_display = (
        "competitor",
        "status_pill",
        "started_at",
        "duration_seconds",
        "ads_found",
        "ads_new",
        "ads_removed",
    )
    list_filter = ("status", "competitor__set__brand")
    search_fields = ("competitor__name", "error_message")
    readonly_fields = ("started_at", "finished_at", "duration_seconds")
    list_select_related = ("competitor__set__brand",)
    date_hierarchy = "started_at"

    @admin.display(description="Status")
    def status_pill(self, obj: ScrapeRun) -> str:
        colors = {
            "pending": "#888",
            "running": "#2196F3",
            "success": "#4CAF50",
            "failed": "#F44336",
            "blocked": "#FF9800",
        }
        color = colors.get(obj.status, "#888")
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px;">{}</span>',
            color, obj.get_status_display(),
        )
