"""Coupon (promotion) management views for the staff dashboard."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from coupons.models import Coupon, CouponRedemption

from ..access import (
    ADDITION,
    CHANGE,
    log_admin_action,
    require_permission,
    safe_redirect_url,
    staff_member_required,
)
from ..forms import CouponForm


@require_GET
@staff_member_required
def coupon_list(request):
    qs = (
        Coupon.objects.annotate(
            redemption_count=Count("redemptions", distinct=True),
            order_count=Count("orders", distinct=True),
        )
        .order_by("-created_at")
    )
    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(Q(code__icontains=query) | Q(description__icontains=query))
    status = request.GET.get("status", "all")
    now = timezone.now()
    if status == "active":
        qs = qs.filter(is_active=True, valid_from__lte=now, valid_until__gte=now)
    elif status == "scheduled":
        qs = qs.filter(is_active=True, valid_from__gt=now)
    elif status == "expired":
        qs = qs.filter(valid_until__lt=now)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page": page,
        "query": query,
        "status": status,
        "now": now,
        "page_title": "Promotions",
        "nav_section": "promotions",
    }
    return render(request, "dashboard/coupon_list.html", context)


@require_http_methods(["GET", "POST"])
@require_permission("coupons.add_coupon")
def coupon_create(request):
    form = CouponForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        coupon = form.save()
        log_admin_action(
            request.user, coupon, ADDITION, f"Created coupon {coupon.code} via dashboard."
        )
        messages.success(request, f"Coupon {coupon.code} created.")
        return redirect("dashboard:coupon_list")
    context = {
        "form": form,
        "page_title": "Create coupon",
        "nav_section": "promotions",
        "is_create": True,
    }
    return render(request, "dashboard/coupon_form.html", context)


@require_http_methods(["GET", "POST"])
@require_permission("coupons.change_coupon")
def coupon_edit(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == "POST":
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            coupon = form.save()
            log_admin_action(
                request.user, coupon, CHANGE, f"Updated coupon {coupon.code} via dashboard."
            )
            messages.success(request, f"Coupon {coupon.code} updated.")
            return redirect("dashboard:coupon_list")
    else:
        form = CouponForm(instance=coupon)

    redemptions = (
        CouponRedemption.objects.filter(coupon=coupon).select_related("order", "user")[:20]
    )
    context = {
        "form": form,
        "coupon": coupon,
        "redemptions": redemptions,
        "now": timezone.now(),
        "page_title": f"Coupon {coupon.code}",
        "nav_section": "promotions",
        "is_create": False,
    }
    return render(request, "dashboard/coupon_form.html", context)


@require_http_methods(["POST"])
@require_permission("coupons.change_coupon")
def coupon_toggle(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.is_active = not coupon.is_active
    coupon.save(update_fields=["is_active"])
    state = "activated" if coupon.is_active else "deactivated"
    log_admin_action(
        request.user, coupon, CHANGE, f"Coupon {coupon.code} {state} via dashboard."
    )
    messages.success(request, f"Coupon {coupon.code} {state}.")
    return redirect(safe_redirect_url(request.POST.get("next"), "dashboard:coupon_list"))
