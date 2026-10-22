from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, ProductVariant


def generate_order_number():
    return f"LL-{timezone.localdate():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"


class Order(models.Model):
    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on Delivery"
        RAZORPAY = "razorpay", "Razorpay (test mode)"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PROCESSING = "processing", "Processing"
        PACKED = "packed", "Packed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        RETURNED = "returned", "Returned"

    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.PROCESSING, Status.CANCELLED},
        Status.PROCESSING: {Status.PACKED, Status.CANCELLED},
        Status.PACKED: {Status.SHIPPED, Status.CANCELLED},
        Status.SHIPPED: {Status.DELIVERED},
        Status.DELIVERED: {Status.RETURNED},
        Status.CANCELLED: set(),
        Status.RETURNED: set(),
    }

    order_number = models.CharField(max_length=24, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    checkout_token = models.CharField(max_length=64, unique=True, null=True, blank=True)

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    delivery_instructions = models.TextField(blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    coupon = models.ForeignKey(
        "coupons.Coupon", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    coupon_code = models.CharField(max_length=40, blank=True)

    payment_method = models.CharField(max_length=12, choices=PaymentMethod.choices)
    payment_status = models.CharField(
        max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    internal_note = models.TextField(blank=True)
    tracking_carrier = models.CharField(
        max_length=60, blank=True, help_text="Courier name, e.g. Delhivery."
    )
    tracking_number = models.CharField(max_length=60, blank=True, db_index=True)
    stock_restored = models.BooleanField(default=False, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["order_number"]),
        ]

    def __str__(self):
        return self.order_number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = generate_order_number()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("orders:order_detail", kwargs={"order_number": self.order_number})

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def can_cancel(self):
        return self.status in {
            self.Status.PENDING,
            self.Status.CONFIRMED,
            self.Status.PROCESSING,
        }

    def allowed_next_statuses(self):
        return self.ALLOWED_TRANSITIONS.get(self.Status(self.status), set())

    def set_status(self, new_status, changed_by=None, note=""):
        """Apply a validated status transition and record it in the timeline."""
        new_status = str(new_status)
        if new_status == self.status:
            return False
        if new_status not in self.allowed_next_statuses():
            raise ValidationError(
                f"Cannot move an order from {self.get_status_display()} to {new_status}."
            )
        with transaction.atomic():
            self.status = new_status
            if new_status == self.Status.CANCELLED:
                self.restore_stock()
            self.save(update_fields=["status", "stock_restored", "updated_at"])
            OrderStatusHistory.objects.create(
                order=self, status=new_status, note=note, changed_by=changed_by
            )
            if new_status == self.Status.DELIVERED:
                from .notifications import send_order_email

                transaction.on_commit(lambda: send_order_email(self, "delivered"))
        return True

    def restore_stock(self):
        """Return reserved inventory exactly once when an order is cancelled."""
        if self.stock_restored:
            return
        for item in self.items.select_related("variant"):
            if item.variant_id:
                ProductVariant.objects.filter(pk=item.variant_id).update(
                    stock=models.F("stock") + item.quantity
                )
        self.stock_restored = True

    def mark_paid(self, provider_payment_id="", note=""):
        if self.payment_status == self.PaymentStatus.PAID:
            return False
        self.payment_status = self.PaymentStatus.PAID
        self.save(update_fields=["payment_status", "updated_at"])
        if self.status == self.Status.PENDING:
            self.set_status(self.Status.CONFIRMED, note=note or "Payment verified.")
        return True


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_items"
    )
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True
    )
    product_name = models.CharField(max_length=200)
    sku = models.CharField(max_length=60)
    size = models.CharField(max_length=20)
    color = models.CharField(max_length=40)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=12, choices=Order.Status.choices)
    note = models.CharField(max_length=240, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name_plural = "order status history"

    def __str__(self):
        return f"{self.order.order_number}: {self.status}"


class Payment(models.Model):
    """One payment attempt for an order. Razorpay callbacks are recorded here."""

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    provider = models.CharField(max_length=20, default="razorpay")
    provider_order_id = models.CharField(max_length=80, unique=True)
    provider_payment_id = models.CharField(max_length=80, blank=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED)
    signature_verified = models.BooleanField(default=False)
    error_message = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider_order_id} ({self.status})"
