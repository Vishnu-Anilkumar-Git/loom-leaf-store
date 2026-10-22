from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy, path

from . import views

app_name = "accounts"

urlpatterns = [
    path("accounts/register/", views.register, name="register"),
    path("accounts/login/", views.StoreLoginView.as_view(), name="login"),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset_form.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "accounts/password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("accounts/logout/", views.StoreLogoutView.as_view(), name="logout"),
    path("account/", views.profile, name="profile"),
    path("account/orders/", views.order_history, name="order_history"),
    path("account/password/", views.StorePasswordChangeView.as_view(), name="password_change"),
    path("account/addresses/new/", views.address_create, name="address_create"),
    path("account/addresses/<int:pk>/edit/", views.address_edit, name="address_edit"),
    path("account/addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
]
