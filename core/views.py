from django.contrib import messages
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from catalog.filters import base_queryset
from catalog.models import Category, Collection, Product

from .forms import ContactForm
from .models import Page, SiteSettings


def home(request):
    site = SiteSettings.load()
    categories = Category.objects.filter(
        is_active=True, kind__in=[Category.MEN, Category.UNISEX]
    ).order_by("sort_order")
    collections = Collection.objects.filter(is_active=True).order_by("sort_order")[:4]
    products = base_queryset().filter(
        category__kind__in=[Category.MEN, Category.UNISEX]
    ).order_by("-is_featured", "-is_new_arrival", "-created_at")[:8]
    featured = [p for p in products if p.is_featured][:4]
    best_of = products
    editorial_collection = collections[0] if collections else None
    return render(
        request,
        "core/home.html",
        {
            "site_settings": site,
            "categories": categories,
            "collections": collections,
            "best_of_products": best_of,
            "featured_products": featured,
            "editorial_collection": editorial_collection,
            "hide_footer_newsletter": True,
        },
    )


def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "core/page.html", {"page": page, "title": page.title})


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Thank you — your message has been recorded. We reply within two business days.",
        )
        return redirect("core:contact")
    site = SiteSettings.load()
    return render(
        request,
        "core/contact.html",
        {"form": form, "site_settings": site, "title": "Contact"},
    )


def about(request):
    page = Page.objects.filter(slug="about", is_published=True).first()
    return render(request, "core/about.html", {"page": page, "title": "About"})


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
