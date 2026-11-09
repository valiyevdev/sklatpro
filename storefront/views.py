from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
import json
import uuid as uuid_mod
from .models import (
    OnlineCart, OnlineCartItem, CustomerAddress, Wishlist,
    ProductReview, AbandonedCart
)
from products.models import Product, ProductVariant, Category, Brand
from pricing.models import PriceList, PriceListEntry, Promotion, Coupon
from ecommerce.models import SalesChannel, ShippingMethod, PaymentTransaction


def get_store_context(request):
    company_slug = request.GET.get('store', '')
    company = None
    if company_slug:
        from users.models import Company
        company = Company.objects.filter(slug=company_slug, is_active=True).first()
    if not company and hasattr(request, 'user') and request.user.is_authenticated and request.user.company:
        company = request.user.company
    if not company:
        from users.models import Company
        company = Company.objects.filter(is_active=True).first()
    return company


def get_or_create_cart(request, company):
    if request.user.is_authenticated:
        from sales.models import Customer
        customer = Customer.objects.filter(
            company=company, email=request.user.email
        ).first()
        cart = OnlineCart.objects.filter(
            company=company, customer=customer
        ).first()
        if not cart:
            cart = OnlineCart.objects.create(
                company=company, customer=customer,
                session_key=request.session.session_key or ''
            )
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart = OnlineCart.objects.filter(
            company=company, session_key=session_key, customer=None
        ).first()
        if not cart:
            cart = OnlineCart.objects.create(
                company=company, session_key=session_key, customer=None
            )
    return cart


def storefront_home(request):
    company = get_store_context(request)
    if not company:
        return render(request, 'storefront/no_store.html')

    products = Product.objects.filter(
        company=company, status='active', quantity__gt=0
    ).select_related('brand', 'category_fk')[:20]

    categories = Category.objects.filter(
        company=company, is_active=True, parent=None
    )[:12]

    featured_products = Product.objects.filter(
        company=company, status='active', quantity__gt=0
    ).order_by('-created_at')[:8]

    cart = get_or_create_cart(request, company) if hasattr(request, 'session') else None
    cart_count = cart.item_count if cart else 0

    context = {
        'store_company': company,
        'products': products,
        'featured_products': featured_products,
        'categories': categories,
        'cart_count': cart_count,
    }
    return render(request, 'storefront/home.html', context)


def product_catalog(request):
    company = get_store_context(request)
    if not company:
        return render(request, 'storefront/no_store.html')

    products = Product.objects.filter(
        company=company, status='active'
    ).select_related('brand', 'category_fk')

    category_slug = request.GET.get('category', '')
    brand_slug = request.GET.get('brand', '')
    search = request.GET.get('q', '')
    sort = request.GET.get('sort', 'name')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    in_stock = request.GET.get('in_stock', '')

    if category_slug:
        products = products.filter(category_fk__slug=category_slug)
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)
    if search:
        products = products.filter(
            Q(name__icontains=search) | Q(sku__icontains=search) |
            Q(description__icontains=search)
        )
    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except Exception:
            pass
    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except Exception:
            pass
    if in_stock == '1':
        products = products.filter(quantity__gt=0)

    sort_map = {
        'name': 'name',
        'price_asc': 'price',
        'price_desc': '-price',
        'newest': '-created_at',
    }
    products = products.order_by(sort_map.get(sort, 'name'))

    categories = Category.objects.filter(company=company, is_active=True, parent=None)
    brands = Brand.objects.filter(company=company, is_active=True)

    cart = get_or_create_cart(request, company)
    cart_count = cart.item_count

    total_count = products.count()
    page_size = 24
    page = int(request.GET.get('page', 1))
    products = products[(page - 1) * page_size:page * page_size]
    total_pages = (total_count + page_size - 1) // page_size

    context = {
        'store_company': company,
        'products': products,
        'categories': categories,
        'brands': brands,
        'selected_category': category_slug,
        'selected_brand': brand_slug,
        'search': search,
        'sort': sort,
        'min_price': min_price,
        'max_price': max_price,
        'in_stock': in_stock,
        'cart_count': cart_count,
        'total_count': total_count,
        'page': page,
        'total_pages': total_pages,
    }
    return render(request, 'storefront/catalog.html', context)


