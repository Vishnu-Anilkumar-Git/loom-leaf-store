from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from catalog.testing import make_user

from .models import Address

User = get_user_model()


class AuthTests(TestCase):
    def test_registration_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Asha",
                "last_name": "Rao",
                "username": "asharao",
                "email": "asha@example.com",
                "password1": "StrongPass!9021",
                "password2": "StrongPass!9021",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="asharao")
        self.assertTrue(user.check_password("StrongPass!9021"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertTrue(hasattr(user, "profile"))

    def test_duplicate_email_is_rejected(self):
        make_user(username="existing", email="asha@example.com")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "asharao",
                "email": "asha@example.com",
                "password1": "StrongPass!9021",
                "password2": "StrongPass!9021",
            },
        )
        self.assertContains(response, "already exists with this email")
        self.assertFalse(User.objects.filter(username="asharao").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_emails_token_and_completes_reset(self):
        user = make_user(username="reset-user", email="reset@example.com")
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "reset@example.com"}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)
        reset_url = next(
            line.strip() for line in mail.outbox[0].body.splitlines()
            if "/accounts/reset/" in line
        )
        from urllib.parse import urlsplit

        path = urlsplit(reset_url).path
        uidb64, token = path.strip("/").split("/")[-2:]
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        path = response["Location"]
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            path,
            {"new_password1": "NewStrongPass!9032", "new_password2": "NewStrongPass!9032"},
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass!9032"))

    def test_password_reset_response_does_not_disclose_unknown_email(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "missing@example.com"}, follow=True
        )
        self.assertContains(response, "If an account exists")
        self.assertEqual(len(mail.outbox), 0)

    def test_login_with_email(self):
        make_user(username="asha", email="asha@example.com", password="TestPass!2345")
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "asha@example.com", "password": "TestPass!2345"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_requires_post_and_clears_session(self):
        user = make_user()
        self.client.force_login(user)
        get_response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(get_response.status_code, 405)
        post_response = self.client.post(reverse("accounts:logout"))
        self.assertEqual(post_response.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_account_pages_require_authentication(self):
        for name in ("accounts:profile", "accounts:order_history", "wishlist:detail"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn("/accounts/login/", response["Location"])


class AddressTests(TestCase):
    def setUp(self):
        self.user = make_user(username="owner")
        self.other = make_user(username="other")
        self.address = Address.objects.create(
            user=self.user,
            label="Home",
            full_name="Owner Person",
            phone="9876543210",
            line1="12 Test Street",
            city="Mumbai",
            state="Maharashtra",
            postal_code="400001",
        )

    def test_owner_can_edit_address(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:address_edit", args=[self.address.pk]))
        self.assertEqual(response.status_code, 200)

    def test_other_customer_cannot_edit_or_delete(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("accounts:address_edit", args=[self.address.pk]))
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse("accounts:address_delete", args=[self.address.pk])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Address.objects.filter(pk=self.address.pk).exists())

    def test_invalid_pin_code_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:address_create"),
            {
                "label": "Work",
                "full_name": "Owner Person",
                "phone": "9876543210",
                "line1": "1 Road",
                "city": "Pune",
                "state": "Maharashtra",
                "postal_code": "123",
            },
        )
        self.assertContains(response, "valid 6-digit PIN")
        self.assertEqual(self.user.addresses.count(), 1)

    def test_profile_update(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "New",
                "last_name": "Name",
                "email": "new@example.com",
                "phone": "9123456780",
                "marketing_opt_in": "on",
            },
            follow=True,
        )
        self.assertContains(response, "updated")
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.email, "new@example.com")
