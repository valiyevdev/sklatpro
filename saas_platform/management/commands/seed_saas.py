from django.core.management.base import BaseCommand
from saas_platform.models import Permission, Role, SubscriptionPlan


class Command(BaseCommand):
    help = 'Seed default permissions, system roles, and subscription plans'

    def handle(self, *args, **options):
        self.stdout.write('Seeding permissions...')
        permissions_data = [
            ('view', 'products', 'View Products'),
            ('create', 'products', 'Create Products'),
            ('edit', 'products', 'Edit Products'),
            ('delete', 'products', 'Delete Products'),
            ('view', 'inventory', 'View Inventory'),
            ('adjust', 'inventory', 'Adjust Inventory'),
            ('count', 'inventory', 'Count Inventory'),
            ('view', 'warehouses', 'View Warehouses'),
            ('create', 'warehouses', 'Create Warehouses'),
            ('edit', 'warehouses', 'Edit Warehouses'),
            ('view', 'purchases', 'View Purchases'),
            ('create', 'purchases', 'Create Purchases'),
            ('approve', 'purchases', 'Approve Purchases'),
            ('receive', 'purchases', 'Receive Purchases'),
            ('view', 'sales', 'View Sales'),
            ('create', 'sales', 'Create Sales'),
            ('cancel', 'sales', 'Cancel Sales'),
            ('return_sale', 'sales', 'Return Sales'),
            ('view', 'orders', 'View Orders'),
            ('create', 'orders', 'Create Orders'),
            ('edit', 'orders', 'Edit Orders'),
            ('cancel', 'orders', 'Cancel Orders'),
            ('view', 'crm', 'View CRM'),
            ('edit', 'crm', 'Edit CRM'),
            ('view', 'finance', 'View Finance'),
            ('create', 'finance', 'Create Finance'),
            ('approve', 'finance', 'Approve Finance'),
            ('view', 'pos', 'View POS'),
            ('operate', 'pos', 'Operate POS'),
            ('view', 'wms', 'View WMS'),
            ('pick', 'wms', 'Pick Orders'),
            ('pack', 'wms', 'Pack Orders'),
            ('ship', 'wms', 'Ship Orders'),
            ('view', 'logistics', 'View Logistics'),
            ('dispatch', 'logistics', 'Dispatch Deliveries'),
            ('view', 'reports', 'View Reports'),
            ('finance_view', 'reports', 'View Financial Reports'),
            ('view', 'documents', 'View Documents'),
            ('create', 'documents', 'Create Documents'),
            ('manage', 'integrations', 'Manage Integrations'),
            ('manage', 'automation', 'Manage Automation'),
            ('use', 'ai', 'Use AI'),
            ('execute_actions', 'ai', 'Execute AI Actions'),
            ('view', 'users', 'View Users'),
            ('create', 'users', 'Create Users'),
            ('edit', 'users', 'Edit Users'),
            ('delete', 'users', 'Delete Users'),
            ('manage', 'company', 'Manage Company Settings'),
            ('admin', 'platform', 'Platform Administration'),
        ]

        created_count = 0
        for codename, module, name in permissions_data:
            _, created = Permission.objects.get_or_create(
                codename=codename,
                module=module,
                defaults={
                    'name': name,
                    'is_platform_only': module == 'platform',
                },
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'  Created {created_count} permissions'))

        self.stdout.write('Seeding system roles...')
        all_perms = Permission.objects.all()
        product_perms = Permission.objects.filter(module='products')
        inventory_perms = Permission.objects.filter(module='inventory')
        sales_perms = Permission.objects.filter(module='sales')
        order_perms = Permission.objects.filter(module='orders')
        finance_perms = Permission.objects.filter(module='finance')
        wms_perms = Permission.objects.filter(module='wms')
        logistics_perms = Permission.objects.filter(module='logistics')
        crm_perms = Permission.objects.filter(module='crm')
        reports_perms = Permission.objects.filter(module='reports')
        pos_perms = Permission.objects.filter(module='pos')
        ai_perms = Permission.objects.filter(module='ai')
        automation_perms = Permission.objects.filter(module='automation')
        integrations_perms = Permission.objects.filter(module='integrations')
        documents_perms = Permission.objects.filter(module='documents')
        users_perms = Permission.objects.filter(module='users')
        company_perms = Permission.objects.filter(module='company')
        platform_perms = Permission.objects.filter(module='platform')

        roles_data = [
            ('platform-owner', 'Platform Owner', 'platform', 'Platform-level admin', platform_perms, True),
            ('company-admin', 'Company Admin', 'company', 'Full company access', all_perms, True),
            ('manager', 'Manager', 'company', 'Department manager', product_perms | inventory_perms | sales_perms | order_perms | finance_perms | reports_perms | crm_perms | documents_perms | ai_perms | automation_perms, False),
            ('sales-manager', 'Sales Manager', 'company', 'Sales team lead', sales_perms | order_perms | crm_perms | reports_perms, False),
            ('sales-employee', 'Sales Employee', 'company', 'Sales staff', sales_perms.filter(codename__in=['view', 'create']) | order_perms.filter(codename__in=['view', 'create']) | crm_perms.filter(codename='view'), False),
            ('warehouse-manager', 'Warehouse Manager', 'company', 'Warehouse team lead', wms_perms | inventory_perms | logistics_perms.filter(codename='view'), False),
            ('warehouse-worker', 'Warehouse Worker', 'company', 'Warehouse staff', wms_perms.filter(codename__in=['view', 'pick', 'pack']), False),
            ('accountant', 'Accountant', 'company', 'Finance team', finance_perms | reports_perms.filter(codename__in=['view', 'finance_view']), False),
            ('cashier', 'Cashier', 'company', 'POS operator', pos_perms | sales_perms.filter(codename__in=['view', 'create']), False),
            ('viewer', 'Viewer', 'company', 'Read-only access', all_perms.filter(codename='view'), False),
        ]

        created_count = 0
        for slug, name, scope, desc, perms, is_system in roles_data:
            role, created = Role.objects.get_or_create(
                slug=slug,
                company=None,
                defaults={'name': name, 'scope': scope, 'description': desc, 'is_system': is_system},
            )
            if created:
                role.permissions.set(perms)
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'  Created {created_count} system roles'))

        self.stdout.write('Seeding subscription plans...')
        plans_data = [
            {'name': 'Free', 'slug': 'free', 'price_monthly': 0, 'price_yearly': 0,
             'max_users': 3, 'max_products': 100, 'max_warehouses': 1, 'max_orders_monthly': 50,
             'max_storage_mb': 100, 'max_api_calls_daily': 0, 'max_ai_requests_monthly': 10,
             'display_order': 0},
            {'name': 'Starter', 'slug': 'starter', 'price_monthly': 29, 'price_yearly': 290,
             'max_users': 5, 'max_products': 1000, 'max_warehouses': 3, 'max_orders_monthly': 500,
             'max_storage_mb': 500, 'max_api_calls_daily': 500, 'max_ai_requests_monthly': 50,
             'display_order': 1},
            {'name': 'Professional', 'slug': 'professional', 'price_monthly': 79, 'price_yearly': 790,
             'max_users': 20, 'max_products': 10000, 'max_warehouses': 10, 'max_orders_monthly': 5000,
             'max_storage_mb': 5000, 'max_api_calls_daily': 5000, 'max_ai_requests_monthly': 200,
             'display_order': 2},
            {'name': 'Business', 'slug': 'business', 'price_monthly': 199, 'price_yearly': 1990,
             'max_users': 50, 'max_products': 50000, 'max_warehouses': 50, 'max_orders_monthly': 50000,
             'max_storage_mb': 20000, 'max_api_calls_daily': 20000, 'max_ai_requests_monthly': 500,
             'display_order': 3},
            {'name': 'Enterprise', 'slug': 'enterprise', 'price_monthly': 499, 'price_yearly': 4990,
             'max_users': 999999, 'max_products': 999999, 'max_warehouses': 999999,
             'max_orders_monthly': 999999, 'max_storage_mb': 100000,
             'max_api_calls_daily': 100000, 'max_ai_requests_monthly': 2000,
             'display_order': 4},
        ]

        created_count = 0
        for plan_data in plans_data:
            _, created = SubscriptionPlan.objects.get_or_create(
                slug=plan_data['slug'],
                defaults=plan_data,
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(f'  Created {created_count} subscription plans'))

        self.stdout.write(self.style.SUCCESS('Seeding complete.'))
