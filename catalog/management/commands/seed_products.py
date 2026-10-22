"""Idempotent demonstration data for LOOM&LEAF.

Running this command repeatedly never duplicates products, variants or images.
Existing stock and admin edits are preserved.
"""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import Category, Collection, Color, Product, ProductVariant, Size
from core.models import Page, SiteSettings
from coupons.models import Coupon

STATIC = Path(settings.BASE_DIR) / "static" / "images"

CATEGORY_DATA = [
    ("men", "Men", "Elevated everyday essentials.", "category-men.jpg", 1),
    ("unisex", "Unisex", "Considered essentials, made to wear your way.", "category-men.jpg", 2),
]

COLLECTION_DATA = [
    ("everyday-essentials", "Everyday Essentials", "The pieces you reach for first.",
     "collection-everyday.jpg", 1),
    ("elevated-streetwear", "Elevated Streetwear", "Relaxed shapes, considered details.",
     "collection-streetwear.jpg", 2),
    ("new-season", "New Season 2026", "The newest chapter of LOOM&LEAF.",
     "editorial-portrait.jpg", 3),
]

SIZES = [
    ("XS", "xs", 1, False), ("S", "s", 2, False), ("M", "m", 3, False),
    ("L", "l", 4, False), ("XL", "xl", 5, False), ("XXL", "xxl", 6, False),
]

COLORS = [
    ("Black", "black", "#111111", 1), ("Ivory", "ivory", "#F4F2ED", 2),
    ("Stone", "stone", "#B9B2A6", 3), ("Charcoal", "charcoal", "#3A3A3A", 4),
    ("Olive", "olive", "#6B6B52", 5), ("Clay", "clay", "#A98E7D", 6),
]

