"""Query helpers for dashboard metrics, date filtering and CSV export.

All money is Decimal; nothing here converts to float. Date ranges are resolved
from GET parameters once and reused by the dashboard, reports and exports so
every page agrees on what "this month" means.
"""
import csv
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone

from coupons.models import CouponRedemption
from orders.models import Order, OrderItem
from reviews.models import Review

# Orders that represent revenue: cancelled/returned never count.
REVENUE_EXCLUDE = ("cancelled", "returned")

RANGE_CHOICES = {
    "today": "Today",
    "week": "This week",
    "month": "This month",
    "custom": "Custom range",
    "all": "All time",
}


def _local_dt(day, end_of_day=False):
    value = time.max if end_of_day else time.min
    return timezone.make_aware(datetime.combine(day, value))


def resolve_date_range(request):
    """Return (start, end, label, range_key) from ?range=&from=&to=.

    ``start``/``end`` are aware datetimes (inclusive) or None for all time.
    """
    key = request.GET.get("range", "month")
    if key not in RANGE_CHOICES:
        key = "month"
    now = timezone.localtime()
    today = now.date()

    if key == "today":
        return _local_dt(today), _local_dt(today, True), RANGE_CHOICES["today"], key
    if key == "week":
        start = today - timedelta(days=today.weekday())  # Monday
        return _local_dt(start), _local_dt(today, True), RANGE_CHOICES["week"], key
    if key == "month":
        start = today.replace(day=1)
        return _local_dt(start), _local_dt(today, True), RANGE_CHOICES["month"], key
    if key == "custom":
        start = _parse_date(request.GET.get("from")) or today.replace(day=1)
        end = _parse_date(request.GET.get("to")) or today
        if start > end:
            start, end = end, start
        label = f"{start:%d %b %Y} → {end:%d %b %Y}"
        return _local_dt(start), _local_dt(end, True), label, key
    return None, None, RANGE_CHOICES["all"], "all"


def _parse_date(raw):
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def orders_in_range(start, end, queryset=None):
    qs = queryset if queryset is not None else Order.objects.all()
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    return qs


def sales_metrics(start, end):
    """Revenue, order count, average order value and discounts for the range."""
    orders = orders_in_range(start, end).exclude(status__in=REVENUE_EXCLUDE)
    totals = orders.aggregate(
        revenue=Sum("total_amount"),
        discount=Sum("discount_amount"),
        count=Count("id"),
    )
    revenue = totals["revenue"] or Decimal("0.00")
    count = totals["count"] or 0
    average = (revenue / count).quantize(Decimal("0.01")) if count else Decimal("0.00")
    return {
        "revenue": revenue,
        "discount": totals["discount"] or Decimal("0.00"),
        "order_count": count,
        "average_order": average,
    }


def sales_trend(start, end, max_days=31):
    """Daily revenue list [(date, Decimal), …] for the bar chart."""
    if start is None:
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=13)
        start, end = _local_dt(start_date), _local_dt(end_date, True)
    else:
        start_date = start.date()
        end_date = end.date()
        if (end_date - start_date).days >= max_days:
            start_date = end_date - timedelta(days=max_days - 1)
            start = _local_dt(start_date)

    rows = (
        orders_in_range(start, end)
        .exclude(status__in=REVENUE_EXCLUDE)
        .values_list("created_at__date")
        .annotate(day_revenue=Sum("total_amount"))
        .order_by("created_at__date")
    )
    lookup = {row[0]: row[1] for row in rows}

    days = []
    cursor = start_date
    while cursor <= end_date:
        days.append((cursor, lookup.get(cursor) or Decimal("0.00")))
        cursor += timedelta(days=1)
    return days


def inventory_stats(low_threshold=5):
    """Variant-level stock statistics used by the dashboard and reports."""
    return {
        "low_threshold": low_threshold,
        "low": low_stock_variants(low_threshold),
        "out": out_of_stock_variants(),
    }


def low_stock_variants(threshold=5):
    from catalog.models import ProductVariant

    return (
        ProductVariant.objects.filter(is_active=True, stock__gt=0, stock__lte=threshold)
        .select_related("product", "size", "color")
        .order_by("stock", "product__name")
    )


def out_of_stock_variants():
    from catalog.models import ProductVariant

    return (
        ProductVariant.objects.filter(is_active=True, stock=0)
        .select_related("product", "size", "color")
        .order_by("product__name")
    )


def customer_stats(user):
    """Order count and lifetime spend for one customer (excl. cancelled)."""
    orders = user.orders.exclude(status__in=REVENUE_EXCLUDE)
    agg = orders.aggregate(spent=Sum("total_amount"), count=Count("id"))
    return agg["count"] or 0, agg["spent"] or Decimal("0.00")


def top_products(start, end, limit=10):
    return (
        OrderItem.objects.filter(order__created_at__gte=start, order__created_at__lte=end)
        .exclude(order__status__in=REVENUE_EXCLUDE)
        .values("product_name")
        .annotate(
            units=Sum("quantity"),
            revenue=Sum("line_total"),
            orders=Count("order", distinct=True),
        )
        .order_by("-units")[:limit]
    )


def coupon_usage(start, end):
    rows = (
        CouponRedemption.objects.filter(created_at__gte=start, created_at__lte=end)
        .select_related("coupon")
        .values("coupon__code")
        .annotate(
            used=Count("id"),
            discount=Sum("order__discount_amount"),
        )
        .order_by("-used")
    )
    return rows


def build_csv(filename, headers, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response
