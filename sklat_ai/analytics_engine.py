import logging
from decimal import Decimal
from datetime import timedelta
from collections import defaultdict
from django.db.models import Sum, Count, Avg, F, Q, StdDev
from django.utils import timezone

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects anomalies in sales, inventory, and financial data."""

    def detect_sales_anomalies(self, company, lookback_days=30):
        from sales.models import Sale
        now = timezone.now()
        end = now
        start = now - timedelta(days=lookback_days)
        daily_sales = list(
            Sale.objects.filter(company=company, date__gte=start.date(), date__lte=end.date())
            .values('date')
            .annotate(daily_total=Sum('total'), daily_count=Count('id'))
            .order_by('date')
        )
        if len(daily_sales) < 3:
            return []
        amounts = [float(d['daily_total'] or 0) for d in daily_sales]
        mean = sum(amounts) / len(amounts)
        variance = sum((a - mean) ** 2 for a in amounts) / len(amounts)
        std = variance ** 0.5 if variance > 0 else 0
        anomalies = []
        for i, d in enumerate(daily_sales):
            val = float(d['daily_total'] or 0)
            if std > 0 and abs(val - mean) > 2 * std:
                direction = 'spike' if val > mean else 'drop'
                anomalies.append({
                    'date': str(d['date']),
                    'amount': val,
                    'expected': round(mean, 2),
                    'deviation': round((val - mean) / std, 2) if std else 0,
                    'direction': direction,
                    'count': d['daily_count'],
                })
        return anomalies

    def detect_inventory_anomalies(self, company):
        from products.models import Product
        products = Product.objects.filter(company=company, status='active')
        anomalies = []
        for p in products[:200]:
            qty = getattr(p, 'quantity', 0) or 0
            min_stock = getattr(p, 'minimum_stock', 0) or 0
            max_stock = getattr(p, 'max_stock', 0) or 0
            if qty <= 0:
                anomalies.append({'product': p.name, 'type': 'out_of_stock', 'quantity': qty, 'min_stock': min_stock})
            elif min_stock > 0 and qty <= min_stock:
                anomalies.append({'product': p.name, 'type': 'low_stock', 'quantity': qty, 'min_stock': min_stock})
            elif max_stock > 0 and qty > max_stock * 2:
                anomalies.append({'product': p.name, 'type': 'overstock', 'quantity': qty, 'max_stock': max_stock})
        return anomalies

    def detect_financial_anomalies(self, company, lookback_days=30):
        from finance.models import FinancialTransaction
        now = timezone.now()
        start = now - timedelta(days=lookback_days)
        daily = list(
            FinancialTransaction.objects.filter(
                company=company, direction='income', created_at__gte=start
            ).values('created_at__date')
            .annotate(daily_total=Sum('amount'))
            .order_by('created_at__date')
        )
        if len(daily) < 3:
            return []
        amounts = [float(d['daily_total'] or 0) for d in daily]
        mean = sum(amounts) / len(amounts)
        variance = sum((a - mean) ** 2 for a in amounts) / len(amounts)
        std = variance ** 0.5 if variance > 0 else 0
        anomalies = []
        for d in daily:
            val = float(d['daily_total'] or 0)
            if std > 0 and abs(val - mean) > 2 * std:
                anomalies.append({
                    'date': str(d['created_at__date']),
                    'amount': val,
                    'expected': round(mean, 2),
                    'direction': 'spike' if val > mean else 'drop',
                })
        return anomalies


class DemandForecaster:
    """Forecasts product demand using historical sales data."""

    def forecast_product(self, company, product_id, horizon_days=30):
        from sales.models import SaleItem
        from products.models import Product
        from inventory.models import StockLevel
        product = Product.objects.filter(company=company, pk=product_id).first()
        if not product:
            return None
        now = timezone.now()
        lookback = now - timedelta(days=90)
        daily = list(
            SaleItem.objects.filter(
                sale__company=company, product_id=product_id, sale__date__gte=lookback.date()
            ).values('sale__date')
            .annotate(daily_qty=Sum('quantity'))
            .order_by('sale__date')
        )
        if not daily:
            return None
        amounts = [float(d['daily_qty'] or 0) for d in daily]
        avg_daily = sum(amounts) / len(amounts) if amounts else 0
        if len(amounts) >= 7:
            recent = amounts[-7:]
            older = amounts[:-7] if len(amounts) > 7 else amounts
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older) if older else recent_avg
            trend_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
            if trend_pct > 10:
                trend = 'increasing'
            elif trend_pct < -10:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
            trend_pct = 0
        predicted = avg_daily * horizon_days
        stock = StockLevel.objects.filter(company=company, product=product).first()
        current_qty = stock.quantity if stock else getattr(product, 'quantity', 0) or 0
        days_until_stockout = int(current_qty / avg_daily) if avg_daily > 0 else None
        return {
            'product_id': product_id,
            'product_name': product.name,
            'horizon_days': horizon_days,
            'avg_daily_demand': round(avg_daily, 2),
            'predicted_demand': round(predicted, 0),
            'trend': trend,
            'trend_pct': round(trend_pct, 1),
            'current_stock': current_qty,
            'days_until_stockout': days_until_stockout,
            'data_days': len(daily),
        }

    def forecast_all(self, company, horizon_days=30):
        from products.models import Product
        products = Product.objects.filter(company=company, status='active')
        forecasts = []
        for p in products[:100]:
            f = self.forecast_product(company, p.pk, horizon_days)
            if f:
                forecasts.append(f)
        return sorted(forecasts, key=lambda x: x.get('days_until_stockout') or 9999)


class SmartReorder:
    """Calculates smart reorder suggestions."""

    def calculate(self, company):
        from products.models import Product
        from inventory.models import StockLevel
        from sales.models import SaleItem
        now = timezone.now()
        products = Product.objects.filter(company=company, status='active')
        suggestions = []
        for p in products[:200]:
            qty = getattr(p, 'quantity', 0) or 0
            min_stock = getattr(p, 'minimum_stock', 0) or 0
            if min_stock <= 0 or qty > min_stock:
                continue
            lookback = now - timedelta(days=60)
            avg_daily = SaleItem.objects.filter(
                sale__company=company, product=p, sale__date__gte=lookback.date()
            ).aggregate(avg=Avg('quantity'))['avg'] or 1
            lead_time = 7
            safety_stock = int(avg_daily * 3)
            reorder_qty = int(avg_daily * (lead_time + safety_stock)) - qty
            if reorder_qty < 1:
                reorder_qty = 1
            suggestions.append({
                'product_id': p.pk,
                'product_name': p.name,
                'current_stock': qty,
                'min_stock': min_stock,
                'avg_daily_demand': round(avg_daily, 2),
                'suggested_order_qty': reorder_qty,
                'urgency': 'critical' if qty == 0 else 'high',
            })
        return sorted(suggestions, key=lambda x: x['current_stock'])


class SupplierIntelligence:
    """Analyzes supplier performance."""

    def analyze(self, company, lookback_days=90):
        from purchases.models import Purchase, PurchaseItem, Supplier
        now = timezone.now()
        start = now - timedelta(days=lookback_days)
        suppliers = Supplier.objects.filter(company=company)
        results = []
        for s in suppliers[:50]:
            purchases = Purchase.objects.filter(
                company=company, supplier=s, order_date__gte=start.date()
            )
            agg = purchases.aggregate(
                total_value=Sum('total'), count=Count('id'), avg_value=Avg('total')
            )
            on_time = purchases.filter(expected_date__lte=timezone.now().date(), status='received').count()
            total_received = purchases.filter(status='received').count()
            reliability = (on_time / total_received * 100) if total_received > 0 else 0
            results.append({
                'supplier_id': s.pk,
                'supplier_name': s.name,
                'total_purchases': float(agg['total_value'] or 0),
                'order_count': agg['count'] or 0,
                'avg_order_value': float(agg['avg_value'] or 0),
                'on_time_rate': round(reliability, 1),
                'current_balance': float(getattr(s, 'balance', 0) or 0),
            })
        return sorted(results, key=lambda x: x['total_purchases'], reverse=True)


class CustomerIntelligence:
    """Analyzes customer behavior and segments."""

    def analyze(self, company, lookback_days=90):
        from sales.models import Sale, Customer
        now = timezone.now()
        start = now - timedelta(days=lookback_days)
        customers = Customer.objects.filter(company=company)
        results = []
        for c in customers[:200]:
            sales = Sale.objects.filter(
                company=company, customer=c, date__gte=start.date()
            )
            agg = sales.aggregate(
                total_spent=Sum('total'), order_count=Count('id'), avg_order=Avg('total')
            )
            last_sale = sales.order_by('-date').first()
            days_since = (now.date() - last_sale.date).days if last_sale else 999
            if days_since <= 30:
                segment = 'active'
            elif days_since <= 90:
                segment = 'at_risk'
            else:
                segment = 'churned'
            results.append({
                'customer_id': c.pk,
                'customer_name': c.name,
                'total_spent': float(agg['total_spent'] or 0),
                'order_count': agg['order_count'] or 0,
                'avg_order': float(agg['avg_order'] or 0),
                'days_since_last_order': days_since,
                'segment': segment,
                'debt': float(getattr(c, 'total_debt', 0) or 0),
            })
        return sorted(results, key=lambda x: x['total_spent'], reverse=True)


class ProfitabilityAnalyzer:
    """Analyzes product and category profitability."""

    def analyze_products(self, company, lookback_days=90):
        from sales.models import SaleItem
        from purchases.models import PurchaseItem
        now = timezone.now()
        start = now - timedelta(days=lookback_days)
        sales = (
            SaleItem.objects.filter(sale__company=company, sale__date__gte=start.date())
            .values('product__name')
            .annotate(revenue=Sum('total'), units=Sum('quantity'))
        )
        purchases = {
            r['product__name']: r['cost']
            for r in PurchaseItem.objects.filter(
                purchase__company=company, purchase__order_date__gte=start.date()
            ).values('product__name').annotate(cost=Sum('total'))
        }
        results = []
        for s in sales:
            name = s['product__name']
            revenue = float(s['revenue'] or 0)
            cost = float(purchases.get(name, 0))
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else 0
            results.append({
                'product': name,
                'revenue': revenue,
                'cost': cost,
                'profit': profit,
                'margin': round(margin, 1),
                'units_sold': s['units'] or 0,
            })
        return sorted(results, key=lambda x: x['profit'], reverse=True)


class HealthScorer:
    """Calculates overall business health score."""

    def calculate(self, company):
        try:
            from sales.models import Sale
            from products.models import Product
            from finance.models import FinancialTransaction
            from sales.models import Customer
            
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_month = (month_start - timedelta(days=1)).replace(day=1)

            sales_this = Sale.objects.filter(
                company=company, created_at__gte=month_start, status__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total'), count=Count('id'))
            sales_prev = Sale.objects.filter(
                company=company, created_at__gte=prev_month, created_at__lt=month_start,
                status__in=['confirmed', 'completed']
            ).aggregate(total=Sum('total'))

            this_total = float(sales_this.get('total') or 0)
            prev_total = float(sales_prev.get('total') or 1)
            sales_growth = ((this_total - prev_total) / prev_total * 100) if prev_total > 0 else 0

            if sales_growth > 10:
                sales_score = min(100, 70 + sales_growth)
            elif sales_growth > 0:
                sales_score = 60 + sales_growth * 2
            elif sales_growth > -10:
                sales_score = 50 + sales_growth * 2
            else:
                sales_score = max(0, 40 + sales_growth)

            products = Product.objects.filter(company=company, status='active')
            total_products = products.count()
            low_stock = 0
            out_of_stock = 0
            for p in products[:200]:
                qty = getattr(p, 'quantity', 0) or 0
                min_s = getattr(p, 'minimum_stock', 0) or 0
                if qty <= 0:
                    out_of_stock += 1
                elif min_s > 0 and qty <= min_s:
                    low_stock += 1
            
            if total_products > 0:
                inventory_score = 100 - (low_stock / total_products * 60) - (out_of_stock / total_products * 40)
            else:
                inventory_score = 80
            inventory_score = max(0, min(100, inventory_score))

            income = FinancialTransaction.objects.filter(
                company=company, direction='income', created_at__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0
            expense = FinancialTransaction.objects.filter(
                company=company, direction='expense', created_at__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0
            income = float(income)
            expense = float(expense)
            margin = ((income - expense) / income * 100) if income > 0 else 0
            finance_score = min(100, max(0, 50 + margin))

            try:
                total_custs = Customer.objects.filter(company=company).count()
                active_custs = Customer.objects.filter(
                    company=company, customer_status='active'
                ).count()
                retention = (active_custs / total_custs * 100) if total_custs > 0 else 0
                customer_score = min(100, max(0, retention))
            except Exception:
                customer_score = 50

            operations_score = (sales_score + inventory_score + finance_score) / 3

            overall = (sales_score * 0.25 + inventory_score * 0.20 + finance_score * 0.25 + customer_score * 0.15 + operations_score * 0.15)
            if overall >= 70:
                status = 'healthy'
            elif overall >= 40:
                status = 'watch'
            else:
                status = 'critical'

            return {
                'overall_score': round(overall, 1),
                'overall_status': status,
                'sales_score': round(sales_score, 1),
                'inventory_score': round(inventory_score, 1),
                'finance_score': round(finance_score, 1),
                'customer_score': round(customer_score, 1),
                'operations_score': round(operations_score, 1),
            }
        except Exception:
            return {
                'overall_score': 50,
                'overall_status': 'watch',
                'sales_score': 50,
                'inventory_score': 50,
                'finance_score': 50,
                'customer_score': 50,
                'operations_score': 50,
            }


anomaly_detector = AnomalyDetector()
demand_forecaster = DemandForecaster()
smart_reorder = SmartReorder()
supplier_intelligence = SupplierIntelligence()
customer_intelligence = CustomerIntelligence()
profitability_analyzer = ProfitabilityAnalyzer()
health_scorer = HealthScorer()
