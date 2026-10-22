from django.urls import path

from . import views

app_name = "wishlist"

urlpatterns = [
    path("wishlist/", views.wishlist_detail, name="detail"),
    path("wishlist/toggle/<slug:slug>/", views.toggle, name="toggle"),
]
