from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import redirect

from .models import NewsletterSubscriber


def _redirect_back(request):
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not next_url.startswith("/"):
        next_url = "/"
    return redirect(next_url)


def subscribe(request):
    if request.method != "POST":
        return redirect("core:home")
    email = (request.POST.get("email") or "").strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Please enter a valid email address.")
        return _redirect_back(request)

    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email, defaults={"source": "storefront"}
    )
    if created:
        messages.success(request, "You're on the list. New season notes, first.")
    elif not subscriber.is_active:
        subscriber.is_active = True
        subscriber.save(update_fields=["is_active"])
        messages.success(request, "Welcome back — your subscription has been reactivated.")
    else:
        messages.info(request, "You're already subscribed with that email.")
    return _redirect_back(request)
