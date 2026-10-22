import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Address, Profile
from cart.services import cart_issue, cart_totals, get_cart
from core.models import SiteSettings

from .forms import CheckoutForm
from .models import Order, Payment
from .services import (
    PaymentError,
    confirm_razorpay_payment,
    create_razorpay_order,
    payment_page_context,
    place_order,
    razorpay_configured,
)

PROGRESS_STEPS = [
    (Order.Status.CONFIRMED, "Confirmed"),
    (Order.Status.PROCESSING, "Processing"),
    (Order.Status.PACKED, "Packed"),
    (Order.Status.SHIPPED, "Shipped"),
    (Order.Status.DELIVERED, "Delivered"),
]


def _new_checkout_token(request):
    token = uuid.uuid4().hex
    request.session["checkout_token"] = token
    return token


def _existing_order(request, token):
    if not token:
        return None
    return Order.objects.filter(user=request.user, checkout_token=token).first()


@login_required
def checkout(request):
    # Idempotency is checked before anything else so a refreshed POST redirects
    # to the order that was already created instead of showing an empty bag.
    if request.method == "POST":
        existing_order = _existing_order(
            request, request.POST.get("checkout_token", "")
        )
        if existing_order:
            messages.info(request, "This order has already been placed.")
            return redirect(existing_order.get_absolute_url())

    cart = get_cart(request, create=False)
    if cart is None or not cart.items.exists():
        messages.info(request, "Your bag is empty — add a piece before checking out.")
        return redirect("cart:detail")
    issue = cart_issue(cart)
    if issue:
        messages.error(request, issue)
        return redirect("cart:detail")

    token = request.session.get("checkout_token") or _new_checkout_token(request)
    initial = {"checkout_token": token, "payment_method": Order.PaymentMethod.COD}
    default_address = request.user.addresses.filter(is_default=True).first()
    profile, _ = Profile.objects.get_or_create(user=request.user)
    initial.update(
        {
            "full_name": request.user.get_full_name() or request.user.get_username(),
            "email": request.user.email,
            "phone": profile.phone,
        }
    )
    if default_address:
        initial.update(
            {
                "full_name": default_address.full_name,
                "phone": default_address.phone,
                "address_line1": default_address.line1,
                "address_line2": default_address.line2,
                "city": default_address.city,
                "state": default_address.state,
                "postal_code": default_address.postal_code,
            }
        )

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        posted_token = request.POST.get("checkout_token", "")
        if form.is_valid():
            if (
                form.cleaned_data["payment_method"] == Order.PaymentMethod.RAZORPAY
                and not razorpay_configured()
            ):
                form.add_error(
                    "payment_method",
                    "Razorpay test mode is not configured on this installation. "
                    "Choose Cash on Delivery or add test API keys to .env.",
                )
            else:
                try:
                    order = place_order(
                        user=request.user,
                        cart=cart,
                        cleaned_data=form.cleaned_data,
                        payment_method=form.cleaned_data["payment_method"],
                    )
                except ValidationError as exc:
                    form.add_error(None, exc.messages[0] if exc.messages else "Checkout failed.")
                except IntegrityError:
                    existing = Order.objects.filter(
                        user=request.user, checkout_token=posted_token
                    ).first()
                    if existing:
                        messages.info(request, "This order has already been placed.")
                        return redirect(existing.get_absolute_url())
                    form.add_error(
                        None, "We could not place your order. Please try again."
                    )
                except Exception:
                    form.add_error(
                        None,
                        "We could not place your order. No payment has been taken. "
                        "Please try again.",
                    )
                else:
                    request.session.pop("checkout_token", None)
                    if form.cleaned_data.get("save_address"):
                        Address.objects.create(
                            user=request.user,
                            label="Checkout",
                            full_name=order.full_name,
                            phone=order.phone,
                            line1=order.address_line1,
                            line2=order.address_line2,
                            city=order.city,
                            state=order.state,
                            postal_code=order.postal_code,
                            is_default=not request.user.addresses.exists(),
                        )
                    if order.payment_method == Order.PaymentMethod.RAZORPAY:
                        try:
                            create_razorpay_order(order)
                        except PaymentError as exc:
                            order.payment_status = Order.PaymentStatus.FAILED
                            order.save(update_fields=["payment_status", "updated_at"])
                            order.set_status(
                                Order.Status.CANCELLED,
                                changed_by=request.user,
                                note="Payment could not be started; inventory released.",
                            )
                            messages.error(
                                request,
                                f"{exc} The order was cancelled and stock released.",
                            )
                            return redirect(order.get_absolute_url())
                        return redirect("orders:payment", order_number=order.order_number)
                    messages.success(
                        request,
                        f"Order {order.order_number} confirmed. We will contact you for delivery.",
                    )
                    return redirect(order.get_absolute_url())
        else:
            messages.error(request, "Please review the highlighted delivery details.")
    else:
        form = CheckoutForm(initial=initial)

    totals = cart_totals(cart)
    return render(
        request,
        "orders/checkout.html",
        {
            "form": form,
            "cart": cart,
            "totals": totals,
            "site_settings": SiteSettings.load(),
            "razorpay_available": razorpay_configured(),
            "title": "Checkout",
        },
    )


