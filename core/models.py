from decimal import Decimal

from django.db import models
from django.utils.text import slugify


class SiteSettings(models.Model):
    """Singleton store configuration editable from Django admin."""

    announcement_text = models.CharField(
        max_length=180,
        default="NEW SEASON ARRIVALS — DISCOVER THE COLLECTION",
    )
    announcement_enabled = models.BooleanField(default=True)

    hero_slogan = models.CharField(max_length=120, default="FASHION THAT MOVES WITH YOU")
    hero_supporting_copy = models.CharField(
        max_length=220, default="Designed for everyday. Made to stand apart."
    )
    hero_collection_label = models.CharField(max_length=120, default="NEW COLLECTION / 2026")

    shipping_flat_rate = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("99.00"))
    free_shipping_threshold = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1999.00")
    )

    contact_email = models.EmailField(default="hello@loomandleaf.example")
    support_hours = models.CharField(max_length=120, default="Mon–Sat, 10:00–18:00 IST")
    instagram_url = models.URLField(blank=True, default="")
    pinterest_url = models.URLField(blank=True, default="")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site settings"
        verbose_name_plural = "Site settings"

    def __str__(self):
        return "LOOM&LEAF site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def shipping_for(self, subtotal: Decimal) -> Decimal:
        subtotal = Decimal(subtotal or 0)
        if subtotal <= 0:
            return Decimal("0.00")
        if self.free_shipping_threshold and subtotal >= self.free_shipping_threshold:
            return Decimal("0.00")
        return self.shipping_flat_rate

    def free_shipping_remaining(self, subtotal: Decimal) -> Decimal:
        subtotal = Decimal(subtotal or 0)
        remaining = (self.free_shipping_threshold or Decimal("0")) - subtotal
        return max(remaining, Decimal("0.00"))


class Page(models.Model):
    """Editable static/policy page rendered by core.views.page_detail."""

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True)
    intro = models.CharField(max_length=260, blank=True)
    body = models.TextField(help_text="Separate paragraphs with blank lines.")
    is_published = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class ContactMessage(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField()
    subject = models.CharField(max_length=160)
    message = models.TextField()
    is_handled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.name}"
