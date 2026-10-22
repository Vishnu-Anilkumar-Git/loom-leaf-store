from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from .validators import validate_image_upload


class Category(models.Model):
    """The storefront departments: Men and Unisex."""

    MEN = "men"
    UNISEX = "unisex"
    WOMEN = "women"  # Retained for legacy records; hidden from storefront.
    KIDS = "kids"  # Retained for legacy records; hidden from storefront.
    KIND_CHOICES = [(MEN, "Men"), (UNISEX, "Unisex"), (WOMEN, "Women (legacy)"), (KIDS, "Kids (legacy)")]

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, unique=True)
    description = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to="categories/", blank=True, validators=[validate_image_upload])
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        route = {
            self.MEN: "catalog:men",
            self.UNISEX: "catalog:unisex",
        }.get(self.kind, "catalog:product_list")
        return reverse(route)


class Collection(models.Model):
    """Editorial collections that cut across departments."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True)
    description = models.CharField(max_length=240, blank=True)
    image = models.ImageField(upload_to="collections/", blank=True, validators=[validate_image_upload])
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:collection_detail", kwargs={"slug": self.slug})


class Size(models.Model):
    name = models.CharField(max_length=20, unique=True)
    code = models.SlugField(max_length=20, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_kids = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Color(models.Model):
    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, default="#111111")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_ratings(self):
        return self.annotate(
            rating_avg=models.Avg(
                "reviews__rating",
                filter=models.Q(reviews__is_approved=True),
            ),
            rating_total=models.Count(
                "reviews",
                filter=models.Q(reviews__is_approved=True),
                distinct=True,
            ),
        )


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    collections = models.ManyToManyField(Collection, blank=True, related_name="products")
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True)
    sku = models.CharField("SKU", max_length=40, unique=True)
    short_description = models.CharField(max_length=240, blank=True)
    description = models.TextField()
    details_and_care = models.TextField(
        blank=True, help_text="Materials, fit and care instructions."
    )
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Optional promotional price. Must be lower than the base price.",
    )
    main_image = models.ImageField(upload_to="products/", blank=True, validators=[validate_image_upload])
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "name"]
        indexes = [
            models.Index(fields=["is_active", "-created_at"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_featured"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = self.slug or slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    @property
    def has_sale(self):
        return self.sale_price is not None and self.sale_price < self.base_price

    @property
    def price(self):
        return self.sale_price if self.has_sale else self.base_price

    @property
    def discount_percent(self):
        if not self.has_sale or not self.base_price:
            return 0
        return round((self.base_price - self.sale_price) / self.base_price * 100)

    @property
    def stock_total(self):
        # Uses the prefetched variants cache where available — no per-card queries.
        return sum(v.stock for v in self.variants.all() if v.is_active)

    @property
    def in_stock(self):
        return self.stock_total > 0

    @property
    def size_list(self):
        seen = set()
        sizes = []
        for variant in self.variants.all():
            if variant.is_active and variant.size_id not in seen:
                seen.add(variant.size_id)
                sizes.append(variant.size)
        return sizes

    @property
    def color_list(self):
        seen = set()
        colors = []
        for variant in self.variants.all():
            if variant.is_active and variant.color_id not in seen and variant.stock > 0:
                seen.add(variant.color_id)
                colors.append(variant.color)
        return colors

    def available_sizes(self):
        return Size.objects.filter(
            variants__product=self, variants__is_active=True
        ).distinct().order_by("sort_order")

    def available_colors(self):
        return Color.objects.filter(
            variants__product=self, variants__is_active=True
        ).distinct().order_by("sort_order")

    def variant_catalogue(self):
        """Data used by the detail page JS to validate size/color combinations."""
        return [
            {
                "id": v.pk,
                "size": v.size.code,
                "color": v.color.slug,
                "stock": v.stock,
            }
            for v in self.variants.filter(is_active=True).select_related("size", "color")
        ]


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/", validators=[validate_image_upload])
    alt_text = models.CharField(max_length=180, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.product.name} image {self.sort_order}"


class ProductVariant(models.Model):
    """Size/colour stock unit. Stock lives here, never on the parent product."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.ForeignKey(Size, on_delete=models.PROTECT, related_name="variants")
    color = models.ForeignKey(Color, on_delete=models.PROTECT, related_name="variants")
    sku = models.CharField(max_length=60, unique=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["size__sort_order", "color__sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "color"], name="unique_product_size_color"
            ),
        ]

    def __str__(self):
        return f"{self.product.sku} / {self.size.name} / {self.color.name}"

    @property
    def in_stock(self):
        return self.is_active and self.stock > 0

    def clean(self):
        if self.product_id and self.stock == 0 and not self.is_active:
            # Zero stock is allowed; simply inactive.
            pass
