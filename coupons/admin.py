from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import Coupon, CouponRedemption


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code", "discount_type", "value", "min_order_amount", "max_discount",
        "valid_from", "valid_until", "times_used", "usage_limit", "is_active",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code", "description")
    readonly_fields = ("times_used", "created_at")
    list_editable = ("is_active",)
    fieldsets = (
        ("Coupon", {"fields": ("code", "description", "is_active")}),
        ("Discount", {"fields": (
            "discount_type", "value", "min_order_amount", "max_discount",
        )}),
        ("Validity", {"fields": ("valid_from", "valid_until")}),
        ("Limits", {"fields": ("usage_limit", "per_customer_limit", "times_used")}),
    )

    def get_changeform_initial_data(self, request):
        now = timezone.now()
        return {
            "valid_from": now,
            "valid_until": now + timedelta(days=30),
        }


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "order", "user", "email", "created_at")
    search_fields = ("coupon__code", "order__order_number", "email")
    readonly_fields = [field.name for field in CouponRedemption._meta.fields]

    def has_add_permission(self, request):
        return False
