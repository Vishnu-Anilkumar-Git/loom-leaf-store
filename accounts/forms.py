from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from .models import Address, Profile

User = get_user_model()

INPUT = {"class": "form-control"}


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={**INPUT, "autocomplete": "email"}),
    )
    first_name = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={**INPUT, "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={**INPUT, "autocomplete": "family-name"}),
    )
    marketing_opt_in = forms.BooleanField(
        required=False,
        label="Email me new season notes and private sales",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email"]
        widgets = {
            "username": forms.TextInput(attrs={**INPUT, "autocomplete": "username"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs.update(
                {"class": "form-control", "autocomplete": "new-password"}
            )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already exists with this email.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.marketing_opt_in = self.cleaned_data.get("marketing_opt_in", False)
            profile.save(update_fields=["marketing_opt_in"])
        return user


class StoreLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(attrs={**INPUT, "autocomplete": "username", "autofocus": True}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={**INPUT, "autocomplete": "current-password"})
    )

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        if "@" in value:
            user = User.objects.filter(email__iexact=value).first()
            if user:
                return user.get_username()
        return value


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={**INPUT, "autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        max_length=80, required=False,
        widget=forms.TextInput(attrs={**INPUT, "autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={**INPUT, "autocomplete": "email"})
    )

    class Meta:
        model = Profile
        fields = ["phone", "marketing_opt_in"]
        widgets = {
            "phone": forms.TextInput(attrs={**INPUT, "autocomplete": "tel"}),
            "marketing_opt_in": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError("Another account already uses this email.")
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save(update_fields=["first_name", "last_name", "email"])
            profile.save()
        return profile


class StorePasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("old_password", "new_password1", "new_password2"):
            self.fields[name].widget.attrs.update({"class": "form-control"})


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "label", "full_name", "phone", "line1", "line2",
            "city", "state", "postal_code", "is_default",
        ]
        widgets = {
            "label": forms.TextInput(attrs={**INPUT, "placeholder": "Home / Work"}),
            "full_name": forms.TextInput(attrs={**INPUT, "autocomplete": "name"}),
            "phone": forms.TextInput(attrs={**INPUT, "autocomplete": "tel"}),
            "line1": forms.TextInput(attrs={**INPUT, "autocomplete": "address-line1"}),
            "line2": forms.TextInput(attrs={**INPUT, "autocomplete": "address-line2"}),
            "city": forms.TextInput(attrs={**INPUT, "autocomplete": "address-level2"}),
            "state": forms.Select(attrs={**INPUT}),
            "postal_code": forms.TextInput(
                attrs={**INPUT, "autocomplete": "postal-code", "inputmode": "numeric"}
            ),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_postal_code(self):
        code = self.cleaned_data["postal_code"].strip()
        if not (len(code) == 6 and code.isdigit()):
            raise forms.ValidationError("Enter a valid 6-digit PIN code.")
        return code

    def clean_phone(self):
        digits = "".join(ch for ch in self.cleaned_data["phone"] if ch.isdigit())
        if len(digits) < 10 or len(digits) > 13:
            raise forms.ValidationError("Enter a valid phone number.")
        return self.cleaned_data["phone"].strip()
