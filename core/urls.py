from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
    path("pages/<slug:slug>/", views.page_detail, name="page"),
    path("shipping-policy/", views.page_detail, {"slug": "shipping-policy"}, name="shipping_policy"),
    path("returns-policy/", views.page_detail, {"slug": "returns-policy"}, name="returns_policy"),
    path("privacy-policy/", views.page_detail, {"slug": "privacy-policy"}, name="privacy_policy"),
    path("terms/", views.page_detail, {"slug": "terms-and-conditions"}, name="terms"),
]
