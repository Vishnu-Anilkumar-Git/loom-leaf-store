from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cart.models import Cart
from cart.services import add_item, get_cart
from catalog.models import ProductVariant
from catalog.testing import make_product, make_user
from coupons.models import Coupon, CouponRedemption
from core.models import SiteSettings

from .models import Order, OrderItem, Payment
from .services import (
    PaymentError,
    confirm_razorpay_payment,
    create_razorpay_order,
    verify_signature,
)

User = get_user_model()


class CheckoutTests(TestCase):
    def setUp(self):
        SiteSettings.load()
        self.user = make_user(username="buyer")
        self.product = make_product(price="1490.00", sale_price="1190.00", stock=5)
        self.variant = self.product.variants.first()
        self.client.force_login(self.user)
        self.cart = Cart.objects.create(user=self.user)
        add_item(self.cart, self.product, self.variant, 1)
        self.checkout_token = "checkout-token-1234567890"
        self.payload = {
            "full_name": "Buyer Person",
            "email": "buyer@example.com",
            "phone": "9876543210",
            "address_line1": "12 Test Street",
            "address_line2": "",
            "city": "Mumbai",
            "state": "Maharashtra",
            "postal_code": "400001",
            "delivery_instructions": "Ring the bell.",
            "payment_method": "cod",
            "checkout_token": self.checkout_token,
        }

    def _checkout(self, **overrides):
        data = {**self.payload, **overrides}
        return self.client.post(reverse("orders:checkout"), data)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_cod_checkout_creates_order_and_snapshots(self):
        response = self._checkout()
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(order.subtotal, Decimal("1190.00"))
        self.assertEqual(order.total_amount, Decimal("1289.00"))
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.unit_price, Decimal("1190.00"))
        self.assertEqual(item.sku, self.variant.sku)
        self.assertEqual(item.size, "M")
        self.assertEqual(item.color, "Black")
        self.assertEqual(order.shipping_amount, Decimal("99.00"))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 4)
        self.assertFalse(Cart.objects.get(user=self.user).items.exists())

        # Price edits after purchase never rewrite the snapshot.
        self.product.base_price = Decimal("9999.00")
        self.product.save(update_fields=["base_price"])
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("1190.00"))

    def test_order_confirmation_page_is_visible_to_owner(self):
        self._checkout()
        order = Order.objects.get(user=self.user)
        response = self.client.get(order.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)
        self.assertContains(response, "Ring the bell.")

    def test_repeated_submission_is_idempotent(self):
        self._checkout()
        order = Order.objects.get(user=self.user)
        response = self._checkout()
        self.assertEqual(response.status_code, 302)
        self.assertIn(order.get_absolute_url(), response["Location"])
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        self.assertEqual(OrderItem.objects.filter(order=order).count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 4)

    def test_stock_is_revalidated_at_checkout(self):
        self.variant.stock = 0
        self.variant.save(update_fields=["stock"])
        response = self._checkout()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 0)

    def test_coupon_applied_and_usage_counted_once(self):
        coupon = Coupon.objects.create(
            code="SAVE100",
            discount_type="fixed",
            value=Decimal("100.00"),
            min_order_amount=Decimal("500.00"),
            per_customer_limit=1,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
        )
        cart = Cart.objects.get(user=self.user)
        cart.coupon = coupon
        cart.save(update_fields=["coupon"])
        self._checkout()
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.discount_amount, Decimal("100.00"))
        self.assertEqual(order.total_amount, Decimal("1189.00"))
        coupon.refresh_from_db()
        self.assertEqual(coupon.times_used, 1)
        self.assertTrue(CouponRedemption.objects.filter(order=order).exists())

    def test_per_customer_coupon_limit_is_enforced(self):
        coupon = Coupon.objects.create(
            code="ONCEONLY",
            discount_type="fixed",
            value=Decimal("100.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
            per_customer_limit=1,
        )
        previous_order = Order.objects.create(
            user=self.user,
            full_name="Buyer",
            email="buyer@example.com",
            phone="9876543210",
            address_line1="1",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            total_amount=Decimal("1000.00"),
            payment_method=Order.PaymentMethod.COD,
        )
        CouponRedemption.objects.create(coupon=coupon, order=previous_order, user=self.user)
        cart = Cart.objects.get(user=self.user)
        cart.coupon = coupon
        cart.save(update_fields=["coupon"])
        self._checkout()
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        coupon.refresh_from_db()
        self.assertEqual(coupon.times_used, 0)

    def test_global_coupon_usage_limit_is_enforced(self):
        coupon = Coupon.objects.create(
            code="LASTONE",
            discount_type="fixed",
            value=Decimal("100.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
            usage_limit=1,
            times_used=1,
        )
        cart = Cart.objects.get(user=self.user)
        cart.coupon = coupon
        cart.save(update_fields=["coupon"])
        self._checkout()
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(self._checkout(), "usage limit")

    def test_inactive_coupon_fails_checkout(self):
        coupon = Coupon.objects.create(
            code="NOTACTIVE",
            discount_type="fixed",
            value=Decimal("100.00"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
            is_active=False,
        )
        cart = Cart.objects.get(user=self.user)
        cart.coupon = coupon
        cart.save(update_fields=["coupon"])
        response = self._checkout()
        self.assertEqual(Order.objects.count(), 0)
        self.assertContains(response, "not active")

    def test_other_customer_cannot_view_order(self):
        self._checkout()
        order = Order.objects.get(user=self.user)
        intruder = make_user(username="intruder")
        self.client.force_login(intruder)
        response = self.client.get(order.get_absolute_url())
        self.assertEqual(response.status_code, 404)

    def test_customer_can_cancel_and_stock_is_restored_once(self):
        self._checkout()
        order = Order.objects.get(user=self.user)
        self.client.post(reverse("orders:cancel", args=[order.order_number]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)
        self.client.post(reverse("orders:cancel", args=[order.order_number]))
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

    def test_full_name_and_postal_validation(self):
        response = self._checkout(postal_code="12", phone="12345")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "valid 6-digit PIN code")
        self.assertContains(response, "valid 10-digit Indian mobile number")
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_razorpay_unavailable_does_not_create_order(self):
        response = self._checkout(payment_method="razorpay")
        self.assertContains(response, "Razorpay test mode is not configured")
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Cart.objects.get(user=self.user).items.count(), 1)

    @override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET="")
    def test_create_gateway_order_without_credentials_raises(self):
        order = self._make_pending_order()
        with self.assertRaises(PaymentError):
            create_razorpay_order(order)

    def _make_pending_order(self):
        return Order.objects.create(
            user=self.user,
            full_name="Buyer Person",
            email="buyer@example.com",
            phone="9876543210",
            address_line1="1 Street",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            subtotal=Decimal("1190.00"),
            shipping_amount=Decimal("0.00"),
            total_amount=Decimal("1190.00"),
            payment_method=Order.PaymentMethod.RAZORPAY,
        )


@override_settings(RAZORPAY_KEY_ID="rzp_test_key", RAZORPAY_KEY_SECRET="test_secret")
class RazorpayVerificationTests(TestCase):
    def setUp(self):
        self.user = make_user(username="razorpaybuyer")
        self.order = Order.objects.create(
            user=self.user,
            full_name="Razorpay Buyer",
            email="razor@example.com",
            phone="9876543210",
            address_line1="1 Street",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            subtotal=Decimal("1490.00"),
            shipping_amount=Decimal("0.00"),
            total_amount=Decimal("1490.00"),
            payment_method=Order.PaymentMethod.RAZORPAY,
        )
        self.payment = Payment.objects.create(
            order=self.order,
            provider_order_id="order_test123",
            amount=Decimal("1490.00"),
            currency="INR",
            status=Payment.Status.CREATED,
        )

    def _signature(self, payment_id="pay_test123"):
        return hmac.new(
            b"test_secret",
            f"order_test123|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def test_signature_helper(self):
        self.assertTrue(
            verify_signature("order_test123", "pay_test123", self._signature())
        )
        self.assertFalse(verify_signature("order_test123", "pay_test123", "bad"))

    @patch("orders.services.verify_gateway_payment", return_value=True)
    def test_payment_verify_view_marks_order_paid(self, mock_verify):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("orders:payment_verify", args=[self.order.order_number]),
            {
                "razorpay_order_id": "order_test123",
                "razorpay_payment_id": "pay_test123",
                "razorpay_signature": self._signature(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    @patch("orders.services.verify_gateway_payment", return_value=True)
    def test_payment_verify_view_rejects_bad_signature(self, mock_verify):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("orders:payment_verify", args=[self.order.order_number]),
            {
                "razorpay_order_id": "order_test123",
                "razorpay_payment_id": "pay_test123",
                "razorpay_signature": "tampered",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    @patch("orders.services.verify_gateway_payment", return_value=True)
    def test_valid_payment_is_applied_once(self, mock_verify):
        order = confirm_razorpay_payment(
            order=self.order,
            razorpay_order_id="order_test123",
            razorpay_payment_id="pay_test123",
            signature=self._signature(),
        )
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.payment.refresh_from_db()
        self.assertTrue(self.payment.signature_verified)
        self.assertEqual(self.payment.provider_payment_id, "pay_test123")

        confirm_razorpay_payment(
            order=self.order,
            razorpay_order_id="order_test123",
            razorpay_payment_id="pay_test123",
            signature=self._signature(),
        )
        self.assertEqual(
            order.status_history.filter(status=Order.Status.CONFIRMED).count(), 1
        )
        self.assertEqual(mock_verify.call_count, 1)

    @patch("orders.services.verify_gateway_payment", return_value=True)
    def test_invalid_signature_is_rejected(self, mock_verify):
        with self.assertRaises(PaymentError):
            confirm_razorpay_payment(
                order=self.order,
                razorpay_order_id="order_test123",
                razorpay_payment_id="pay_test123",
                signature="invalid",
            )
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertEqual(self.order.status, Order.Status.PENDING)
        mock_verify.assert_not_called()

    @patch("orders.services.verify_gateway_payment", return_value=True)
    def test_amount_mismatch_is_rejected(self, mock_verify):
        self.payment.amount = Decimal("1.00")
        self.payment.save(update_fields=["amount"])
        with self.assertRaises(PaymentError):
            confirm_razorpay_payment(
                order=self.order,
                razorpay_order_id="order_test123",
                razorpay_payment_id="pay_test123",
                signature=self._signature(),
            )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)
        mock_verify.assert_not_called()

    @patch("orders.services.verify_gateway_payment", return_value=True)
    def test_unknown_gateway_order_is_rejected(self, mock_verify):
        with self.assertRaises(PaymentError):
            confirm_razorpay_payment(
                order=self.order,
                razorpay_order_id="order_not_ours",
                razorpay_payment_id="pay_test123",
                signature=self._signature(),
            )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

    @patch("orders.services.verify_gateway_payment", side_effect=PaymentError("Gateway could not verify"))
    def test_gateway_verification_failure_does_not_mark_paid(self, mock_verify):
        with self.assertRaises(PaymentError):
            confirm_razorpay_payment(
                order=self.order,
                razorpay_order_id="order_test123",
                razorpay_payment_id="pay_test123",
                signature=self._signature(),
            )
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)


class OrderTransitionTests(TestCase):
    def test_invalid_transition_is_rejected(self):
        user = make_user(username="staffuser")
        order = Order.objects.create(
            user=user,
            full_name="A",
            email="a@example.com",
            phone="9876543210",
            address_line1="1",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            total_amount=Decimal("10.00"),
            payment_method=Order.PaymentMethod.COD,
        )
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            order.set_status(Order.Status.DELIVERED)
        order.set_status(Order.Status.CONFIRMED)
        order.set_status(Order.Status.PROCESSING)
        self.assertEqual(order.status, Order.Status.PROCESSING)
