"""Tests for the staff dashboard: access, products, inventory, orders, customers,
promotions and reports."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Color, Product, ProductVariant, Size
from catalog.testing import make_product, make_user
from coupons.models import Coupon
from orders.models import Order

User = get_user_model()


def make_staff(username="manager", **kwargs):
    """Staff user holding the model permissions the dashboard checks."""
    user = make_user(username=username, is_staff=True, **kwargs)
    codenames = [
        "add_product",
        "change_product",
        "delete_product",
        "add_coupon",
        "change_coupon",
        "change_order",
        "change_user",
    ]
    permissions = Permission.objects.filter(codename__in=codenames)
    user.user_permissions.add(*permissions)
    return user


def make_order(user, *, status=Order.Status.PENDING, total="1000.00",
               payment_method=Order.PaymentMethod.COD, **kwargs):
    defaults = {
        "full_name": "Test Buyer",
        "email": "buyer@example.com",
        "phone": "9876543210",
        "address_line1": "1 Test Street",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postal_code": "400001",
        "subtotal": Decimal(total),
        "total_amount": Decimal(total),
        "payment_method": payment_method,
        "status": status,
    }
    defaults.update(kwargs)
    return Order.objects.create(user=user, **defaults)


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.customer = make_user(username="shopper")

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_customer_is_forbidden(self):
        self.client.force_login(self.customer)
        for name in ("dashboard:home", "dashboard:order_list", "dashboard:product_list"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 403, name)

    def test_customer_cannot_mutate_products(self):
        product = make_product()
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("dashboard:product_archive", args=[product.pk]), {"next": "/"}
        )
        self.assertEqual(response.status_code, 403)
        product.refresh_from_db()
        self.assertTrue(product.is_active)

    def test_staff_can_view_every_page(self):
        self.client.force_login(self.staff)
        make_product()
        order = make_order(self.customer)
        coupon = Coupon.objects.create(
            code="TEST10",
            discount_type="percentage",
            value=Decimal("10"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
        )
        pages = [
            reverse("dashboard:home"),
            reverse("dashboard:product_list"),
            reverse("dashboard:product_create"),
            reverse("dashboard:inventory"),
            reverse("dashboard:order_list"),
            reverse("dashboard:order_detail", args=[order.order_number]),
            reverse("dashboard:customer_list"),
            reverse("dashboard:customer_detail", args=[self.customer.pk]),
            reverse("dashboard:coupon_list"),
            reverse("dashboard:coupon_create"),
            reverse("dashboard:coupon_edit", args=[coupon.pk]),
            reverse("dashboard:reports"),
            reverse("dashboard:export_csv") + "?kind=orders",
        ]
        for url in pages:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)

    def test_staff_without_permission_cannot_change_products(self):
        limited = make_user(username="viewer", is_staff=True)
        product = make_product()
        self.client.force_login(limited)
        response = self.client.get(reverse("dashboard:product_list"))
        self.assertEqual(response.status_code, 200)  # view-only staff may browse
        response = self.client.post(
            reverse("dashboard:product_edit", args=[product.pk]),
            {
                "name": product.name,
                "sku": product.sku,
                "category": product.category_id,
                "description": product.description,
                "base_price": "999.00",
                "sale_price": "",
                "collections": [],
            },
        )
        self.assertEqual(response.status_code, 403)
        product.refresh_from_db()
        self.assertEqual(product.base_price, Decimal("1490.00"))

    def test_superusers_have_permissions(self):
        superuser = User.objects.create_superuser("boss", "boss@example.com", "Pass!2345x")
        self.assertTrue(superuser.has_perm("catalog.change_product"))


class DashboardHomeTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.customer = make_user(username="buyer")
        self.client.force_login(self.staff)

    def test_metrics_exclude_cancelled_orders(self):
        make_order(self.customer, status=Order.Status.CONFIRMED, total="1000.00")
        make_order(self.customer, status=Order.Status.CANCELLED, total="500.00")
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["revenue"], Decimal("1000.00"))
        self.assertEqual(response.context["metrics"]["order_count"], 1)

    def test_today_range_hides_older_orders(self):
        old = make_order(self.customer, status=Order.Status.CONFIRMED, total="900.00")
        Order.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        response = self.client.get(reverse("dashboard:home") + "?range=today")
        self.assertEqual(response.context["metrics"]["revenue"], Decimal("0.00"))
        response = self.client.get(reverse("dashboard:home") + "?range=month")
        self.assertEqual(response.context["metrics"]["revenue"], Decimal("900.00"))

    def test_low_stock_products_are_listed(self):
        product = make_product(stock=2)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.context["low_stock_count"], 1)
        self.assertEqual(response.context["low_stock"][0].product, product)


class ProductManagementTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.client.force_login(self.staff)
        self.category = make_product().category
        self.size = Size.objects.first()
        self.color = Color.objects.first()

    def _payload(self, **overrides):
        data = {
            "name": "Dashboard Oxford Shirt",
            "sku": "LL-DB-001",
            "category": self.category.pk,
            "short_description": "Crisp Oxford shirt.",
            "description": "A shirt created from the dashboard.",
            "details_and_care": "Machine wash cold.",
            "base_price": "2190.00",
            "sale_price": "",
            "is_active": "on",
            "is_featured": "",
            "is_new_arrival": "on",
            "variants-TOTAL_FORMS": "1",
            "variants-INITIAL_FORMS": "0",
            "variants-MIN_NUM_FORMS": "0",
            "variants-MAX_NUM_FORMS": "1000",
            "variants-0-id": "",
            "variants-0-product": "",
            "variants-0-size": self.size.pk,
            "variants-0-color": self.color.pk,
            "variants-0-sku": "LL-DB-001-M-BLACK",
            "variants-0-stock": "8",
            "variants-0-is_active": "on",
            "variants-0-DELETE": "",
        }
        data.update(overrides)
        return data

    def test_create_product_with_variant(self):
        response = self.client.post(reverse("dashboard:product_create"), self._payload())
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(sku="LL-DB-001")
        self.assertEqual(product.variants.count(), 1)
        self.assertEqual(product.stock_total, 8)
        self.assertTrue(product.is_new_arrival)
        self.assertFalse(product.is_featured)
        self.assertTrue(
            LogEntry.objects.filter(
                user=self.staff, action_flag=ADDITION, object_id=str(product.pk)
            ).exists()
        )

    def test_sale_price_must_be_below_base(self):
        response = self.client.post(
            reverse("dashboard:product_create"), self._payload(sale_price="2490.00")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sale price must be lower")
        self.assertFalse(Product.objects.filter(sku="LL-DB-001").exists())

    def test_base_price_must_be_positive(self):
        response = self.client.post(
            reverse("dashboard:product_create"), self._payload(base_price="0")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "greater than zero")

    def test_duplicate_variant_rows_are_rejected(self):
        data = self._payload(
            **{
                "variants-TOTAL_FORMS": "2",
                "variants-1-id": "",
                "variants-1-product": "",
                "variants-1-size": self.size.pk,
                "variants-1-color": self.color.pk,
                "variants-1-sku": "LL-DB-001-M-BLACK-2",
                "variants-1-stock": "3",
                "variants-1-DELETE": "",
            }
        )
        response = self.client.post(reverse("dashboard:product_create"), data)
        self.assertEqual(response.status_code, 200)
        # Django's formset or the dashboard's own check rejects the duplicate row.
        self.assertContains(response, "duplicate")
        self.assertFalse(Product.objects.filter(sku="LL-DB-001").exists())

    def test_edit_updates_prices_and_logs(self):
        product = make_product()
        variant = product.variants.first()
        url = reverse("dashboard:product_edit", args=[product.pk])
        data = {
            "name": product.name,
            "sku": product.sku,
            "category": product.category_id,
            "short_description": product.short_description,
            "description": product.description,
            "details_and_care": product.details_and_care,
            "base_price": "1790.00",
            "sale_price": "",
            "is_active": "on",
            "collections": [],
            "variants-TOTAL_FORMS": "1",
            "variants-INITIAL_FORMS": "1",
            "variants-MIN_NUM_FORMS": "0",
            "variants-MAX_NUM_FORMS": "1000",
            "variants-0-id": variant.pk,
            "variants-0-product": product.pk,
            "variants-0-size": variant.size_id,
            "variants-0-color": variant.color_id,
            "variants-0-sku": variant.sku,
            "variants-0-stock": str(variant.stock),
            "variants-0-is_active": "on",
            "variants-0-DELETE": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.base_price, Decimal("1790.00"))
        self.assertTrue(
            LogEntry.objects.filter(user=self.staff, action_flag=CHANGE).exists()
        )

    def test_archive_toggle_hides_product(self):
        product = make_product()
        response = self.client.post(
            reverse("dashboard:product_archive", args=[product.pk])
        )
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertFalse(product.is_active)


class InventoryTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.client.force_login(self.staff)
        self.product = make_product(stock=4)
        self.variant = self.product.variants.first()

    def test_inventory_update_changes_stock_and_logs(self):
        response = self.client.post(
            reverse("dashboard:inventory_update", args=[self.variant.pk]),
            {"stock": "12", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 12)
        self.assertTrue(
            LogEntry.objects.filter(
                user=self.staff, action_flag=CHANGE, object_id=str(self.variant.pk)
            ).exists()
        )

    def test_negative_stock_is_rejected(self):
        response = self.client.post(
            reverse("dashboard:inventory_update", args=[self.variant.pk]),
            {"stock": "-3", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 4)

    def test_out_of_stock_filter(self):
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock=0)
        response = self.client.get(reverse("dashboard:inventory") + "?section=out")
        self.assertEqual(len(response.context["page"].object_list), 1)

    def test_inventory_page_lists_variant(self):
        response = self.client.get(reverse("dashboard:inventory"))
        self.assertContains(response, self.variant.sku)


class OrderManagementTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.customer = make_user(username="buyer")
        self.product = make_product()
        self.order = make_order(self.customer)
        self.client.force_login(self.staff)

    def test_search_by_order_number(self):
        response = self.client.get(
            reverse("dashboard:order_list") + f"?q={self.order.order_number}"
        )
        self.assertEqual(len(response.context["page"].object_list), 1)
        response = self.client.get(reverse("dashboard:order_list") + "?q=nomatch")
        self.assertEqual(len(response.context["page"].object_list), 0)

    def test_status_filter(self):
        make_order(self.customer, status=Order.Status.SHIPPED)
        response = self.client.get(
            reverse("dashboard:order_list") + f"?status={Order.Status.SHIPPED}"
        )
        self.assertEqual(len(response.context["page"].object_list), 1)

    def test_valid_transition_is_applied_and_recorded(self):
        response = self.client.post(
            reverse("dashboard:order_set_status", args=[self.order.order_number]),
            {"target": Order.Status.CONFIRMED, "note": "stock verified"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        entry = self.order.status_history.first()
        self.assertEqual(entry.changed_by, self.staff)
        self.assertEqual(entry.note, "stock verified")
        self.assertTrue(
            LogEntry.objects.filter(user=self.staff, action_flag=CHANGE).exists()
        )

    def test_invalid_transition_is_rejected(self):
        self.order.set_status(Order.Status.CONFIRMED)
        response = self.client.post(
            reverse("dashboard:order_set_status", args=[self.order.order_number]),
            {"target": Order.Status.DELIVERED},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

    def test_cancelling_from_dashboard_restores_stock(self):
        variant = self.product.variants.first()
        variant.stock = 0
        variant.save(update_fields=["stock"])
        self.order.set_status(Order.Status.CONFIRMED)
        from orders.models import OrderItem

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            variant=variant,
            product_name=self.product.name,
            sku=variant.sku,
            size=variant.size.name,
            color=variant.color.name,
            quantity=3,
            unit_price=self.product.price,
            line_total=self.product.price * 3,
        )
        self.client.post(
            reverse("dashboard:order_set_status", args=[self.order.order_number]),
            {"target": Order.Status.CANCELLED},
        )
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 3)

    def test_internal_note_is_recorded_with_author(self):
        response = self.client.post(
            reverse("dashboard:order_add_note", args=[self.order.order_number]),
            {"note": "Customer requested gift wrap."},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertIn("Customer requested gift wrap.", self.order.internal_note)
        self.assertIn("[manager]", self.order.internal_note)

    def test_empty_note_is_rejected(self):
        response = self.client.post(
            reverse("dashboard:order_add_note", args=[self.order.order_number]),
            {"note": "   "},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.internal_note, "")

    def test_tracking_details_are_saved(self):
        response = self.client.post(
            reverse("dashboard:order_save_tracking", args=[self.order.order_number]),
            {"tracking_carrier": "Delhivery", "tracking_number": "DLV123456"},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.tracking_carrier, "Delhivery")
        self.assertEqual(self.order.tracking_number, "DLV123456")

    def test_cod_mark_paid_confirms_order(self):
        response = self.client.post(
            reverse("dashboard:order_mark_paid", args=[self.order.order_number])
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

    def test_online_payment_cannot_be_marked_manually(self):
        online = make_order(
            self.customer, payment_method=Order.PaymentMethod.RAZORPAY
        )
        response = self.client.post(
            reverse("dashboard:order_mark_paid", args=[online.order_number])
        )
        self.assertEqual(response.status_code, 302)
        online.refresh_from_db()
        self.assertEqual(online.payment_status, Order.PaymentStatus.PENDING)


class CustomerTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.customer = make_user(username="buyer", email="buyer@example.com")
        self.client.force_login(self.staff)

    def test_staff_accounts_are_not_listed_as_customers(self):
        response = self.client.get(reverse("dashboard:customer_list"))
        names = [customer.username for customer in response.context["page"].object_list]
        self.assertIn("buyer", names)
        self.assertNotIn("manager", names)

    def test_search_by_email(self):
        response = self.client.get(
            reverse("dashboard:customer_list") + "?q=buyer@example.com"
        )
        self.assertEqual(len(response.context["page"].object_list), 1)

    def test_lifetime_spend_excludes_cancelled(self):
        make_order(self.customer, status=Order.Status.CONFIRMED, total="700.00")
        make_order(self.customer, status=Order.Status.CANCELLED, total="300.00")
        response = self.client.get(
            reverse("dashboard:customer_detail", args=[self.customer.pk])
        )
        self.assertEqual(response.context["lifetime_spend"], Decimal("700.00"))
        self.assertEqual(response.context["orders_total"], 1)

    def test_edit_updates_profile_and_logs(self):
        response = self.client.post(
            reverse("dashboard:customer_edit", args=[self.customer.pk]),
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": "buyer@example.com",
                "phone": "9812345678",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertEqual(self.customer.profile.phone, "9812345678")
        self.assertTrue(
            LogEntry.objects.filter(user=self.staff, action_flag=CHANGE).exists()
        )

    def test_duplicate_email_is_rejected(self):
        make_user(username="other", email="taken@example.com")
        response = self.client.post(
            reverse("dashboard:customer_edit", args=[self.customer.pk]),
            {
                "first_name": "Buyer",
                "last_name": "Person",
                "email": "taken@example.com",
                "phone": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.email, "buyer@example.com")


class PromotionTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.client.force_login(self.staff)

    def _payload(self, **overrides):
        data = {
            "code": "SPRING10",
            "description": "Spring sale",
            "discount_type": "percentage",
            "value": "10",
            "min_order_amount": "0",
            "max_discount": "",
            "valid_from": (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "valid_until": (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
            "is_active": "on",
            "usage_limit": "",
            "per_customer_limit": "1",
        }
        data.update(overrides)
        return data

    def test_create_coupon(self):
        response = self.client.post(reverse("dashboard:coupon_create"), self._payload())
        self.assertEqual(response.status_code, 302)
        coupon = Coupon.objects.get(code="SPRING10")
        self.assertEqual(coupon.value, Decimal("10.00"))
        self.assertTrue(
            LogEntry.objects.filter(
                user=self.staff, action_flag=ADDITION, object_id=str(coupon.pk)
            ).exists()
        )

    def test_percentage_over_100_is_rejected(self):
        response = self.client.post(
            reverse("dashboard:coupon_create"), self._payload(value="150")
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot exceed 100%")

    def test_end_before_start_is_rejected(self):
        response = self.client.post(
            reverse("dashboard:coupon_create"),
            self._payload(
                valid_from=(timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M"),
                valid_until=(timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "End date must be after")

    def test_duplicate_code_is_rejected(self):
        Coupon.objects.create(
            code="SPRING10",
            discount_type="fixed",
            value=Decimal("100"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
        )
        response = self.client.post(reverse("dashboard:coupon_create"), self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")

    def test_toggle_deactivates_coupon(self):
        coupon = Coupon.objects.create(
            code="TURNMEOFF",
            discount_type="fixed",
            value=Decimal("50"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
        )
        self.client.post(reverse("dashboard:coupon_toggle", args=[coupon.pk]))
        coupon.refresh_from_db()
        self.assertFalse(coupon.is_active)


class ReportTests(TestCase):
    def setUp(self):
        self.staff = make_staff(username="manager")
        self.customer = make_user(username="buyer")
        self.client.force_login(self.staff)

    def test_report_shows_revenue(self):
        make_order(self.customer, status=Order.Status.CONFIRMED, total="1500.00")
        response = self.client.get(reverse("dashboard:reports"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["revenue"], Decimal("1500.00"))

    def test_orders_csv_export(self):
        order = make_order(self.customer, status=Order.Status.CONFIRMED, total="1500.00")
        response = self.client.get(reverse("dashboard:export_csv") + "?kind=orders")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        body = response.content.decode()
        self.assertIn(order.order_number, body)
        self.assertIn("1500.00", body)

    def test_orders_csv_respects_range(self):
        old = make_order(self.customer, status=Order.Status.CONFIRMED, total="800.00")
        Order.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=10)
        )
        response = self.client.get(
            reverse("dashboard:export_csv") + "?kind=orders&range=today"
        )
        self.assertNotIn("800.00", response.content.decode())

    def test_products_csv_export(self):
        make_product()
        response = self.client.get(reverse("dashboard:export_csv") + "?kind=products")
        body = response.content.decode()
        self.assertIn("SKU", body)
        self.assertIn("LL-T-001", body)

    def test_daily_pdf_and_xlsx_exports_require_staff_and_include_orders(self):
        from datetime import date

        order = make_order(self.customer, status=Order.Status.CONFIRMED, total="321.00")
        for kind, content_type in (("pdf", "application/pdf"), ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")):
            response = self.client.get(
                reverse("dashboard:export_csv") + f"?kind={kind}&day={timezone.localdate():%Y-%m-%d}"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], content_type)
            if kind == "pdf":
                from io import BytesIO
                from pypdf import PdfReader

                pdf_text = " ".join(
                    page.extract_text() or ""
                    for page in PdfReader(BytesIO(response.content)).pages
                )
                self.assertIn(order.order_number, pdf_text.replace("\n", ""))
            else:
                import openpyxl
                from io import BytesIO

                sheet = openpyxl.load_workbook(BytesIO(response.content), read_only=True).active
                self.assertEqual(sheet["A2"].value, order.order_number)

    def test_daily_exports_exclude_orders_from_other_days(self):
        old = make_order(self.customer, status=Order.Status.CONFIRMED, total="777.00")
        Order.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=3))
        response = self.client.get(
            reverse("dashboard:export_csv") + f"?kind=xlsx&day={timezone.localdate():%Y-%m-%d}"
        )
        self.assertNotIn(b"777.00", response.content)

    def test_coupons_csv_export(self):
        Coupon.objects.create(
            code="CSVONLY",
            discount_type="fixed",
            value=Decimal("50"),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=1),
        )
        response = self.client.get(reverse("dashboard:export_csv") + "?kind=coupons")
        self.assertIn("CSVONLY", response.content.decode())
