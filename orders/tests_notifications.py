from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from cart.models import Cart
from cart.services import add_item
from catalog.testing import make_product, make_user
from orders.models import Order
from orders.notifications import send_abandoned_cart_reminders, send_order_email


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="https://shop.example")
class OrderNotificationTests(TestCase):
    def setUp(self):
        self.user = make_user(username="mailbuyer", email="mailbuyer@example.com")
        self.order = Order.objects.create(
            user=self.user, full_name="Mail Buyer", email=self.user.email,
            phone="9876543210", address_line1="1 Main St", city="Mumbai",
            state="Maharashtra", postal_code="400001", total_amount="120.00",
            payment_method=Order.PaymentMethod.COD,
        )

    def test_placed_and_delivered_emails_include_order_reference(self):
        from django.core import mail

        send_order_email(self.order, "placed")
        send_order_email(self.order, "delivered")
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn(self.order.order_number, mail.outbox[0].body)
        self.assertIn("delivered", mail.outbox[1].subject.lower())

    def test_abandoned_cart_reminder_is_sent_once_after_24_hours(self):
        from django.core import mail

        now = timezone.now()
        cart = Cart.objects.create(user=self.user)
        product = make_product(stock=5)
        add_item(cart, product, product.variants.first(), 1)
        Cart.objects.filter(pk=cart.pk).update(updated_at=now - timedelta(hours=25))
        self.assertEqual(send_abandoned_cart_reminders(now=now), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(send_abandoned_cart_reminders(now=now), 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_cart_reminder_skips_cart_updated_within_window(self):
        now = timezone.now()
        cart = Cart.objects.create(user=self.user)
        product = make_product(stock=5)
        add_item(cart, product, product.variants.first(), 1)
        self.assertEqual(send_abandoned_cart_reminders(now=now), 0)
