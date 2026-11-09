from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Sum, F
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from .models import Product, Category, Brand, Unit, ProductVariant
from .forms import ProductForm, ProductVariantForm, CategoryForm, BrandForm
from activity.models import Activity
from core.translations import get_translation
from inventory.models import StockEngine


# ==========================================
# PRODUCT VIEWS
# ==========================================

@login_required
@never_cache
def product_list(request):
    company = request.user.company
    lang = request.session.get('language', 'uz')
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    brand_filter = request.GET.get('brand', '')
    status_filter = request.GET.get('status', '')
    stock_filter = request.GET.get('stock_status', '')
    sort_by = request.GET.get('sort', '-created_at')

    if company:
        products = Product.objects.filter(company=company)
    else:
        products = Product.objects.all()

    products = products.select_related('category_fk', 'brand', 'unit')

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query) |
            Q(barcode__icontains=search_query) |
            Q(supplier__icontains=search_query)
        )

    if category_filter:
        products = products.filter(category_fk_id=category_filter)

    if brand_filter:
        products = products.filter(brand_id=brand_filter)

    if status_filter:
        products = products.filter(status=status_filter)

    if stock_filter:
        if stock_filter == 'out_of_stock':
            products = products.filter(quantity=0)
        elif stock_filter == 'low_stock':
            products = products.filter(quantity__gt=0, quantity__lte=5)
        elif stock_filter == 'in_stock':
            products = products.filter(quantity__gt=5)

    valid_sort_fields = [
        'name', '-name', 'sku', '-sku', 'quantity', '-quantity',
        'price', '-price', 'created_at', '-created_at', 'updated_at', '-updated_at'
    ]
    if sort_by in valid_sort_fields:
        products = products.order_by(sort_by)
    else:
        products = products.order_by('-created_at')

    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.filter(is_active=True, company=company) if company else Category.objects.filter(is_active=True)
    brands = Brand.objects.filter(is_active=True, company=company) if company else Brand.objects.filter(is_active=True)
    active_products = Product.objects.filter(company=company, status='active').count() if company else Product.objects.filter(status='active').count()

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category_filter': category_filter,
        'brand_filter': brand_filter,
        'status_filter': status_filter,
        'stock_filter': stock_filter,
        'sort_by': sort_by,
        'categories': categories,
        'brands': brands,
        'product_count': paginator.count,
        'active_products': active_products,
        'company': company,
    }
    return render(request, 'products/product_list.html', context)


@login_required
@never_cache
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            messages.error(request, get_translation('no_product_access', lang))
            return redirect('product_list')

    from inventory.models import Transaction
    transactions = Transaction.objects.filter(product=product).select_related('user').order_by('-created_at')[:20]
    variants = product.variants.all()

    context = {
        'product': product,
        'transactions': transactions,
        'variants': variants,
    }
    return render(request, 'products/product_detail.html', context)


@login_required
@never_cache
def product_create(request):
    company = request.user.company
    lang = request.session.get('language', 'uz')
    if not (request.user.is_superuser or request.user.is_company_admin() or request.user.is_manager()):
        return HttpResponseForbidden('Mahsulotni faqat egasi yoki menejer boshqaradi')
    if not company and not request.user.is_superuser:
        messages.error(request, get_translation('no_company_assigned', lang))
        return redirect('login')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            with transaction.atomic():
                product = form.save(commit=False)
                product.company = company
                product.save()
                warehouse = StockEngine.default_warehouse(company)
                if warehouse:
                    level = StockEngine.get_stock_level(product, warehouse, company)
                    if product.quantity:
                        StockEngine.initialize_product_stock(
                            product, warehouse, company, product.quantity,
                            user=request.user, notes='Product creation'
                        )
            Activity.log_activity(
                activity_type='product_added',
                description=f'{product.name} added. SKU: {product.sku}',
                user=request.user,
                related_object_type='Product',
                related_object_id=product.id
            )
            messages.success(request, get_translation('product_created', lang))
            return redirect('product_detail', pk=product.pk)
    else:
        initial = {}
        requested_type = request.GET.get('type')
        if requested_type in dict(Product.PRODUCT_TYPE_CHOICES):
            initial['product_type'] = requested_type
        form = ProductForm(company=company, initial=initial)

    return render(request, 'products/product_form.html', {
        'form': form,
        'title': get_translation('add_product', lang),
        'company': company,
    })


