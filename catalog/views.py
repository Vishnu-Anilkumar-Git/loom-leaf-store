from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, render

from reviews.forms import ReviewForm

from .filters import base_queryset, filter_products
from .models import Category, Collection, Product


def _list_context(request, *, title, eyebrow, base=None, extra=None):
    context = {"title": title, "eyebrow": eyebrow, "hide_footer_newsletter": False}
    context.update(filter_products(request, base))
    if extra:
        context.update(extra)
    return context


def product_list(request):
    context = _list_context(request, title="All Products", eyebrow="The full collection")
    return render(request, "catalog/product_list.html", context)


def category_products(request, category):
    category_obj = get_object_or_404(Category, kind=category, is_active=True)
    base = base_queryset().filter(category=category_obj)
    context = _list_context(
        request,
        title=category_obj.name,
        eyebrow=f"{category_obj.name} / Collection",
        base=base,
        extra={"category_obj": category_obj},
    )
    context["category_description"] = category_obj.description
    context["category_image"] = category_obj.image
    return render(request, "catalog/product_list.html", context)


def new_arrivals(request):
    base = base_queryset().filter(
        Q(is_new_arrival=True) | Q(collections__slug="new-season")
    )
    context = _list_context(
        request, title="New Arrivals", eyebrow="Just landed", base=base
    )
    return render(request, "catalog/product_list.html", context)


def search(request):
    query = (request.GET.get("q") or "").strip()
    context = _list_context(request, title="Search", eyebrow="Find your piece")
    context["search_query"] = query
    if not query:
        context.update(
            {"products": [], "result_count": 0, "page_obj": None, "search_empty": True}
        )
    return render(request, "catalog/product_list.html", context)


def collection_list(request):
    collections = Collection.objects.filter(is_active=True).annotate(
        product_count=Count(
            "products",
            filter=Q(
                products__is_active=True,
                products__category__kind__in=[Category.MEN, Category.UNISEX],
            ),
        )
    )
    return render(
        request,
        "catalog/collection_list.html",
        {"collections": collections, "title": "Collections", "eyebrow": "LOOM&LEAF edits"},
    )


def collection_detail(request, slug):
    collection = get_object_or_404(Collection, slug=slug, is_active=True)
    base = base_queryset().filter(collections=collection)
    context = _list_context(
        request,
        title=collection.name,
        eyebrow="Collection",
        base=base,
        extra={"collection": collection},
    )
    context["collection_description"] = collection.description
    return render(request, "catalog/product_list.html", context)


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.active()
        .filter(category__kind__in=[Category.MEN, Category.UNISEX])
        .select_related("category")
        .prefetch_related("images", "variants__size", "variants__color", "collections", "reviews__user"),
        slug=slug,
    )
    approved_reviews = product.reviews.filter(is_approved=True).select_related("user")
    rating = approved_reviews.aggregate(avg=Avg("rating"), total=Count("id"))
    related = (
        base_queryset()
        .filter(category=product.category)
        .exclude(pk=product.pk)[:4]
    )
    gallery = [product.main_image] if product.main_image else []
    gallery += [image.image for image in product.images.all() if image.image]
    user_reviewed = (
        request.user.is_authenticated
        and product.reviews.filter(user=request.user).exists()
    )
    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "approved_reviews": approved_reviews,
            "rating_avg": rating["avg"] or 0,
            "rating_total": rating["total"],
            "rating_breakdown": [
                {
                    "star": star,
                    "count": approved_reviews.filter(rating=star).count(),
                }
                for star in (5, 4, 3, 2, 1)
            ],
            "related_products": related,
            "gallery": gallery,
            "review_form": ReviewForm(),
            "user_reviewed": user_reviewed,
            "reviews": approved_reviews,
            "title": product.name,
        },
    )
