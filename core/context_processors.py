"""Shared storefront template context.

Failures are swallowed so an unavailable database can never take down the
custom 500 page itself.
"""
from django.utils import timezone


def storefront(request):
    data = {
        "site_settings": None,
        "nav_categories": [],
        "nav_collections": [],
        "cart_count": 0,
        "wishlist_count": 0,
        "wishlist_ids": [],
        "current_year": timezone.localdate().year,
    }
    try:
        from catalog.models import Category, Collection
        from core.models import SiteSettings
        from cart.services import get_cart

        data["site_settings"] = SiteSettings.load()
        data["nav_categories"] = list(
            Category.objects.filter(
                is_active=True, kind__in=[Category.MEN, Category.UNISEX]
            ).order_by("sort_order")
        )
        data["nav_collections"] = list(
            Collection.objects.filter(is_active=True).order_by("sort_order")[:4]
        )
        cart = get_cart(request, create=False)
        data["cart_count"] = cart.item_count if cart else 0
        if request.user.is_authenticated:
            from wishlist.models import WishlistItem

            ids = list(
                WishlistItem.objects.filter(user=request.user).values_list(
                    "product_id", flat=True
                )
            )
            data["wishlist_ids"] = ids
            data["wishlist_count"] = len(ids)
    except Exception:
        pass
    return data
