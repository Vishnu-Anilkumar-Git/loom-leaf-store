from django.test import Client, TestCase
from django.urls import reverse

from .models import NewsletterSubscriber


class NewsletterTests(TestCase):
    def test_subscribe_creates_subscriber(self):
        response = self.client.post(
            reverse("newsletter:subscribe"),
            {"email": "Reader@Example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(NewsletterSubscriber.objects.filter(email="reader@example.com").exists())
        self.assertContains(response, "on the list")

    def test_duplicate_subscription_is_handled(self):
        NewsletterSubscriber.objects.create(email="reader@example.com")
        response = self.client.post(
            reverse("newsletter:subscribe"),
            {"email": "reader@example.com"},
            follow=True,
        )
        self.assertContains(response, "already subscribed")
        self.assertEqual(NewsletterSubscriber.objects.count(), 1)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(
            reverse("newsletter:subscribe"), {"email": "not-an-email"}, follow=True
        )
        self.assertContains(response, "valid email")
        self.assertEqual(NewsletterSubscriber.objects.count(), 0)

    def test_inactive_subscriber_is_reactivated(self):
        NewsletterSubscriber.objects.create(email="reader@example.com", is_active=False)
        response = self.client.post(
            reverse("newsletter:subscribe"),
            {"email": "reader@example.com"},
            follow=True,
        )
        self.assertContains(response, "reactivated")
        self.assertTrue(NewsletterSubscriber.objects.get().is_active)

    def test_subscribe_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("newsletter:subscribe"), {"email": "reader@example.com"}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(NewsletterSubscriber.objects.count(), 0)
