from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    extra = 0
    can_delete = False


try:
    admin.site.unregister(User)
except NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "is_staff", "is_active")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "city", "state", "postal_code", "is_default")
    list_filter = ("state", "is_default")
    search_fields = ("full_name", "user__username", "city", "postal_code")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "marketing_opt_in", "updated_at")
    search_fields = ("user__username", "user__email", "phone")
    list_filter = ("marketing_opt_in",)