PRODUCTS = [
    {
        "sku": "LL-M-001", "name": "Essential Oversized T-Shirt", "category": "men",
        "price": "1490", "sale": "1190", "featured": True, "new": True,
        "image": "products/mens-oversized-tee.jpg",
        "short": "Heavyweight cotton, dropped shoulders, an easy oversized line.",
        "description": (
            "Cut from dense 240 GSM combed cotton, the Essential Oversized T-Shirt is "
            "the quiet foundation of the wardrobe. A dropped shoulder and boxy body give "
            "it presence without volume, while the ribbed neckline keeps its shape."
        ),
        "care": "100% cotton. Machine wash cold with like colours. Do not bleach. "
                "Tumble dry low. Warm iron if needed.",
        "collections": ["everyday-essentials"], "colors": ["black", "ivory", "stone"],
    },
    {
        "sku": "LL-M-002", "name": "Minimal Relaxed Fit Shirt", "category": "men",
        "price": "2290", "sale": None, "featured": True, "new": True,
        "image": "products/mens-relaxed-shirt.jpg",
        "short": "Crisp cotton poplin with a relaxed, unstudied collar.",
        "description": (
            "A modern shirt with an unhurried attitude. Garment-washed cotton poplin "
            "softens with wear, while a relaxed body and slightly longer hem make it "
            "equally at home open over a tee or buttoned to the top."
        ),
        "care": "100% cotton poplin. Machine wash cold, inside out. Line dry in shade. "
                "Steam or iron on medium.",
        "collections": ["everyday-essentials", "elevated-streetwear"],
        "colors": ["ivory", "charcoal"],
    },
    {
        "sku": "LL-M-003", "name": "Everyday Straight-Leg Trousers", "category": "men",
        "price": "2790", "sale": "2290", "featured": False, "new": False,
        "image": "products/mens-trousers.jpg",
        "short": "A clean straight leg in a fluid cotton blend.",
        "description": (
            "Designed to move from desk to dinner without a second thought. A mid-rise "
            "waist, pressed centre crease and straight leg create a sharp line in a "
            "fabric light enough for Indian weather."
        ),
        "care": "Cotton-rich blend. Dry clean or gentle machine wash cold. Do not tumble dry.",
        "collections": ["everyday-essentials"], "colors": ["charcoal", "stone"],
    },
    {
        "sku": "LL-M-004", "name": "Monochrome Lightweight Jacket", "category": "men",
        "price": "4490", "sale": None, "featured": True, "new": False,
        "image": "products/mens-jacket.jpg",
        "short": "A softly structured layer in matte technical twill.",
        "description": (
            "An unlined jacket with a clean funnel neck and hidden placket. Matte "
            "technical twill holds a subtle structure while staying light enough to "
            "layer through the season. Finished with deep side pockets and a tonal zip."
        ),
        "care": "Shell: recycled polyester twill. Machine wash cold on a gentle cycle. "
                "Close the zip before washing. Do not iron trims.",
        "collections": ["elevated-streetwear"], "colors": ["black", "olive"],
    },
    {
        "sku": "LL-U-001", "name": "Essential Cotton Top", "category": "unisex",
        "price": "1290", "sale": None, "featured": False, "new": True,
        "image": "products/mens-oversized-tee.jpg",
        "short": "A close-fitting essential with a clean, curved neckline.",
        "description": (
            "The everyday top, refined. A compact cotton jersey with just enough "
            "stretch, shaped to sit smoothly under blazers and jackets. The neckline is "
            "finished with a fine binding for a clean edge."
        ),
        "care": "95% cotton, 5% elastane. Machine wash cold. Dry flat in shade.",
        "collections": ["everyday-essentials"], "colors": ["black", "ivory"],
    },
    {
        "sku": "LL-U-002", "name": "Relaxed Linen Shirt", "category": "unisex",
        "price": "2490", "sale": "1990", "featured": True, "new": False,
        "image": "products/mens-relaxed-shirt.jpg",
        "short": "Washed linen, a relaxed collar and an easy borrowed fit.",
        "description": (
            "A warm-weather layer with a deliberately relaxed attitude. Pure linen is "
            "washed for a lived-in hand, with a low collar and curved hem that work best "
            "left open over a simple base."
        ),
        "care": "100% linen. Machine wash cold on a gentle cycle. Line dry. "
                "Embrace the natural crease — or steam lightly.",
        "collections": ["everyday-essentials"], "colors": ["ivory", "clay"],
    },
    {
        "sku": "LL-U-003", "name": "Minimal Everyday Trousers", "category": "unisex",
        "price": "2690", "sale": None, "featured": False, "new": False,
        "image": "products/mens-trousers.jpg",
        "short": "High-rise, wide-leg tailoring with an elasticated back.",
        "description": (
            "Clean tailoring that behaves like loungewear. A high-rise waist with a "
            "hidden elastic back gives comfort, while the wide leg and front pleat keep "
            "the line polished."
        ),
        "care": "Viscose-rich blend. Dry clean recommended. Cool iron on reverse.",
        "collections": ["everyday-essentials"], "colors": ["black", "stone"],
    },
    {
        "sku": "LL-U-004", "name": "Oversized Layering Jacket", "category": "unisex",
        "price": "4890", "sale": None, "featured": True, "new": True,
        "image": "products/mens-jacket.jpg",
        "short": "An oversized cocoon layer with dropped shoulders.",
        "description": (
            "A statement layer cut with a cocoon silhouette and dropped shoulders. The "
            "matte finish and tonal buttons keep it minimal; the generous cut means it "
            "layers comfortably over knitwear."
        ),
        "care": "Wool-blend felt. Dry clean only. Store on a wide hanger.",
        "collections": ["elevated-streetwear", "new-season"], "colors": ["charcoal", "black"],
    },
    {
        "sku": "LL-U-005", "name": "Everyday Cotton T-Shirt", "category": "unisex",
        "price": "790", "sale": None, "featured": False, "new": True,
        "image": "products/mens-oversized-tee.jpg",
        "short": "Soft cotton jersey with a relaxed, everyday fit.",
        "description": (
            "A simple tee made for long days. Soft cotton jersey, a roomy body and a "
            "stretchy ribbed neckline that survives repeated dressing."
        ),
        "care": "100% cotton. Machine wash warm with like colours. Tumble dry low.",
        "collections": ["everyday-essentials"], "colors": ["ivory", "black"],
    },
    {
        "sku": "LL-U-006", "name": "Relaxed Everyday Sweatshirt", "category": "unisex",
        "price": "1190", "sale": "990", "featured": True, "new": False,
        "image": "products/mens-jacket.jpg",
        "short": "Brushed fleece, dropped shoulders, room to move.",
        "description": (
            "A soft brushed-back sweatshirt with dropped shoulders and a wide ribbed hem. "
            "Warm without weight, and roomy enough to layer over a tee."
        ),
        "care": "Cotton-poly fleece. Machine wash cold. Do not bleach. Tumble dry low.",
        "collections": ["everyday-essentials", "elevated-streetwear"],
        "colors": ["stone", "olive"],
    },
    {
        "sku": "LL-U-007", "name": "Comfortable Cotton Shorts", "category": "unisex",
        "price": "890", "sale": None, "featured": False, "new": False,
        "image": "products/mens-trousers.jpg",
        "short": "Soft cotton shorts with a soft elastic waist.",
        "description": (
            "Easy pull-on shorts in a breathable cotton weave. A soft elastic waist and "
            "deep pockets keep them comfortable for the whole day."
        ),
        "care": "100% cotton. Machine wash warm. Tumble dry low. Warm iron.",
        "collections": ["everyday-essentials"], "colors": ["black", "stone"],
    },
    {
        "sku": "LL-U-008", "name": "Everyday Co-ord Set", "category": "unisex",
        "price": "1890", "sale": None, "featured": True, "new": True,
        "image": "products/mens-relaxed-shirt.jpg",
        "short": "A matching tee-and-shorts set in soft cotton.",
        "description": (
            "An effortless two-piece in breathable cotton jersey: a relaxed tee and "
            "matching shorts with an elastic waist. Made to be worn together, or apart "
            "with everything else."
        ),
        "care": "100% cotton jersey. Machine wash cold. Do not bleach. Dry flat.",
        "collections": ["everyday-essentials", "new-season"], "colors": ["ivory", "clay"],
    },
]

