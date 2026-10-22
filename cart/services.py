"""Cart domain services.

All price and inventory checks happen here or in the checkout service — never in
templates or the browser.
"""
from decimal import Decimal

from django.db import transaction

from catalog.models import Product, ProductVariant

from .models import Cart, CartItem

MAX_QUANTITY_PER_LINE = 10


def get_cart(request, create=True):
    """Return the active cart for the request, creating one only when needed."""
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart is None and create:
            cart = Cart.objects.create(user=request.user)
        return cart

    # Prefer the cart id saved in the session: Django rotates the session key
    # during login, so the original key alone would orphan an anonymous bag.
    cart_id = request.session.get("cart_id")
    cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first() if cart_id else None
    if cart is not None:
        return cart

    session_key = request.session.session_key
    if not session_key:
        if not create:
            return None
        request.session.create()
        session_key = request.session.session_key
    cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
    if cart is None and create:
        cart = Cart.objects.create(session_key=session_key)
    if cart is not None:
        request.session["cart_id"] = cart.pk
    return cart


def merge_session_cart(request, user):
    """Merge an anonymous session cart into the authenticated user's cart."""
    cart_id = request.session.get("cart_id")
    session_key = request.session.session_key
    session_cart = None
    if cart_id:
        session_cart = Cart.objects.filter(pk=cart_id, user__isnull=True).first()
    if session_cart is None and session_key:
        session_cart = Cart.objects.filter(
            session_key=session_key, user__isnull=True
        ).first()
    request.session.pop("cart_id", None)
    if not session_cart:
        return
    user_cart, _ = Cart.objects.get_or_create(user=user)

    with transaction.atomic():
        for item in session_cart.items.select_related("variant", "product"):
            existing = user_cart.items.filter(variant=item.variant).first()
            if existing:
                existing.quantity = min(
                    existing.quantity + item.quantity,
                    MAX_QUANTITY_PER_LINE,
                    item.variant.stock,
                )
                existing.save(update_fields=["quantity"])
            else:
                CartItem.objects.create(
                    cart=user_cart,
                    product=item.product,
                    variant=item.variant,
                    quantity=min(item.quantity, MAX_QUANTITY_PER_LINE, item.variant.stock),
                )
        if not user_cart.coupon and session_cart.coupon:
            user_cart.coupon = session_cart.coupon
            user_cart.save(update_fields=["coupon", "updated_at"])
        session_cart.delete()


def add_item(cart, product, variant, quantity=1):
    """Validate and add a variant to a cart. Raises ValueError with a safe message."""
    if not product.is_active:
        raise ValueError("This product is no longer available.")
    if variant is None or variant.product_id != product.pk or not variant.is_active:
        raise ValueError("Please choose an available size and colour.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a whole number.")
    if quantity < 1:
        raise ValueError("Quantity must be at least 1.")
    if quantity > MAX_QUANTITY_PER_LINE:
        raise ValueError(f"You can order up to {MAX_QUANTITY_PER_LINE} units per size.")
    if variant.stock < quantity:
        raise ValueError(f"Only {variant.stock} left in this size and colour.")

    item = CartItem.objects.filter(cart=cart, variant=variant).first()
    new_quantity = quantity + (item.quantity if item else 0)
    if new_quantity > variant.stock:
        raise ValueError(
            f"You already have {item.quantity} in your bag. Only {variant.stock} available."
        )
    new_quantity = min(new_quantity, MAX_QUANTITY_PER_LINE)
    if item:
        item.quantity = new_quantity
        item.save(update_fields=["quantity"])
    else:
        item = CartItem.objects.create(
            cart=cart, product=product, variant=variant, quantity=new_quantity
        )
    cart.save(update_fields=["updated_at"])
    return item


def resolve_variant(product, size_code=None, color_slug=None):
    """Look up an active variant from raw form input without trusting the client."""
    variants = product.variants.filter(is_active=True).select_related("size", "color")
    if size_code:
        variants = variants.filter(size__code=size_code)
    if color_slug:
        variants = variants.filter(color__slug=color_slug)
    return variants.first()


def update_item(cart, item_id, quantity):
    item = cart.items.filter(pk=item_id).select_related("variant").first()
    if item is None:
        raise ValueError("That bag item no longer exists.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a whole number.")
    if quantity < 1:
        raise ValueError("Quantity must be at least 1. Remove the item instead.")
    if quantity > MAX_QUANTITY_PER_LINE:
        raise ValueError(f"You can order up to {MAX_QUANTITY_PER_LINE} units per size.")
    if quantity > item.variant.stock:
        raise ValueError(f"Only {item.variant.stock} available in this size and colour.")
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    cart.save(update_fields=["updated_at"])
    return item


def remove_item(cart, item_id):
    deleted, _ = cart.items.filter(pk=item_id).delete()
    cart.save(update_fields=["updated_at"])
    return bool(deleted)


def clear_cart(cart):
    cart.items.all().delete()
    cart.coupon = None
    cart.save(update_fields=["coupon", "updated_at"])


def cart_totals(cart):
    subtotal = cart.subtotal
    return {
        "subtotal": subtotal,
        "discount": cart.discount(),
        "shipping": cart.shipping(),
        "total": cart.total,
        "savings": sum(
            (
                (item.product.base_price - item.product.price) * item.quantity
                for item in cart.items.all()
                if item.product.has_sale
            ),
            Decimal("0.00"),
        ),
    }


def cart_issue(cart):
    """Return a message when a cart line is no longer purchasable."""
    for item in cart.items.select_related("product", "variant"):
        if not item.product.is_active:
            return f"{item.product.name} is no longer available."
        if not item.variant.is_active:
            return f"{item.product.name} ({item.variant.size.name}) is no longer available."
        if item.quantity > item.variant.stock:
            return (
                f"Only {item.variant.stock} of {item.product.name} "
                f"({item.variant.size.name}) remain in stock."
            )
    return None