def product_detail(request, slug):
    company = get_store_context(request)
    if not company:
        return render(request, 'storefront/no_store.html')

    try:
        product = get_object_or_404(
            Product, slug=slug, company=company, status='active'
        )
    except Exception:
        product = get_object_or_404(
            Product, pk=slug, company=company, status='active'
        )
    variants = product.variants.filter(is_active=True)
    reviews = ProductReview.objects.filter(
        product=product, status='approved'
    ).select_related('customer')[:20]
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
    review_count = reviews.count()

    related_products = Product.objects.filter(
        company=company, category_fk=product.category_fk, status='active'
    ).exclude(pk=product.pk)[:4]

    cart = get_or_create_cart(request, company)
    cart_count = cart.item_count
    in_wishlist = False
    if request.user.is_authenticated:
        from sales.models import Customer
        customer = Customer.objects.filter(company=company, email=request.user.email).first()
        if customer:
            in_wishlist = Wishlist.objects.filter(customer=customer, product=product).exists()

    context = {
        'store_company': company,
        'product': product,
        'variants': variants,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'related_products': related_products,
        'cart_count': cart_count,
        'in_wishlist': in_wishlist,
    }
    return render(request, 'storefront/product_detail.html', context)


def cart_view(request):
    company = get_store_context(request)
    if not company:
        return render(request, 'storefront/no_store.html')

    cart = get_or_create_cart(request, company)
    cart_items = cart.items.select_related('product', 'variant')

    shipping_methods = ShippingMethod.objects.filter(
        company=company, status='active'
    )

    coupon_discount = cart.coupon_discount
    subtotal = cart.subtotal
    total = cart.total

    context = {
        'store_company': company,
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'coupon_discount': coupon_discount,
        'total': total,
        'shipping_methods': shipping_methods,
        'cart_count': cart.item_count,
    }
    return render(request, 'storefront/cart.html', context)


def add_to_cart(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)

    company = get_store_context(request)
    if not company:
        return JsonResponse({'error': 'No store'}, status=400)

    product_id = request.POST.get('product_id')
    variant_id = request.POST.get('variant_id', '')
    quantity = int(request.POST.get('quantity', 1))

    product = get_object_or_404(Product, pk=product_id, company=company, status='active')

    available = product.quantity
    variant = None
    if variant_id:
        variant = get_object_or_404(ProductVariant, pk=variant_id, product=product, is_active=True)
        available = variant.quantity

    if quantity > available:
        messages_text = 'Insufficient stock.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': messages_text}, status=400)
        from django.contrib import messages
        messages.warning(request, messages_text)
        return redirect('storefront:product_detail', slug=product.slug)

    cart = get_or_create_cart(request, company)
    cart_item, created = OnlineCartItem.objects.get_or_create(
        cart=cart, product=product, variant=variant,
        defaults={'quantity': quantity, 'unit_price': product.price}
    )
    if not created:
        cart_item.quantity += quantity
        if cart_item.quantity > available:
            cart_item.quantity = available
        cart_item.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart.item_count,
            'message': f'{product.name} added to cart'
        })

    from django.contrib import messages
    messages.success(request, f'{product.name} added to cart.')
    return redirect('storefront:cart')


def update_cart_item(request, item_id):
    if request.method != 'POST':
        return redirect('storefront:cart')

    company = get_store_context(request)
    cart = get_or_create_cart(request, company)
    item = get_object_or_404(OnlineCartItem, pk=item_id, cart=cart)

    action = request.POST.get('action', 'update')
    if action == 'remove':
        item.delete()
    else:
        quantity = int(request.POST.get('quantity', 1))
        available = item.variant.quantity if item.variant else item.product.quantity
        item.quantity = min(quantity, max(1, available))
        item.save()

    return redirect('storefront:cart')


def apply_coupon(request):
    if request.method != 'POST':
        return redirect('storefront:cart')

    company = get_store_context(request)
    cart = get_or_create_cart(request, company)
    code = request.POST.get('coupon_code', '').strip()

    if not code:
        from django.contrib import messages
        messages.warning(request, 'Please enter a coupon code.')
        return redirect('storefront:cart')

    coupon = Coupon.objects.filter(
        company=company, code__iexact=code, is_active=True
    ).first()

    from django.contrib import messages
    if not coupon or not coupon.is_currently_valid:
        messages.error(request, 'Invalid or expired coupon code.')
        return redirect('storefront:cart')

    if cart.subtotal < coupon.min_order_total:
        messages.warning(request, f'Minimum order {coupon.min_order_total} required.')
        return redirect('storefront:cart')

    discount = coupon.calculate_discount(cart.subtotal)
    cart.coupon_code = coupon.code
    cart.coupon_discount = discount
    cart.save()

    messages.success(request, f'Coupon applied. Discount: {discount}')
    return redirect('storefront:cart')


