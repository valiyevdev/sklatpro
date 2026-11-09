from datetime import timedelta
from decimal import Decimal
import time
import threading
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from typing import Dict, Any, Optional


class ContextBuilder:
    """Builds controlled data context for AI queries with caching."""

    _cache = {}
    _cache_time = {}
    _lock = threading.Lock()
    CACHE_TTL = 300

    def get_context(self, company, query, permissions=None):
        """Build context based on the user's question and available permissions."""
        cache_key = f"{company.pk}:{query[:50].lower().strip()}"
        now = time.time()
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and now - self._cache_time.get(cache_key, 0) < self.CACHE_TTL:
                return cached

        context = {'company_id': company.id, 'company_name': str(company)}
        
        context['sales'] = self._get_sales_context(company)
        context['inventory'] = self._get_inventory_context(company)
        context['finance'] = self._get_finance_context(company)
        context['customers'] = self._get_customer_context(company)
        context['orders'] = self._get_order_context(company)
        context['products'] = self._get_product_context(company)

        with self._lock:
            self._cache[cache_key] = context
            self._cache_time[cache_key] = time.time()

        return context
    
    def _get_sales_context(self, company):
        try:
            from sales.models import Sale, SaleItem
            from products.models import Product
            
            now = timezone.now()
            this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
            
            this_month = Sale.objects.filter(
                company=company, created_at__gte=this_month_start, status__in=['confirmed', 'completed']
            ).aggregate(
                total=Sum('total'),
                count=Count('id'),
                avg=Avg('total')
            )
            
            last_month = Sale.objects.filter(
                company=company, created_at__gte=last_month_start, created_at__lt=this_month_start,
                status__in=['confirmed', 'completed']
            ).aggregate(
                total=Sum('total'),
                count=Count('id'),
            )
            
            this_total = Decimal(str(this_month.get('total') or 0))
            last_total = Decimal(str(last_month.get('total') or 0))
            growth = 0.0
            if last_total > 0:
                growth = float((this_total - last_total) / last_total * 100)
            
            top_products = list(SaleItem.objects.filter(
                sale__company=company, sale__created_at__gte=this_month_start,
                sale__status__in=['confirmed', 'completed']
            ).values('product__name').annotate(
                qty=Sum('quantity'), revenue=Sum('total')
            ).order_by('-revenue')[:5])
            
            return {
                'this_month_total': float(this_total),
                'this_month_count': this_month.get('count', 0),
                'last_month_total': float(last_total),
                'growth_pct': round(growth, 1),
                'top_products': top_products,
            }
        except Exception:
            return {}
    
    def _get_inventory_context(self, company):
        try:
            from products.models import Product
            
            products = Product.objects.filter(company=company)
            total = products.count()
            low_stock = products.filter(status='active').count()
            
            out_of_stock = 0
            low_stock_list = []
            for p in products.filter(status='active')[:50]:
                qty = getattr(p, 'quantity', 0) or 0
                min_stock = getattr(p, 'minimum_stock', 0) or 0
                if qty <= 0:
                    out_of_stock += 1
                elif min_stock > 0 and qty <= min_stock:
                    low_stock_list.append({
                        'name': p.name,
                        'quantity': qty,
                        'min_stock': min_stock,
                    })
            
            return {
                'total_products': total,
                'out_of_stock': out_of_stock,
                'low_stock_count': len(low_stock_list),
                'low_stock_products': low_stock_list[:10],
            }
        except Exception:
            return {}
    
    def _get_finance_context(self, company):
        try:
            from finance.models import FinancialTransaction
            
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            income = FinancialTransaction.objects.filter(
                company=company, direction='income', created_at__gte=month_start
            ).aggregate(total=Sum('amount'))
            
            expenses = FinancialTransaction.objects.filter(
                company=company, direction='expense', created_at__gte=month_start
            ).aggregate(total=Sum('amount'))
            
            income_total = Decimal(str(income.get('total') or 0))
            expense_total = Decimal(str(expenses.get('total') or 0))
            profit = income_total - expense_total
            margin = 0.0
            if income_total > 0:
                margin = float(profit / income_total * 100)
            
            return {
                'month_income': float(income_total),
                'month_expenses': float(expense_total),
                'month_profit': float(profit),
                'margin_pct': round(margin, 1),
            }
        except Exception:
            return {}
    
    def _get_customer_context(self, company):
        try:
            from sales.models import Customer
            
            customers = Customer.objects.filter(company=company)
            total = customers.count()
            active = customers.filter(customer_status='active').count()
            vip = customers.filter(rfm_segment='Champions').count()
            high_debt = customers.filter(total_debt__gt=0).count()
            
            return {
                'total_customers': total,
                'active_customers': active,
                'vip_customers': vip,
                'high_debt_customers': high_debt,
            }
        except Exception:
            return {}
    
    def _get_order_context(self, company):
        try:
            from orders.models import Order
            
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            orders = Order.objects.filter(company=company, created_at__gte=month_start)
            total = orders.count()
            completed = orders.filter(status='completed').count()
            cancelled = orders.filter(status='cancelled').count()
            pending = orders.exclude(status__in=['completed', 'cancelled']).count()
            
            return {
                'month_orders': total,
                'completed': completed,
                'cancelled': cancelled,
                'pending': pending,
            }
        except Exception:
            return {}
    
    def _get_product_context(self, company):
        try:
            from products.models import Product
            
            products = Product.objects.filter(company=company)
            return {
                'total': products.count(),
                'active': products.filter(status='active').count(),
            }
        except Exception:
            return {}


# Singleton
context_builder = ContextBuilder()
