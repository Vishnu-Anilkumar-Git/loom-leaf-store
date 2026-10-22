from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Product
from .testing import make_product


class ProductModelTests(TestCase):
    def test_sale_price_and_discount(self):
        product = make_product(price="2000.00", sale_price="1500.00")
        self.assertTrue(product.has_sale)
        self.assertEqual(product.price, Decimal("1500.00"))
        self.assertEqual(product.discount_percent, 25)

    def test_stock_is_variant_level(self):
        product = make_product(stock=4)
        self.assertEqual(product.stock_total, 4)
        self.assertTrue(product.in_stock)
        product.variants.update(stock=0)
        product.refresh_from_db()
        self.assertFalse(product.in_stock)

    def test_category_url(self):
        product = make_product()
        self.assertEqual(product.get_absolute_url(), f"/products/{product.slug}/")
        self.assertEqual(product.category.get_absolute_url(), "/men/")


class CatalogueViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tshirt = make_product(
            sku="LL-M-901", name="Alpha Tee", price="1200.00", sale_price="900.00",
            stock=5, is_new_arrival=True,
        )
        cls.jacket = make_product(
            sku="LL-U-902", name="Zulu Jacket", kind="unisex", price="4200.00",
            color_slug="ivory", stock=0,
        )
        cls.kids = make_product(
            sku="LL-U-903", name="Everyday Shirt", kind="unisex", price="700.00",
            size_code="l", color_slug="stone", stock=8,
        )

    def test_list_page_shows_active_products(self):
        response = self.client.get(reverse("catalog:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Tee")
        self.assertContains(response, "Zulu Jacket")
        self.assertContains(response, "Everyday Shirt")

    def test_legacy_department_products_are_hidden_from_all_shop_routes(self):
        from .testing import make_product

        legacy = make_product(
            sku="LL-W-904", name="Legacy Product", kind="women", price="1200.00"
        )
        for url in (
            reverse("catalog:product_list"),
            reverse("catalog:search") + "?q=Legacy",
            reverse("catalog:new_arrivals"),
            reverse("catalog:collection_list"),
        ):
            response = self.client.get(url)
            self.assertNotContains(response, "Legacy Product")
        self.assertEqual(self.client.get(legacy.get_absolute_url()).status_code, 404)

    def test_unisex_category_route_filters(self):
        response = self.client.get(reverse("catalog:unisex"))
        self.assertContains(response, "Zulu Jacket")
        self.assertNotContains(response, "Alpha Tee")

    def test_inactive_product_is_hidden_and_404(self):
        self.tshirt.is_active = False
        self.tshirt.save(update_fields=["is_active"])
        response = self.client.get(reverse("catalog:product_list"))
        self.assertNotContains(response, "Alpha Tee")
        detail = self.client.get(self.tshirt.get_absolute_url())
        self.assertEqual(detail.status_code, 404)

    def test_category_route_filters(self):
        response = self.client.get(reverse("catalog:men"))
        self.assertContains(response, "Alpha Tee")
        self.assertNotContains(response, "Zulu Jacket")

    def test_search_by_name_and_sku(self):
        response = self.client.get(reverse("catalog:search"), {"q": "zulu"})
        self.assertContains(response, "Zulu Jacket")
        self.assertNotContains(response, "Alpha Tee")
        response = self.client.get(reverse("catalog:search"), {"q": "LL-U-903"})
        self.assertContains(response, "Everyday Shirt")

    def test_empty_search_state(self):
        response = self.client.get(reverse("catalog:search"), {"q": "zzzz-no-result"})
        self.assertContains(response, "No results for")
        self.assertEqual(response.context["result_count"], 0)

    def test_price_filter(self):
        response = self.client.get(reverse("catalog:product_list"), {"max_price": "1000"})
        self.assertContains(response, "Alpha Tee")
        self.assertNotContains(response, "Zulu Jacket")

    def test_size_and_colour_filters(self):
        response = self.client.get(reverse("catalog:product_list"), {"size": "l"})
        self.assertContains(response, "Everyday Shirt")
        self.assertNotContains(response, "Alpha Tee")
        response = self.client.get(reverse("catalog:product_list"), {"color": "ivory"})
        self.assertContains(response, "Zulu Jacket")
        self.assertNotContains(response, "Alpha Tee")

    def test_sale_and_availability_filters(self):
        response = self.client.get(reverse("catalog:product_list"), {"sale": "1"})
        self.assertContains(response, "Alpha Tee")
        self.assertNotContains(response, "Zulu Jacket")
        response = self.client.get(
            reverse("catalog:product_list"), {"availability": "in_stock"}
        )
        self.assertContains(response, "Alpha Tee")
        self.assertNotContains(response, "Zulu Jacket")

    def test_sorting_by_price(self):
        response = self.client.get(
            reverse("catalog:product_list"), {"sort": "price_asc"}
        )
        names = [p.name for p in response.context["products"]]
        self.assertEqual(names, ["Everyday Shirt", "Alpha Tee", "Zulu Jacket"])

    def test_new_arrivals(self):
        response = self.client.get(reverse("catalog:new_arrivals"))
        self.assertContains(response, "Alpha Tee")
        self.assertNotContains(response, "Zulu Jacket")

    def test_pagination(self):
        for index in range(15):
            make_product(
                sku=f"LL-P-{index:03d}",
                name=f"Paged Product {index}",
                price="1000.00",
            )
        response = self.client.get(reverse("catalog:product_list"))
        self.assertEqual(response.context["page_obj"].paginator.per_page, 12)
        self.assertTrue(response.context["page_obj"].has_next())

    def test_product_detail_and_review_section(self):
        response = self.client.get(self.tshirt.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Tee")
        self.assertContains(response, "No reviews yet")
        self.assertContains(response, "variant-data")

    def test_variant_data_contains_stock(self):
        data = self.tshirt.variant_catalogue()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["stock"], 5)
        self.assertEqual(data[0]["size"], "m")
