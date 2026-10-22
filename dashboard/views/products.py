"""Product and inventory management views for the staff dashboard."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from catalog.models import Color, Product, ProductVariant, Size

from ..access import (
    ADDITION,
    CHANGE,
    log_admin_action,
    require_permission,
    safe_redirect_url,
    staff_member_required,
)
from ..forms import ProductForm, StockAdjustForm, VariantFormSet
from ..services import low_stock_variants, out_of_stock_variants

SORT_CHOICES = {
    "newest": "-created_at",
    "name": "name",
    "price_asc": "base_price",
    "price_desc": "-base_price",
    "stock_asc": "stock_units",
    "stock_desc": "-stock_units",
}


@require_GET
@staff_member_required
def product_list(request):
    qs = Product.objects.select_related("category").annotate(
        stock_units=Sum(
            "variants__stock",
            filter=Q(variants__is_active=True),
        )
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
        )

    status = request.GET.get("status", "all")
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "archived":
        qs = qs.filter(is_active=False)
    elif status == "sale":
        qs = qs.filter(sale_price__isnull=False)
    elif status == "new":
        qs = qs.filter(is_new_arrival=True)

    category = request.GET.get("category", "")
    if category:
        qs = qs.filter(category__slug=category)

    stock_filter = request.GET.get("stock", "")
    if stock_filter == "in":
        qs = qs.filter(variants__stock__gt=0, variants__is_active=True).distinct()
    elif stock_filter == "out":
        qs = qs.exclude(variants__stock__gt=0, variants__is_active=True)

    sort = request.GET.get("sort", "newest")
    order_field = SORT_CHOICES.get(sort, "-created_at")
    qs = qs.order_by(order_field, "-id")

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page": page,
        "query": query,
        "status": status,
        "category": category,
        "stock_filter": stock_filter,
        "sort": sort,
        "categories": list(Product.objects.values_list("category__slug", "category__name").distinct()),
        "page_title": "Products",
        "nav_section": "products",
    }
    return render(request, "dashboard/product_list.html", context)


@require_http_methods(["GET", "POST"])
@require_permission("catalog.add_product")
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    formset = VariantFormSet(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            product = form.save()
            formset.instance = product
            formset.save()
        log_admin_action(
            request.user, product, ADDITION, f"Created product {product.sku} via dashboard."
        )
        messages.success(request, f"“{product.name}” was created.")
        return redirect("dashboard:product_edit", product.pk)
    context = {
        "form": form,
        "formset": formset,
        "page_title": "Add product",
        "nav_section": "products",
        "is_create": True,
    }
    return render(request, "dashboard/product_form.html", context)


@require_http_methods(["GET", "POST"])
@require_permission("catalog.change_product")
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        formset = VariantFormSet(request.POST, request.FILES, instance=product)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                product = form.save()
                formset.save()
            log_admin_action(
                request.user, product, CHANGE, f"Updated product {product.sku} via dashboard."
            )
            messages.success(request, f"“{product.name}” was updated.")
            return redirect("dashboard:product_edit", product.pk)
    else:
        form = ProductForm(instance=product)
        formset = VariantFormSet(instance=product)

    context = {
        "form": form,
        "formset": formset,
        "product": product,
        "page_title": product.name,
        "nav_section": "products",
        "is_create": False,
    }
    return render(request, "dashboard/product_form.html", context)


@require_http_methods(["POST"])
@require_permission("catalog.change_product")
def product_archive(request, pk):
    """Activate/deactivate (archive) a product. POST-only, CSRF protected."""
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active", "updated_at"])
    action = "archived" if not product.is_active else "restored"
    log_admin_action(
        request.user, product, CHANGE, f"Product {product.sku} {action} via dashboard."
    )
    messages.success(request, f"“{product.name}” was {action}.")
    return redirect(safe_redirect_url(request.POST.get("next"), "dashboard:product_list"))


@require_GET
@staff_member_required
def inventory(request):
    section = request.GET.get("section", "all")
    queryset = (
        ProductVariant.objects.select_related("product", "size", "color").order_by(
            "product__name", "size__sort_order", "color__sort_order"
        )
    )
    if section == "low":
        queryset = queryset.filter(is_active=True, stock__gt=0, stock__lte=5)
    elif section == "out":
        queryset = queryset.filter(is_active=True, stock=0)
    elif section == "inactive":
        queryset = queryset.filter(is_active=False)

    query = request.GET.get("q", "").strip()
    if query:
        queryset = queryset.filter(
            Q(product__name__icontains=query)
            | Q(sku__icontains=query)
            | Q(color__name__icontains=query)
        )

    paginator = Paginator(queryset, 25)
    page = paginator.get_page(request.GET.get("page"))

    stats = {
        "low": low_stock_variants().count(),
        "out": out_of_stock_variants().count(),
        "total": ProductVariant.objects.filter(is_active=True).count(),
    }

    context = {
        "page": page,
        "section": section,
        "query": query,
        "stats": stats,
        "page_title": "Inventory",
        "nav_section": "inventory",
    }
    return render(request, "dashboard/inventory.html", context)


@require_http_methods(["POST"])
@require_permission("catalog.change_product")
def inventory_update(request, pk):
    """Update stock for a single variant (size + colour level)."""
    variant = get_object_or_404(
        ProductVariant.objects.select_related("product", "size", "color"), pk=pk
    )
    form = StockAdjustForm(request.POST, instance=variant)
    if form.is_valid():
        old_stock = variant.stock
        variant = form.save()
        log_admin_action(
            request.user,
            variant,
            CHANGE,
            f"Stock for {variant.product.sku} / {variant.size.name} / {variant.color.name}: "
            f"{old_stock} → {variant.stock}",
            model=ProductVariant,
        )
        messages.success(
            request,
            f"Stock updated: {variant.product.name} · {variant.size.name} · "
            f"{variant.color.name} → {variant.stock}.",
        )
    else:
        for error in form.non_field_errors() + form.errors.get("stock", []):
            messages.error(request, error)
    return redirect(safe_redirect_url(request.POST.get("next"), "dashboard:inventory"))
