from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ("product", "variant", "quantity", "added_at")
    can_delete = True


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "item_count", "updated_at")
    search_fields = ("user__username", "session_key")
    inlines = [CartItemInline]
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Items")
    def item_count(self, obj):
        return obj.item_count


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("cart", "product", "variant", "quantity", "added_at")
    search_fields = ("product__name", "cart__user__username")
