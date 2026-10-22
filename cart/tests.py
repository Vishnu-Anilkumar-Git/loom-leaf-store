from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import ProductVariant
from catalog.testing import make_product, make_user
from coupons.models import Coupon

from .models import Cart, CartItem
from .services import add_item, get_cart


class CartServiceTests(TestCase):
    def setUp(self):
        self.product = make_product(stock=5)
        self.variant = self.product.variants.first()
        self.user = make_user()
        self.cart = Cart.objects.create(user=self.user)

    def test_add_and_duplicate_rows_merge(self):
        add_item(self.cart, self.product, self.variant, 2)
        add_item(self.cart, self.product, self.variant, 1)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 1)
        self.assertEqual(self.cart.items.first().quantity, 3)

    def test_quantity_cannot_exceed_stock(self):
        with self.assertRaises(ValueError):
            add_item(self.cart, self.product, self.variant, 6)

    def test_quantity_cannot_be_zero_or_negative(self):
        with self.assertRaises(ValueError):
            add_item(self.cart, self.product, self.variant, 0)
        with self.assertRaises(ValueError):
            add_item(self.cart, self.product, self.variant, -2)

    def test_inactive_product_cannot_be_added(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        with self.assertRaises(ValueError):
            add_item(self.cart, self.product, self.variant, 1)

    def test_wrong_variant_is_rejected(self):
        other = make_product(sku="LL-OTHER", name="Other Product", stock=3)
        with self.assertRaises(ValueError):
            add_item(self.cart, self.product, other.variants.first(), 1)

    def test_totals_use_server_prices_and_shipping(self):
        from core.models import SiteSettings

        SiteSettings.load()
        add_item(self.cart, self.product, self.variant, 2)
        self.assertEqual(self.cart.subtotal, Decimal("2980.00"))
        self.assertEqual(self.cart.shipping(), Decimal("0.00"))
        self.assertEqual(self.cart.total, Decimal("2980.00"))


class CartViewTests(TestCase):
    def setUp(self):
        self.product = make_product(stock=4)
        self.variant = self.product.variants.first()

    def test_anonymous_cart_persists_in_session(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "color": "black", "quantity": 1},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "added to your bag")
        response = self.client.get(reverse("cart:detail"))
        self.assertContains(response, "Test Oversized T-Shirt")
        self.assertTrue(
            Cart.objects.filter(session_key=self.client.session.session_key).exists()
        )

    def test_missing_size_is_rejected(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"quantity": 1},
            follow=True,
        )
        self.assertContains(response, "choose a size")

    def test_missing_colour_is_rejected_when_colours_exist(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "quantity": 1},
            follow=True,
        )
        self.assertContains(response, "choose a colour")

    def test_invalid_size_is_rejected(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "xxxl", "color": "black", "quantity": 1},
            follow=True,
        )
        self.assertContains(response, "choose an available size")

    def test_quantity_beyond_stock_is_rejected(self):
        response = self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "color": "black", "quantity": 11},
            follow=True,
        )
        self.assertContains(response, "up to 10 units")

    def test_update_and_remove(self):
        self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "color": "black", "quantity": 1},
        )
        cart = Cart.objects.get(session_key=self.client.session.session_key)
        item = cart.items.first()
        self.client.post(
            reverse("cart:update", args=[item.pk]), {"quantity": 3}
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)
        self.client.post(reverse("cart:remove", args=[item.pk]))
        self.assertFalse(CartItem.objects.filter(pk=item.pk).exists())

    def test_login_merges_session_cart(self):
        self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "color": "black", "quantity": 2},
        )
        user = make_user()
        self.client.post(
            reverse("accounts:login"),
            {"username": user.username, "password": "TestPass!2345"},
        )
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.context["cart"].user, user)
        self.assertEqual(response.context["cart"].items.count(), 1)
        self.assertFalse(Cart.objects.filter(session_key__isnull=False).exists())

    def test_expired_coupon_is_not_applied(self):
        coupon = Coupon.objects.create(
            code="OLD",
            discount_type="percentage",
            value=10,
            min_order_amount=0,
            valid_from=timezone.now() - timedelta(days=10),
            valid_until=timezone.now() - timedelta(days=1),
        )
        self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "color": "black", "quantity": 1},
        )
        response = self.client.post(
            reverse("cart:apply_coupon"), {"code": "old"}, follow=True
        )
        self.assertContains(response, "expired")
        cart = Cart.objects.get(session_key=self.client.session.session_key)
        self.assertIsNone(cart.coupon)

    def test_valid_coupon_is_applied_and_discount_capped(self):
        Coupon.objects.create(
            code="WELCOME10",
            discount_type="percentage",
            value=10,
            min_order_amount=1000,
            max_discount=Decimal("100.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
        )
        self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "color": "black", "quantity": 1},
        )
        response = self.client.post(
            reverse("cart:apply_coupon"), {"code": "welcome10"}, follow=True
        )
        self.assertContains(response, "applied")
        cart = Cart.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(cart.coupon.code, "WELCOME10")
        self.assertEqual(cart.discount(), Decimal("100.00"))

    def test_empty_cart_page(self):
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your bag is empty")
