from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    DISCOUNT_TYPES = [(PERCENTAGE, "Percentage"), (FIXED, "Fixed amount")]

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(max_length=12, choices=DISCOUNT_TYPES, default=PERCENTAGE)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    max_discount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Optional cap for percentage coupons.",
    )
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    usage_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Total successful redemptions allowed. Blank = unlimited."
    )
    per_customer_limit = models.PositiveSmallIntegerField(
        default=1, help_text="Redemptions allowed per signed-in customer."
    )
    times_used = models.PositiveIntegerField(default=0, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        if self.value is not None and self.value <= 0:
            raise ValidationError({"value": "Discount value must be greater than zero."})
        if self.discount_type == self.PERCENTAGE and self.value and self.value > 100:
            raise ValidationError({"value": "A percentage discount cannot exceed 100%."})
        if self.valid_from and self.valid_until and self.valid_from >= self.valid_until:
            raise ValidationError({"valid_until": "End date must be after the start date."})

    def is_live(self, now=None):
        now = now or timezone.now()
        return self.is_active and self.valid_from <= now <= self.valid_until

    def usage_exhausted(self):
        return self.usage_limit is not None and self.times_used >= self.usage_limit

    def validate_for(self, subtotal, user=None):
        """Return an error string for an unusable coupon, otherwise ``None``."""
        now = timezone.now()
        if not self.is_active:
            return "This coupon is not active."
        if now < self.valid_from:
            return "This coupon is not valid yet."
        if now > self.valid_until:
            return "This coupon has expired."
        if self.usage_exhausted():
            return "This coupon has reached its usage limit."
        if Decimal(subtotal) < self.min_order_amount:
            return f"This coupon requires a minimum order of ₹{self.min_order_amount:,.0f}."
        if user is not None and user.is_authenticated:
            used = CouponRedemption.objects.filter(coupon=self, user=user).count()
            if self.per_customer_limit and used >= self.per_customer_limit:
                return "You have already used this coupon the maximum number of times."
        return None

    def calculate_discount(self, subtotal):
        subtotal = Decimal(subtotal or 0)
        if subtotal <= 0:
            return Decimal("0.00")
        if self.discount_type == self.PERCENTAGE:
            discount = subtotal * Decimal(self.value) / Decimal("100")
        else:
            discount = Decimal(self.value)
        if self.max_discount is not None:
            discount = min(discount, self.max_discount)
        discount = min(discount, subtotal)
        return max(discount, Decimal("0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="coupon_redemption"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_redemptions",
    )
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.coupon.code} → {self.order.order_number}"


class CouponError(Exception):
    pass
