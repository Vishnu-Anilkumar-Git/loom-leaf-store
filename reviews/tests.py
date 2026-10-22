from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.testing import make_product, make_user
from orders.models import Order, OrderItem

from .models import Review


class ReviewTests(TestCase):
    def setUp(self):
        self.user = make_user(username="reviewer")
        self.product = make_product(stock=5)
        self.client.force_login(self.user)

    def test_unauthenticated_review_redirects_to_login(self):
        self.client.logout()
        response = self.client.post(
            reverse("reviews:submit", args=[self.product.slug]),
            {"rating": 5, "body": "Excellent everyday piece."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_authenticated_review_is_created_pending_moderation(self):
        response = self.client.post(
            reverse("reviews:submit", args=[self.product.slug]),
            {"rating": 4, "title": "Good fit", "body": "Soft cotton and a relaxed cut."},
        )
        self.assertEqual(response.status_code, 302)
        review = Review.objects.get(product=self.product, user=self.user)
        self.assertEqual(review.rating, 4)
        self.assertFalse(review.is_approved)
        self.assertFalse(review.is_verified_purchase)

        detail = self.client.get(self.product.get_absolute_url())
        self.assertEqual(detail.context["rating_total"], 0)

    def test_duplicate_review_is_blocked(self):
        Review.objects.create(
            product=self.product, user=self.user, rating=5, body="First review text.",
            is_approved=True,
        )
        response = self.client.post(
            reverse("reviews:submit", args=[self.product.slug]),
            {"rating": 1, "body": "A second attempt at a review."},
            follow=True,
        )
        self.assertContains(response, "already reviewed")
        self.assertEqual(Review.objects.filter(product=self.product).count(), 1)

    def test_invalid_rating_is_rejected(self):
        response = self.client.post(
            reverse("reviews:submit", args=[self.product.slug]),
            {"rating": 9, "body": "This rating is outside the allowed range."},
            follow=True,
        )
        self.assertContains(response, "could not be saved")
        self.assertFalse(Review.objects.filter(product=self.product).exists())

    def test_short_review_body_is_rejected(self):
        self.client.post(
            reverse("reviews:submit", args=[self.product.slug]),
            {"rating": 4, "body": "Short"},
        )
        self.assertFalse(Review.objects.filter(product=self.product).exists())

    def test_verified_purchase_is_computed_from_orders(self):
        order = Order.objects.create(
            user=self.user,
            full_name="Reviewer",
            email="reviewer@example.com",
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
        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=self.product.variants.first(),
            product_name=self.product.name,
            sku=self.product.sku,
            size="M",
            color="Black",
            quantity=1,
            unit_price=Decimal("1490.00"),
            line_total=Decimal("1490.00"),
        )
        review = Review.objects.create(
            product=self.product, user=self.user, rating=5, body="Verified purchase review."
        )
        self.assertTrue(review.is_verified_purchase)

    def test_aggregate_uses_only_approved_reviews(self):
        other = make_user(username="second")
        Review.objects.create(
            product=self.product, user=self.user, rating=5, body="Approved review text.",
            is_approved=True,
        )
        Review.objects.create(
            product=self.product, user=other, rating=1, body="Pending review text.",
            is_approved=False,
        )
        response = self.client.get(self.product.get_absolute_url())
        self.assertEqual(response.context["rating_total"], 1)
        self.assertEqual(response.context["rating_avg"], 5)
        self.assertContains(response, "Sample data", count=0)

    def test_review_page_marks_demo_reviews_as_samples(self):
        Review.objects.create(
            product=self.product, user=self.user, rating=5, body="Demo review text.",
            is_approved=True, is_demo=True,
        )
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, "Sample data")
        self.assertContains(response, "not real customer testimonials")