PAGES = [
    {
        "slug": "about",
        "title": "A quieter kind of fashion",
        "intro": "LOOM&LEAF is a demonstration fashion storefront built with Django.",
        "body": (
            "LOOM&LEAF is an original fictional label created for this Django storefront "
            "project. The design language is inspired by contemporary editorial fashion: "
            "restrained type, monochrome photography and generous space.\n\n"
            "Every product, price and policy on this site is demonstration data. The "
            "brand does not operate as a real retailer, and the sample photography is "
            "used under the Unsplash licence. No real customer testimonials are shown.\n\n"
            "The application demonstrates a complete shopping flow — catalogue, variants, "
            "cart, coupon validation, accounts, stock-safe checkout, COD orders, Razorpay "
            "test-mode payments, reviews and administration."
        ),
    },
    {
        "slug": "shipping-policy",
        "title": "Shipping policy",
        "intro": "How demonstration orders would be dispatched.",
        "body": (
            "This is a demonstration storefront. No physical goods are shipped.\n\n"
            "For the purpose of the demo checkout, orders are shown as dispatched within "
            "2–4 business days, with delivery estimated at 3–7 business days across India. "
            "Shipping is ₹99 per order and free on orders of ₹1,999 or more. These values "
            "are configurable in Site settings in Django admin.\n\n"
            "Cash on Delivery is available in the demo. Real-world COD availability would "
            "depend on the delivery partner and PIN code.\n\n"
            "Questions about a demonstration order can be sent through the contact form; "
            "no real delivery is scheduled."
        ),
    },
    {
        "slug": "returns-policy",
        "title": "Returns & exchanges",
        "intro": "A plain-language returns policy for this demonstration store.",
        "body": (
            "No real purchases are fulfilled, so no physical returns can be accepted.\n\n"
            "The storefront is designed around a 7-day return window from delivery for "
            "unused items with original tags. Exchanges would depend on stock availability. "
            "Prepaid refunds would be returned to the original payment method within 5–7 "
            "business days after inspection; Cash on Delivery refunds would be arranged by "
            "bank transfer.\n\n"
            "Orders can be cancelled from the order page while they are Confirmed or "
            "Processing and unpaid. Paid orders would be handled through support in a real "
            "store; this demo does not process refunds."
        ),
    },
    {
        "slug": "privacy-policy",
        "title": "Privacy policy",
        "intro": "What this demo stores, and where.",
        "body": (
            "LOOM&LEAF stores account details (username, email, name, optional phone), "
            "shipping details you enter at checkout, order history, cart and wishlist "
            "contents in a local SQLite database for demonstration purposes.\n\n"
            "Passwords are stored using Django's password hashing; plaintext passwords are "
            "never saved. Session cookies are used to keep you signed in and to persist an "
            "anonymous bag. CSRF cookies protect forms.\n\n"
            "If Razorpay test mode is configured, payment processing is handled by Razorpay "
            "and this application stores only gateway order/payment identifiers and amounts. "
            "No card details are collected or stored here. This demo does not sell or share "
            "personal data with advertisers.\n\n"
            "Contact messages and newsletter subscriptions are stored in the same local "
            "database. This is a development project, not a production service."
        ),
    },
    {
        "slug": "terms-and-conditions",
        "title": "Terms & conditions",
        "intro": "The ground rules for using this demonstration storefront.",
        "body": (
            "By using this site you acknowledge that LOOM&LEAF is a demonstration "
            "e-commerce application. Products, inventory, prices, reviews marked as samples, "
            "and policies are illustrative and do not form a real retail offer.\n\n"
            "All prices are displayed in Indian rupees (INR). Orders placed with Cash on "
            "Delivery or Razorpay test mode are recorded in the local database and are not "
            "fulfilled. Do not use real payment credentials with the test integration.\n\n"
            "The site's code and design are provided for portfolio and learning purposes. "
            "Photography is sourced from Unsplash under its licence. Brand names and copy are "
            "original to this project."
        ),
    },
]

