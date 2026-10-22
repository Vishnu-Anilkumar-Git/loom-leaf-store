from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("products/", views.product_list, name="product_list"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
    path("men/", views.category_products, {"category": "men"}, name="men"),
    path("unisex/", views.category_products, {"category": "unisex"}, name="unisex"),
    path("new-arrivals/", views.new_arrivals, name="new_arrivals"),
    path("search/", views.search, name="search"),
    path("collections/", views.collection_list, name="collection_list"),
    path("collections/<slug:slug>/", views.collection_detail, name="collection_detail"),
]
