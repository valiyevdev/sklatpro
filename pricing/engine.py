from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional, List
from django.db import models
from django.utils import timezone


@dataclass
class PriceResult:
    base_price: Decimal = Decimal('0')
    final_price: Decimal = Decimal('0')
    currency: str = 'UZS'
    price_list_name: str = ''
    price_list_entry_id: Optional[int] = None
    customer_price_id: Optional[int] = None
    applied_rule: str = 'product_default'
    discount_amount: Decimal = Decimal('0')
    discount_reason: str = ''
    promo_name: str = ''
    promo_discount: Decimal = Decimal('0')
    coupon_discount: Decimal = Decimal('0')
    coupon_code: str = ''
    explanation: List[dict] = field(default_factory=list)
    is_resolved: bool = False

    def add_explanation(self, label, price, detail=''):
        self.explanation.append({'label': label, 'price': str(price), 'detail': detail})


def resolve_price(company, product, customer=None, quantity=Decimal('1'),
                  warehouse=None, channel='', date=None, variant=None,
                  coupon_code=None):
    from pricing.models import (
        PriceListEntry, CustomerSpecificPrice, Promotion, Coupon
    )

    if date is None:
        date = timezone.now().date()

    result = PriceResult(
        base_price=product.price,
        final_price=product.price,
        currency='UZS',
    )
    result.add_explanation('Base Price', product.price, 'Product default price')

    # === PRIORITY 1: Customer-Specific Price ===
    cp_qs = CustomerSpecificPrice.objects.filter(
        company=company, product=product, is_active=True,
        min_quantity__lte=quantity,
    )
    if customer:
        cp_qs = cp_qs.filter(
            models.Q(customer=customer) | models.Q(customer__isnull=True)
        )
    cp_qs = cp_qs.filter(
        models.Q(start_date__isnull=True) | models.Q(start_date__lte=date)
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=date)
    ).order_by('-priority', 'price')

    cp = cp_qs.first()
    if cp:
        result.final_price = cp.price
        result.customer_price_id = cp.id
        result.applied_rule = 'customer_specific'
        result.discount_amount = product.price - cp.price
        result.add_explanation('Customer-Specific Price', cp.price,
                               f'{customer.name if customer else "Customer"} special')
        result.is_resolved = True

    # === PRIORITY 2: Price List Entry ===
    if not result.is_resolved:
        entries = PriceListEntry.objects.filter(
            price_list__company=company,
            product=product,
            is_active=True,
            min_quantity__lte=quantity,
            price_list__status='active',
        ).filter(
            models.Q(max_quantity__gte=quantity) | models.Q(max_quantity__isnull=True)
        ).filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=date)
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=date)
        ).select_related('price_list').order_by('-price_list__priority', 'price')

        if warehouse:
            entries = entries.filter(
                models.Q(price_list__warehouse__isnull=True) | models.Q(price_list__warehouse=warehouse)
            )
        if channel:
            entries = entries.filter(
                models.Q(price_list__channel='') | models.Q(price_list__channel=channel)
            )
        if customer:
            from crm.models import CustomerSegmentAssignment
            segment_ids = list(
                CustomerSegmentAssignment.objects.filter(
                    customer=customer
                ).values_list('segment_id', flat=True)
            )
            if segment_ids:
                entries = entries.filter(
                    models.Q(price_list__customer_segment__isnull=True) |
                    models.Q(price_list__customer_segment_id__in=segment_ids)
                )
            else:
                entries = entries.filter(price_list__customer_segment__isnull=True)

        entry = entries.first()
        if entry:
            result.final_price = entry.price
            result.price_list_name = entry.price_list.name
            result.price_list_entry_id = entry.id
            result.applied_rule = 'price_list'
            result.discount_amount = product.price - entry.price
            result.add_explanation('Price List', entry.price, entry.price_list.name)
            result.is_resolved = True

    # === PRIORITY 3: Active Promotion ===
    promos = Promotion.objects.filter(
        company=company, status='active',
    ).filter(
        models.Q(start_date__isnull=True) | models.Q(start_date__lte=date)
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=date)
    )

    if customer:
        promos = promos.filter(
            models.Q(applicable_customers__isnull=True) |
            models.Q(applicable_customers=customer)
        )
        from crm.models import CustomerSegmentAssignment
        segment_ids = list(
            CustomerSegmentAssignment.objects.filter(
                customer=customer
            ).values_list('segment_id', flat=True)
        )
        if segment_ids:
            promos = promos.filter(
                models.Q(applicable_segments__isnull=True) |
                models.Q(applicable_segments_id__in=segment_ids)
            )

    promos = promos.filter(
        models.Q(applicable_products__isnull=True) |
        models.Q(applicable_products=product)
    ).filter(
        models.Q(min_quantity__lte=quantity)
    ).order_by('-priority')

    for promo in promos:
        if promo.is_currently_valid:
            if promo.discount_type in ('percentage', 'fixed', 'fixed_price'):
                promo_discount = promo.calculate_discount(result.final_price)
                if promo_discount > 0:
                    result.final_price = max(result.final_price - promo_discount, Decimal('0'))
                    result.promo_name = promo.name
                    result.promo_discount = promo_discount
                    result.applied_rule = 'promotion'
                    result.discount_amount = product.price - result.final_price
                    result.add_explanation(
                        f'Promotion: {promo.name}',
                        result.final_price,
                        f'-{promo_discount} ({promo.get_discount_type_display()})'
                    )
                    result.is_resolved = True
                    break

    # === PRIORITY 4: Coupon ===
    if coupon_code:
        try:
            coupon = Coupon.objects.get(
                company=company, code=coupon_code.strip().upper(), is_active=True,
            )
            coupon_valid = coupon.is_currently_valid
            if coupon_valid:
                coupon_discount = coupon.calculate_discount(result.final_price)
                if coupon_discount > 0:
                    result.final_price = max(result.final_price - coupon_discount, Decimal('0'))
                    result.coupon_discount = coupon_discount
                    result.coupon_code = coupon.code
                    result.discount_amount = product.price - result.final_price
                    result.add_explanation(
                        f'Coupon: {coupon.code}',
                        result.final_price,
                        f'-{coupon_discount}'
                    )
        except Coupon.DoesNotExist:
            result.add_explanation('Coupon', result.final_price, f'{coupon_code} - invalid')

    result.final_price = result.final_price.quantize(Decimal('0.01'))
    result.discount_amount = (product.price - result.final_price).quantize(Decimal('0.01'))

    return result


