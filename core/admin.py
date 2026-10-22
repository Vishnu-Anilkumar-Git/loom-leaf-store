from django.contrib import admin

from .models import ContactMessage, Page, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Announcement bar", {"fields": ("announcement_enabled", "announcement_text")}),
        ("Homepage hero", {"fields": (
            "hero_slogan", "hero_supporting_copy", "hero_collection_label",
        )}),
        ("Shipping", {"fields": ("shipping_flat_rate", "free_shipping_threshold")}),
        ("Contact & social", {"fields": (
            "contact_email", "support_hours", "instagram_url", "pinterest_url",
        )}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def response_add(self, request, obj, post_url_continue=None):
        from django.shortcuts import redirect

        return redirect("admin:core_sitesettings_changelist")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "is_published", "updated_at")
    list_editable = ("is_published",)
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "name", "email", "is_handled", "created_at")
    list_filter = ("is_handled", "created_at")
    search_fields = ("name", "email", "subject", "message")
    list_editable = ("is_handled",)
    readonly_fields = ("name", "email", "subject", "message", "created_at")
