from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from inventory.models import StockLevel
from pos.models import CashShift, POSTerminal
from products.models import Category, Product, Unit
from sales.models import Customer
from users.models import Company, User
from warehouses.models import Warehouse


class Command(BaseCommand):
    help = 'Seed a small Uzbek retail shop with demo POS data.'

    PRODUCTS = [
        ('Guruch Oq 1 kg', 'Grocery', 24000, 18500, 32, 8),
        ('Shakar 1 kg', 'Grocery', 14500, 11000, 45, 10),
        ('Un Oliy 1 kg', 'Grocery', 11500, 8500, 28, 8),
        ('Makaron 500 g', 'Grocery', 9000, 6500, 40, 10),
        ('Yog\' 1 litr', 'Grocery', 21000, 16500, 22, 6),
        ('Choy qora 100 g', 'Grocery', 17000, 12500, 18, 5),
        ('Tuz 1 kg', 'Grocery', 4000, 2800, 36, 8),
        ('Konserva no\'xat', 'Grocery', 14500, 10500, 14, 5),
        ('Pechenye Shirin', 'Grocery', 12500, 9000, 25, 7),
        ('Sut 1 litr', 'Grocery', 11000, 8500, 16, 6),
        ('Coca Cola 1.5 litr', 'Drinks', 15000, 10500, 30, 8),
        ('Fanta 1.5 litr', 'Drinks', 15000, 10500, 24, 8),
        ('Suv Chortoq 1.5 litr', 'Drinks', 5000, 3200, 60, 15),
        ('Sharbat 1 litr', 'Drinks', 13000, 9000, 20, 6),
        ('Energetik ichimlik', 'Drinks', 12000, 8500, 12, 5),
        ('Qahva 3 in 1', 'Drinks', 1800, 1100, 70, 20),
        ('Choy sovuq 0.5 litr', 'Drinks', 8000, 5200, 19, 6),
        ('Limonad 0.5 litr', 'Drinks', 7000, 4500, 26, 7),
        ('USB-C kabel 1 m', 'Phone accessories', 35000, 22000, 18, 5),
        ('Lightning kabel 1 m', 'Phone accessories', 42000, 28000, 11, 4),
        ('Micro USB kabel', 'Phone accessories', 28000, 17500, 15, 4),
        ('Telefon g\'ilofi universal', 'Phone accessories', 30000, 18000, 9, 3),
        ('Himoya oynasi 6.1', 'Phone accessories', 25000, 14000, 20, 5),
        ('Quvvatlagich 20W', 'Phone accessories', 85000, 58000, 7, 3),
        ('Quloqchin simli', 'Phone accessories', 45000, 28000, 13, 4),
        ('Powerbank 10000 mAh', 'Phone accessories', 160000, 115000, 5, 2),
        ('SIM karta qutisi', 'Phone accessories', 7000, 3500, 18, 5),
        ('Telefon stendi', 'Phone accessories', 22000, 13000, 8, 3),
        ('USB fleshka 32 GB', 'Phone accessories', 75000, 52000, 6, 2),
        ('Ruchka ko\'k', 'Stationery', 3000, 1500, 80, 20),
        ('Ruchka qora', 'Stationery', 3000, 1500, 75, 20),
        ('Qalam HB', 'Stationery', 2500, 1200, 50, 15),
        ('Daftar 48 varaq', 'Stationery', 9000, 5500, 32, 8),
        ('Daftar 96 varaq', 'Stationery', 16000, 10000, 20, 6),
        ('O\'chirg\'ich', 'Stationery', 2500, 1200, 45, 12),
        ('Lineyka 20 sm', 'Stationery', 4000, 2200, 22, 6),
        ('Skotch kichik', 'Stationery', 7000, 4000, 16, 5),
        ('Marker permanent', 'Stationery', 8500, 5000, 13, 4),
        ('Rangli qalamlar 12 dona', 'Stationery', 28000, 17500, 8, 3),
        ('Fayl papka A4', 'Stationery', 12000, 7000, 17, 5),
    ]

    CUSTOMERS = [
        ('Aziza Karimova', '+998901234567'),
        ('Jasur Akmalov', '+998912345678'),
        ('Dilnoza Shopirova', '+998931234567'),
        ('Bekzod Tursunov', '+998941234567'),
        ('Malika Rustamova', '+998951234567'),
        ('Sardor Qodirov', '+998971234567'),
    ]

    def handle(self, *args, **options):
        with transaction.atomic():
            company, _ = Company.objects.get_or_create(
                slug='demo-shop',
                defaults={
                    'company_name': 'SKLAT Demo Shop',
                    'email': 'demo@sklat.local',
                    'phone': '+998 71 200 00 00',
                    'city': 'Toshkent',
                    'country': 'Uzbekistan',
                    'currency': 'UZS',
                    'theme': 'dark',
                    'subscription_plan': 'basic',
                    'is_active': True,
                },
            )
            user, created_user = User.objects.get_or_create(
                email='demo@sklat.local',
                defaults={
                    'first_name': 'Demo', 'last_name': 'Kassir',
                    'role': 'COMPANY_ADMIN', 'company': company,
                    'is_staff': True, 'is_active': True,
                },
            )
            if created_user:
                user.set_password('demo12345')
                user.save(update_fields=['password'])
            elif user.company_id != company.pk:
                user.company = company
                user.save(update_fields=['company'])

            unit, _ = Unit.objects.get_or_create(name='Dona', defaults={'symbol': 'dona'})
            categories = {}
            for order, name in enumerate(['Grocery', 'Drinks', 'Phone accessories', 'Stationery']):
                category, _ = Category.objects.get_or_create(
                    company=company, name=name,
                    defaults={'slug': slugify(name), 'sort_order': order, 'is_active': True},
                )
                categories[name] = category

            warehouse, _ = Warehouse.objects.get_or_create(
                company=company, code='DEMO-WH',
                defaults={'name': 'Demo do\'kon ombori', 'warehouse_type': 'retail', 'is_active': True, 'is_main': True, 'city': 'Toshkent', 'country': 'Uzbekistan'},
            )
            created_products = 0
            for index, (name, category_name, price, purchase_price, stock, minimum) in enumerate(self.PRODUCTS, 1):
                product, created = Product.objects.update_or_create(
                    sku=f'DEMO-{index:03d}',
                    defaults={
                        'company': company, 'name': name,
                        'category_fk': categories[category_name], 'category': 'other',
                        'product_type': 'general', 'unit': unit,
                        'price': Decimal(str(price)), 'purchase_price': Decimal(str(purchase_price)),
                        'quantity': stock, 'min_stock': minimum, 'max_stock': max(stock * 4, 100),
                        'status': 'active', 'barcode': f'99890{index:06d}',
                    },
                )
                StockLevel.objects.update_or_create(
                    company=company, product=product, warehouse=warehouse,
                    defaults={'quantity': stock, 'reserved': 0},
                )
                if created:
                    created_products += 1

            terminal, _ = POSTerminal.objects.get_or_create(
                code='DEMO-POS',
                defaults={'company': company, 'warehouse': warehouse, 'name': 'Demo kassasi', 'status': 'active', 'is_active': True, 'barcode_scanner': True},
            )
            CashShift.objects.get_or_create(
                company=company, terminal=terminal, cashier=user, status='open',
                defaults={'shift_number': 'DEMO-SHIFT', 'opening_amount': Decimal('500000'), 'created_by': user},
            )
            for name, phone in self.CUSTOMERS:
                Customer.objects.get_or_create(company=company, phone=phone, defaults={'name': name, 'payment_terms': 'credit'})

        self.stdout.write(self.style.SUCCESS('Demo ma\'lumotlari tayyor.'))
        self.stdout.write(f'Kirish: demo@sklat.local / demo12345')
        self.stdout.write(f'Mahsulotlar: {len(self.PRODUCTS)} (yangi: {created_products})')
        self.stdout.write('Terminal: DEMO-POS, URL: /pos/workspace/?terminal=<terminal_id>')
