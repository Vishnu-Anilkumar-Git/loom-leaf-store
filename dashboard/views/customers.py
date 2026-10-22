"""Customer management views for the staff dashboard.

Only non-staff accounts appear here. Edits are limited to contact details —
passwords, permissions and payment data are never exposed or editable here.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from accounts.models import Address, Profile

from ..access import CHANGE, log_admin_action, require_permission, staff_member_required
from ..forms import CustomerEditForm
from ..services import customer_stats

User = get_user_model()

# Revenue-defining statuses: cancelled/returned orders never count as spend.
EXCLUDED_STATUSES = ("cancelled", "returned")


@require_GET
@staff_member_required
def customer_list(request):
    qs = User.objects.filter(is_staff=False).annotate(
        order_count=Count(
            "orders", filter=~Q(orders__status__in=EXCLUDED_STATUSES), distinct=True
        ),
        lifetime_spend=Sum(
            "orders__total_amount", filter=~Q(orders__status__in=EXCLUDED_STATUSES)
        ),
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(username__icontains=query)
            | Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(profile__phone__icontains=query)
        )

    sort = request.GET.get("sort", "newest")
    order_map = {
        "newest": "-date_joined",
        "name": "first_name",
        "spend": "-lifetime_spend",
        "orders": "-order_count",
    }
    qs = qs.order_by(order_map.get(sort, "-date_joined"), "-id")

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page": page,
        "query": query,
        "sort": sort,
        "page_title": "Customers",
        "nav_section": "customers",
    }
    return render(request, "dashboard/customer_list.html", context)


@require_GET
@staff_member_required
def customer_detail(request, pk):
    user = get_object_or_404(User.objects.filter(is_staff=False), pk=pk)
    orders = user.orders.all()
    order_count, spend = customer_stats(user)
    profile = Profile.objects.filter(user=user).first()
    addresses = Address.objects.filter(user=user)
    context = {
        "customer": user,
        "profile": profile,
        "addresses": addresses,
        "orders": orders[:20],
        "orders_total": order_count,
        "lifetime_spend": spend,
        "edit_form": CustomerEditForm(instance=user),
        "page_title": user.get_full_name() or user.get_username(),
        "nav_section": "customers",
    }
    return render(request, "dashboard/customer_detail.html", context)


@require_http_methods(["POST"])
@require_permission("auth.change_user")
def customer_edit(request, pk):
    user = get_object_or_404(User.objects.filter(is_staff=False), pk=pk)
    form = CustomerEditForm(request.POST, instance=user)
    if form.is_valid():
        updated = form.save()
        log_admin_action(
            request.user,
            updated,
            CHANGE,
            f"Updated customer details for {updated.get_username()} via dashboard.",
            model=User,
        )
        messages.success(request, "Customer details updated.")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}" if field != "__all__" else error)
    return redirect("dashboard:customer_detail", user.pk)
