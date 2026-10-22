"""Forms for the staff dashboard.

ModelForms delegate uniqueness and model-level validation to Django; extra
business rules (positive prices, sale below base, duplicate variants) are
checked here so mistakes surface as form errors instead of 500s.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q

from accounts.models import Profile
from catalog.models import Category, Collection, Color, Product, ProductVariant, Size
from coupons.models import Coupon

User = get_user_model()


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name",
            "sku",
            "category",
            "collections",
            "short_description",
            "description",
            "details_and_care",
            "base_price",
            "sale_price",
            "main_image",
            "is_active",
            "is_featured",
            "is_new_arrival",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": "dash-input", "placeholder": "Product name"}),
            "sku": forms.TextInput(attrs={"class": "dash-input", "placeholder": "LL-TS-001"}),
            "short_description": forms.Textarea(
                attrs={"class": "dash-input", "rows": 2, "placeholder": "One-line summary"}
            ),
            "description": forms.Textarea(
                attrs={"class": "dash-input", "rows": 5, "placeholder": "Full product description"}
            ),
            "details_and_care": forms.Textarea(
                attrs={"class": "dash-input", "rows": 3, "placeholder": "Materials, fit, care"}
            ),
            "base_price": forms.NumberInput(attrs={"class": "dash-input", "min": "0", "step": "0.01"}),
            "sale_price": forms.NumberInput(
                attrs={"class": "dash-input", "min": "0", "step": "0.01", "placeholder": "Optional"}
            ),
            "main_image": forms.ClearableFileInput(attrs={"class": "dash-file"}),
            "category": forms.Select(attrs={"class": "dash-input"}),
            "collections": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("is_active", "is_featured", "is_new_arrival"):
            self.fields[name].widget.attrs.update({"class": "dash-check"})
            # Rendered as plain checkboxes: unchecked means False, never an error.
            self.fields[name].required = False
        self.fields["category"].queryset = Category.objects.filter(
            is_active=True, kind__in=[Category.MEN, Category.UNISEX]
        )
        self.fields["collections"].queryset = Collection.objects.filter(is_active=True)
        self.fields["base_price"].label = "Base price (₹)"
        self.fields["sale_price"].label = "Sale price (₹)"

    def clean_base_price(self):
        value = self.cleaned_data["base_price"]
        if value <= 0:
            raise ValidationError("Base price must be greater than zero.")
        return value

    def clean_sale_price(self):
        value = self.cleaned_data.get("sale_price")
        if value is None:
            return value
        if value <= 0:
            raise ValidationError("Sale price must be greater than zero, or left empty.")
        base = self.cleaned_data.get("base_price")
        if base is not None and value >= base:
            raise ValidationError("Sale price must be lower than the base price.")
        return value


class VariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ("size", "color", "sku", "stock", "is_active")
        widgets = {
            "size": forms.Select(attrs={"class": "dash-input dash-input--sm"}),
            "color": forms.Select(attrs={"class": "dash-input dash-input--sm"}),
            "sku": forms.TextInput(attrs={"class": "dash-input dash-input--sm"}),
            "stock": forms.NumberInput(
                attrs={"class": "dash-input dash-input--sm", "min": "0"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "dash-check"}),
        }

    def clean_stock(self):
        stock = self.cleaned_data.get("stock")
        if stock is not None and stock < 0:
            raise ValidationError("Stock cannot be negative.")
        return stock


BaseVariantFormSet = forms.inlineformset_factory(
    Product,
    ProductVariant,
    form=VariantForm,
    fields=("size", "color", "sku", "stock", "is_active"),
    extra=2,
    can_delete=True,
)


class VariantFormSet(BaseVariantFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            size = form.cleaned_data.get("size")
            color = form.cleaned_data.get("color")
            if size and color:
                key = (size.pk, color.pk)
                if key in seen:
                    raise ValidationError(
                        "Duplicate variant: each size/colour combination may appear only once."
                    )
                seen.add(key)


class StockAdjustForm(forms.ModelForm):
    """Single-variant stock override used on the inventory page."""

    class Meta:
        model = ProductVariant
        fields = ("stock", "is_active")
        widgets = {
            "stock": forms.NumberInput(
                attrs={"class": "dash-input dash-input--sm stock-input", "min": "0"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "dash-check"}),
        }

    def clean_stock(self):
        stock = self.cleaned_data["stock"]
        if stock < 0:
            raise ValidationError("Stock cannot be negative.")
        return stock


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = (
            "code",
            "description",
            "discount_type",
            "value",
            "min_order_amount",
            "max_discount",
            "valid_from",
            "valid_until",
            "is_active",
            "usage_limit",
            "per_customer_limit",
        )
        widgets = {
            "code": forms.TextInput(
                attrs={"class": "dash-input", "placeholder": "WELCOME10", "autocapitalize": "characters"}
            ),
            "description": forms.TextInput(
                attrs={"class": "dash-input", "placeholder": "Short description"}
            ),
            "discount_type": forms.Select(attrs={"class": "dash-input"}),
            "value": forms.NumberInput(attrs={"class": "dash-input", "min": "0", "step": "0.01"}),
            "min_order_amount": forms.NumberInput(
                attrs={"class": "dash-input", "min": "0", "step": "0.01"}
            ),
            "max_discount": forms.NumberInput(
                attrs={"class": "dash-input", "min": "0", "step": "0.01", "placeholder": "No cap"}
            ),
            "valid_from": forms.DateTimeInput(
                attrs={"class": "dash-input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "valid_until": forms.DateTimeInput(
                attrs={"class": "dash-input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "usage_limit": forms.NumberInput(
                attrs={"class": "dash-input", "min": "0", "placeholder": "Unlimited"}
            ),
            "per_customer_limit": forms.NumberInput(attrs={"class": "dash-input", "min": "0"}),
            "is_active": forms.CheckboxInput(attrs={"class": "dash-check"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["value"].label = "Discount value"
        self.fields["valid_from"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
        self.fields["valid_until"].input_formats = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"]
        if self.instance.pk:
            for field in ("valid_from", "valid_until"):
                value = self.initial.get(field)
                if value and hasattr(value, "strftime"):
                    self.initial[field] = value.strftime("%Y-%m-%dT%H:%M")

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise ValidationError("A coupon code is required.")
        qs = Coupon.objects.filter(code=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A coupon with this code already exists.")
        return code


class InternalNoteForm(forms.Form):
    note = forms.CharField(
        label="Internal note",
        widget=forms.Textarea(
            attrs={"class": "dash-input", "rows": 2, "placeholder": "Visible to staff only"}
        ),
        max_length=1000,
        required=True,
    )


class TrackingForm(forms.Form):
    tracking_carrier = forms.CharField(
        max_length=60,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "dash-input", "placeholder": "e.g. Delhivery, Blue Dart"}
        ),
    )
    tracking_number = forms.CharField(
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"class": "dash-input", "placeholder": "Tracking reference"}),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("tracking_carrier") and not cleaned.get("tracking_number"):
            raise ValidationError("Enter a carrier or a tracking number to save tracking details.")
        return cleaned


class CustomerEditForm(forms.ModelForm):
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "dash-input", "placeholder": "Phone"}),
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "dash-input"}),
            "last_name": forms.TextInput(attrs={"class": "dash-input"}),
            "email": forms.EmailInput(attrs={"class": "dash-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = getattr(self.instance, "profile", None)
        if profile and "phone" in self.fields:
            self.fields["phone"].initial = profile.phone
        self.fields["first_name"].required = True
        self.fields["email"].required = True

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Another customer already uses this email address.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        phone = self.cleaned_data.get("phone", "")
        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone = phone
            profile.save(update_fields=["phone", "updated_at"])
        return user


class DateRangeForm(forms.Form):
    """Custom date range inputs used by the dashboard and reports filters."""

    range = forms.ChoiceField(
        choices=[("custom", "Custom range")],
        required=False,
        widget=forms.HiddenInput,
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "dash-input", "type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "dash-input", "type": "date"}),
    )
