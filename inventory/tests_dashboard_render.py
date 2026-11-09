"""Throwaway render smoke test for templates/inventory/dashboard.html.

Runs against Django's isolated TEST database, so db.sqlite3 is untouched.
"""
import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from inventory.models import Transaction
from products.models import Product
from users.models import Company, User


class DashboardRenderTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company_name="Test Co", slug="test-co", email="ops@test.test",
        )
        self.user = User.objects.create_user(
            "ops@test.test", password="x", company=self.company,
        )
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        self.low = Product.objects.create(
            company=self.company, name="Kritik mahsulot", sku="LOW-1",
            category="electronics", quantity=2, min_stock=5, max_stock=50,
            price=Decimal("1250000.50"),
        )
        self.zero = Product.objects.create(
            company=self.company, name="Tugagan mahsulot", sku="OUT-1",
            category="food", quantity=0, min_stock=3, max_stock=30,
            price=Decimal("999.99"),
        )
        self.over = Product.objects.create(
            company=self.company, name="Ortiqcha mahsulot", sku="OVR-1",
            category="clothing", quantity=900, min_stock=5, max_stock=100,
            price=Decimal("10"),
        )
        self.ok = Product.objects.create(
            company=self.company, name="Yetarli mahsulot", sku="OK-1",
            category="tools", quantity=40, min_stock=5, max_stock=100,
            price=Decimal("50"),
        )

        # Transaction.save() moves product.quantity, so the OUT is booked
        # against a product that has stock to give.
        Transaction.objects.create(
            company=self.company, product=self.low, user=self.user,
            transaction_type="IN", quantity=2,
        )
        Transaction.objects.create(
            company=self.company, product=self.ok, user=self.user,
            transaction_type="OUT", quantity=1,
        )

    def _get(self, lang="uz"):
        session = self.client.session
        session["language"] = lang
        session.save()
        return self.client.get(reverse("dashboard"))

    def test_dashboard_renders_in_all_languages(self):
        for lang in ("uz", "uz_cyr", "ru", "en"):
            with self.subTest(lang=lang):
                resp = self._get(lang)
                self.assertEqual(resp.status_code, 200, lang)
                body = resp.content.decode()
                # No Django tag may leak into the output. `}}` is not a useful
                # marker here because base.html ships nested CSS/JS braces.
                for marker in ("{%", "{{"):
                    self.assertFalse(marker in body, f"{marker} leaked ({lang})")
                self.assertIn("dbdCategoryChart", body, lang)
                self.assertIn('<script id="dbdCategoryData"', body, lang)

    def test_real_counts_reach_the_template(self):
        resp = self._get()
        ctx = resp.context
        self.assertEqual(ctx["total_products"], 4)
        self.assertEqual(ctx["low_stock_count"], 1)
        self.assertEqual(ctx["out_of_stock_count"], 1)
        self.assertEqual(ctx["overstock_count"], 1)
        self.assertEqual(ctx["recent_stock_in"], 2)
        self.assertEqual(ctx["recent_stock_out"], 1)
        self.assertEqual(ctx["low_stock_products"][0].sku, "LOW-1")
        self.assertEqual(ctx["out_of_stock_products"][0].sku, "OUT-1")
        counts = list(ctx["category_counts"].values())
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_chart_payload_is_json(self):
        body = self._get().content.decode()
        start = body.index('id="dbdCategoryData"')
        start = body.index(">", start) + 1
        raw = body[start:body.index("</script>", start)]
        data = json.loads(raw)
        self.assertEqual(sum(data.values()), 4)
        self.assertEqual(sorted(data.values()), [1, 1, 1, 1])

    def test_numbers_are_grouped(self):
        body = self._get().content.decode()
        # 4*1250000.50 + 0 + 900*10 + 39*50 = 5010952
        self.assertIn("5 010 952 so'm", body)
        self.assertNotIn("5010952.00", body)

    def test_empty_company_has_states_not_crash(self):
        Transaction.objects.all().delete()
        Product.objects.all().delete()
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("dbd-state", body)
        # No chart payload is emitted, so the canvas/JSON pair is absent
        # (the id string still appears in the script that guards for it).
        self.assertFalse('<script id="dbdCategoryData"' in body)
        self.assertFalse('id="dbdCategoryChart"' in body)
        # The empty-category CTA is the only place category_list is linked.
        self.assertIn(f'href="{reverse("category_list")}"', body)
        self.assertIn("0 so'm", body)

    def test_hrefs_resolve(self):
        body = self._get().content.decode()
        for url in (
            reverse("product_create"), reverse("stock_in"), reverse("stock_out"),
            reverse("scanner:scanner_view"), reverse("low_stock_list"),
            reverse("out_of_stock_list"), reverse("overstock_list"),
            reverse("transaction_list"), reverse("business_insights"),
            reverse("finance:customer_debt_list"), reverse("finance:supplier_debt_list"),
            reverse("inventory_table"), reverse("inventory_overview"),
            reverse("product_list"),
        ):
            self.assertTrue(f'href="{url}"' in body, f"missing href {url}")
