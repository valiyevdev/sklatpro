import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import StockAdjustment, StockMovement
from products.models import Product
from users.models import Company
from warehouses.models import Warehouse

User = get_user_model()


class MovementHistoryFilterTests(TestCase):
    """Regression cover for the filter bar and empty state of the
    Movement History page.

    Guards three bugs that a purely visual redesign would have hidden:
    the view used to read `type`/`product` while the form posted
    `movement_type`/`product_id` (so two filters never applied), a
    hand-edited `product_id` raised, and any movement with a NULL
    `user`/`warehouse` crashed template rendering.
    """

    def setUp(self):
        self.company = Company.objects.create(
            company_name='ACME', slug='acme', email='ops@acme.test',
        )
        self.user = User.objects.create_user(
            'op@acme.test', password='x', company=self.company,
        )
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

        self.alpha = Product.objects.create(
            company=self.company, name='Alpha', sku='A-1', price=0,
        )
        self.beta = Product.objects.create(
            company=self.company, name='Beta', sku='B-2', price=0,
        )

        for i in range(40):
            StockMovement.objects.create(
                company=self.company,
                product=self.alpha if i % 2 == 0 else self.beta,
                direction='IN',
                movement_type='stock_in',
                quantity=i + 1,
                reference_number='REF-%03d' % i,
            )
        StockMovement.objects.create(
            company=self.company, product=self.beta, direction='OUT',
            movement_type='sale', quantity=5,
        )

    def url(self):
        return reverse('movement_history')

    # ---------- filter bar ----------

    def test_unfiltered_renders_search_and_collapsed_sheet(self):
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('mvh-search__input', html)
        self.assertIn('mvh-filter-toggle', html)
        # Collapsed by default, so the page opens with one clean row.
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('hidden', html.split('id="mvh-filter-sheet"')[1][:60])
        # Labels must resolve, not leak raw i18n keys.
        for key in ('filters', 'apply_filters', 'search_movements_placeholder'):
            self.assertNotIn('>%s<' % key, html)

    def test_movement_type_filter_applies_and_opens_sheet(self):
        resp = self.client.get(self.url(), {'movement_type': 'sale'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['page_obj'].paginator.count, 1)
        html = resp.content.decode()
        # An active filter is never hidden behind a collapsed control.
        self.assertIn('aria-expanded="true"', html)
        self.assertIn('mvh-filter-toggle is-active', html)
        self.assertNotIn('hidden', html.split('id="mvh-filter-sheet"')[1][:60])
        self.assertIn('<option value="sale" selected>', html)

    def test_product_filter_applies(self):
        resp = self.client.get(self.url(), {'product_id': self.beta.pk})
        self.assertEqual(resp.status_code, 200)
        # 20 alternating beta rows plus the extra sale row.
        self.assertEqual(resp.context['page_obj'].paginator.count, 21)
        self.assertIn('value="%d" selected' % self.beta.pk, resp.content.decode())

    def test_direction_and_date_filters_apply(self):
        resp = self.client.get(self.url(), {'direction': 'OUT'})
        self.assertEqual(resp.context['page_obj'].paginator.count, 1)

        today = datetime.date.today().isoformat()
        resp = self.client.get(self.url(), {'date_from': today, 'date_to': today})
        self.assertEqual(resp.context['page_obj'].paginator.count, 41)

    def test_search_filter_applies(self):
        resp = self.client.get(self.url(), {'q': 'Alpha'})
        self.assertEqual(resp.context['page_obj'].paginator.count, 20)
        resp = self.client.get(self.url(), {'q': 'REF-007'})
        self.assertEqual(resp.context['page_obj'].paginator.count, 1)

    def test_movement_type_options_track_the_model(self):
        html = self.client.get(self.url()).content.decode()
        for value, _label in StockMovement.MOVEMENT_TYPES:
            self.assertIn('value="%s"' % value, html)
        # Values from an older schema must not be offered: selecting one
        # silently produced an empty result set.
        for stale in ('return', 'purchase_receive', 'sale_reserve', 'initial'):
            self.assertNotIn('value="%s"' % stale, html)

    def test_malformed_product_id_does_not_500(self):
        resp = self.client.get(self.url(), {'product_id': 'not-a-number'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['page_obj'].paginator.count, 41)

    # ---------- rows ----------

    def test_null_user_and_warehouse_rows_render(self):
        StockMovement.objects.create(
            company=self.company, product=self.alpha, direction='IN',
            movement_type='correction', quantity=1, user=None, warehouse=None,
        )
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('&mdash;', resp.content.decode())

    # ---------- pagination ----------

    def test_pagination_preserves_filter_state(self):
        # 40 more alpha rows so the filtered set spans two pages (30/page).
        for _ in range(40):
            StockMovement.objects.create(
                company=self.company, product=self.alpha, direction='IN',
                movement_type='stock_in', quantity=1,
            )
        resp = self.client.get(self.url(), {'movement_type': 'stock_in', 'q': 'Alpha'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['page_obj'].has_other_pages())
        html = resp.content.decode()
        self.assertIn('mvh-pagination', html)
        self.assertIn('mvh-page-info', html)
        self.assertIn('movement_type=stock_in', html)
        self.assertIn('q=Alpha', html)

    def test_pagination_escapes_odd_search_terms(self):
        resp = self.client.get(self.url(), {'q': 'a&b=c d', 'page': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('q=a&b=c d', resp.content.decode())

    # ---------- empty state ----------

    def test_empty_state_when_nothing_matches(self):
        resp = self.client.get(self.url(), {'q': 'zzz-no-such-thing'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('class="mvh-empty"', html)
        self.assertIn('class="mvh-empty__title"', html)
        # A filtered dead end offers a way out. Match the anchor markup,
        # not the rule of the same name in the <style> block.
        self.assertIn('mvh-btn mvh-btn--ghost mvh-empty__action', html)

    def test_empty_state_without_filters_has_no_reset_link(self):
        StockMovement.objects.all().delete()
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('class="mvh-empty"', html)
        # Nothing to reset, so no reset affordance is offered.
        self.assertNotIn('mvh-btn mvh-btn--ghost mvh-empty__action', html)


class StockBucketConsistencyTests(TestCase):
    """The dashboard alert tabs must agree with the real backend query.

    `Product.stock_status` classifies out_of_stock -> low_stock ->
    overstock in that order, but every surface that *counted* or *listed* a
    bucket used to inline its own lookups, and they drifted: the overstock
    lookup was a bare `quantity__gte=max_stock` with no `min_stock` guard,
    so any product whose min_stock was >= its max_stock landed in BOTH the
    low-stock and overstock buckets and the tab totals overshot the real
    product count. These tests pin the buckets to `stock_status`.
    """

    def setUp(self):
        self.company = Company.objects.create(
            company_name='ACME', slug='acme', email='ops@acme.test',
        )
        self.other = Company.objects.create(
            company_name='OTHER', slug='other', email='ops@other.test',
        )
        self.user = User.objects.create_user(
            'op@acme.test', password='x', company=self.company,
        )
        self.user.is_staff = True
        self.user.save()
        self.client.force_login(self.user)

    def make(self, name, quantity, min_stock=5, max_stock=100, company=None):
        return Product.objects.create(
            company=company or self.company,
            name=name, sku=name.upper().replace(' ', '-'),
            price=0, quantity=quantity,
            min_stock=min_stock, max_stock=max_stock,
        )

    # ---------- buckets mirror stock_status ----------

    def test_buckets_match_stock_status_for_a_normal_product(self):
        p = self.make('Normal', quantity=50)
        self.assertEqual(p.stock_status, 'in_stock')
        self.assertFalse(Product.low_stock_qs(self.company).filter(pk=p.pk).exists())
        self.assertFalse(Product.overstock_qs(self.company).filter(pk=p.pk).exists())

    def test_inverted_thresholds_do_not_double_count(self):
        # min_stock >= max_stock is the config that used to trip the bug:
        # stock_status calls this low_stock, but the old overstock lookup
        # matched it too.
        p = self.make('Inverted', quantity=60, min_stock=100, max_stock=50)
        self.assertEqual(p.stock_status, 'low_stock')
        self.assertTrue(Product.low_stock_qs(self.company).filter(pk=p.pk).exists())
        self.assertFalse(
            Product.overstock_qs(self.company).filter(pk=p.pk).exists(),
            'a low_stock product must not also be counted as overstock',
        )

    def test_max_stock_zero_does_not_sweep_every_product(self):
        # max_stock=0 is degenerate: stock_status itself calls anything with
        # quantity > min_stock "overstock", because 40 >= 0. What matters is
        # that the buckets stay disjoint, so the old bare
        # `quantity__gte=max_stock` could not sweep the low/out-of-stock
        # products in as well and inflate the overstock total.
        low = self.make('Low', quantity=4, min_stock=5, max_stock=0)
        zero = self.make('Zero', quantity=0, min_stock=5, max_stock=0)
        healthy = self.make('Healthy', quantity=40, min_stock=5, max_stock=0)

        self.assertEqual(low.stock_status, 'low_stock')
        self.assertEqual(zero.stock_status, 'out_of_stock')
        self.assertEqual(healthy.stock_status, 'overstock')

        overstock = Product.overstock_qs(self.company)
        self.assertFalse(overstock.filter(pk=low.pk).exists())
        self.assertFalse(overstock.filter(pk=zero.pk).exists())
        self.assertTrue(overstock.filter(pk=healthy.pk).exists())
        self.assertEqual(
            overstock.count(),
            sum(
                1 for p in Product.objects.filter(company=self.company)
                if p.stock_status == 'overstock'
            ),
        )

    def test_buckets_are_mutually_exclusive_and_complete(self):
        cases = [
            ('Zero', 0, 5, 100),        # out_of_stock
            ('AtMin', 5, 5, 100),       # low_stock
            ('BelowMin', 3, 5, 100),    # low_stock
            ('Healthy', 50, 5, 100),    # in_stock
            ('AtMax', 100, 5, 100),     # overstock
            ('AboveMax', 250, 5, 100),  # overstock
            ('Inverted', 60, 100, 50),  # low_stock (not overstock)
        ]
        for name, qty, lo, hi in cases:
            self.make(name, quantity=qty, min_stock=lo, max_stock=hi)

        products = Product.objects.filter(company=self.company)
        self.assertEqual(products.count(), len(cases))
        for status in ('out_of_stock', 'low_stock', 'in_stock', 'overstock'):
            expected = {
                p.pk for p in products if p.stock_status == status
            }
            got = set(
                products.filter(
                    **Product.STOCK_BUCKET_FILTERS[status]
                ).values_list('pk', flat=True)
            )
            self.assertEqual(expected, got, 'bucket %r disagrees' % status)

        # No product may appear in two buckets, and none may fall out of
        # all of them.
        seen = set()
        for status in ('out_of_stock', 'low_stock', 'overstock'):
            pks = set(
                Product.objects.filter(company=self.company).filter(
                    **Product.STOCK_BUCKET_FILTERS[status]
                ).values_list('pk', flat=True)
            )
            self.assertFalse(seen & pks, 'product counted in two buckets')
            seen |= pks

    # ---------- dashboard tab counts ----------

    def test_dashboard_tab_counts_match_the_query(self):
        self.make('Zero', quantity=0, min_stock=5, max_stock=100)
        self.make('Low', quantity=4, min_stock=5, max_stock=100)
        self.make('Over', quantity=100, min_stock=5, max_stock=100)
        self.make('Fine', quantity=40, min_stock=5, max_stock=100)

        resp = self.client.get(reverse('inventory_overview'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['low_stock'], 1)
        self.assertEqual(resp.context['out_of_stock'], 1)
        self.assertEqual(resp.context['overstock'], 1)
        # Panel contents come from the same buckets as the counts above.
        self.assertEqual(len(resp.context['low_stock_products']), 1)
        self.assertEqual(len(resp.context['out_of_stock_products']), 1)
        self.assertEqual(len(resp.context['overstock_products']), 1)
        self.assertEqual(
            resp.context['low_stock_products'][0].name, 'Low'
        )

    def test_tab_counts_are_scoped_to_the_company(self):
        self.make('Mine', quantity=0, min_stock=5, max_stock=100)
        self.make('Theirs', quantity=0, min_stock=5, max_stock=100,
                  company=self.other)
        resp = self.client.get(reverse('inventory_overview'))
        self.assertEqual(resp.context['out_of_stock'], 1)
        self.assertEqual(Product.out_of_stock_qs().count(), 2)

    # ---------- stat cards ----------

    def test_duplicate_low_stock_stat_card_is_gone(self):
        self.make('Low', quantity=4, min_stock=5, max_stock=100)
        html = self.client.get(reverse('inventory_overview')).content.decode()
        # The KAM QOLGAN tab is the only place this number should appear.
        self.assertNotIn('products_low_stock_count', html)
        self.assertIn('daw-tab__count', html)

    def test_remaining_stat_cards_are_not_hardcoded_zero(self):
        # These three cards read `total_products_count` / `total_stock_qty`
        # / `total_inventory_value`, none of which the view ever supplied,
        # so each one fell through `|default:"0"` and rendered 0.
        self.make('Fine', quantity=40, min_stock=5, max_stock=100)
        resp = self.client.get(reverse('inventory_overview'))
        self.assertEqual(resp.context['total_products'], 1)
        self.assertEqual(resp.context['total_units'], 40)
        self.assertEqual(resp.context['total_value'], 0)
        html = resp.content.decode()
        for stale in ('{{ total_products_count|', '{{ total_stock_qty|',
                      '{{ total_inventory_value|'):
            self.assertNotIn(stale, html)

    # ---------- list views agree with the tabs ----------

    def test_list_views_use_the_same_buckets_as_the_tabs(self):
        self.make('Zero', quantity=0, min_stock=5, max_stock=100)
        self.make('Low', quantity=4, min_stock=5, max_stock=100)
        self.make('Over', quantity=100, min_stock=5, max_stock=100)
        self.make('Inverted', quantity=60, min_stock=100, max_stock=50)

        expected = {
            'low_stock_list': ['Inverted', 'Low'],
            'out_of_stock_list': ['Zero'],
            'overstock_list': ['Over'],
        }
        for url_name, names in expected.items():
            with self.subTest(view=url_name):
                resp = self.client.get(reverse(url_name))
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.context['total_count'], len(names))
                self.assertEqual(
                    sorted(p.name for p in resp.context['page_obj']),
                    sorted(names),
                )

    # ---------- mobile bottom clearance ----------

    def test_mobile_bottom_padding_is_applied(self):
        # The lowest replenish button sat under the mobile Safari URL bar.
        html = self.client.get(reverse('inventory_overview')).content.decode()
        self.assertIn('@media(max-width:767px)', html)
        self.assertIn('#main-content{padding-bottom:', html)
        self.assertIn('var(--sp-20)', html)
        self.assertIn('env(safe-area-inset-bottom', html)


class AdjustmentListRenderTests(TestCase):
    """The redesigned adjustment list must keep its desktop table, its
    mobile card fallback and its empty state in sync with the view."""

    def setUp(self):
        self.company = Company.objects.create(
            company_name='Adjust Co', slug='adjust-co',
            email='ops@adjust.test',
        )
        self.other_company = Company.objects.create(
            company_name='Other Co', slug='other-co',
            email='ops@other.test',
        )
        self.user = User.objects.create_user(
            'op@adjust.test', password='x', company=self.company,
        )
        self.user.first_name = 'Ali'
        self.user.last_name = 'Valiyev'
        self.user.save()
        self.client.force_login(self.user)

        self.warehouse = Warehouse.objects.create(
            company=self.company, name='Markaziy ombor', code='MAIN',
        )
        self.other_warehouse = Warehouse.objects.create(
            company=self.other_company, name='Begona ombor', code='OTHER',
        )

    def url(self):
        return reverse('adjustment_list')

    def test_empty_state_renders_inside_the_glass_card(self):
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('adj-card', html)
        self.assertIn('adj-empty', html)
        self.assertIn('adj-empty__icon', html)
        self.assertEqual(resp.context['page_obj'].paginator.count, 0)
        self.assertNotIn('<table', html)
        self.assertIn('linear-gradient(to right, #4f46e5, #7c3aed)', html)

    def test_populated_list_renders_table_and_mobile_cards(self):
        StockAdjustment.objects.create(
            company=self.company, warehouse=self.warehouse,
            status=StockAdjustment.STATUS_PENDING,
            reason='Inventarizatsiya natijasi', created_by=self.user,
        )
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('ADJ-0001', html)
        self.assertIn('Markaziy ombor', html)
        self.assertIn('Inventarizatsiya natijasi', html)
        self.assertIn('adj-table', html)
        self.assertIn('adj-cards', html)
        self.assertIn('adj-mcard', html)
        self.assertIn('Ali Valiyev', html)

    def test_adjustments_are_scoped_to_the_current_company(self):
        StockAdjustment.objects.create(
            company=self.company, warehouse=self.warehouse,
            reference='ADJ-MINE', status=StockAdjustment.STATUS_DRAFT,
            reason='Mine', created_by=self.user,
        )
        StockAdjustment.objects.create(
            company=self.other_company, warehouse=self.other_warehouse,
            reference='ADJ-THEIRS', status=StockAdjustment.STATUS_DRAFT,
            reason='Theirs', created_by=self.user,
        )
        resp = self.client.get(self.url())
        self.assertEqual(resp.context['page_obj'].paginator.count, 1)
        self.assertIn('Mine', resp.content.decode())
        self.assertNotIn('Theirs', resp.content.decode())


class AdjustmentFormRenderTests(TestCase):
    """The create-adjustment form must keep its glass cards, responsive
    action stack and tenant-scoped warehouse choices."""

    def setUp(self):
        self.company = Company.objects.create(
            company_name='Form Co', slug='form-co',
            email='ops@form.test',
        )
        self.other_company = Company.objects.create(
            company_name='Form Other Co', slug='form-other-co',
            email='ops@form-other.test',
        )
        self.user = User.objects.create_user(
            'form@form.test', password='x', company=self.company,
        )
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(
            company=self.company, name='Markaziy ombor', code='FORM-MAIN',
        )
        self.other_warehouse = Warehouse.objects.create(
            company=self.other_company, name='Begona ombor', code='FORM-OTHER',
        )

    def url(self):
        return reverse('adjustment_create')

    def test_form_renders_glass_cards_and_responsive_actions(self):
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('adjf-head', html)
        self.assertIn('adjf-card', html)
        self.assertIn('adjf-form', html)
        self.assertIn('adjf-actions', html)
        self.assertIn('adjf-btn--primary', html)
        self.assertIn('adjf-btn--secondary', html)
        self.assertIn('flex-direction: column-reverse', html)
        self.assertIn('max-width: 768px', html)
        self.assertIn('backdrop-filter: blur(24px)', html)
        self.assertIn('linear-gradient(to right, #4f46e5, #7c3aed)', html)
        self.assertIn('name="warehouse"', html)
        self.assertIn('name="reason"', html)
        self.assertIn('name="notes"', html)
        self.assertIn('Markaziy ombor', html)
        self.assertNotIn('Begona ombor', html)

    def test_invalid_submission_marks_the_field(self):
        resp = self.client.post(self.url(), {'warehouse': '', 'reason': '', 'notes': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('adjf-field--error', resp.content.decode())
        self.assertEqual(StockAdjustment.objects.count(), 0)

    def test_valid_submission_creates_company_adjustment(self):
        resp = self.client.post(self.url(), {
            'warehouse': self.warehouse.pk,
            'reason': 'Inventarizatsiya kamligi',
            'notes': 'Kunlik tekshiruv',
        })
        adjustment = StockAdjustment.objects.get()
        self.assertEqual(adjustment.company, self.company)
        self.assertEqual(adjustment.created_by, self.user)
        self.assertEqual(adjustment.reason, 'Inventarizatsiya kamligi')
        self.assertRedirects(resp, reverse('adjustment_detail', args=[adjustment.pk]))

    def test_other_company_warehouse_cannot_be_submitted(self):
        resp = self.client.post(self.url(), {
            'warehouse': self.other_warehouse.pk,
            'reason': 'Cross tenant',
            'notes': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(StockAdjustment.objects.count(), 0)


class InventoryTablePolishTests(TestCase):
    """Guards the glass-shell markup and status pills of the inventory table.

    The redesign is scoped CSS, so these assertions cover the class hooks the
    stylesheet depends on plus the formatted price that must keep the Uzbek
    space-separated thousands notation.
    """

    def setUp(self):
        self.company = Company.objects.create(
            company_name='Table Co', slug='table-co', email='table@acme.test',
        )
        self.user = User.objects.create_user(
            'table@acme.test', password='x', company=self.company,
        )
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            company=self.company, name='Stol', sku='TBL-001',
            price='50000', quantity=30, min_stock=5, max_stock=1000,
        )

    def url(self):
        return reverse('inventory_table')

    def test_renders_glass_shell_status_dot_and_formatted_price(self):
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('invt-header', html)
        self.assertIn('invt-table-card', html)
        self.assertIn('invt-status__dot', html)
        self.assertIn('invt-action', html)
        self.assertIn('invt-col--num', html)
        self.assertIn("50 000 so'm", html)
        self.assertIn('invt-status--success', html)

    def test_low_stock_uses_warning_pill(self):
        self.product.quantity = 3
        self.product.save(update_fields=['quantity'])
        resp = self.client.get(self.url())
        self.assertIn('invt-status--warning', resp.content.decode())
