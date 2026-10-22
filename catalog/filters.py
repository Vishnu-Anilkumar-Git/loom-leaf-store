"""Catalogue filtering, search and sorting (all server-side)."""
from decimal import Decimal, InvalidOperation

from django.core.paginator import Paginator
from django.db.models import Avg, Case, Count, DecimalField, F, Q, Value, When
from django.db.models.functions import Coalesce

from .models import Category, Collection, Color, Product, Size

SORT_OPTIONS = {
    "featured": "Featured",
    "newest": "Newest",
    "price_asc": "Price: low to high",
    "price_desc": "Price: high to low",
    "name": "Name A–Z",
}

PAGE_SIZE = 12


def parse_decimal(value):
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount >= 0 else None


def base_queryset():
    price_expression = Case(
        When(sale_price__isnull=False, sale_price__lt=F("base_price"), then=F("sale_price")),
        default=F("base_price"),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    return (
        Product.objects.active()
        .select_related("category")
        .prefetch_related("variants__size", "variants__color", "collections")
        .annotate(
            effective_price=price_expression,
            rating_avg=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            rating_total=Count("reviews", filter=Q(reviews__is_approved=True), distinct=True),
        )
    )


def filter_products(request, queryset=None):
    qs = queryset if queryset is not None else base_queryset()
    # Legacy Women/Kids catalog records are intentionally excluded from all shopper
    # listings, search, collections and new-arrival pages.
    qs = qs.filter(category__kind__in=[Category.MEN, Category.UNISEX])
    params = request.GET

    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(short_description__icontains=q)
            | Q(description__icontains=q)
            | Q(sku__icontains=q)
            | Q(category__name__icontains=q)
        )

    category_kind = (params.get("category") or "").strip()
    if category_kind:
        qs = qs.filter(category__kind=category_kind)

    collection_slug = (params.get("collection") or "").strip()
    if collection_slug:
        qs = qs.filter(collections__slug=collection_slug)

    min_price = parse_decimal(params.get("min_price"))
    max_price = parse_decimal(params.get("max_price"))
    if min_price is not None:
        qs = qs.filter(effective_price__gte=min_price)
    if max_price is not None:
        qs = qs.filter(effective_price__lte=max_price)
    if min_price is not None and max_price is not None and min_price > max_price:
        qs = qs.none()

    sizes = [s for s in params.getlist("size") if s]
    if sizes:
        qs = qs.filter(variants__size__code__in=sizes, variants__is_active=True)
    colors = [c for c in params.getlist("color") if c]
    if colors:
        qs = qs.filter(variants__color__slug__in=colors, variants__is_active=True)
    if params.get("availability") == "in_stock":
        qs = qs.filter(variants__stock__gt=0, variants__is_active=True)
    if params.get("sale") in {"1", "on", "true"}:
        qs = qs.filter(sale_price__isnull=False, sale_price__lt=F("base_price"))

    sort = params.get("sort") if params.get("sort") in SORT_OPTIONS else "featured"
    ordering = {
        "featured": ["-is_featured", "-is_new_arrival", "-created_at", "name"],
        "newest": ["-created_at", "name"],
        "price_asc": ["effective_price", "name"],
        "price_desc": ["-effective_price", "name"],
        "name": ["name"],
    }[sort]
    qs = qs.order_by(*ordering).distinct()

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(params.get("page"))

    query = params.copy()
    query.pop("page", None)
    query_string = query.urlencode()

    active_filters = {
        "q": q,
        "category": category_kind,
        "collection": collection_slug,
        "min_price": params.get("min_price", ""),
        "max_price": params.get("max_price", ""),
        "size": sizes,
        "color": colors,
        "availability": params.get("availability", ""),
        "sale": params.get("sale", ""),
        "sort": sort,
    }
    has_filters = any(
        [
            q,
            category_kind,
            collection_slug,
            params.get("min_price"),
            params.get("max_price"),
            sizes,
            colors,
            params.get("availability"),
            params.get("sale"),
        ]
    )
    return {
        "page_obj": page,
        "products": page.object_list,
        "result_count": paginator.count,
        "categories": Category.objects.filter(
            is_active=True, kind__in=[Category.MEN, Category.UNISEX]
        ),
        "collections": Collection.objects.filter(is_active=True),
        "sizes": Size.objects.all(),
        "colors": Color.objects.all(),
        "sort_options": SORT_OPTIONS,
        "active_filters": active_filters,
        "has_filters": has_filters,
        "query_string": query_string,
        "search_query": q,
    }
