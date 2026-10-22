from django.contrib import admin, messages

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "product", "user", "rating", "title", "is_verified_purchase",
        "is_approved", "is_demo", "created_at",
    )
    list_filter = ("is_approved", "is_verified_purchase", "is_demo", "rating", "created_at")
    search_fields = ("product__name", "user__username", "title", "body")
    readonly_fields = ("is_verified_purchase", "created_at", "updated_at")
    list_editable = ("is_approved",)
    actions = ["approve_reviews", "reject_reviews"]

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        count = queryset.update(is_approved=True)
        messages.success(request, f"{count} review(s) approved.")

    @admin.action(description="Unpublish selected reviews")
    def reject_reviews(self, request, queryset):
        count = queryset.update(is_approved=False)
        messages.success(request, f"{count} review(s) unpublished.")
