from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import *  # noqa: F401,F403 - keep app model import surface stable
from products.models import Product, Unit
from users.models import Company

User = get_user_model()


class ScannerResultsTests(TestCase):
    """Cover the mobile-first result card on the scanner results page.

    The `{% empty %}` branch this page used to carry lived inside
    <tbody>, so hiding the table below `md` also hid the "no results"
    message. These tests pin the card/table split and the shared empty
    state so that regression cannot come back.
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

        self.pcs = Unit.objects.create(name='Dona', symbol='dona')

    def make(self, name, sku, quantity, min_stock=0, max_stock=100, unit=True):
        return Product.objects.create(
            company=self.company,
            name=name,
            sku=sku,
            price=1000,
            quantity=quantity,
            min_stock=min_stock,
            max_stock=max_stock,
            unit=self.pcs if unit else None,
        )

    def url(self):
        return reverse('scanner:scanner_search')

    # ---------- card layout ----------

    def test_renders_card_and_table_for_a_match(self):
        self.make('Arabica', 'ARABICA3170', 0)
        resp = self.client.get(self.url(), {'q': 'Arabica'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_count'], 1)
        html = resp.content.decode()
        # Card list is present...
        self.assertIn('class="sres-cards"', html)
        self.assertIn('sres-card__name', html)
        self.assertIn('Arabica', html)
        self.assertIn('ARABICA3170', html)
        # ...and so is the desktop table, hidden by CSS below `md`.
        self.assertIn('class="sres-table"', html)
        self.assertIn('table-pro', html)

    def test_table_is_hidden_below_the_md_breakpoint(self):
        self.make('Arabica', 'ARABICA3170', 0)
        html = self.client.get(self.url(), {'q': 'Arabica'}).content.decode()
        # The `md` breakpoint of the design spec is 768px; the table must
        # be display:none at or under 767px and the cards hidden from 768px.
        self.assertIn('@media (max-width: 767px)', html)
        self.assertIn('@media (min-width: 768px)', html)

    def test_card_encodes_each_stock_state(self):
        self.make('OutItem', 'OUT-1', 0)
        self.make('LowItem', 'LOW-1', 2, min_stock=5)
        self.make('GoodItem', 'GOOD-1', 50)
        self.make('OverItem', 'OVER-1', 500)
        html = self.client.get(self.url(), {'q': 'Item'}).content.decode()
        for state in ('out_of_stock', 'low_stock', 'in_stock', 'overstock'):
            # Card modifier, status text colour and the left-edge accent
            # are all present, so the state never relies on hue alone.
            self.assertIn('class="sres-card sres-card--%s"' % state, html)
            self.assertIn('sres-card__status--%s' % state, html)
            self.assertIn('.sres-card--%s' % state, html)

    def test_stock_count_and_unit_render(self):
        self.make('Arabica', 'ARABICA3170', 7)
        html = self.client.get(self.url(), {'q': 'Arabica'}).content.decode()
        self.assertIn('sres-card__status--in_stock', html)
        self.assertIn('>7', html)
        self.assertIn('dona', html)

    def test_product_without_unit_does_not_crash(self):
        # `unit` is a nullable FK; a chained lookup on NULL raises inside
        # the template engine, so the card must guard it.
        self.make('NoUnit', 'NOUNIT-1', 3, unit=False)
        resp = self.client.get(self.url(), {'q': 'NoUnit'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('NoUnit', resp.content.decode())

    def test_card_action_links_to_product_detail(self):
        p = self.make('Arabica', 'ARABICA3170', 0)
        html = self.client.get(self.url(), {'q': 'Arabica'}).content.decode()
        self.assertIn(reverse('product_detail', args=[p.pk]), html)
        self.assertIn('sres-card__go', html)

    # ---------- empty state ----------

    def test_no_match_shows_empty_state_outside_the_table(self):
        resp = self.client.get(self.url(), {'q': 'zzz-nothing'})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Empty state must be its own block, not a <tbody> branch, so it
        # still shows on phones where the table is hidden. Match the
        # markup, not the identically-named rules in the <style> block.
        self.assertIn('class="empty-state sres-empty"', html)
        self.assertNotIn('<table', html)
        self.assertNotIn('<h4 class="sres-card__name">', html)
        # No result count badge when there is nothing to count.
        self.assertNotIn('class="badge-pro sres-head__badge"', html)

    def test_empty_query_shows_empty_state(self):
        resp = self.client.get(self.url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn('class="empty-state sres-empty"', resp.content.decode())
        self.assertEqual(resp.context['total_count'], 0)

    def test_empty_state_offers_a_way_back_to_the_scanner(self):
        html = self.client.get(self.url(), {'q': 'zzz'}).content.decode()
        self.assertIn(reverse('scanner:scanner_view'), html)