@login_required
@never_cache
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    lang = request.session.get('language', 'uz')
    if not (request.user.is_superuser or request.user.is_company_admin() or request.user.is_manager()):
        return HttpResponseForbidden('Mahsulotni faqat egasi yoki menejer boshqaradi')
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            messages.error(request, get_translation('no_product_access', lang))
            return redirect('product_list')

    if request.method == 'POST':
        old_prices = (product.price, product.wholesale_price, product.purchase_price)
        form = ProductForm(request.POST, request.FILES, instance=product, company=request.user.company)
        if form.is_valid():
            form.save()
            Activity.log_activity(
                activity_type='product_updated',
                description=f'{product.name} updated. SKU: {product.sku}',
                user=request.user,
                related_object_type='Product',
                related_object_id=product.id
            )
            new_prices = (product.price, product.wholesale_price, product.purchase_price)
            if old_prices != new_prices:
                Activity.log_activity('product_updated', f'Price changed for {product.name}: {old_prices} -> {new_prices}', user=request.user, company=request.user.company, related_object_type='Product', related_object_id=product.pk)
            messages.success(request, get_translation('product_updated', lang))
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductForm(instance=product, company=request.user.company)

    return render(request, 'products/product_form.html', {
        'form': form,
        'product': product,
        'title': get_translation('edit_product', lang),
        'company': request.user.company,
    })


@login_required
@never_cache
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    lang = request.session.get('language', 'uz')
    if not (request.user.is_superuser or request.user.is_company_admin() or request.user.is_manager()):
        return HttpResponseForbidden('Mahsulotni faqat egasi yoki menejer o‘chirishi mumkin')
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            messages.error(request, get_translation('no_product_access', lang))
            return redirect('product_list')

    if request.method == 'POST':
        product_name = product.name
        product_sku = product.sku
        product.delete()
        Activity.log_activity(
            activity_type='product_deleted',
            description=f'{product_name} deleted. SKU: {product_sku}',
            user=request.user,
            related_object_type='Product',
            related_object_id=pk
        )
        messages.success(request, get_translation('product_deleted', lang))
        return redirect('product_list')

    return render(request, 'products/product_confirm_delete.html', {
        'product': product,
        'company': request.user.company,
    })


