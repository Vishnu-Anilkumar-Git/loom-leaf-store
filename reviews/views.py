from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from catalog.models import Product

from .forms import ReviewForm


@login_required
def submit_review(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if request.method != "POST":
        return redirect(f"{product.get_absolute_url()}#reviews")
    if product.reviews.filter(user=request.user).exists():
        messages.info(request, "You have already reviewed this piece.")
        return redirect(f"{product.get_absolute_url()}#reviews")
    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.is_approved = False
        review.save()
        messages.success(
            request, "Thank you — your review is awaiting moderation before it appears."
        )
    else:
        messages.error(
            request,
            "Your review could not be saved. Please check the rating and review text.",
        )
    return redirect(f"{product.get_absolute_url()}#reviews")
