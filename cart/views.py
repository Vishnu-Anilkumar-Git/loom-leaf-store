from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Product
from coupons.models import Coupon

from .models import Cart
from .services import (
    add_item,
    cart_issue,
    cart_totals,
    get_cart,
    remove_item,
    resolve_variant,
    update_item,
)


def _safe_next(request, fallback):
    target = request.POST.get("next") or request.GET.get("next")
    if not target or not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


def cart_detail(request):
    cart = get_cart(request, create=False)
    context = {"cart": cart, "title": "Your Bag"}
    if cart:
        issue = cart_issue(cart)
        coupon_error = None
        if cart.coupon_id:
            coupon_error = cart.coupon.validate_for(cart.subtotal, request.user)
            if coupon_error:
                cart.coupon = None
                cart.save(update_fields=["coupon", "updated_at"])
        context.update(cart_totals(cart))
        context["cart_issue"] = issue
        context["coupon_error"] = coupon_error
        from core.models import SiteSettings

        site = SiteSettings.load()
        context["free_shipping_remaining"] = site.free_shipping_remaining(cart.subtotal)
    else:
        context.update(
            {"subtotal": 0, "discount": 0, "shipping": 0, "total": 0, "savings": 0}
        )
    return render(request, "cart/cart_detail.html", context)


@require_POST
def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    cart = get_cart(request)
    size_code = request.POST.get("size")
    color_slug = request.POST.get("color")
    if product.variants.filter(is_active=True, stock__gt=0).exists():
        if not size_code:
            messages.error(request, "Please choose a size before adding this piece.")
            return redirect(_safe_next(request, product.get_absolute_url()))
        if product.color_list and not color_slug:
            messages.error(request, "Please choose a colour before adding this piece.")
            return redirect(_safe_next(request, product.get_absolute_url()))
    variant = resolve_variant(product, size_code, color_slug)
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    try:
        add_item(cart, product, variant, quantity)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(_safe_next(request, product.get_absolute_url()))
    messages.success(request, f"{product.name} added to your bag.")
    return redirect(_safe_next(request, "cart:detail"))


@require_POST
def update_cart_item(request, item_id):
    cart = get_cart(request, create=False)
    if cart is None:
        messages.error(request, "Your bag is empty.")
        return redirect("cart:detail")
    try:
        update_item(cart, item_id, request.POST.get("quantity"))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("cart:detail")
    messages.success(request, "Your bag has been updated.")
    return redirect(_safe_next(request, "cart:detail"))


@require_POST
def remove_cart_item(request, item_id):
    cart = get_cart(request, create=False)
    if cart is None:
        messages.error(request, "Your bag is empty.")
        return redirect("cart:detail")
    if remove_item(cart, item_id):
        messages.success(request, "Item removed from your bag.")
    return redirect("cart:detail")


@require_POST
def apply_coupon(request):
    cart = get_cart(request, create=False)
    if cart is None or not cart.items.exists():
        messages.error(request, "Add something to your bag before applying a coupon.")
        return redirect("cart:detail")
    code = (request.POST.get("code") or "").strip().upper()
    coupon = Coupon.objects.filter(code=code).first()
    if coupon is None:
        messages.error(request, "That coupon code is not valid.")
        return redirect("cart:detail")
    error = coupon.validate_for(cart.subtotal, request.user)
    if error:
        messages.error(request, error)
        return redirect("cart:detail")
    cart.coupon = coupon
    cart.save(update_fields=["coupon", "updated_at"])
    messages.success(request, f"Coupon {coupon.code} applied.")
    return redirect("cart:detail")


@require_POST
def remove_coupon(request):
    cart = get_cart(request, create=False)
    if cart:
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])
        messages.success(request, "Coupon removed.")
    return redirect("cart:detail")