@login_required
@never_cache
def product_barcode(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            return HttpResponse('Forbidden', status=403)
    barcode_buffer = product.generate_barcode_image()
    if barcode_buffer:
        response = HttpResponse(barcode_buffer.getvalue(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="barcode_{product.sku}.png"'
        return response
    return HttpResponse('Barcode not available', status=404)


@login_required
@never_cache
def product_qrcode(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            return HttpResponse('Forbidden', status=403)
    if product.qr_code:
        response = HttpResponse(product.qr_code.read(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="qrcode_{product.sku}.png"'
        return response
    return HttpResponse('QR Code not available', status=404)


@login_required
@require_POST
def product_duplicate(request, pk):
    product = get_object_or_404(Product, pk=pk)
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            messages.error(request, get_translation('no_product_access', lang))
            return redirect('product_list')

    new_product = Product.objects.create(
        company=product.company,
        name=f'{product.name} (Copy)',
        category=product.category,
        category_fk=product.category_fk,
        brand=product.brand,
        unit=product.unit,
        quantity=0,
        price=product.price,
        purchase_price=product.purchase_price,
        description=product.description,
        supplier=product.supplier,
        status=product.status,
        min_stock=product.min_stock,
        max_stock=product.max_stock,
        product_type=product.product_type,
        storage_conditions=product.storage_conditions,
        weight_unit=product.weight_unit,
        netto_brutto=product.netto_brutto,
        measurement_unit=product.measurement_unit,
        volume=product.volume,
        weight=product.weight,
        length=product.length,
        width=product.width,
        height=product.height,
        batch_number=product.batch_number,
        shelf=product.shelf,
        rack=product.rack,
        section=product.section,
        notes=product.notes,
    )
    messages.success(request, get_translation('product_created', lang))
    return redirect('product_detail', pk=new_product.pk)


# ==========================================
# VARIANT VIEWS
# ==========================================

@login_required
@never_cache
def variant_create(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            messages.error(request, get_translation('no_product_access', lang))
            return redirect('product_list')

    if request.method == 'POST':
        form = ProductVariantForm(request.POST, request.FILES)
        if form.is_valid():
            variant = form.save(commit=False)
            variant.product = product
            variant.save()
            messages.success(request, get_translation('product_created', lang))
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductVariantForm()

    return render(request, 'products/variant_form.html', {
        'form': form,
        'product': product,
        'title': 'Add Variant',
    })


@login_required
@never_cache
def variant_update(request, product_pk, pk):
    product = get_object_or_404(Product, pk=product_pk)
    variant = get_object_or_404(ProductVariant, pk=pk, product=product)
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            messages.error(request, get_translation('no_product_access', lang))
            return redirect('product_list')

    if request.method == 'POST':
        form = ProductVariantForm(request.POST, request.FILES, instance=variant)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('product_updated', lang))
            return redirect('product_detail', pk=product.pk)
    else:
        form = ProductVariantForm(instance=variant)

    return render(request, 'products/variant_form.html', {
        'form': form,
        'product': product,
        'variant': variant,
        'title': 'Edit Variant',
    })


@login_required
@require_POST
def variant_delete(request, product_pk, pk):
    product = get_object_or_404(Product, pk=product_pk)
    variant = get_object_or_404(ProductVariant, pk=pk, product=product)
    lang = request.session.get('language', 'uz')
    if not request.user.is_superuser:
        if not request.user.company or product.company != request.user.company:
            messages.error(request, get_translation('no_product_access', lang))
            return redirect('product_list')
    variant.delete()
    messages.success(request, get_translation('product_deleted', lang))
    return redirect('product_detail', pk=product.pk)


# ==========================================
# CATEGORY VIEWS
# ==========================================

@login_required
@never_cache
def category_list(request):
    company = request.user.company
    categories = Category.objects.filter(company=company) if company else Category.objects.all()
    categories = categories.select_related('parent').annotate(product_count=Count('products'))
    return render(request, 'products/category_list.html', {'categories': categories})


@login_required
@never_cache
def category_create(request):
    company = request.user.company
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.company = company
            cat.save()
            messages.success(request, get_translation('product_created', lang))
            return redirect('category_list')
    else:
        form = CategoryForm(company=company)
    return render(request, 'products/category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
@never_cache
def category_update(request, pk):
    company = request.user.company
    category = get_object_or_404(Category, pk=pk)
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('product_updated', lang))
            return redirect('category_list')
    else:
        form = CategoryForm(instance=category, company=company)
    return render(request, 'products/category_form.html', {'form': form, 'category': category, 'title': 'Edit Category'})


@login_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    lang = request.session.get('language', 'uz')
    category.delete()
    messages.success(request, get_translation('product_deleted', lang))
    return redirect('category_list')


# ==========================================
# BRAND VIEWS
# ==========================================

@login_required
@never_cache
def brand_list(request):
    company = request.user.company
    brands = Brand.objects.filter(company=company) if company else Brand.objects.all()
    brands = brands.annotate(product_count=Count('products'))
    return render(request, 'products/brand_list.html', {'brands': brands})


@login_required
@never_cache
def brand_create(request):
    company = request.user.company
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        form = BrandForm(request.POST, request.FILES)
        if form.is_valid():
            brand = form.save(commit=False)
            brand.company = company
            brand.save()
            messages.success(request, get_translation('product_created', lang))
            return redirect('brand_list')
    else:
        form = BrandForm()
    return render(request, 'products/brand_form.html', {'form': form, 'title': 'Add Brand'})


@login_required
@never_cache
def brand_update(request, pk):
    company = request.user.company
    brand = get_object_or_404(Brand, pk=pk)
    lang = request.session.get('language', 'uz')
    if request.method == 'POST':
        form = BrandForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            form.save()
            messages.success(request, get_translation('product_updated', lang))
            return redirect('brand_list')
    else:
        form = BrandForm(instance=brand)
    return render(request, 'products/brand_form.html', {'form': form, 'brand': brand, 'title': 'Edit Brand'})


@login_required
@require_POST
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    lang = request.session.get('language', 'uz')
    brand.delete()
    messages.success(request, get_translation('product_deleted', lang))
    return redirect('brand_list')


# ==========================================
# UNIT VIEWS
# ==========================================

@login_required
@never_cache
def unit_list(request):
    units = Unit.objects.all().annotate(product_count=Count('products'))
    return render(request, 'products/unit_list.html', {'units': units})


@login_required
@require_POST
def unit_create(request):
    lang = request.session.get('language', 'uz')
    name = request.POST.get('name', '').strip()
    symbol = request.POST.get('symbol', '').strip()
    if name:
        Unit.objects.create(name=name, symbol=symbol)
        messages.success(request, get_translation('product_created', lang))
    return redirect('unit_list')


@login_required
@require_POST
def unit_delete(request, pk):
    unit = get_object_or_404(Unit, pk=pk)
    lang = request.session.get('language', 'uz')
    unit.delete()
    messages.success(request, get_translation('product_deleted', lang))
    return redirect('unit_list')


# ==========================================
# AJAX VIEWS
# ==========================================

@login_required
def product_search_api(request):
    company = request.user.company
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse({'results': []})

    products = Product.objects.filter(company=company) if company else Product.objects.all()
    products = products.filter(
        Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q)
    )[:20]

    results = [{
        'id': p.id,
        'name': p.name,
        'sku': p.sku,
        'price': str(p.price),
        'quantity': p.quantity,
        'unit': str(p.unit) if p.unit else '',
    } for p in products]

    return JsonResponse({'results': results})
