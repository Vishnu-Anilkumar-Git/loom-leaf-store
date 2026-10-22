from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from catalog.models import Product

from .models import WishlistItem


def _safe_next(request, fallback):
    target = request.POST.get("next") or fallback
    if not target.startswith("/") or target.startswith("//"):
        return fallback
    return target


@login_required
def wishlist_detail(request):
    items = (
        WishlistItem.objects.filter(user=request.user)
        .select_related("product", "product__category")
        .prefetch_related("product__variants__size", "product__variants__color")
    )
    return render(request, "wishlist/wishlist.html", {"items": items, "title": "Wishlist"})


def toggle(request, slug):
    if request.method != "POST":
        return redirect("wishlist:detail")
    if not request.user.is_authenticated:
        return login_required_response(request)
    product = get_object_or_404(Product, slug=slug, is_active=True)
    item, created = WishlistItem.objects.get_or_create(user=request.user, product=product)
    if not created:
        item.delete()
    count = WishlistItem.objects.filter(user=request.user).count()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"saved": created, "count": count})
    messages.success(
        request,
        "Saved to your wishlist." if created else "Removed from your wishlist.",
    )
    return redirect(_safe_next(request, product.get_absolute_url()))


def login_required_response(request):
    login_url = f"/accounts/login/?next={request.POST.get('next', '/wishlist/')}"
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {"error": "Sign in to save pieces to your wishlist.", "login_url": login_url},
            status=401,
        )
    messages.info(request, "Sign in to save pieces to your wishlist.")
    return redirect(login_url)
