from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from orders.models import Order
from .models import (
    SalesChannel, ChannelProduct, ChannelCategory, ChannelStockAllocation,
    PaymentProvider, PaymentTransaction, MarketplaceIntegration,
    MarketplaceProductMapping, IntegrationLog, SyncJob, WebhookConfig, ShippingMethod
)


def get_company(request):
    if request.user.is_superuser:
        return request.user.company or None
    return getattr(request.user, 'company', None)


@login_required
def ecommerce_dashboard(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    channels = SalesChannel.objects.filter(company=company)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    active_channels = channels.filter(status='active')
    total_orders_today = channels.aggregate(t=Sum('orders_today'))['t'] or 0
    total_revenue_today = channels.aggregate(t=Sum('revenue_today'))['t'] or 0

    recent_orders = orders_qs = Order.objects.filter(
        company=company, created_at__date__gte=week_ago
    ).order_by('-created_at')[:10]

    channel_stats = []
    for ch in active_channels:
        ch_orders = ch.channel_orders.filter(created_at__date=today)
        channel_stats.append({
            'channel': ch,
            'orders_today': ch_orders.count(),
            'revenue_today': ch_orders.aggregate(t=Sum('total'))['t'] or 0,
        })

    integration_logs = IntegrationLog.objects.filter(company=company)[:10]
    sync_jobs = SyncJob.objects.filter(company=company)[:5]
    recent_payments = PaymentTransaction.objects.filter(company=company).order_by('-created_at')[:10]

    marketplace_integrations = MarketplaceIntegration.objects.filter(company=company)
    payment_providers = PaymentProvider.objects.filter(company=company)

    context = {
        'channels': channels,
        'active_channels': active_channels,
        'total_orders_today': total_orders_today,
        'total_revenue_today': total_revenue_today,
        'channel_stats': channel_stats,
        'recent_orders': recent_orders,
        'integration_logs': integration_logs,
        'sync_jobs': sync_jobs,
        'recent_payments': recent_payments,
        'marketplace_integrations': marketplace_integrations,
        'payment_providers': payment_providers,
        'total_channels': channels.count(),
        'active_marketplaces': marketplace_integrations.filter(status='active').count(),
        'active_payment_providers': payment_providers.filter(status='active').count(),
    }
    return render(request, 'ecommerce/dashboard.html', context)


@login_required
def channel_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    channels = SalesChannel.objects.filter(company=company)
    channel_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    search = request.GET.get('q', '')

    if channel_type:
        channels = channels.filter(channel_type=channel_type)
    if status:
        channels = channels.filter(status=status)
    if search:
        channels = channels.filter(Q(name__icontains=search) | Q(code__icontains=search))

    context = {
        'channels': channels,
        'channel_type': channel_type,
        'status': status,
        'search': search,
        'channel_types': SalesChannel.CHANNEL_TYPE_CHOICES,
        'status_choices': SalesChannel.STATUS_CHOICES,
    }
    return render(request, 'ecommerce/channels/list.html', context)


@login_required
def channel_create(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    if request.method == 'POST':
        channel = SalesChannel(
            company=company,
            name=request.POST.get('name', ''),
            code=request.POST.get('code', ''),
            channel_type=request.POST.get('channel_type', 'website'),
            status=request.POST.get('status', 'setup'),
            currency=request.POST.get('currency', 'UZS'),
            description=request.POST.get('description', ''),
            website_url=request.POST.get('website_url', ''),
            is_default=request.POST.get('is_default') == 'on',
        )
        channel.save()
        messages.success(request, f'Channel "{channel.name}" created successfully.')
        return redirect('ecommerce:channel_detail', pk=channel.pk)

    from warehouses.models import Warehouse
    from pricing.models import PriceList
    context = {
        'warehouses': Warehouse.objects.filter(company=company),
        'price_lists': PriceList.objects.filter(company=company),
        'channel_types': SalesChannel.CHANNEL_TYPE_CHOICES,
        'currency_choices': SalesChannel.CURRENCY_CHOICES,
    }
    return render(request, 'ecommerce/channels/create.html', context)


@login_required
def channel_detail(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    channel = get_object_or_404(SalesChannel, pk=pk, company=company)
    channel_products = ChannelProduct.objects.filter(channel=channel).select_related('product')[:50]
    sync_jobs = SyncJob.objects.filter(channel=channel)[:10]
    recent_logs = IntegrationLog.objects.filter(
        company=company, provider=channel.code
    ).order_by('-created_at')[:20]

    today = timezone.now().date()
    today_orders = channel.channel_orders.filter(created_at__date=today)

    context = {
        'channel': channel,
        'channel_products': channel_products,
        'sync_jobs': sync_jobs,
        'recent_logs': recent_logs,
        'today_orders': today_orders.count(),
        'today_revenue': today_orders.aggregate(t=Sum('total'))['t'] or 0,
    }
    return render(request, 'ecommerce/channels/detail.html', context)


@login_required
def channel_toggle(request, pk):
    company = get_company(request)
    channel = get_object_or_404(SalesChannel, pk=pk, company=company)
    if channel.status == 'active':
        channel.status = 'inactive'
        messages.info(request, f'Channel "{channel.name}" disabled.')
    else:
        channel.status = 'active'
        messages.success(request, f'Channel "{channel.name}" enabled.')
    channel.save()
    return redirect('ecommerce:channel_detail', pk=pk)


@login_required
def integration_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    marketplaces = MarketplaceIntegration.objects.filter(company=company)
    payment_providers = PaymentProvider.objects.filter(company=company)
    webhooks = WebhookConfig.objects.filter(company=company)
    shipping_methods = ShippingMethod.objects.filter(company=company)

    context = {
        'marketplaces': marketplaces,
        'payment_providers': payment_providers,
        'webhooks': webhooks,
        'shipping_methods': shipping_methods,
    }
    return render(request, 'ecommerce/integrations/list.html', context)


@login_required
def integration_logs(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    logs = IntegrationLog.objects.filter(company=company)
    provider = request.GET.get('provider', '')
    status = request.GET.get('status', '')

    if provider:
        logs = logs.filter(provider=provider)
    if status:
        logs = logs.filter(status=status)

    providers = IntegrationLog.objects.filter(company=company).values_list('provider', flat=True).distinct()

    context = {
        'logs': logs[:100],
        'providers': providers,
        'selected_provider': provider,
        'selected_status': status,
    }
    return render(request, 'ecommerce/integrations/logs.html', context)


@login_required
def sync_jobs_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    jobs = SyncJob.objects.filter(company=company)
    status_filter = request.GET.get('status', '')
    if status_filter:
        jobs = jobs.filter(status=status_filter)

    context = {
        'jobs': jobs[:50],
        'status_filter': status_filter,
    }
    return render(request, 'ecommerce/sync/jobs.html', context)


@login_required
def channel_products_manage(request, pk):
    company = get_company(request)
    channel = get_object_or_404(SalesChannel, pk=pk, company=company)
    channel_products = ChannelProduct.objects.filter(channel=channel).select_related('product')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_product':
            product_id = request.POST.get('product_id')
            from products.models import Product
            product = get_object_or_404(Product, pk=product_id, company=company)
            cp, created = ChannelProduct.objects.get_or_create(
                channel=channel, product=product,
                defaults={'visibility': 'visible'}
            )
            if created:
                messages.success(request, f'Product "{product.name}" added to {channel.name}.')
            else:
                messages.info(request, f'Product "{product.name}" already in {channel.name}.')
        elif action == 'update_visibility':
            cp_id = request.POST.get('channel_product_id')
            visibility = request.POST.get('visibility', 'visible')
            cp = get_object_or_404(ChannelProduct, pk=cp_id, channel=channel)
            cp.visibility = visibility
            cp.save()
            messages.success(request, f'Visibility updated for "{cp.product.name}".')
        elif action == 'remove_product':
            cp_id = request.POST.get('channel_product_id')
            cp = get_object_or_404(ChannelProduct, pk=cp_id, channel=channel)
            name = cp.product.name
            cp.delete()
            messages.success(request, f'Product "{name}" removed from {channel.name}.')
        return redirect('ecommerce:channel_products', pk=pk)

    from products.models import Product
    all_products = Product.objects.filter(company=company, status='active')
    added_ids = channel_products.values_list('product_id', flat=True)
    available_products = all_products.exclude(pk__in=added_ids)

    context = {
        'channel': channel,
        'channel_products': channel_products,
        'available_products': available_products[:50],
    }
    return render(request, 'ecommerce/channels/products.html', context)


@login_required
def channel_stock_allocations(request, pk):
    company = get_company(request)
    channel = get_object_or_404(SalesChannel, pk=pk, company=company)
    allocations = ChannelStockAllocation.objects.filter(channel=channel).select_related('product')

    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        allocated = int(request.POST.get('allocated_quantity', 0))
        safety = int(request.POST.get('safety_stock', 0))
        from products.models import Product
        product = get_object_or_404(Product, pk=product_id, company=company)
        alloc, _ = ChannelStockAllocation.objects.update_or_create(
            channel=channel, product=product,
            defaults={'allocated_quantity': allocated, 'safety_stock': safety}
        )
        messages.success(request, f'Stock allocation updated for "{product.name}".')
        return redirect('ecommerce:channel_stock', pk=pk)

    from products.models import Product
    all_products = Product.objects.filter(company=company, status='active')

    context = {
        'channel': channel,
        'allocations': allocations,
        'all_products': all_products,
    }
    return render(request, 'ecommerce/channels/stock.html', context)


@login_required
def payment_providers_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    providers = PaymentProvider.objects.filter(company=company)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            provider = PaymentProvider(
                company=company,
                name=request.POST.get('name', ''),
                provider_type=request.POST.get('provider_type', 'manual'),
                merchant_id=request.POST.get('merchant_id', ''),
                api_url=request.POST.get('api_url', ''),
                test_mode=request.POST.get('test_mode') == 'on',
            )
            provider.save()
            messages.success(request, f'Payment provider "{provider.name}" created.')
        elif action == 'toggle':
            pp_id = request.POST.get('provider_id')
            pp = get_object_or_404(PaymentProvider, pk=pp_id, company=company)
            pp.status = 'inactive' if pp.status == 'active' else 'active'
            pp.save()
            messages.success(request, f'Provider "{pp.name}" status updated.')
        return redirect('ecommerce:payment_providers')

    context = {'providers': providers}
    return render(request, 'ecommerce/integrations/payment_providers.html', context)


@login_required
def marketplace_detail(request, pk):
    company = get_company(request)
    marketplace = get_object_or_404(MarketplaceIntegration, pk=pk, company=company)
    mappings = MarketplaceProductMapping.objects.filter(integration=marketplace).select_related('product')
    recent_logs = IntegrationLog.objects.filter(
        company=company, provider=marketplace.marketplace_type
    ).order_by('-created_at')[:20]

    context = {
        'marketplace': marketplace,
        'mappings': mappings,
        'recent_logs': recent_logs,
    }
    return render(request, 'ecommerce/integrations/marketplace_detail.html', context)


@login_required
def shipping_methods_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'ecommerce/no_company.html')

    methods = ShippingMethod.objects.filter(company=company)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create':
            method = ShippingMethod(
                company=company,
                name=request.POST.get('name', ''),
                code=request.POST.get('code', ''),
                calculation=request.POST.get('calculation', 'fixed'),
                base_fee=Decimal(request.POST.get('base_fee', '0') or '0'),
                per_kg_fee=Decimal(request.POST.get('per_kg_fee', '0') or '0'),
                estimated_days_min=int(request.POST.get('estimated_days_min', '1') or '1'),
                estimated_days_max=int(request.POST.get('estimated_days_max', '7') or '7'),
            )
            method.save()
            messages.success(request, f'Shipping method "{method.name}" created.')
        return redirect('ecommerce:shipping_methods')

    channels = SalesChannel.objects.filter(company=company)
    context = {'methods': methods, 'channels': channels}
    return render(request, 'ecommerce/integrations/shipping.html', context)
