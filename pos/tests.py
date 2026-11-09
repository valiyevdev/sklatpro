from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import POSTerminal, CashShift, POSReceipt, POSReceiptItem, POSReturn
from sales.models import Customer, Sale, SalePayment, Debt, DebtPayment
from products.models import Product, Unit
from warehouses.models import Warehouse
from users.models import Company
from inventory.models import StockLevel
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class POSTerminalModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company_name='Test Company',
            slug='test-company',
            subscription_plan='basic',
            currency='UZS',
            theme='light',
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            name='Main Warehouse',
            code='WH001',
            warehouse_type='retail',
        )
        self.terminal = POSTerminal.objects.create(
            company=self.company,
            warehouse=self.warehouse,
            name='Terminal 1',
            code='T001',
            serial_number='SN123456',
        )

    def test_terminal_creation(self):
        self.assertEqual(self.terminal.name, 'Terminal 1')
        self.assertEqual(self.terminal.code, 'T001')
        self.assertEqual(self.terminal.status, 'active')

    def test_terminal_str(self):
        self.assertEqual(str(self.terminal), 'Terminal 1 (T001)')

    def test_terminal_to_dict(self):
        data = self.terminal.to_dict()
        self.assertEqual(data['id'], self.terminal.pk)
        self.assertEqual(data['name'], 'Terminal 1')
        self.assertEqual(data['code'], 'T001')


class CashShiftModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company_name='Test Company',
            slug='test-company',
            subscription_plan='basic',
            currency='UZS',
            theme='light',
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            name='Main Warehouse',
            code='WH001',
            warehouse_type='retail',
        )
        self.terminal = POSTerminal.objects.create(
            company=self.company,
            warehouse=self.warehouse,
            name='Terminal 1',
            code='T001',
        )
        self.user = User.objects.create_user(
            email='cashier@test.com',
            password='testpass123',
            company=self.company,
        )
        self.shift = CashShift.objects.create(
            company=self.company,
            terminal=self.terminal,
            cashier=self.user,
            shift_number='SHIFT-0001',
            opening_amount=Decimal('100000'),
            created_by=self.user,
        )

    def test_shift_creation(self):
        self.assertEqual(self.shift.shift_number, 'SHIFT-0001')
        self.assertEqual(self.shift.status, 'open')
        self.assertEqual(self.shift.opening_amount, Decimal('100000'))

    def test_shift_close(self):
        self.shift.close_shift(Decimal('500000'), Decimal('500000'))
        self.assertEqual(self.shift.status, 'closed')
        self.assertEqual(self.shift.closing_amount, Decimal('500000'))
        self.assertEqual(self.shift.difference, Decimal('0'))


class POSReceiptModelTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company_name='Test Company',
            slug='test-company',
            subscription_plan='basic',
            currency='UZS',
            theme='light',
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company,
            name='Main Warehouse',
            code='WH001',
            warehouse_type='retail',
        )
        self.terminal = POSTerminal.objects.create(
            company=self.company,
            warehouse=self.warehouse,
            name='Terminal 1',
            code='T001',
        )
        self.user = User.objects.create_user(
            email='cashier@test.com',
            password='testpass123',
            company=self.company,
        )
        self.shift = CashShift.objects.create(
            company=self.company,
            terminal=self.terminal,
            cashier=self.user,
            shift_number='SHIFT-0001',
            opening_amount=Decimal('100000'),
            created_by=self.user,
        )
        self.unit = Unit.objects.create(
            name='Piece',
            symbol='dona',
        )
        self.product = Product.objects.create(
            company=self.company,
            name='Test Product',
            sku='TEST001',
            barcode='123456789',
            price=Decimal('10000'),
            purchase_price=Decimal('8000'),
            unit=self.unit,
            quantity=100,
        )
        self.receipt = POSReceipt.objects.create(
            company=self.company,
            terminal=self.terminal,
            shift=self.shift,
            receipt_number='POS-000001',
            warehouse=self.warehouse,
            created_by=self.user,
        )

    def test_receipt_creation(self):
        self.assertEqual(self.receipt.receipt_number, 'POS-000001')
        self.assertEqual(self.receipt.status, 'draft')

    def test_receipt_item_creation(self):
        item = POSReceiptItem.objects.create(
            receipt=self.receipt,
            product=self.product,
            quantity=Decimal('2'),
            unit_price=Decimal('10000'),
        )
        self.assertEqual(item.line_total, Decimal('20000'))

    def test_receipt_calculate_total(self):
        POSReceiptItem.objects.create(
            receipt=self.receipt,
            product=self.product,
            quantity=Decimal('2'),
            unit_price=Decimal('10000'),
        )
        self.receipt.calculate_total()
        self.assertEqual(self.receipt.subtotal, Decimal('20000'))
        self.assertEqual(self.receipt.total, Decimal('20000'))

    def test_receipt_complete(self):
        POSReceiptItem.objects.create(
            receipt=self.receipt,
            product=self.product,
            quantity=Decimal('1'),
            unit_price=Decimal('10000'),
        )
        self.receipt.calculate_total()
        self.receipt.complete('cash', Decimal('10000'))
        self.assertEqual(self.receipt.status, 'completed')
        self.assertEqual(self.receipt.payment_method, 'cash')
        self.assertEqual(self.receipt.change, Decimal('0'))


class POSWorkspaceFlowTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            company_name='Workspace Company', slug='workspace-company',
            subscription_plan='basic', currency='UZS', theme='light',
        )
        self.warehouse = Warehouse.objects.create(
            company=self.company, name='POS Warehouse', code='POS-WH', warehouse_type='retail'
        )
        self.terminal = POSTerminal.objects.create(
            company=self.company, warehouse=self.warehouse, name='POS', code='POS-01'
        )
        self.user = User.objects.create_user(
            email='workspace@test.com', password='testpass123', company=self.company, role='MANAGER'
        )
        self.shift = CashShift.objects.create(
            company=self.company, terminal=self.terminal, cashier=self.user,
            shift_number='SH-TEST', created_by=self.user,
        )
        self.product = Product.objects.create(
            company=self.company, name='Cable', sku='CBL-01', barcode='789',
            price=Decimal('10000'), purchase_price=Decimal('7000'), quantity=5,
        )
        StockLevel.objects.create(
            company=self.company, product=self.product, warehouse=self.warehouse, quantity=5
        )
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['pos_terminal_id'] = self.terminal.pk
        session.save()

    def test_workspace_search_and_manual_add(self):
        response = self.client.get('/pos/workspace/', {'terminal': self.terminal.pk})
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/pos/api/search/', {'q': 'cable'})
        self.assertEqual(response.json()['products'][0]['id'], self.product.pk)
        response = self.client.post(
            '/pos/api/cart/add/',
            data='{"product_id": %d, "quantity": 2}' % self.product.pk,
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['cart']['items'][0]['quantity'], '2')

    def test_product_create_syncs_stock_level_and_pos_catalog(self):
        response = self.client.post(
            '/pos/api/product/create/',
            data='{"name":"POS New","sku":"POS-NEW","barcode":"9988",'
                 '"price":"50000","purchase_price":"30000","stock":"7",'
                 '"min_stock":"2"}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        product = Product.objects.get(sku='POS-NEW')
        level = StockLevel.objects.get(product=product, warehouse=self.warehouse)
        self.assertEqual(product.quantity, 7)
        self.assertEqual(level.quantity, 7)

        catalog = self.client.get('/pos/api/search/', {'q': 'POS-NEW'}).json()
        self.assertEqual(catalog['products'][0]['name'], 'POS New')
        self.assertEqual(catalog['products'][0]['sku'], 'POS-NEW')
        self.assertEqual(catalog['products'][0]['barcode'], '9988')
        self.assertEqual(catalog['products'][0]['price'], '50000.00')
        self.assertEqual(catalog['products'][0]['available'], 7.0)

    def test_legacy_positive_product_quantity_is_visible_in_pos(self):
        product = Product.objects.create(
            company=self.company, name='Legacy Stock', sku='LEGACY-01',
            price=Decimal('12000'), purchase_price=Decimal('9000'), quantity=6,
        )
        catalog = self.client.get('/pos/api/search/', {'q': product.sku}).json()
        self.assertEqual(catalog['products'][0]['available'], 6.0)

    def test_receipt_list_loads_for_cashier(self):
        response = self.client.get('/pos/receipts/')
        self.assertEqual(response.status_code, 200)

    def test_cart_rejects_quantity_above_stock(self):
        response = self.client.post(
            '/pos/api/cart/add/',
            data='{"product_id": %d, "quantity": 6}' % self.product.pk,
            content_type='application/json',
        )
        self.assertFalse(response.json()['success'])
        self.assertEqual(response.status_code, 400)

    def test_quick_create_does_not_add_stock(self):
        response = self.client.post(
            '/pos/api/product/create/',
            data='{"name":"New item","sku":"NEW-01","price":"2500"}',
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        self.assertEqual(Product.objects.get(sku='NEW-01').quantity, 0)

    def test_catalog_search_includes_stock_threshold_and_pagination(self):
        response = self.client.get('/pos/api/search/', {'q': 'cable', 'page': 1})
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['products'][0]['min_stock'], self.product.min_stock)
        self.assertIn('has_more', data)

    def test_quick_item_can_be_added_to_catalog_stock(self):
        response = self.client.post(
            '/pos/api/product/quick/',
            data='{"name":"Paket","price":"1500","quantity":"3","save_to_catalog":true}',
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        product = Product.objects.get(pk=response.json()['product']['id'])
        self.assertEqual(product.quantity, 3)
        self.assertEqual(product.price, Decimal('1500'))

    def test_csv_import_reports_and_creates_products(self):
        csv_data = b'name,sell_price,buy_price,stock,min_stock,category,sku,barcode\nMarker,8500,5000,4,2,Stationery,CSV-001,99890001\n'
        response = self.client.post('/pos/api/product/import/', {'file': SimpleUploadedFile('products.csv', csv_data, content_type='text/csv')})
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['created'], 1)
        self.assertTrue(Product.objects.filter(sku='CSV-001').exists())

    def test_debt_payment_reduces_customer_balance(self):
        customer = Customer.objects.create(company=self.company, name='Ali Valiyev', phone='+998901112233')
        sale = Sale.objects.create(
            company=self.company, reference='POS-DEBT-01', customer=customer,
            warehouse=self.warehouse, total=Decimal('120000'),
            payment_status='unpaid', payment_terms='credit', status='completed',
            created_by=self.user,
        )
        response = self.client.post(
            '/pos/api/debt/payment/',
            data='{"sale_id": %d, "amount": "50000", "method": "cash"}' % sale.pk,
            content_type='application/json',
        )
        self.assertTrue(response.json()['success'])
        sale.refresh_from_db()
        self.assertEqual(sale.payment_status, 'partial')
        self.assertEqual(response.json()['remaining'], '70000.00')

    def _cart_for_sale(self, quantity='1'):
        response = self.client.post('/pos/api/cart/add/', data='{"product_id": %d, "quantity": "%s"}' % (self.product.pk, quantity), content_type='application/json')
        self.assertTrue(response.json()['success'])

    def test_create_sale_cash_decreases_stock(self):
        self._cart_for_sale()
        response = self.client.post('/pos/api/create-sale/', data='{"terminal_id": %d, "shift_id": %d, "payment_method":"cash", "amount_paid":"10000", "payments":[{"method":"cash","amount":"10000"}], "idempotency_key":"cash-test-1"}' % (self.terminal.pk, self.shift.pk), content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['sale_id'], Sale.objects.get(idempotency_key='cash-test-1').pk)
        self.product.refresh_from_db()
        self.assertEqual(StockLevel.objects.get(product=self.product, warehouse=self.warehouse).quantity, Decimal('4'))
        self.assertEqual(SalePayment.objects.filter(sale__idempotency_key='cash-test-1').count(), 1)

    def test_create_sale_split_payment(self):
        self._cart_for_sale()
        response = self.client.post('/pos/api/create-sale/', data='{"terminal_id": %d, "shift_id": %d, "payment_method":"cash", "amount_paid":"10000", "payments":[{"method":"cash","amount":"4000"},{"method":"card","amount":"6000"}], "idempotency_key":"split-test-1"}' % (self.terminal.pk, self.shift.pk), content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.assertEqual(SalePayment.objects.filter(sale__idempotency_key='split-test-1').count(), 2)

    def test_create_sale_rounds_money_to_two_decimals(self):
        self.product.price = Decimal('999')
        self.product.save(update_fields=['price'])
        self._cart_for_sale('1.333')
        response = self.client.post('/pos/api/create-sale/', data='{"terminal_id": %d, "shift_id": %d, "payment_method":"cash", "amount_paid":"1332", "payments":[{"method":"cash","amount":"1332"}], "idempotency_key":"rounding-test-1"}' % (self.terminal.pk, self.shift.pk), content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.assertEqual(Sale.objects.get(idempotency_key='rounding-test-1').total, Decimal('1331.67'))

    def test_create_sale_rejects_insufficient_stock_and_duplicate(self):
        response = self.client.post('/pos/api/cart/add/', data='{"product_id": %d, "quantity": "6"}' % self.product.pk, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self._cart_for_sale()
        payload = '{"terminal_id": %d, "shift_id": %d, "payment_method":"cash", "amount_paid":"10000", "payments":[{"method":"cash","amount":"10000"}], "idempotency_key":"duplicate-test-1"}' % (self.terminal.pk, self.shift.pk)
        first = self.client.post('/pos/api/create-sale/', data=payload, content_type='application/json')
        second = self.client.post('/pos/api/create-sale/', data=payload, content_type='application/json')
        self.assertTrue(first.json()['success'])
        self.assertTrue(second.json()['success'])
        self.assertTrue(second.json()['duplicate'])
        self.assertEqual(Sale.objects.filter(idempotency_key='duplicate-test-1').count(), 1)

    def _credit_sale(self, customer, amount_paid='0', key='credit-test'):
        self._cart_for_sale()
        self.client.post('/pos/api/cart/customer/', data='{"customer_id": %d}' % customer.pk, content_type='application/json')
        return self.client.post('/pos/api/create-sale/', data='{"terminal_id": %d, "shift_id": %d, "credit_sale": true, "due_date": "%s", "amount_paid": "%s", "payments": %s, "idempotency_key":"%s"}' % (self.terminal.pk, self.shift.pk, (timezone.localdate() + timedelta(days=7)).isoformat(), amount_paid, ('[{"method":"cash","amount":"%s"}]' % amount_paid) if Decimal(amount_paid) else '[]', key), content_type='application/json')

    def test_credit_sale_creates_debt_and_partial_payment(self):
        customer = Customer.objects.create(company=self.company, name='Credit Customer', phone='99890')
        response = self._credit_sale(customer, '2000', 'credit-partial-1')
        self.assertTrue(response.json()['success'])
        debt = Debt.objects.get(sale_id=response.json()['sale_id'])
        self.assertEqual(debt.paid, Decimal('2000'))
        payment = self.client.post('/pos/api/debt/payment/', data='{"debt_id": %d, "amount":"3000", "method":"cash"}' % debt.pk, content_type='application/json')
        self.assertTrue(payment.json()['success'])
        debt.refresh_from_db()
        self.assertEqual(debt.remaining, Decimal('5000'))
        self.assertEqual(DebtPayment.objects.filter(debt=debt).count(), 2)

    def test_debt_payment_rejects_overpayment_and_marks_overdue(self):
        customer = Customer.objects.create(company=self.company, name='Overdue Customer')
        sale = Sale.objects.create(company=self.company, reference='OVERDUE-1', customer=customer, warehouse=self.warehouse, total=Decimal('10000'), payment_status='unpaid', payment_terms='credit', status='completed', created_by=self.user)
        debt = Debt.objects.create(company=self.company, sale=sale, customer=customer, total=Decimal('10000'), due_date=timezone.localdate() - timedelta(days=1), created_by=self.user)
        debt.refresh_status()
        self.assertEqual(debt.status, 'overdue')
        response = self.client.post('/pos/api/debt/payment/', data='{"debt_id": %d, "amount":"10001", "method":"cash"}' % debt.pk, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_credit_limit_rejects_excess_credit(self):
        customer = Customer.objects.create(company=self.company, name='Limited Customer', credit_limit=Decimal('5000'))
        response = self._credit_sale(customer, '0', 'credit-limit-1')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Kredit limiti', response.json()['error'])

    def test_debt_ledger_and_customer_profile_render(self):
        customer = Customer.objects.create(company=self.company, name='Ledger Customer', phone='998901234567')
        sale = Sale.objects.create(company=self.company, reference='LEDGER-1', customer=customer, warehouse=self.warehouse, total=Decimal('10000'), payment_status='unpaid', payment_terms='credit', status='completed', created_by=self.user)
        Debt.objects.create(company=self.company, sale=sale, customer=customer, total=Decimal('10000'), due_date=timezone.localdate() + timedelta(days=7), created_by=self.user)
        ledger = self.client.get('/pos/nasiya-daftari/')
        profile = self.client.get('/pos/nasiya-daftari/mijoz/%d/' % customer.pk)
        self.assertEqual(ledger.status_code, 200)
        self.assertEqual(profile.status_code, 200)
        self.assertContains(ledger, 'Ledger Customer')
        self.assertContains(profile, 'Ledger Customer')

    def test_shift_summary_expense_and_close_report(self):
        opened = self.client.post('/pos/api/shift/open/', data='{"terminal_id": %d, "opening_amount":"50000", "notes":"Tonggi smena"}' % self.terminal.pk, content_type='application/json')
        self.assertTrue(opened.json()['success'])
        shift_id = opened.json()['shift_id']
        expense = self.client.post('/pos/api/shift/expense/', data='{"shift_id": %d, "category":"Transport", "amount":"5000", "note":"Yetkazib berish"}' % shift_id, content_type='application/json')
        self.assertTrue(expense.json()['success'])
        summary = self.client.get('/pos/api/shift/summary/', {'shift_id': shift_id})
        self.assertEqual(Decimal(summary.json()['expenses']), Decimal('5000'))
        closed = self.client.post('/pos/api/shift/close/', data='{"shift_id": %d, "closing_amount":"45000"}' % shift_id, content_type='application/json')
        self.assertTrue(closed.json()['success'])
        self.assertEqual(Decimal(closed.json()['expected']), Decimal('45000'))

    def test_low_stock_api_and_csv_export(self):
        response = self.client.get('/pos/api/low-stock/')
        self.assertTrue(response.json()['success'])
        self.assertTrue(any(item['id'] == self.product.pk for item in response.json()['products']))
        export = self.client.get('/pos/api/low-stock/export/')
        self.assertEqual(export.status_code, 200)
        self.assertIn('buyurtma-royxati.csv', export['Content-Disposition'])

    def test_owner_fast_stock_in_creates_movement_and_increases_stock(self):
        response = self.client.post('/pos/api/stock-in/', data='{"product_id": %d, "quantity":"20", "buy_price":"7500"}' % self.product.pk, content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.assertEqual(StockLevel.objects.get(product=self.product, warehouse=self.warehouse).quantity, Decimal('25'))
        self.assertTrue(self.product.stock_movements.filter(movement_type='purchase', quantity=20).exists())

    def test_owner_partial_return_restores_stock_and_cash_refund(self):
        self._cart_for_sale('2')
        checkout = self.client.post('/pos/api/create-sale/', data='{"terminal_id": %d, "shift_id": %d, "payment_method":"cash", "amount_paid":"20000", "payments":[{"method":"cash","amount":"20000"}], "idempotency_key":"return-sale-1"}' % (self.terminal.pk, self.shift.pk), content_type='application/json')
        self.assertTrue(checkout.json()['success'])
        receipt = POSReceipt.objects.get(pk=checkout.json()['receipt_id'])
        owner = User.objects.create_user(email='owner@test.com', password='testpass123', company=self.company, role='COMPANY_ADMIN')
        self.client.force_login(owner)
        response = self.client.post('/pos/api/return/', data='{"receipt_id": %d, "items":[{"receipt_item_id":%d,"quantity":"1"}], "refund_method":"cash"}' % (receipt.pk, receipt.items.first().pk), content_type='application/json')
        self.assertTrue(response.json()['success'])
        self.assertEqual(POSReturn.objects.count(), 1)
        self.assertEqual(StockLevel.objects.get(product=self.product, warehouse=self.warehouse).quantity, Decimal('4'))

    def test_cashier_cannot_cancel_return_or_change_price(self):
        self.user.role = 'STAFF'
        self.user.save(update_fields=['role'])
        self.client.force_login(self.user)
        self._cart_for_sale()
        price = self.client.post('/pos/api/cart/update/', data='{"key":"%d_", "quantity":"1", "custom_price":"1"}' % self.product.pk, content_type='application/json')
        self.assertEqual(price.status_code, 403)
        receipt = POSReceipt.objects.create(company=self.company, terminal=self.terminal, shift=self.shift, receipt_number='ROLE-1', warehouse=self.warehouse, created_by=self.user, status='completed')
        cancel = self.client.post('/pos/receipts/%d/cancel/' % receipt.pk)
        self.assertEqual(cancel.status_code, 403)
        ret = self.client.post('/pos/api/return/', data='{"receipt_id":%d,"items":[]}' % receipt.pk, content_type='application/json')
        self.assertEqual(ret.status_code, 403)

    def test_cashier_search_does_not_receive_purchase_price(self):
        self.user.role = 'STAFF'
        self.user.save(update_fields=['role'])
        self.client.force_login(self.user)
        response = self.client.get('/pos/api/search/', {'q': 'cable'})
        self.assertIsNone(response.json()['products'][0]['purchase_price'])
