from django.db.models import Sum, Count, Avg, F, Q, Value, CharField, Max, Min, OuterRef, Subquery
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay, TruncQuarter, Coalesce
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import math


def get_date_range(request, default_days=30):
    preset = request.GET.get('preset', '')
    today = timezone.now().date()
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    if start_date and end_date:
        try:
            return (datetime.strptime(start_date, '%Y-%m-%d').date(),
                    datetime.strptime(end_date, '%Y-%m-%d').date())
        except ValueError:
            pass

    presets = {
        'today': (today, today),
        'yesterday': (today - timedelta(days=1), today - timedelta(days=1)),
        'this_week': (today - timedelta(days=today.weekday()), today),
        'last_week': (today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 1)),
        'this_month': (today.replace(day=1), today),
        'last_month': ((today.replace(day=1) - timedelta(days=1)).replace(day=1),
                       today.replace(day=1) - timedelta(days=1)),
        'this_quarter': (today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1), today),
        'last_quarter': (today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1) - timedelta(days=1),
                         today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1) - timedelta(days=1)),
        'this_year': (today.replace(month=1, day=1), today),
        'last_year': (today.replace(year=today.year - 1, month=1, day=1),
                      today.replace(year=today.year - 1, month=12, day=31)),
    }
    if preset in presets:
        return presets[preset]
    return (today - timedelta(days=default_days), today)


def get_prev_date_range(start_date, end_date):
    delta = end_date - start_date
    return (start_date - timedelta(days=delta.days + 1), start_date - timedelta(days=1))


def get_company(request):
    company = getattr(request.user, 'company', None)
    if company:
        return company
    if request.user.is_superuser:
        from django.contrib import messages as _msgs
        _msgs.warning(request, 'Superuser: no company assigned. Showing first company data.')
        from users.models import Company
        return Company.objects.first()
    return None


def safe_div(a, b):
    if b is None or b == 0:
        return Decimal('0')
    return Decimal(str(a)) / Decimal(str(b))


def safe_pct(part, total):
    if total is None or total == 0:
        return Decimal('0')
    return (Decimal(str(part)) / Decimal(str(total))) * Decimal('100')


def fmt_number(n):
    if n is None:
        return '0'
    return f'{n:,.0f}'


def fmt_currency(n, symbol=''):
    if n is None:
        return f'{symbol}0'
    return f'{symbol}{n:,.0f}'


def fmt_pct(n):
    if n is None:
        return '0%'
    return f'{n:.1f}%'
