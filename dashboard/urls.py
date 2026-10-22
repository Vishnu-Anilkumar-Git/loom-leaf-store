from django.urls import path

from .views import customers, main, orders, products, promotions, reports

app_name = "dashboard"

urlpatterns = [
    path("", main.dashboard_home, name="home"),
    # Products & inventory
    path("products/", products.product_list, name="product_list"),
    path("products/new/", products.product_create, name="product_create"),
    path("products/<int:pk>/edit/", products.product_edit, name="product_edit"),
    path("products/<int:pk>/archive/", products.product_archive, name="product_archive"),
    path("inventory/", products.inventory, name="inventory"),
    path("inventory/<int:pk>/update/", products.inventory_update, name="inventory_update"),
    # Orders
    path("orders/", orders.order_list, name="order_list"),
    path("orders/<str:order_number>/", orders.order_detail, name="order_detail"),
    path(
        "orders/<str:order_number>/status/",
        orders.order_set_status,
        name="order_set_status",
    ),
    path("orders/<str:order_number>/note/", orders.order_add_note, name="order_add_note"),
    path(
        "orders/<str:order_number>/tracking/",
        orders.order_save_tracking,
        name="order_save_tracking",
    ),
    path("orders/<str:order_number>/paid/", orders.order_mark_paid, name="order_mark_paid"),
    # Customers
    path("customers/", customers.customer_list, name="customer_list"),
    path("customers/<int:pk>/", customers.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", customers.customer_edit, name="customer_edit"),
    # Promotions
    path("promotions/", promotions.coupon_list, name="coupon_list"),
    path("promotions/new/", promotions.coupon_create, name="coupon_create"),
    path("promotions/<int:pk>/edit/", promotions.coupon_edit, name="coupon_edit"),
    path("promotions/<int:pk>/toggle/", promotions.coupon_toggle, name="coupon_toggle"),
    # Reports
    path("reports/", reports.report_index, name="reports"),
    path("reports/export/", reports.export_csv, name="export_csv"),
]
