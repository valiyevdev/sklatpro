from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from users.models import Company
from products.models import Product, Category

User = get_user_model()

class ProductCardRedesignTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(company_name='Test Company', email='company@test.local')
        self.user = User.objects.create_user(
            email='tester@sklat.local',
            password='testpassword123',
            company=self.company,
            role='admin'
        )
        self.client.force_login(self.user)
        self.category = Category.objects.create(name='Kantselyariya', company=self.company)
        self.product = Product.objects.create(
            company=self.company,
            name='Test Daftar',
            sku='DAFTAR-001',
            barcode='998900000001',
            price=Decimal('15000'),
            purchase_price=Decimal('10000'),
            quantity=25,
            category_fk=self.category,
            status='active'
        )

    def test_product_list_page_renders_card_redesign(self):
        url = reverse('product_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')
        # Verify card structure
        self.assertIn('class="product-card"', content)
        self.assertIn('class="product-card-top"', content)
        self.assertIn('class="product-menu-wrap"', content)
        self.assertIn('class="product-menu-trigger"', content)
        self.assertIn('class="product-dropdown"', content)

        # Verify all 5 actions exist in dropdown
        self.assertIn(reverse('product_update', kwargs={'pk': self.product.pk}), content)
        self.assertIn('Tahrirlash', content)

        self.assertIn(reverse('product_duplicate', kwargs={'pk': self.product.pk}), content)
        self.assertIn('Nusxa ko\'chirish', content)

        self.assertIn(reverse('product_barcode', kwargs={'pk': self.product.pk}), content)
        self.assertIn('Barcode', content)

        self.assertIn(reverse('product_qrcode', kwargs={'pk': self.product.pk}), content)
        self.assertIn('QR kod', content)

        self.assertIn(reverse('product_delete', kwargs={'pk': self.product.pk}), content)
        self.assertIn('O\'chirish', content)

        # Verify old cluttered bottom actions are removed
        self.assertNotIn('class="product-card-actions"', content)
        self.assertNotIn('class="product-tools"', content)

    def test_product_duplicate_action(self):
        url = reverse('product_duplicate', kwargs={'pk': self.product.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        # Verify duplicated product exists
        copies = Product.objects.filter(company=self.company, name__contains='Copy')
        self.assertEqual(copies.count(), 1)
        copy_prod = copies.first()
        self.assertEqual(copy_prod.price, self.product.price)
        self.assertEqual(copy_prod.quantity, 0)
