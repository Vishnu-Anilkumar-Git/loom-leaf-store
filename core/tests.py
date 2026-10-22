from django.test import TestCase
from django.urls import reverse

from catalog.testing import make_category, make_product
from core.models import ContactMessage, Page, SiteSettings


class StorefrontTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        SiteSettings.load()
        make_category("unisex")
        make_category("women")
        make_category("kids")
        for slug, title in [
            ("shipping-policy", "Shipping policy"),
            ("returns-policy", "Returns"),
            ("privacy-policy", "Privacy"),
            ("terms-and-conditions", "Terms"),
        ]:
            Page.objects.get_or_create(slug=slug, defaults={"title": title, "body": "Body."})
        cls.product = make_product(is_featured=True, is_new_arrival=True)

    def test_homepage_uses_menswear_campaign_and_has_no_department_strip(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, "hero-menswear.jpg")
        self.assertContains(response, "The Modern Man")
        self.assertContains(response, "Quiet")
        self.assertNotContains(response, "Shop by department")
        self.assertNotContains(response, "Kids")
        self.assertNotContains(response, "Women")

    def test_homepage_sections_render(self):
        response = self.client.get(reverse("core:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LOOM")
        self.assertContains(response, "Essential menswear")
        self.assertContains(response, "NEW SEASON ARRIVALS")
        self.assertContains(response, self.product.name)
        self.assertContains(response, "Fast delivery")

    def test_announcement_can_be_disabled(self):
        site = SiteSettings.load()
        site.announcement_enabled = False
        site.save()
        response = self.client.get(reverse("core:home"))
        self.assertNotContains(response, "NEW SEASON ARRIVALS")

    def test_policy_pages_render_only_when_published(self):
        Page.objects.create(
            title="Test Policy", slug="test-policy", body="Policy body.", is_published=True
        )
        response = self.client.get(reverse("core:page", args=["test-policy"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Policy body.")
        Page.objects.filter(slug="test-policy").update(is_published=False)
        response = self.client.get(reverse("core:page", args=["test-policy"]))
        self.assertEqual(response.status_code, 404)

    def test_contact_form_stores_message(self):
        response = self.client.post(
            reverse("core:contact"),
            {
                "name": "Asha",
                "email": "asha@example.com",
                "subject": "Fit question",
                "message": "How does the oversized tee fit?",
            },
            follow=True,
        )
        self.assertContains(response, "message has been recorded")
        self.assertTrue(ContactMessage.objects.filter(email="asha@example.com").exists())

    def test_invalid_contact_form_preserves_input(self):
        response = self.client.post(
            reverse("core:contact"),
            {"name": "Asha", "email": "bad-email", "subject": "Hi", "message": "Hello"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bad-email")
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_custom_404(self):
        response = self.client.get("/definitely-not-a-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page has moved on.", status_code=404)

    def test_required_routes_exist(self):
        routes = [
            "/", "/products/", "/men/", "/unisex/", "/new-arrivals/",
            "/search/", "/cart/", "/accounts/register/", "/accounts/login/",
            "/checkout/", "/newsletter/subscribe/", "/admin/", "/contact/",
            "/shipping-policy/", "/returns-policy/", "/privacy-policy/", "/terms/",
        ]
        for route in routes:
            response = self.client.get(route)
            self.assertIn(response.status_code, (200, 302), route)
