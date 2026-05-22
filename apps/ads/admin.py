from django.contrib import admin
from django.utils.html import format_html

from .models import Ad


@admin.register(Ad)
class AdAdmin(admin.ModelAdmin):
    list_display = (
        "lib_id",
        "competitor",
        "language",
        "media_type",
        "is_active",
        "started_text",
        "thumb_preview",
    )
    list_filter = (
        "competitor__set__brand",
        "competitor",
        "language",
        "media_type",
        "is_active",
    )
    search_fields = ("lib_id", "headline", "body_copy", "cta")
    readonly_fields = ("first_seen", "last_seen", "thumb_preview")
    list_select_related = ("competitor__set__brand",)

    @admin.display(description="Thumb")
    def thumb_preview(self, obj: Ad) -> str:
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="max-height:60px;border-radius:4px">',
                obj.thumbnail.url,
            )
        return "—"
