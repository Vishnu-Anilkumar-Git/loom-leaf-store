"""Sales and inventory reports with date filtering and exports."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils import timezone
from django.utils import timezone
from django.views.decorators.http import require_GET

from catalog.models import Product, ProductVariant
from coupons.models import Coupon, CouponRedemption
from orders.models import Order, OrderItem
from reviews.models import Review

from ..access import staff_member_required
from ..exports import export_daily_pdf, export_daily_xlsx
from ..services import (
    RANGE_CHOICES,
    build_csv,
    coupon_usage,
    resolve_date_range,
    sales_metrics,
)

User = get_user_model()
EXCLUDED_STATUSES = ("cancelled", "returned")


@require_GET
@staff_member_required
def report_index(request):
    start, end, label, range_key = resolve_date_range(request)
    metrics = sales_metrics(start, end)

    all_orders = Order.objects.all()
    if start:
        all_orders = all_orders.filter(created_at__gte=start)
    if end:
        all_orders = all_orders.filter(created_at__lte=end)

    status_breakdown = all_orders.values("status").annotate(count=Count("id"))
    raw_counts = {row["status"]: row["count"] for row in status_breakdown}
    status_rows = [
        {"value": value, "label": display, "count": raw_counts.get(value, 0)}
        for value, display in Order.Status.choices
    ]

    items = OrderItem.objects.all()
    if start:
        items = items.filter(order__created_at__gte=start)
    if end:
        items = items.filter(order__created_at__lte=end)
    top_products = list(
        items.exclude(order__status__in=EXCLUDED_STATUSES)
        .values("product_name")
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-revenue")[:10]
    )

    if start:
        discounts = list(coupon_usage(start, end))
    else:
        discounts = list(
            CouponRedemption.objects.values("coupon__code")
            .annotate(used=Count("id"), discount=Sum("order__discount_amount"))
            .order_by("-used")
        )

    active_variants = ProductVariant.objects.filter(is_active=True)
    stock_by_product = {
        row["product_id"]: row["total"]
        for row in active_variants.values("product_id").annotate(total=Sum("stock"))
    }
    inventory_value = Decimal("0.00")
    for product in Product.objects.all():
        inventory_value += stock_by_product.get(product.pk, 0) * product.price

    context = {
        "range_key": range_key,
        "range_label": label,
        "today": timezone.localdate(),
        "range_choices": RANGE_CHOICES,
        "metrics": metrics,
        "status_rows": status_rows,
        "top_products": top_products,
        "discount_rows": discounts,
        "inventory_value": inventory_value,
        "inventory_total": active_variants.count(),
        "out_of_stock": active_variants.filter(stock=0).count(),
        "low_stock": active_variants.filter(stock__gt=0, stock__lte=5).count(),
        "totals": {
            "products": Product.objects.count(),
            "variants": ProductVariant.objects.count(),
            "customers": User.objects.filter(is_staff=False).count(),
            "reviews": Review.objects.count(),
            "reviews_pending": Review.objects.filter(is_approved=False).count(),
        },
        "page_title": "Reports",
        "nav_section": "reports",
    }
    return render(request, "dashboard/report.html", context)


@require_GET
@staff_member_required
def export_csv(request):
    """Download orders, products, or coupons as CSV."""
    start, end, label, _ = resolve_date_range(request)
    kind = request.GET.get("kind", "orders")

    if kind == "products":
        stock_by_product = {
            row["product_id"]: row["total"]
            for row in ProductVariant.objects.filter(is_active=True)
            .values("product_id")
            .annotate(total=Sum("stock"))
        }
        data_rows = [
            [product.sku, product.name, product.category.name, product.base_price,
             product.sale_price or "", "active" if product.is_active else "archived",
             "yes" if product.is_featured else "no", "yes" if product.is_new_arrival else "no",
             stock_by_product.get(product.pk, 0)]
            for product in Product.objects.select_related("category").order_by("name")
        ]
        return build_csv("loomandleaf-products.csv", ["SKU", "Name", "Category", "Base price", "Sale price", "Status", "Featured", "New arrival", "Units in stock"], data_rows)

    if kind == "coupons":
        data_rows = [
            [coupon.code, coupon.get_discount_type_display(), coupon.value, coupon.min_order_amount,
             coupon.max_discount or "", coupon.valid_from.strftime("%Y-%m-%d"),
             coupon.valid_until.strftime("%Y-%m-%d"), "active" if coupon.is_active else "inactive",
             coupon.usage_limit or "unlimited", coupon.redemptions.count(), coupon.times_used]
            for coupon in Coupon.objects.all()
        ]
        return build_csv("loomandleaf-coupons.csv", ["Code", "Type", "Value", "Min order", "Max discount", "Valid from", "Valid until", "Status", "Usage limit", "Redemptions", "Times used"], data_rows)

    if kind not in {"orders", "pdf", "xlsx"}:
        return HttpResponseBadRequest("Unknown export kind.")
    if kind in {"pdf", "xlsx"}:
        raw_day = request.GET.get("day", "")
        try:
            day = date.fromisoformat(raw_day) if raw_day else timezone.localdate()
        except ValueError:
            return HttpResponseBadRequest("day must use YYYY-MM-DD format.")
        return export_daily_pdf(day) if kind == "pdf" else export_daily_xlsx(day)

    qs = Order.objects.select_related("user").prefetch_related("items").order_by("-created_at")
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    data_rows = [
        [order.order_number, order.created_at.strftime("%Y-%m-%d %H:%M"), order.full_name,
         order.email, order.get_payment_method_display(), order.get_payment_status_display(),
         order.get_status_display(), order.subtotal, order.discount_amount, order.shipping_amount,
         order.total_amount, order.coupon_code or "", order.item_count]
        for order in qs
    ]
    slug = label.lower().replace(" ", "-").replace("→", "to")
    return build_csv(f"loomandleaf-orders-{slug}.csv", ["Order number", "Date", "Customer", "Email", "Payment method", "Payment status", "Order status", "Subtotal", "Discount", "Shipping", "Total", "Coupon", "Items"], data_rows)
