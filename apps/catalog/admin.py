from django.contrib import admin

from .models import Brand, Competitor, CompetitorSet


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "industry", "city", "created_at")
    list_filter = ("organization", "industry", "city")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("organization",)


@admin.register(CompetitorSet)
class CompetitorSetAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "subtype", "created_at")
    list_filter = ("brand__organization", "brand", "subtype")
    search_fields = ("name", "slug", "brand__name")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("brand",)


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ("name", "set", "industry", "country", "created_at")
    list_filter = ("set__brand", "set", "country", "industry")
    search_fields = ("name", "slug", "page_id")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("set__brand",)
