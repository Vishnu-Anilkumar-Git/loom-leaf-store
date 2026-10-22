import re

from django import forms

from accounts.models import INDIAN_STATES
from .models import Order


class CheckoutForm(forms.Form):
    full_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"})
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel"}),
    )
    address_line1 = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "address-line1"}
        ),
    )
    address_line2 = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "address-line2"}
        ),
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level2"}),
    )
    state = forms.ChoiceField(
        choices=[("", "Select state")] + INDIAN_STATES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    postal_code = forms.CharField(
        max_length=10,
        widget=forms.TextInput(
            attrs={"class": "form-control", "autocomplete": "postal-code", "inputmode": "numeric"}
        ),
    )
    delivery_instructions = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    payment_method = forms.ChoiceField(
        choices=Order.PaymentMethod.choices,
        initial=Order.PaymentMethod.COD,
        widget=forms.RadioSelect(attrs={"class": "payment-choice"}),
    )
    save_address = forms.BooleanField(
        required=False,
        label="Save this address to my account",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    checkout_token = forms.CharField(widget=forms.HiddenInput)

    def clean_phone(self):
        value = self.cleaned_data["phone"].strip()
        digits = re.sub(r"\D", "", value)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) != 10 or digits[0] not in "6789":
            raise forms.ValidationError("Enter a valid 10-digit Indian mobile number.")
        return digits

    def clean_postal_code(self):
        value = self.cleaned_data["postal_code"].strip()
        if not re.fullmatch(r"\d{6}", value):
            raise forms.ValidationError("Enter a valid 6-digit PIN code.")
        return value

    def clean_full_name(self):
        value = self.cleaned_data["full_name"].strip()
        if len(value) < 2:
            raise forms.ValidationError("Enter your full name.")
        return value

    def clean_checkout_token(self):
        token = (self.cleaned_data["checkout_token"] or "").strip()
        if len(token) < 16:
            raise forms.ValidationError("Your checkout session expired. Please try again.")
        return token