def checkout_view(request):
    company = get_store_context(request)
    if not company:
        return render(request, 'storefront/no_store.html')

    cart = get_or_create_cart(request, company)
    if cart.items.count() == 0:
        from django.contrib import messages
        messages.warning(request, 'Your cart is empty.')
        return redirect('storefront:catalog')

    addresses = []
    if request.user.is_authenticated:
        from sales.models import Customer
        customer = Customer.objects.filter(company=company, email=request.user.email).first()
        if customer:
            addresses = CustomerAddress.objects.filter(customer=customer, is_active=True)

    shipping_methods = ShippingMethod.objects.filter(
        company=company, status='active'
    )

    selected_shipping = request.GET.get('shipping', '')
    shipping_fee = Decimal('0')
    if selected_shipping:
        try:
            sm = ShippingMethod.objects.get(pk=selected_shipping, company=company)
            shipping_fee = sm.calculate_fee(subtotal=cart.subtotal)
        except Exception:
            pass

    total = cart.total + shipping_fee

    if request.method == 'POST':
        from django.contrib import messages as django_messages

        customer = None
        if request.user.is_authenticated:
            from sales.models import Customer
            customer = Customer.objects.filter(company=company, email=request.user.email).first()

        if not customer:
            name = request.POST.get('guest_name', '')
            email = request.POST.get('guest_email', '')
            phone = request.POST.get('guest_phone', '')
            if not name or not email:
                django_messages.error(request, 'Name and email are required.')
                return redirect('storefront:checkout')
            customer, _ = __import__('sales.models', fromlist=['Customer']).Customer.objects.get_or_create(
                company=company, email=email,
                defaults={'name': name, 'phone': phone}
            )

        from orders.models import Order, OrderItem
        from warehouses.models import Warehouse

        warehouse = Warehouse.objects.filter(company=company).first()
        if not warehouse:
            django_messages.error(request, 'No warehouse configured.')
            return redirect('storefront:checkout')

        order_ref = f"SP-{timezone.now().strftime('%Y%m%d')}-{uuid_mod.uuid4().hex[:6].upper()}"

        order = Order(
            company=company,
            reference=order_ref,
            customer=customer,
            warehouse=warehouse,
            total=total,
            discount=cart.coupon_discount,
            payment_status='unpaid',
            status='pending',
            delivery_address=request.POST.get('delivery_address', ''),
            delivery_phone=request.POST.get('delivery_phone', ''),
            delivery_method=request.POST.get('shipping_method', ''),
            customer_notes=request.POST.get('order_notes', ''),
        )
        order.save()

        for item in cart.items.select_related('product', 'variant'):
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount=item.discount,
            )
            item.product.quantity = max(0, item.product.quantity - item.quantity)
            item.product.save(update_fields=['quantity'])

        cart.items.all().delete()
        cart.coupon_code = ''
        cart.coupon_discount = Decimal('0')
        cart.save()

        checkout_data = {
            'order_id': str(order.pk),
            'order_ref': order.reference,
            'total': str(total),
            'payment_method': request.POST.get('payment_method', 'cod'),
        }
        request.session['last_order'] = checkout_data

        django_messages.success(request, f'Order {order.reference} placed successfully!')
        return redirect('storefront:order_confirmation')

    context = {
        'store_company': company,
        'cart': cart,
        'cart_items': cart.items.select_related('product', 'variant'),
        'subtotal': cart.subtotal,
        'coupon_discount': cart.coupon_discount,
        'shipping_fee': shipping_fee,
        'total': total,
        'addresses': addresses,
        'shipping_methods': shipping_methods,
        'selected_shipping': selected_shipping,
        'cart_count': cart.item_count,
    }
    return render(request, 'storefront/checkout.html', context)


