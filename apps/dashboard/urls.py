from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("<slug:brand_slug>/", views.brand_detail, name="brand-detail"),
    path("<slug:brand_slug>/<slug:set_slug>/", views.set_detail, name="set-detail"),
    path(
        "<slug:brand_slug>/<slug:set_slug>/<slug:competitor_slug>/",
        views.competitor_detail,
        name="competitor-detail",
    ),
]
