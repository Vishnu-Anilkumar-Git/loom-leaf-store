from django.conf import settings
from django.db import models

INDIAN_STATES = [
    ("Andhra Pradesh", "Andhra Pradesh"), ("Arunachal Pradesh", "Arunachal Pradesh"),
    ("Assam", "Assam"), ("Bihar", "Bihar"), ("Chhattisgarh", "Chhattisgarh"),
    ("Delhi", "Delhi"), ("Goa", "Goa"), ("Gujarat", "Gujarat"), ("Haryana", "Haryana"),
    ("Himachal Pradesh", "Himachal Pradesh"), ("Jharkhand", "Jharkhand"),
    ("Karnataka", "Karnataka"), ("Kerala", "Kerala"), ("Madhya Pradesh", "Madhya Pradesh"),
    ("Maharashtra", "Maharashtra"), ("Manipur", "Manipur"), ("Meghalaya", "Meghalaya"),
    ("Mizoram", "Mizoram"), ("Nagaland", "Nagaland"), ("Odisha", "Odisha"),
    ("Puducherry", "Puducherry"), ("Punjab", "Punjab"), ("Rajasthan", "Rajasthan"),
    ("Sikkim", "Sikkim"), ("Tamil Nadu", "Tamil Nadu"), ("Telangana", "Telangana"),
    ("Tripura", "Tripura"), ("Uttar Pradesh", "Uttar Pradesh"), ("Uttarakhand", "Uttarakhand"),
    ("West Bengal", "West Bengal"), ("Jammu & Kashmir", "Jammu & Kashmir"),
    ("Ladakh", "Ladakh"), ("Chandigarh", "Chandigarh"),
]


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(max_length=20, blank=True)
    marketing_opt_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile for {self.user.get_username()}"


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    label = models.CharField(max_length=40, default="Home")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    line1 = models.CharField("Address line 1", max_length=200)
    line2 = models.CharField("Address line 2 (optional)", max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, choices=[("", "Select state")] + INDIAN_STATES)
    postal_code = models.CharField("PIN code", max_length=10)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name_plural = "addresses"

    def __str__(self):
        return f"{self.label} — {self.city}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Address.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)