def order_confirmation(request):
    company = get_store_context(request)
    order_data = request.session.get('last_order', {})
    if not order_data:
        return redirect('storefront:catalog')

    from orders.models import Order
    try:
        order = Order.objects.get(pk=order_data['order_id'], company=company)
    except Order.DoesNotExist:
        return redirect('storefront:catalog')

    context = {
        'store_company': company,
        'order': order,
        'order_data': order_data,
        'cart_count': 0,
    }
    return render(request, 'storefront/order_confirmation.html', context)


def order_tracking(request):
    company = get_store_context(request)
    if not company:
        return render(request, 'storefront/no_store.html')

    order_ref = request.GET.get('order', '')
    order = None
    error = ''

    if order_ref:
        from orders.models import Order
        order = Order.objects.filter(
            reference=order_ref, company=company
        ).select_related('customer').first()
        if not order:
            error = 'Order not found.'

    context = {
        'store_company': company,
        'order': order,
        'order_ref': order_ref,
        'error': error,
        'cart_count': 0,
    }
    return render(request, 'storefront/order_tracking.html', context)


def customer_account(request):
    company = get_store_context(request)
    if not company or not request.user.is_authenticated:
        return redirect('storefront:home')

    from sales.models import Customer
    customer = Customer.objects.filter(
        company=company, email=request.user.email
    ).first()
    if not customer:
        from django.contrib import messages
        messages.warning(request, 'No customer account found.')
        return redirect('storefront:home')

    orders = customer.orders.order_by('-created_at')[:20]
    addresses = CustomerAddress.objects.filter(customer=customer)
    wishlist_items = Wishlist.objects.filter(customer=customer).select_related('product')[:20]

    context = {
        'store_company': company,
        'customer': customer,
        'orders': orders,
        'addresses': addresses,
        'wishlist_items': wishlist_items,
        'cart_count': 0,
    }
    return render(request, 'storefront/account.html', context)


def wishlist_toggle(request):
    if request.method != 'POST':
        return redirect('storefront:catalog')

    company = get_store_context(request)
    if not company or not request.user.is_authenticated:
        return redirect('storefront:home')

    from sales.models import Customer
    customer = Customer.objects.filter(company=company, email=request.user.email).first()
    if not customer:
        return redirect('storefront:home')

    product_id = request.POST.get('product_id')
    product = get_object_or_404(Product, pk=product_id, company=company)

    existing = Wishlist.objects.filter(customer=customer, product=product)
    if existing.exists():
        existing.delete()
    else:
        Wishlist.objects.create(customer=customer, product=product)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})

    return redirect('storefront:product_detail', slug=product.slug)


def add_review(request):
    if request.method != 'POST':
        return redirect('storefront:catalog')

    company = get_store_context(request)
    if not company or not request.user.is_authenticated:
        return redirect('storefront:home')

    from sales.models import Customer
    customer = Customer.objects.filter(company=company, email=request.user.email).first()
    if not customer:
        return redirect('storefront:home')

    product_id = request.POST.get('product_id')
    product = get_object_or_404(Product, pk=product_id, company=company)
    rating = int(request.POST.get('rating', 5))
    title = request.POST.get('title', '')
    comment = request.POST.get('comment', '')

    from orders.models import Order
    verified = Order.objects.filter(
        customer=customer, items__product=product, status='completed'
    ).exists()

    ProductReview.objects.create(
        product=product,
        customer=customer,
        rating=min(5, max(1, rating)),
        title=title,
        comment=comment,
        is_verified_purchase=verified,
        status='approved',
    )

    from django.contrib import messages
    messages.success(request, 'Review submitted.')
    return redirect('storefront:product_detail', slug=product.slug)


def category_view(request, slug):
    company = get_store_context(request)
    if not company:
        return render(request, 'storefront/no_store.html')

    category = get_object_or_404(Category, slug=slug, company=company, is_active=True)
    products = Product.objects.filter(
        company=company, category_fk=category, status='active'
    ).select_related('brand', 'category_fk')

    cart = get_or_create_cart(request, company)
    subcategories = category.children.filter(is_active=True)

    context = {
        'store_company': company,
        'category': category,
        'products': products,
        'subcategories': subcategories,
        'cart_count': cart.item_count,
    }
    return render(request, 'storefront/category.html', context)


def api_cart_count(request):
    company = get_store_context(request)
    if not company:
        return JsonResponse({'count': 0})
    cart = get_or_create_cart(request, company)
    return JsonResponse({'count': cart.item_count})
