from django.contrib import admin, messages
from django.db.models import Sum
from django.utils.html import format_html

from .models import Category, Collection, Color, Product, ProductImage, ProductVariant, Size


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "sort_order")


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ("size", "color", "sku", "stock", "is_active")
    autocomplete_fields = ("size", "color")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "sku", "price_display", "stock_display",
        "is_featured", "is_new_arrival", "is_active",
    )
    list_editable = ("is_featured", "is_new_arrival", "is_active")
    list_filter = ("category", "is_active", "is_featured", "is_new_arrival", "collections")
    search_fields = ("name", "sku", "description", "category__name")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("collections",)
    inlines = [ProductImageInline, ProductVariantInline]
    readonly_fields = ("created_at", "updated_at", "image_preview")
    fieldsets = (
        ("Identity", {"fields": ("name", "slug", "sku", "category", "collections")}),
        ("Copy", {"fields": ("short_description", "description", "details_and_care")}),
        ("Pricing", {"fields": ("base_price", "sale_price")}),
        ("Media", {"fields": ("main_image", "image_preview")}),
        ("Merchandising", {"fields": ("is_active", "is_featured", "is_new_arrival")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    actions = ["make_featured", "remove_featured", "deactivate", "activate"]

    @admin.display(description="Price")
    def price_display(self, obj):
        if obj.has_sale:
            return format_html(
                "₹{} <s style='color:#888'>₹{}</s>", obj.sale_price, obj.base_price
            )
        return f"₹{obj.base_price}"

    @admin.display(description="Stock")
    def stock_display(self, obj):
        total = obj.variants.aggregate(total=Sum("stock"))["total"] or 0
        return format_html(
            "<span style='color:{}'>{}</span>", "#a33" if total == 0 else "#111", total
        )

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.main_image:
            return format_html(
                '<img src="{}" style="max-height:180px;border:1px solid #ddd" alt="">',
                obj.main_image.url,
            )
        return "No image uploaded."

    @admin.action(description="Mark selected as featured")
    def make_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        messages.success(request, f"{count} products marked as featured.")

    @admin.action(description="Remove featured flag")
    def remove_featured(self, request, queryset):
        count = queryset.update(is_featured=False)
        messages.success(request, f"{count} products unfeatured.")

    @admin.action(description="Deactivate selected products")
    def deactivate(self, request, queryset):
        count = queryset.update(is_active=False)
        messages.success(request, f"{count} products deactivated.")

    @admin.action(description="Activate selected products")
    def activate(self, request, queryset):
        count = queryset.update(is_active=True)
        messages.success(request, f"{count} products activated.")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "size", "color", "sku", "stock", "is_active")
    list_editable = ("stock", "is_active")
    list_filter = ("size", "color", "is_active")
    search_fields = ("sku", "product__name")
    autocomplete_fields = ("product", "size", "color")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sort_order", "is_kids")
    list_editable = ("sort_order", "is_kids")
    search_fields = ("name", "code")


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "swatch", "sort_order")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug")

    @admin.display(description="Colour")
    def swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;border-radius:50%;'
            'border:1px solid #ccc;background:{}"></span> {}',
            obj.hex_code, obj.hex_code,
        )


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "alt_text", "sort_order")
    search_fields = ("product__name", "alt_text")
