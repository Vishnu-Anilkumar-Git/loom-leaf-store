"""Small factory helpers shared by the Django test suite."""
from decimal import Decimal

from catalog.models import Category, Color, Product, ProductVariant, Size


def make_category(kind="men", name=None):
    name = name or kind.title()
    category, _ = Category.objects.get_or_create(
        kind=kind,
        defaults={"name": name, "slug": kind, "description": f"{name} pieces."},
    )
    return category


def make_product(
    *,
    sku="LL-T-001",
    name="Test Oversized T-Shirt",
    kind="men",
    price="1490.00",
    sale_price=None,
    size_code="m",
    color_slug="black",
    stock=10,
    is_active=True,
    is_featured=False,
    is_new_arrival=False,
):
    category = make_category(kind)
    size, _ = Size.objects.get_or_create(
        code=size_code,
        defaults={"name": size_code.upper(), "sort_order": 3},
    )
    color, _ = Color.objects.get_or_create(
        slug=color_slug,
        defaults={"name": color_slug.title(), "hex_code": "#111111"},
    )
    product, _ = Product.objects.get_or_create(
        sku=sku,
        defaults={
            "name": name,
            "slug": name.lower().replace(" ", "-"),
            "category": category,
            "short_description": "A test piece.",
            "description": "A product used by the automated test suite.",
            "details_and_care": "Test care instructions.",
            "base_price": Decimal(price),
            "sale_price": Decimal(sale_price) if sale_price else None,
            "is_active": is_active,
            "is_featured": is_featured,
            "is_new_arrival": is_new_arrival,
        },
    )
    variant, _ = ProductVariant.objects.get_or_create(
        product=product,
        size=size,
        color=color,
        defaults={"sku": f"{sku}-{size_code}-{color_slug}", "stock": stock},
    )
    if variant.stock != stock:
        variant.stock = stock
        variant.save(update_fields=["stock"])
    return product


def make_user(username="shopper", password="TestPass!2345", email=None, **kwargs):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email or f"{username}@example.com", **kwargs},
    )
    if created:
        user.set_password(password)
        user.save()
    return user
