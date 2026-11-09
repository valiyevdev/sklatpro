from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db.models import Q
from products.models import Product


@login_required
@never_cache
def scanner_view(request):
    return render(request, 'scanner/scanner.html')


@login_required
@never_cache
def scanner_search(request):
    query = request.GET.get('q', '').strip()
    products = []
    if query:
        company = request.user.company
        qs = Product.objects.filter(company=company) if company else Product.objects.all()
        qs = qs.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
        )
        # The result card renders unit + category per row, so pull them in
        # with the products instead of issuing two extra queries each.
        products = qs.select_related('unit', 'category_fk', 'brand')
    return render(request, 'scanner/scanner_results.html', {
        'products': products,
        'query': query,
        'total_count': len(products),
    })
