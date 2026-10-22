from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from catalog.models import Product


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(max_length=2000)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    is_demo = models.BooleanField(
        default=False,
        help_text="Sample layout data — clearly labelled on the storefront as demonstration only.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="unique_review_per_product"),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.rating}/5"

    def save(self, *args, **kwargs):
        if self.user_id and self.product_id:
            self.is_verified_purchase = Product.objects.filter(
                pk=self.product_id,
                order_items__order__user_id=self.user_id,
                order_items__order__status__in=[
                    "confirmed", "processing", "packed", "shipped", "delivered",
                ],
            ).exists()
        super().save(*args, **kwargs)
