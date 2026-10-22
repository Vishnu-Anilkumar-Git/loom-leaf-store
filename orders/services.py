"""Order placement and Razorpay payment services.

Money is always recomputed from the database in this module. The client never
supplies prices, discounts, totals or payment status.
"""
from decimal import Decimal
import hashlib
import hmac
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.urls import reverse

from cart.services import cart_issue, clear_cart, get_cart
from catalog.models import ProductVariant
from coupons.models import Coupon, CouponRedemption
from core.models import SiteSettings

from .models import Order, OrderItem, OrderStatusHistory, Payment

try:  # Razorpay is optional for local COD development.
    import razorpay
except ImportError:  # pragma: no cover - only when dependency is missing
    razorpay = None


class PaymentError(Exception):
    """Raised when a payment cannot be safely started or confirmed."""


def money(value):
    return Decimal(value).quantize(Decimal("0.01"))


def razorpay_client():
    if not razorpay or not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        return None
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def razorpay_configured():
    return bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)


def create_razorpay_order(order):
    """Create the gateway order before the local order is committed."""
    client = razorpay_client()
    if client is None:
        raise PaymentError(
            "Razorpay test credentials are not configured. Choose Cash on Delivery "
            "or add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to .env."
        )
    amount_paise = int((money(order.total_amount) * 100).to_integral_value())
    try:
        gateway_order = client.order.create(
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": order.order_number,
                "payment_capture": 1,
                "notes": {"order_number": order.order_number},
            }
        )
    except Exception as exc:  # network / API errors should not leak details
        raise PaymentError("Razorpay could not create a payment order. Please try again.") from exc
    Payment.objects.create(
        order=order,
        provider="razorpay",
        provider_order_id=gateway_order["id"],
        amount=order.total_amount,
        currency="INR",
        status=Payment.Status.CREATED,
    )
    return gateway_order


@transaction.atomic
def place_order(*, user, cart, cleaned_data, payment_method):
    """Create an order, snapshot its lines, decrement stock and record coupon use."""
    if cart is None or not cart.items.exists():
        raise ValidationError("Your bag is empty.")

    issue = cart_issue(cart)
    if issue:
        raise ValidationError(issue)

    items = list(cart.items.select_related("product", "variant", "variant__size", "variant__color"))
    variant_ids = sorted({item.variant_id for item in items})
    # Lock rows for the duration of the transaction (effective on PostgreSQL/MySQL;
    # SQLite serialises writers, and conditional stock updates below close the gap).
    locked_variants = {
        variant.pk: variant
        for variant in ProductVariant.objects.select_for_update()
        .filter(pk__in=variant_ids)
        .select_related("product", "size", "color")
    }

    subtotal = Decimal("0.00")
    for item in items:
        variant = locked_variants.get(item.variant_id)
        if (
            variant is None
            or not variant.is_active
            or not variant.product.is_active
            or variant.product_id != item.product_id
        ):
            raise ValidationError(f"{item.product.name} is no longer available.")
        if item.quantity < 1:
            raise ValidationError("Invalid quantity in your bag.")
        subtotal += variant.product.price * item.quantity
    subtotal = money(subtotal)

    coupon = None
    discount = Decimal("0.00")
    if cart.coupon_id:
        coupon = Coupon.objects.select_for_update().filter(pk=cart.coupon_id).first()
        if coupon:
            error = coupon.validate_for(subtotal, user)
            if error:
                raise ValidationError(error)
            discount = coupon.calculate_discount(subtotal)
    discount = min(money(discount), subtotal)

    site = SiteSettings.load()
    shipping = site.shipping_for(subtotal)
    total = money(max(subtotal - discount + shipping, Decimal("0.00")))

    order = Order(
        user=user,
        checkout_token=cleaned_data.get("checkout_token") or None,
        full_name=cleaned_data["full_name"],
        email=cleaned_data["email"],
        phone=cleaned_data["phone"],
        address_line1=cleaned_data["address_line1"],
        address_line2=cleaned_data.get("address_line2", ""),
        city=cleaned_data["city"],
        state=cleaned_data["state"],
        postal_code=cleaned_data["postal_code"],
        delivery_instructions=cleaned_data.get("delivery_instructions", ""),
        subtotal=subtotal,
        discount_amount=discount,
        shipping_amount=shipping,
        total_amount=total,
        coupon=coupon,
        coupon_code=coupon.code if coupon else "",
        payment_method=payment_method,
        payment_status=Order.PaymentStatus.PENDING,
        status=Order.Status.PENDING,
    )
    order.save()

    for item in items:
        variant = locked_variants[item.variant_id]
        # Conditional update prevents overselling when two checkouts race.
        updated = ProductVariant.objects.filter(
            pk=variant.pk, is_active=True, stock__gte=item.quantity
        ).update(stock=F("stock") - item.quantity)
        if not updated:
            raise ValidationError(
                f"Only {variant.stock} of {variant.product.name} "
                f"({variant.size.name}) remain in stock."
            )
        unit_price = money(variant.product.price)
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            product_name=variant.product.name,
            sku=variant.sku,
            size=variant.size.name,
            color=variant.color.name,
            quantity=item.quantity,
            unit_price=unit_price,
            line_total=money(unit_price * item.quantity),
        )

    if coupon:
        # Recheck the global limit while the coupon row is locked, then count it once.
        if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
            raise ValidationError("This coupon has reached its usage limit.")
        coupon.times_used = F("times_used") + 1
        coupon.save(update_fields=["times_used"])
        CouponRedemption.objects.create(
            coupon=coupon, order=order, user=user, email=order.email
        )

    OrderStatusHistory.objects.create(
        order=order, status=Order.Status.PENDING, note="Order placed.", changed_by=user
    )
    if payment_method == Order.PaymentMethod.COD:
        order.status = Order.Status.CONFIRMED
        order.save(update_fields=["status", "updated_at"])
        OrderStatusHistory.objects.create(
            order=order,
            status=Order.Status.CONFIRMED,
            note="Cash on Delivery order confirmed.",
            changed_by=user,
        )
    clear_cart(cart)
    # Notify after the transaction commits so no email refers to a rolled-back order.
    from django.db import transaction
    from .notifications import send_order_email

    transaction.on_commit(lambda: send_order_email(order, "placed"))
    return order