def resolve_line_price(company, product, quantity=Decimal('1'), customer=None,
                       warehouse=None, channel='', date=None, coupon_code=None,
                       variant=None):
    price_result = resolve_price(
        company=company, product=product, customer=customer,
        quantity=quantity, warehouse=warehouse, channel=channel,
        date=date, variant=variant, coupon_code=coupon_code,
    )

    line_total = (price_result.final_price * quantity).quantize(Decimal('0.01'))

    return {
        'unit_price': price_result.final_price,
        'line_total': line_total,
        'discount': price_result.discount_amount * quantity,
        'currency': price_result.currency,
        'explanation': price_result.explanation,
        'price_list': price_result.price_list_name,
        'applied_rule': price_result.applied_rule,
        'promo_discount': price_result.promo_discount * quantity,
        'coupon_discount': price_result.coupon_discount * quantity,
        'result': price_result,
    }


def get_price_explanation_text(company, product, quantity=Decimal('1'), customer=None,
                               warehouse=None, channel='', date=None, coupon_code=None):
    result = resolve_price(
        company=company, product=product, customer=customer,
        quantity=quantity, warehouse=warehouse, channel=channel,
        date=date, coupon_code=coupon_code,
    )
    lines = []
    for exp in result.explanation:
        lines.append(f"{exp['label']}: {exp['price']}")
        if exp.get('detail'):
            lines.append(f"  -> {exp['detail']}")
    lines.append(f"Final Price: {result.final_price}")
    return '\n'.join(lines)