COUPONS = [
    {"code": "WELCOME10", "description": "10% off your first order", "discount_type": "percentage",
     "value": "10", "min_order": "1499", "max_discount": "500", "usage_limit": 500},
    {"code": "FLAT200", "description": "₹200 off orders over ₹1,999", "discount_type": "fixed",
     "value": "200", "min_order": "1999", "max_discount": None, "usage_limit": 200},
    {"code": "LOOMSEASON", "description": "15% off new season, capped at ₹750",
     "discount_type": "percentage", "value": "15", "min_order": "2499",
     "max_discount": "750", "usage_limit": 100},
]


class Command(BaseCommand):
    help = "Create idempotent LOOM&LEAF demonstration catalogue, pages and coupons."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-demo-reviews",
            action="store_true",
            help="Do not create the clearly-labelled sample reviews.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        SiteSettings.load()

        for kind, name, description, image_name, order in CATEGORY_DATA:
            category, created = Category.objects.get_or_create(
                kind=kind,
                defaults={
                    "name": name, "slug": kind, "description": description, "sort_order": order,
                },
            )
            category.name = name
            category.description = description
            category.is_active = True
            category.sort_order = order
            category.save(update_fields=["name", "description", "is_active", "sort_order"])
            if created or not category.image or not category.image.storage.exists(category.image.name):
                self._attach(category, "image", STATIC / image_name)

        # Keep old department rows and their linked products for order history, but hide them.
        Category.objects.filter(kind__in=("women", "kids")).update(is_active=False)

        for slug, name, description, image_name, order in COLLECTION_DATA:
            collection, created = Collection.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": description, "sort_order": order},
            )
            if created or not collection.image or not collection.image.storage.exists(collection.image.name):
                self._attach(collection, "image", STATIC / image_name)

        size_map = {}
        for name, code, order, is_kids in SIZES:
            size, _ = Size.objects.get_or_create(
                code=code,
                defaults={"name": name, "sort_order": order, "is_kids": is_kids},
            )
            size_map[code] = size

        color_map = {}
        for name, slug, hex_code, order in COLORS:
            color, _ = Color.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "hex_code": hex_code, "sort_order": order},
            )
            color_map[slug] = color

        categories = {category.kind: category for category in Category.objects.all()}
        collections = {collection.slug: collection for collection in Collection.objects.all()}
        adult_sizes = ["xs", "s", "m", "l", "xl", "xxl"]

        created_count = 0
        for index, data in enumerate(PRODUCTS, start=1):
            slug = data["name"].lower().replace("—", "-").replace("–", "-")
            slug = "-".join(part for part in slug.replace("&", "and").split() if part)
            # Legacy seed SKUs keep their historical slugs, so use each new SKU's
            # distinctive suffix when inserting a converted demo product.
            slug = f"{slug}-{data['sku'].lower()}"
            product, created = Product.objects.get_or_create(
                sku=data["sku"],
                defaults={
                    "name": data["name"],
                    "slug": slug,
                    "category": categories[data["category"]],
                    "short_description": data["short"],
                    "description": data["description"],
                    "details_and_care": data["care"],
                    "base_price": Decimal(data["price"]),
                    "sale_price": Decimal(data["sale"]) if data["sale"] else None,
                    "is_featured": data["featured"],
                    "is_new_arrival": data["new"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
            elif product.category.kind in {"women", "kids"}:
                # Reclassify seeded legacy SKUs without deleting historical products.
                product.category = categories["unisex"]
                product.save(update_fields=["category"])
            if (
                not product.main_image
                or not product.main_image.storage.exists(product.main_image.name)
            ):
                self._attach(product, "main_image", STATIC / data["image"])
            for collection_slug in data["collections"]:
                product.collections.add(collections[collection_slug])

            sizes = adult_sizes
            for color_slug in data["colors"]:
                color = color_map[color_slug]
                for size_code in sizes:
                    size = size_map[size_code]
                    variant_sku = f"{data['sku']}-{size_code.upper()}-{color_slug.upper()}"
                    stock = 6 + (index * 3 + len(color_slug) + len(size_code)) % 9
                    if (index + len(size_code)) % 7 == 0:
                        stock = 0  # demonstrate out-of-stock combinations
                    ProductVariant.objects.get_or_create(
                        product=product,
                        size=size,
                        color=color,
                        defaults={
                            "sku": variant_sku[:60],
                            "stock": stock,
                            "is_active": True,
                        },
                    )

        for page in PAGES:
            Page.objects.get_or_create(
                slug=page["slug"],
                defaults={
                    "title": page["title"], "intro": page["intro"],
                    "body": page["body"], "is_published": True,
                },
            )

        now = timezone.now()
        for coupon_data in COUPONS:
            Coupon.objects.get_or_create(
                code=coupon_data["code"],
                defaults={
                    "description": coupon_data["description"],
                    "discount_type": coupon_data["discount_type"],
                    "value": Decimal(coupon_data["value"]),
                    "min_order_amount": Decimal(coupon_data["min_order"]),
                    "max_discount": (
                        Decimal(coupon_data["max_discount"])
                        if coupon_data["max_discount"] else None
                    ),
                    "usage_limit": coupon_data["usage_limit"],
                    "per_customer_limit": 1,
                    "valid_from": now - timedelta(days=1),
                    "valid_until": now + timedelta(days=90),
                    "is_active": True,
                },
            )

        if not options["skip_demo_reviews"]:
            self._seed_demo_reviews()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {Product.objects.count()} products "
                f"({created_count} created), {ProductVariant.objects.count()} variants, "
                f"{Category.objects.count()} categories, {Coupon.objects.count()} coupons."
            )
        )

    def _attach(self, instance, field_name, source: Path):
        if not source.exists():
            self.stdout.write(self.style.WARNING(f"Missing asset: {source}"))
            return
        with source.open("rb") as handle:
            getattr(instance, field_name).save(source.name, File(handle), save=True)

    def _seed_demo_reviews(self):
        from django.contrib.auth import get_user_model

        from reviews.models import Review

        User = get_user_model()
        demo_user, _ = User.objects.get_or_create(
            username="loom_demo",
            defaults={
                "email": "sample-data@loomandleaf.example",
                "first_name": "Sample",
                "last_name": "Reviewer",
                "is_active": False,
            },
        )
        demo_user.set_unusable_password()
        demo_user.save(update_fields=["password"])

        review_data = [
            ("LL-M-001", 5, "Exactly the fit I wanted",
             "The oversized cut falls nicely without looking boxy. The cotton feels substantial."),
            ("LL-U-002", 4, "Beautifully soft linen",
             "Washed linen with a lovely drape. Slightly relaxed through the shoulder, as intended."),
            ("LL-U-005", 5, "Soft and easy",
             "A simple everyday tee that has survived several washes without losing shape."),
        ]
        for sku, rating, title, body in review_data:
            product = Product.objects.filter(sku=sku).first()
            if not product:
                continue
            Review.objects.get_or_create(
                product=product,
                user=demo_user,
                defaults={
                    "rating": rating, "title": title, "body": body,
                    "is_approved": True, "is_demo": True,
                    "is_verified_purchase": False,
                },
            )
