from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("dashboard/", include("dashboard.urls")),
    path("", include("core.urls")),
    path("", include("catalog.urls")),
    path("", include("cart.urls")),
    path("", include("wishlist.urls")),
    path("", include("accounts.urls")),
    path("", include("orders.urls")),
    path("", include("reviews.urls")),
    path("", include("newsletter.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.error_404"
handler500 = "core.views.error_500"

admin.site.site_header = "LOOM&LEAF Administration"
admin.site.site_title = "LOOM&LEAF"
admin.site.index_title = "Store management"
