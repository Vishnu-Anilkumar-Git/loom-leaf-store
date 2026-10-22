from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.testing import make_product, make_user
from orders.models import Order
from reviews.models import Review

User = get_user_model()


class AdminSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = make_user(username="customer")
        cls.staff = make_user(username="staff", is_staff=True)
        cls.superuser = User.objects.create_superuser(
            "manager", "manager@example.com", "ManagerPass!2026"
        )
        cls.product = make_product(stock=5)
        cls.order = Order.objects.create(
            user=cls.customer,
            full_name="Customer",
            email="customer@example.com",
            phone="9876543210",
            address_line1="1 Street",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
            subtotal=Decimal("1490.00"),
            total_amount=Decimal("1490.00"),
            payment_method=Order.PaymentMethod.COD,
            status=Order.Status.CONFIRMED,
        )
        cls.review = Review.objects.create(
            product=cls.product,
            user=cls.customer,
            rating=4,
            body="Waiting for approval.",
            is_approved=False,
        )

    def test_customer_cannot_access_admin(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_can_open_admin_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Store management")

    def test_plain_staff_without_permissions_cannot_edit_products(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("admin:catalog_product_changelist"))
        self.assertEqual(response.status_code, 403)

    def test_staff_can_advance_order_status(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("admin:orders_order_changelist"),
            {
                "action": "mark_processing",
                "_selected_action": [str(self.order.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertIn("moved to processing", response.content.decode())

    def test_staff_can_approve_review(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse("admin:reviews_review_changelist"),
            {
                "action": "approve_reviews",
                "_selected_action": [str(self.review.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_approved)

    def test_product_admin_page_renders(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse("admin:catalog_product_change", args=[self.product.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Product variants")
