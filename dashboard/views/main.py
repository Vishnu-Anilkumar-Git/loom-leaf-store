from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.shortcuts import render
from django.views.decorators.http import require_GET

from catalog.models import Product
from orders.models import Order
from reviews.models import Review

from ..access import staff_member_required
from ..services import (
    RANGE_CHOICES,
    inventory_stats,
    resolve_date_range,
    sales_metrics,
    sales_trend,
)

User = get_user_model()


@require_GET
@staff_member_required
def dashboard_home(request):
    start, end, label, range_key = resolve_date_range(request)
    metrics = sales_metrics(start, end)

    customers_total = User.objects.filter(is_staff=False, is_active=True).count()
    new_customers = User.objects.filter(is_staff=False, is_active=True)
    if start:
        new_customers = new_customers.filter(date_joined__gte=start)
    if end:
        new_customers = new_customers.filter(date_joined__lte=end)

    products_total = Product.objects.count()
    products_active = Product.objects.filter(is_active=True).count()
    stock = inventory_stats()
    low_variants = list(stock["low"][:6])
    out_count = stock["out"].count()

    trend = sales_trend(start, end)
    peak = max((value for _, value in trend), default=0)
    chart = []
    for day, value in trend:
        height = float(value) / float(peak) * 100 if peak else 0
        chart.append({"date": day, "value": value, "height": round(height, 1)})

    recent_orders = (
        Order.objects.select_related("user")
        .prefetch_related("items")
        .order_by("-created_at")[:8]
    )


    top = _top_sellers(start, end)

    context = {
        "range_key": range_key,
        "range_label": label,
        "range_choices": RANGE_CHOICES,
        "metrics": metrics,
        "customers_total": customers_total,
        "customers_new": new_customers.count(),
        "products_total": products_total,
        "products_active": products_active,
        "low_stock": low_variants,
        "low_stock_count": stock["low"].count(),
        "out_of_stock_count": out_count,
        "low_threshold": stock["low_threshold"],
        "chart": chart,
        "chart_peak": peak,
        "chart_first_date": trend[0][0] if trend else None,
        "chart_last_date": trend[-1][0] if trend else None,
        "recent_orders": recent_orders,
        "top_products": top,
        "pending_orders": Order.objects.filter(
            status__in=["pending", "confirmed", "processing", "packed"]
        ).count(),
        "unapproved_reviews": Review.objects.filter(is_approved=False).count(),
        "page_title": "Dashboard",
    }
    return render(request, "dashboard/dashboard.html", context)


def _top_sellers(start, end, limit=5):
    from orders.models import OrderItem

    qs = OrderItem.objects.all()
    if start:
        qs = qs.filter(order__created_at__gte=start)
    if end:
        qs = qs.filter(order__created_at__lte=end)
    return (
        qs.exclude(order__status__in=("cancelled", "returned"))
        .values("product_name")
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-units")[:limit]
    )
