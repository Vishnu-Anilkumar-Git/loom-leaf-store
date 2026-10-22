from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .models import Order, OrderItem, OrderStatusHistory, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "product", "variant", "product_name", "sku", "size", "color",
        "quantity", "unit_price", "line_total",
    )

    def has_add_permission(self, request, obj=None):
        return False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("status", "note", "changed_by", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = (
        "provider", "provider_order_id", "provider_payment_id", "amount",
        "currency", "status", "signature_verified", "error_message", "created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "full_name", "email", "total_display", "payment_method",
        "payment_status", "status", "created_at",
    )
    list_filter = (
        "status", "payment_status", "payment_method", "created_at",
    )
    search_fields = ("order_number", "email", "full_name", "phone")
    date_hierarchy = "created_at"
    inlines = [OrderItemInline, OrderStatusHistoryInline, PaymentInline]
    readonly_fields = (
        "order_number", "user", "checkout_token", "subtotal", "discount_amount",
        "shipping_amount", "total_amount", "coupon", "coupon_code",
        "payment_method", "payment_status", "status", "stock_restored",
        "created_at", "updated_at",
    )
    fieldsets = (
        ("Order", {"fields": ("order_number", "user", "status", "payment_status")}),
        ("Delivery", {"fields": (
            "full_name", "email", "phone", "address_line1", "address_line2",
            "city", "state", "postal_code", "delivery_instructions",
        )}),
        ("Money", {"fields": (
            "subtotal", "discount_amount", "shipping_amount", "total_amount",
            "coupon", "coupon_code",
        )}),
        ("Payment", {"fields": ("payment_method", "stock_restored")}),
        ("Internal", {"fields": ("internal_note", "created_at", "updated_at")}),
    )
    actions = [
        "confirm_orders", "mark_processing", "mark_packed", "mark_shipped",
        "mark_delivered", "cancel_orders", "mark_payment_received",
    ]

    def has_add_permission(self, request):
        return False

    @admin.display(description="Total")
    def total_display(self, obj):
        return format_html("<strong>₹{}</strong>", obj.total_amount)

    def _transition(self, request, queryset, new_status):
        changed = 0
        skipped = 0
        for order in queryset:
            try:
                if order.set_status(
                    new_status, changed_by=request.user, note="Updated from admin action."
                ):
                    changed += 1
                else:
                    skipped += 1
            except ValidationError:
                skipped += 1
        level = messages.SUCCESS if changed else messages.WARNING
        self.message_user(
            request,
            f"{changed} order(s) moved to {new_status}. {skipped} skipped.",
            level=level,
        )

    @admin.action(description="Confirm selected orders")
    def confirm_orders(self, request, queryset):
        self._transition(request, queryset, Order.Status.CONFIRMED)

    @admin.action(description="Mark selected as processing")
    def mark_processing(self, request, queryset):
        self._transition(request, queryset, Order.Status.PROCESSING)

    @admin.action(description="Mark selected as packed")
    def mark_packed(self, request, queryset):
        self._transition(request, queryset, Order.Status.PACKED)

    @admin.action(description="Mark selected as shipped")
    def mark_shipped(self, request, queryset):
        self._transition(request, queryset, Order.Status.SHIPPED)

    @admin.action(description="Mark selected as delivered")
    def mark_delivered(self, request, queryset):
        for order in queryset:
            if order.payment_method == Order.PaymentMethod.COD:
                order.payment_status = Order.PaymentStatus.PAID
                order.save(update_fields=["payment_status", "updated_at"])
        self._transition(request, queryset, Order.Status.DELIVERED)

    @admin.action(description="Cancel selected orders (restores stock)")
    def cancel_orders(self, request, queryset):
        self._transition(request, queryset, Order.Status.CANCELLED)

    @admin.action(description="Mark COD payment received")
    def mark_payment_received(self, request, queryset):
        count = 0
        for order in queryset:
            if order.payment_status != Order.PaymentStatus.PAID:
                order.payment_status = Order.PaymentStatus.PAID
                order.save(update_fields=["payment_status", "updated_at"])
                count += 1
        self.message_user(request, f"{count} order(s) marked as paid.", messages.SUCCESS)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "provider_order_id", "order", "amount", "status",
        "signature_verified", "created_at",
    )
    list_filter = ("status", "signature_verified")
    search_fields = ("provider_order_id", "provider_payment_id", "order__order_number")
    readonly_fields = [field.name for field in Payment._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "note", "changed_by", "created_at")
    list_filter = ("status",)
    search_fields = ("order__order_number", "note")
    readonly_fields = [field.name for field in OrderStatusHistory._meta.fields]
