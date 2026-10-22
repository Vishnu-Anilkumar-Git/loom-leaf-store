"""Order management views for the staff dashboard."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from orders.models import Order

from ..access import CHANGE, log_admin_action, require_permission, staff_member_required
from ..forms import InternalNoteForm, TrackingForm
from ..services import RANGE_CHOICES, resolve_date_range

STATUS_CHOICES = Order.Status


@require_GET
@staff_member_required
def order_list(request):
    qs = Order.objects.select_related("user").prefetch_related("items")

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(order_number__icontains=query)
            | Q(full_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(user__username__icontains=query)
        )

    status = request.GET.get("status", "")
    if status in STATUS_CHOICES.values:
        qs = qs.filter(status=status)

    payment = request.GET.get("payment", "")
    if payment in Order.PaymentStatus.values:
        qs = qs.filter(payment_status=payment)

    method = request.GET.get("method", "")
    if method in Order.PaymentMethod.values:
        qs = qs.filter(payment_method=method)

    start, end, label, range_key = resolve_date_range(request)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page": page,
        "query": query,
        "status": status,
        "payment": payment,
        "method": method,
        "range_key": range_key,
        "range_label": label,
        "range_choices": RANGE_CHOICES,
        "status_choices": STATUS_CHOICES.choices,
        "payment_choices": Order.PaymentStatus.choices,
        "method_choices": Order.PaymentMethod.choices,
        "page_title": "Orders",
        "nav_section": "orders",
    }
    return render(request, "dashboard/order_list.html", context)


@require_GET
@staff_member_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.select_related("user", "coupon").prefetch_related(
            "items", "status_history__changed_by", "payments"
        ),
        order_number=order_number,
    )
    context = {
        "order": order,
        "status_form_initial": {"target": order.status},
        "note_form": InternalNoteForm(),
        "tracking_form": TrackingForm(
            initial={
                "tracking_carrier": order.tracking_carrier,
                "tracking_number": order.tracking_number,
            }
        ),
        "allowed_next": [
            (value, label)
            for value, label in STATUS_CHOICES.choices
            if value in order.allowed_next_statuses()
        ],
        "page_title": order.order_number,
        "nav_section": "orders",
    }
    return render(request, "dashboard/order_detail.html", context)


@require_http_methods(["POST"])
@require_permission("orders.change_order")
def order_set_status(request, order_number):
    """Apply one validated status transition; invalid moves are rejected."""
    order = get_object_or_404(Order, order_number=order_number)
    target = request.POST.get("target", "")
    note = (request.POST.get("note") or "").strip()
    if target not in {value for value, _ in STATUS_CHOICES.choices}:
        messages.error(request, "Unknown order status.")
        return redirect("dashboard:order_detail", order.order_number)
    if target == order.status:
        messages.info(request, f"Order is already {order.get_status_display()}.")
        return redirect("dashboard:order_detail", order.order_number)
    try:
        order.set_status(target, changed_by=request.user, note=note)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("dashboard:order_detail", order.order_number)
    log_admin_action(
        request.user,
        order,
        CHANGE,
        f"Order {order.order_number} status changed to {target}. {note}".strip(),
        model=Order,
    )
    messages.success(request, f"Order {order.order_number} → {order.get_status_display()}.")
    return redirect("dashboard:order_detail", order.order_number)


@require_http_methods(["POST"])
@require_permission("orders.change_order")
def order_add_note(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    form = InternalNoteForm(request.POST)
    if form.is_valid():
        note = form.cleaned_data["note"].strip()
        existing = order.internal_note.strip()
        order.internal_note = f"{existing}\n\n[{request.user.username}] {note}".strip()
        order.save(update_fields=["internal_note", "updated_at"])
        log_admin_action(
            request.user, order, CHANGE, f"Internal note added to {order.order_number}.", model=Order
        )
        messages.success(request, "Internal note saved.")
    else:
        messages.error(request, "The note could not be empty.")
    return redirect("dashboard:order_detail", order.order_number)


@require_http_methods(["POST"])
@require_permission("orders.change_order")
def order_save_tracking(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    form = TrackingForm(request.POST)
    if form.is_valid():
        order.tracking_carrier = form.cleaned_data.get("tracking_carrier", "").strip()
        order.tracking_number = form.cleaned_data.get("tracking_number", "").strip()
        order.save(update_fields=["tracking_carrier", "tracking_number", "updated_at"])
        log_admin_action(
            request.user,
            order,
            CHANGE,
            f"Tracking saved for {order.order_number}: "
            f"{order.tracking_carrier} {order.tracking_number}".strip(),
            model=Order,
        )
        messages.success(request, "Tracking details saved.")
    else:
        for error in form.non_field_errors():
            messages.error(request, error)
    return redirect("dashboard:order_detail", order.order_number)


@require_http_methods(["POST"])
@require_permission("orders.change_order")
def order_mark_paid(request, order_number):
    """Record a manual (COD) payment as verified. No-op for already-paid orders."""
    order = get_object_or_404(Order, order_number=order_number)
    if order.payment_status == Order.PaymentStatus.PAID:
        messages.info(request, "This order is already marked paid.")
        return redirect("dashboard:order_detail", order.order_number)
    if order.payment_method != Order.PaymentMethod.COD:
        messages.error(
            request,
            "Only Cash on Delivery orders can be marked paid manually; "
            "online payments are confirmed by signature verification.",
        )
        return redirect("dashboard:order_detail", order.order_number)
    note = (request.POST.get("note") or "Payment collected manually.").strip()
    order.mark_paid(note=note)
    log_admin_action(
        request.user,
        order,
        CHANGE,
        f"Order {order.order_number} marked paid (COD). {note}".strip(),
        model=Order,
    )
    messages.success(request, f"Order {order.order_number} marked as paid.")
    return redirect("dashboard:order_detail", order.order_number)
