from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache
from products.models import Product, Category, Brand, Unit
import csv
from io import TextIOWrapper
from django.http import HttpResponse


@login_required
@never_cache
def import_export_index(request):
    return render(request, 'import_export/index.html')


@login_required
@never_cache
def import_products(request):
    company = request.user.company
    if request.method == 'POST' and request.FILES.get('file'):
        csv_file = request.FILES['file']
        decoded = TextIOWrapper(csv_file, encoding='utf-8-sig')
        reader = csv.DictReader(decoded)
        imported = 0
        updated = 0
        errors = []
        for i, row in enumerate(reader, start=1):
            try:
                name = row.get('name', '').strip()
                if not name:
                    errors.append(f"Row {i}: Missing name")
                    continue
                sku = row.get('sku', '').strip()
                category_name = row.get('category', '').strip()
                brand_name = row.get('brand', '').strip()
                unit_name = row.get('unit', '').strip()

                category_fk = None
                if category_name:
                    category_fk, _ = Category.objects.get_or_create(
                        company=company, name=category_name, defaults={'is_active': True}
                    )
                brand = None
                if brand_name:
                    brand, _ = Brand.objects.get_or_create(
                        company=company, name=brand_name, defaults={'is_active': True}
                    )
                unit = None
                if unit_name:
                    unit = Unit.objects.filter(name__iexact=unit_name).first()
                    if not unit:
                        unit = Unit.objects.create(name=unit_name, symbol=unit_name[:4])

                price = float(row.get('price', 0) or 0)
                purchase_price = float(row.get('purchase_price', 0) or 0)
                quantity = int(float(row.get('quantity', 0) or 0))
                status = row.get('status', 'active').strip() or 'active'

                if sku:
                    existing = Product.objects.filter(company=company, sku=sku).first()
                    if existing:
                        existing.name = name
                        existing.price = price
                        existing.purchase_price = purchase_price
                        existing.quantity = quantity
                        if category_fk:
                            existing.category_fk = category_fk
                        if brand:
                            existing.brand = brand
                        if unit:
                            existing.unit = unit
                        existing.description = row.get('description', '') or existing.description
                        existing.status = status
                        existing.save()
                        updated += 1
                        continue

                product = Product.objects.create(
                    company=company,
                    name=name,
                    sku=sku,
                    category_fk=category_fk,
                    brand=brand,
                    unit=unit,
                    price=price,
                    purchase_price=purchase_price,
                    quantity=quantity,
                    description=row.get('description', '') or '',
                    supplier=row.get('supplier', '') or '',
                    batch_number=row.get('batch_number', '') or '',
                    status=status,
                    min_stock=row.get('min_stock', 0) or 0,
                    max_stock=row.get('max_stock', 0) or 0,
                )
                imported += 1
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
        return render(request, 'import_export/import_result.html', {
            'imported': imported,
            'updated': updated,
            'errors': errors,
        })
    return render(request, 'import_export/import_products.html')


@login_required
@never_cache
def export_products(request):
    company = request.user.company
    products = Product.objects.filter(company=company).select_related('category_fk', 'brand', 'unit') if company else Product.objects.all()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'name', 'sku', 'barcode', 'category', 'brand', 'unit',
        'quantity', 'price', 'purchase_price', 'description',
        'supplier', 'batch_number', 'status', 'min_stock', 'max_stock',
    ])
    for p in products:
        writer.writerow([
            p.name, p.sku or '', p.barcode or '',
            p.category_fk.name if p.category_fk else (p.category or ''),
            p.brand.name if p.brand else '',
            p.unit.name if p.unit else '',
            p.quantity, p.price, p.purchase_price or '',
            p.description or '', p.supplier or '',
            p.batch_number or '', p.status,
            p.min_stock or '', p.max_stock or '',
        ])
    return response