@login_required
def order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "status_history", "payments"),
        order_number=order_number,
        user=request.user,
    )
    status_order = [step for step, _ in PROGRESS_STEPS]
    current_index = status_order.index(order.status) if order.status in status_order else -1
    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "progress_steps": [
                {
                    "status": step,
                    "label": label,
                    "done": current_index >= index,
                    "current": order.status == step,
                }
                for index, (step, label) in enumerate(PROGRESS_STEPS)
            ],
            "is_cancelled": order.status in {Order.Status.CANCELLED, Order.Status.RETURNED},
            "can_cancel": order.can_cancel and order.payment_status != Order.PaymentStatus.PAID,
            "latest_payment": order.payments.order_by("-id").first(),
            "title": f"Order {order.order_number}",
        },
    )


@login_required
@require_POST
def cancel_order(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    if order.payment_status == Order.PaymentStatus.PAID:
        messages.error(
            request,
            "This order is already paid. Please contact support to arrange a cancellation or return.",
        )
        return redirect(order.get_absolute_url())
    try:
        order.set_status(
            Order.Status.CANCELLED, changed_by=request.user, note="Cancelled by customer."
        )
        messages.success(request, "Your order has been cancelled and stock released.")
    except ValidationError:
        messages.error(request, "This order can no longer be cancelled online.")
    return redirect(order.get_absolute_url())


@login_required
def payment(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    if order.payment_method != Order.PaymentMethod.RAZORPAY:
        return redirect(order.get_absolute_url())
    if order.payment_status == Order.PaymentStatus.PAID:
        messages.info(request, "This order is already paid.")
        return redirect(order.get_absolute_url())
    if order.status in {Order.Status.CANCELLED, Order.Status.RETURNED}:
        messages.error(request, "This order was cancelled, so payment is not possible.")
        return redirect(order.get_absolute_url())
    if not razorpay_configured():
        messages.error(
            request,
            "Razorpay test credentials are not configured. The order remains unpaid.",
        )
        return redirect(order.get_absolute_url())

    if not order.payments.filter(status=Payment.Status.CREATED).exists():
        try:
            create_razorpay_order(order)
        except PaymentError as exc:
            messages.error(request, str(exc))
            return redirect(order.get_absolute_url())

    context = payment_page_context(order)
    context["title"] = f"Pay for {order.order_number}"
    cancellation_url = reverse(
        "orders:payment_cancelled", kwargs={"order_number": order.order_number}
    )
    context["payment_data"] = {
        "key": settings.RAZORPAY_KEY_ID,
        "order_id": context["payment"].provider_order_id,
        "amount": context["amount_paise"],
        "currency": "INR",
        "description": f"LOOM&LEAF order {order.order_number}",
        "prefill": {
            "name": order.full_name,
            "email": order.email,
            "contact": order.phone,
        },
        "verify_url": reverse(
            "orders:payment_verify", kwargs={"order_number": order.order_number}
        ),
        "cancelled_url": cancellation_url,
        "return_url": order.get_absolute_url(),
    }
    return render(request, "orders/payment.html", context)


@login_required
@require_POST
def payment_verify(request, order_number):
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    if order.payment_method != Order.PaymentMethod.RAZORPAY:
        return JsonResponse({"ok": False, "error": "This order is not a Razorpay order."}, status=400)
    order_id = (request.POST.get("razorpay_order_id") or "").strip()
    payment_id = (request.POST.get("razorpay_payment_id") or "").strip()
    signature = (request.POST.get("razorpay_signature") or "").strip()
    try:
        confirm_razorpay_payment(
            order=order,
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            signature=signature,
        )
    except PaymentError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        return JsonResponse(
            {"ok": False, "error": "Payment verification failed. No order status was changed."},
            status=400,
        )
    return JsonResponse({"ok": True, "redirect": order.get_absolute_url()})


@login_required
@require_POST
def payment_cancelled(request, order_number):
    """Record an abandoned checkout attempt without ever marking it paid."""
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    if order.payment_status == Order.PaymentStatus.PAID:
        return JsonResponse({"ok": True})
    payment = order.payments.filter(status=Payment.Status.CREATED).order_by("-id").first()
    if payment:
        payment.status = Payment.Status.FAILED
        payment.error_message = "Checkout was closed before payment completed."
        payment.save(update_fields=["status", "error_message", "updated_at"])
    order.payment_status = Order.PaymentStatus.FAILED
    order.save(update_fields=["payment_status", "updated_at"])
    return JsonResponse({"ok": True})