def verify_signature(razorpay_order_id, razorpay_payment_id, signature):
    if not (razorpay_order_id and razorpay_payment_id and signature):
        return False
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_gateway_payment(payment_record, payment_id):
    """Ask Razorpay whether the payment is captured/authorized for this exact order.

    Any API failure is treated as unverified: the browser can never promote an
    order to paid on its own.
    """
    client = razorpay_client()
    if client is None:
        raise PaymentError("Payment verification is unavailable: gateway credentials missing.")
    try:
        payload = client.payment.fetch(payment_id)
    except Exception as exc:
        raise PaymentError("Could not verify this payment with Razorpay.") from exc
    expected_amount = int((money(payment_record.amount) * 100).to_integral_value())
    if (
        payload.get("order_id") != payment_record.provider_order_id
        or int(payload.get("amount", 0)) != expected_amount
        or payload.get("currency") != "INR"
        or payload.get("status") not in {"captured", "authorized"}
    ):
        raise PaymentError("The payment details did not match this order.")
    return True


def confirm_razorpay_payment(*, order, razorpay_order_id, razorpay_payment_id, signature):
    """Idempotently verify and apply a Razorpay callback to exactly one order."""
    payment = Payment.objects.filter(
        order=order, provider_order_id=razorpay_order_id
    ).first()
    if payment is None:
        raise PaymentError("No matching payment attempt exists for this order.")

    if payment.status == Payment.Status.PAID or order.payment_status == Order.PaymentStatus.PAID:
        return order  # duplicate callback — already applied

    if not verify_signature(razorpay_order_id, razorpay_payment_id, signature):
        payment.status = Payment.Status.FAILED
        payment.error_message = "Signature verification failed."
        payment.save(update_fields=["status", "error_message", "updated_at"])
        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status", "updated_at"])
        raise PaymentError("Payment signature verification failed.")

    if int((money(payment.amount) * 100).to_integral_value()) != int(
        (money(order.total_amount) * 100).to_integral_value()
    ):
        raise PaymentError("Payment amount does not match the order total.")

    # Network verification happens outside the database transaction.
    verify_gateway_payment(payment, razorpay_payment_id)

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked_payment.status == Payment.Status.PAID:
            return locked_order
        locked_payment.status = Payment.Status.PAID
        locked_payment.provider_payment_id = razorpay_payment_id
        locked_payment.signature_verified = True
        locked_payment.error_message = ""
        locked_payment.save(
            update_fields=[
                "status", "provider_payment_id", "signature_verified",
                "error_message", "updated_at",
            ]
        )
        locked_order.mark_paid(
            provider_payment_id=razorpay_payment_id, note="Razorpay payment verified."
        )
        return locked_order


def payment_page_context(order):
    payment = order.payments.filter(status=Payment.Status.CREATED).order_by("-id").first()
    callback_url = urljoin(
        settings.SITE_URL.rstrip("/") + "/",
        reverse("orders:payment_verify", kwargs={"order_number": order.order_number}).lstrip("/"),
    )
    return {
        "order": order,
        "payment": payment,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "callback_url": callback_url,
        "amount_paise": int((money(order.total_amount) * 100).to_integral_value()),
    }
