"""Customer order emails and scheduled abandoned-cart reminders."""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone


def send_order_email(order, event):
    """Send a lifecycle message; console backend is used in local development."""
    subjects = {
        "placed": f"We received your order {order.order_number}",
        "delivered": f"Your order {order.order_number} has been delivered",
    }
    if event not in subjects or not order.email:
        return 0
    context = {"order": order, "site_name": settings.SITE_NAME, "site_url": settings.SITE_URL.rstrip("/")}
    body = render_to_string(f"orders/emails/{event}.txt", context)
    return send_mail(subjects[event], body, settings.DEFAULT_FROM_EMAIL, [order.email], fail_silently=True)


def send_abandoned_cart_reminders(now=None, age=timedelta(hours=24)):
    """Send at most one reminder per eligible signed-in customer's cart.

    Run periodically with `manage.py send_cart_reminders`. A non-empty cart is
    eligible only when its last update is at least `age` old and newer than the
    most recent order, avoiding reminders for carts already purchased.
    """
    from cart.models import Cart

    now = now or timezone.now()
    cutoff = now - age
    sent = 0
    carts = (
        Cart.objects.filter(user__isnull=False, updated_at__lte=cutoff)
        .exclude(user__email="")
        .filter(
            items__isnull=False,
            items__product__is_active=True,
            items__variant__is_active=True,
            items__variant__stock__gt=0,
        )
        .select_related("user")
        .distinct()
        .prefetch_related("items__product", "items__variant__size", "items__variant__color")
    )
    for cart in carts.iterator(chunk_size=100):
        latest_order = cart.user.orders.order_by("-created_at").values_list("created_at", flat=True).first()
        if latest_order and latest_order >= cart.created_at:
            continue
        already_sent = cart.abandoned_reminder_sent_at is not None
        if already_sent:
            continue
        if not cart.items.filter(product__is_active=True, variant__is_active=True, variant__stock__gt=0).exists():
            continue
        context = {
            "user": cart.user,
            "cart": cart,
            "site_name": settings.SITE_NAME,
            "checkout_url": f"{settings.SITE_URL.rstrip('/')}/cart/",
        }
        body = render_to_string("cart/emails/abandoned.txt", context)
        result = send_mail(
            f"Your bag is waiting at {settings.SITE_NAME}",
            body,
            settings.DEFAULT_FROM_EMAIL,
            [cart.user.email],
            fail_silently=True,
        )
        # Mark only on successful delivery; failures can be retried next run.
        if result:
            Cart.objects.filter(pk=cart.pk, abandoned_reminder_sent_at__isnull=True).update(
                abandoned_reminder_sent_at=now
            )
            sent += 1
    return sent
