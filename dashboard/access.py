"""Access control helpers for the staff dashboard.

Every dashboard route requires an active staff account; mutating routes also
require the relevant Django model permission. Superusers hold all permissions
automatically through Django's permission framework.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.db.models import Sum

from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.contenttypes.models import ContentType


def _is_staff(user):
    return user.is_authenticated and user.is_active and user.is_staff


staff_required = login_required(user_passes_test(_is_staff))


def staff_member_required(view_func):
    """Login-redirect for anonymous visitors, 403 for signed-in customers."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if not _is_staff(request.user):
            raise PermissionDenied("The staff dashboard is restricted to store administrators.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def require_permission(permission):
    """Raise 403 unless the user holds ``permission`` (superusers always do)."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated or not _is_staff(request.user):
                from django.contrib.auth.views import redirect_to_login

                if not request.user.is_authenticated:
                    return redirect_to_login(request.get_full_path())
                raise PermissionDenied("The staff dashboard is restricted to store administrators.")
            if not request.user.has_perm(permission):
                raise PermissionDenied(f"Missing permission: {permission}.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def safe_redirect_url(raw, fallback):
    """Only accept same-site relative paths for post-action redirects."""
    if raw and isinstance(raw, str) and raw.startswith("/") and not raw.startswith("//"):
        return raw
    return fallback


def log_admin_action(user, obj, flag, message="", model=None):
    """Record a dashboard change in Django's admin log (admin log section)."""
    try:
        model = model or type(obj)
        content_type = ContentType.objects.get_for_model(model)
        LogEntry.objects.create(
            user_id=user.pk,
            content_type_id=content_type.pk,
            object_id=str(obj.pk),
            object_repr=(str(obj)[:200] if obj is not None else ""),
            action_flag=flag,
            change_message=message or "",
        )
    except Exception:
        # Logging must never break the requested operation.
        pass


__all__ = [
    "staff_required",
    "staff_member_required",
    "require_permission",
    "safe_redirect_url",
    "log_admin_action",
    "ADDITION",
    "CHANGE",
    "DELETION",
    "Sum",
]
