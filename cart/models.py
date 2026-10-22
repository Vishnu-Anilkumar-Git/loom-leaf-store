from decimal import Decimal

from django.conf import settings
from django.db import models

from catalog.models import Product, ProductVariant


class Cart(models.Model):
    """Exactly one active cart per user, plus a session cart for anonymous visitors."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=40, unique=True, null=True, blank=True)
    coupon = models.ForeignKey(
        "coupons.Coupon", on_delete=models.SET_NULL, null=True, blank=True, related_name="carts"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    abandoned_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name="cart_has_owner",
            )
        ]

    def __str__(self):
        return f"Cart #{self.pk} ({self.user or self.session_key})"

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0.00"))

    def discount(self):
        if not self.coupon:
            return Decimal("0.00")
        if self.coupon.validate_for(self.subtotal, self.user) is not None:
            return Decimal("0.00")
        return self.coupon.calculate_discount(self.subtotal)

    def shipping(self):
        from core.models import SiteSettings

        return SiteSettings.load().shipping_for(self.subtotal)

    @property
    def total(self):
        return max(self.subtotal - self.discount() + self.shipping(), Decimal("0.00"))


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="unique_cart_variant"),
        ]

    def __str__(self):
        return f"{self.product.name} × {self.quantity}"

    @property
    def unit_price(self):
        return self.product.price

    @property
    def line_total(self):
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    @property
    def max_quantity(self):
        return min(self.variant.stock, 10)
