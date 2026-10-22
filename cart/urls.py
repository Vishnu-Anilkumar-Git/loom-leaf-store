from django.urls import path

from . import views

app_name = "cart"

urlpatterns = [
    path("cart/", views.cart_detail, name="detail"),
    path("cart/add/<slug:slug>/", views.add_to_cart, name="add"),
    path("cart/update/<int:item_id>/", views.update_cart_item, name="update"),
    path("cart/remove/<int:item_id>/", views.remove_cart_item, name="remove"),
    path("cart/coupon/apply/", views.apply_coupon, name="apply_coupon"),
    path("cart/coupon/remove/", views.remove_coupon, name="remove_coupon"),
]
