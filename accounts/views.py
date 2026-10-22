from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from orders.models import Order

from .forms import (
    AddressForm,
    ProfileForm,
    RegisterForm,
    StoreLoginForm,
    StorePasswordChangeForm,
)
from .models import Address, Profile


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome to LOOM&LEAF. Your account is ready.")
        return redirect("core:home")
    return render(request, "accounts/register.html", {"form": form, "title": "Create account"})


class StoreLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = StoreLoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, "Signed in.")
        return super().form_valid(form)


class StoreLogoutView(LogoutView):
    next_page = reverse_lazy("core:home")

    def post(self, request, *args, **kwargs):
        messages.success(request, "You have been signed out.")
        return super().post(request, *args, **kwargs)


@login_required
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Your details have been updated.")
            return redirect("accounts:profile")
        messages.error(request, "Please correct the highlighted fields.")
    else:
        form = ProfileForm(instance=profile_obj)
    recent_orders = request.user.orders.all()[:3]
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "profile_obj": profile_obj,
            "addresses": request.user.addresses.all(),
            "recent_orders": recent_orders,
            "wishlist_count": request.user.wishlist_items.count(),
            "title": "My account",
        },
    )


@login_required
def order_history(request):
    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(
        request, "accounts/order_history.html", {"orders": orders, "title": "Order history"}
    )


@login_required
def address_create(request):
    initial = {}
    if not request.user.addresses.exists():
        initial["is_default"] = True
    form = AddressForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        address.save()
        messages.success(request, "Address saved.")
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/address_form.html",
        {"form": form, "title": "Add address", "heading": "New address"},
    )


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Address updated.")
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/address_form.html",
        {"form": form, "title": "Edit address", "heading": "Edit address"},
    )


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        address.delete()
        messages.success(request, "Address removed.")
    return redirect("accounts:profile")


class StorePasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StorePasswordChangeForm
    success_url = reverse_lazy("accounts:profile")

    def form_valid(self, form):
        messages.success(self.request, "Your password has been changed.")
        return super().form_valid(form)
