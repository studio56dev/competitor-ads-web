from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, render

from apps.ads.models import Ad
from apps.ads.services import cluster_by_copy, summarize_ads
from apps.catalog.models import Brand, Competitor, CompetitorSet


def home(request):
    brands = (
        Brand.objects.annotate(
            set_count=Count("sets", distinct=True),
            ad_count=Count("sets__competitors__ads", distinct=True),
        ).order_by("name")
    )
    return render(request, "dashboard/home.html", {"brands": brands})


def brand_detail(request, brand_slug):
    brand = get_object_or_404(Brand, slug=brand_slug)
    sets = (
        brand.sets.annotate(
            competitor_count=Count("competitors", distinct=True),
            ad_count=Count("competitors__ads", distinct=True),
        ).order_by("name")
    )
    return render(request, "dashboard/brand_detail.html", {"brand": brand, "sets": sets})


def set_detail(request, brand_slug, set_slug):
    cs = get_object_or_404(
        CompetitorSet.objects.select_related("brand"),
        brand__slug=brand_slug, slug=set_slug,
    )
    competitors = (
        cs.competitors.annotate(
            ad_count=Count("ads", distinct=True),
            active_ad_count=Sum("ads__variant_count"),
        ).order_by("name")
    )
    return render(
        request, "dashboard/set_detail.html",
        {"brand": cs.brand, "set": cs, "competitors": competitors},
    )


def competitor_detail(request, brand_slug, set_slug, competitor_slug):
    competitor = get_object_or_404(
        Competitor.objects.select_related("set__brand"),
        set__brand__slug=brand_slug,
        set__slug=set_slug,
        slug=competitor_slug,
    )
    ads = list(competitor.ads.all())
    stats = summarize_ads(ads)

    # Cluster analysis using dict-style accessors for compatibility
    ad_dicts = [
        {
            "bodyCopy": a.body_copy,
            "headline": a.headline,
            "variant": a.variant_text,
        }
        for a in ads
    ]
    clusters = cluster_by_copy(ad_dicts)[:8]

    lang_filter = request.GET.get("lang", "all")
    fmt_filter = request.GET.get("format", "all")
    q = (request.GET.get("q") or "").strip().lower()

    def keep(ad: Ad) -> bool:
        if lang_filter != "all" and ad.language != lang_filter:
            return False
        if fmt_filter != "all" and ad.media_type != fmt_filter:
            return False
        if q:
            hay = (ad.body_copy + " " + (ad.headline or "")).lower()
            if q not in hay:
                return False
        return True

    visible_ads = [a for a in ads if keep(a)]

    return render(
        request,
        "dashboard/competitor_detail.html",
        {
            "brand": competitor.set.brand,
            "set": competitor.set,
            "competitor": competitor,
            "all_ads": ads,
            "ads": visible_ads,
            "stats": stats,
            "clusters": clusters,
            "lang_filter": lang_filter,
            "fmt_filter": fmt_filter,
            "q": q,
        },
    )
