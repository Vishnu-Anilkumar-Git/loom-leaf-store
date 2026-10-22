from django.test import TestCase
from django.urls import reverse

from catalog.testing import make_product, make_user

from .models import WishlistItem


class WishlistTests(TestCase):
    def setUp(self):
        self.user = make_user(username="wisher")
        self.product = make_product(stock=5)

    def test_anonymous_user_is_asked_to_sign_in(self):
        response = self.client.post(
            reverse("wishlist:toggle", args=[self.product.slug]),
            {"next": self.product.get_absolute_url()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_anonymous_ajax_gets_401_json(self):
        response = self.client.post(
            reverse("wishlist:toggle", args=[self.product.slug]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("login_url", response.json())

    def test_toggle_adds_removes_and_never_duplicates(self):
        self.client.force_login(self.user)
        url = reverse("wishlist:toggle", args=[self.product.slug])
        first = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(first.json()["saved"])
        self.assertEqual(first.json()["count"], 1)
        self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(WishlistItem.objects.filter(user=self.user).count(), 1)
        second = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertFalse(second.json()["saved"])
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_wishlist_page_and_add_to_bag(self):
        self.client.force_login(self.user)
        WishlistItem.objects.create(user=self.user, product=self.product)
        response = self.client.get(reverse("wishlist:detail"))
        self.assertContains(response, self.product.name)
        response = self.client.post(
            reverse("cart:add", args=[self.product.slug]),
            {"size": "m", "color": "black", "quantity": 1, "next": reverse("wishlist:detail")},
            follow=True,
        )
        self.assertContains(response, "added to your bag")

    def test_wishlist_is_private(self):
        other = make_user(username="otherwisher")
        WishlistItem.objects.create(user=other, product=self.product)
        self.client.force_login(self.user)
        response = self.client.get(reverse("wishlist:detail"))
        self.assertNotContains(response, self.product.name)
        self.assertContains(response, "Your wishlist is empty")
