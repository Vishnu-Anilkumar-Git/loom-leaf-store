from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("orders/<str:order_number>/", views.order_detail, name="order_detail"),
    path("orders/<str:order_number>/cancel/", views.cancel_order, name="cancel"),
    path("orders/<str:order_number>/pay/", views.payment, name="payment"),
    path("orders/<str:order_number>/pay/verify/", views.payment_verify, name="payment_verify"),
    path(
        "orders/<str:order_number>/pay/cancelled/",
        views.payment_cancelled,
        name="payment_cancelled",
    ),
]
