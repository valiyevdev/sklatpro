import logging
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count

from .models import AIInsight, AIRecommendation, AIForecast, AIUsageLog, AIBusinessHealth
from .analytics_engine import (
    anomaly_detector, demand_forecaster, smart_reorder,
    supplier_intelligence, customer_intelligence, profitability_analyzer,
    health_scorer,
)

logger = logging.getLogger(__name__)


class AutoInsightEngine:
    """Automatically generates insights and recommendations from business data."""

    def generate_all(self, company, user=None):
        """Run all insight generators and return a summary of what was created."""
        created = {'insights': 0, 'recommendations': 0}

        self._check_sales_anomalies(company, created)
        self._check_inventory_health(company, created)
        self._check_financial_health(company, created)
        self._check_reorder_needs(company, created)
        self._check_customer_segments(company, created)
        self._check_supplier_performance(company, created)
        self._check_forecast_warnings(company, created)
        self._update_health_score(company)

        return created

    def _check_sales_anomalies(self, company, created):
        try:
            anomalies = anomaly_detector.detect_sales_anomalies(company)
            if not anomalies:
                return
            existing = AIInsight.objects.filter(
                company=company, insight_type='anomaly', related_module='sales',
                created_at__date=timezone.now().date()
            ).count()
            if existing > 0:
                return

            for a in anomalies[:3]:
                direction = a.get('direction', 'anomaly')
                title = f"Sales {direction.title()}: ${a['amount']:,.0f} on {a['date']}"
                desc = (
                    f"Detected a sales {direction} on {a['date']}. "
                    f"Actual: ${a['amount']:,.2f}, Expected: ${a['expected']:,.2f}. "
                    f"Deviation: {a.get('deviation', 'N/A')} standard deviations."
                )
                AIInsight.objects.create(
                    company=company, insight_type='anomaly',
                    title=title, description=desc,
                    related_module='sales', priority='high',
                    confidence=0.85,
                    evidence={'anomaly_data': a},
                )
                created['insights'] += 1
        except Exception as e:
            logger.error(f"Sales anomaly check failed: {e}")

    def _check_inventory_health(self, company, created):
        try:
            from products.models import Product
            products = Product.objects.filter(company=company, status='active')
            out_of_stock = []
            low_stock = []
            for p in products[:200]:
                qty = getattr(p, 'quantity', 0) or 0
                min_s = getattr(p, 'minimum_stock', 0) or 0
                if qty <= 0:
                    out_of_stock.append(p)
                elif min_s > 0 and qty <= min_s:
                    low_stock.append(p)

            if out_of_stock and not AIInsight.objects.filter(
                company=company, insight_type='alert', related_module='inventory',
                title__startswith='Out of Stock', created_at__date=timezone.now().date()
            ).exists():
                names = ', '.join(p.name for p in out_of_stock[:5])
                AIInsight.objects.create(
                    company=company, insight_type='alert',
                    title=f'{len(out_of_stock)} Products Out of Stock',
                    description=f'{len(out_of_stock)} products have zero stock: {names}.',
                    related_module='inventory', priority='critical', confidence=1.0,
                )
                created['insights'] += 1

            if low_stock and not AIInsight.objects.filter(
                company=company, insight_type='alert', related_module='inventory',
                title__startswith='Low Stock', created_at__date=timezone.now().date()
            ).exists():
                names = ', '.join(p.name for p in low_stock[:5])
                AIInsight.objects.create(
                    company=company, insight_type='alert',
                    title=f'{len(low_stock)} Products Running Low',
                    description=f'{len(low_stock)} products are below minimum stock: {names}.',
                    related_module='inventory', priority='high', confidence=1.0,
                )
                created['insights'] += 1
        except Exception as e:
            logger.error(f"Inventory health check failed: {e}")

    def _check_financial_health(self, company, created):
        try:
            from finance.models import FinancialTransaction
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            income = float(FinancialTransaction.objects.filter(
                company=company, direction='income', created_at__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0)
            expense = float(FinancialTransaction.objects.filter(
                company=company, direction='expense', created_at__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0)

            if income > 0:
                margin = (income - expense) / income * 100
                if margin < 5 and not AIInsight.objects.filter(
                    company=company, insight_type='alert', related_module='finance',
                    title__startswith='Low Profit', created_at__date=timezone.now().date()
                ).exists():
                    AIInsight.objects.create(
                        company=company, insight_type='alert',
                        title=f'Low Profit Margin: {margin:.1f}%',
                        description=f'Monthly profit margin is only {margin:.1f}% (Income: ${income:,.2f}, Expenses: ${expense:,.2f}).',
                        related_module='finance', priority='high', confidence=1.0,
                    )
                    created['insights'] += 1
        except Exception as e:
            logger.error(f"Financial health check failed: {e}")

    def _check_reorder_needs(self, company, created):
        try:
            suggestions = smart_reorder.calculate(company)
            if not suggestions:
                return
            existing = AIRecommendation.objects.filter(
                company=company, category='restock', status='pending',
                created_at__date=timezone.now().date()
            ).count()
            if existing > 0:
                return

            for s in suggestions[:5]:
                AIRecommendation.objects.create(
                    company=company, category='restock',
                    title=f"Reorder {s['product_name']}",
                    description=(
                        f"Current stock: {s['current_stock']}, Min: {s['min_stock']}. "
                        f"Suggested order: {s['suggested_order_qty']} units."
                    ),
                    priority=s['urgency'],
                    confidence=0.9,
                    action_type='create_purchase_draft',
                    action_config={
                        'product_id': str(s['product_id']),
                        'quantity': s['suggested_order_qty'],
                        'product_name': s['product_name'],
                    },
                    related_module='inventory',
                )
                created['recommendations'] += 1
        except Exception as e:
            logger.error(f"Reorder check failed: {e}")

    def _check_customer_segments(self, company, created):
        try:
            customers = customer_intelligence.analyze(company)
            churned = [c for c in customers if c['segment'] == 'churned' and c['total_spent'] > 100]
            if churned and not AIRecommendation.objects.filter(
                company=company, category='customer', status='pending',
                title__startswith='Win-back', created_at__date=timezone.now().date()
            ).exists():
                names = ', '.join(c['customer_name'] for c in churned[:3])
                AIRecommendation.objects.create(
                    company=company, category='customer',
                    title=f'Win-back Campaign for {len(churned)} Lapsed Customers',
                    description=(
                        f'{len(churned)} high-value customers have not ordered in 90+ days: {names}. '
                        f'Total historical value: ${sum(c["total_spent"] for c in churned):,.2f}.'
                    ),
                    priority='medium',
                    confidence=0.75,
                    action_type='create_reminder',
                    related_module='crm',
                )
                created['recommendations'] += 1
        except Exception as e:
            logger.error(f"Customer segment check failed: {e}")

    def _check_supplier_performance(self, company, created):
        try:
            suppliers = supplier_intelligence.analyze(company)
            unreliable = [s for s in suppliers if s['on_time_rate'] < 70 and s['order_count'] >= 3]
            if unreliable and not AIRecommendation.objects.filter(
                company=company, category='supplier', status='pending',
                title__startswith='Review Supplier', created_at__date=timezone.now().date()
            ).exists():
                for s in unreliable[:2]:
                    AIRecommendation.objects.create(
                        company=company, category='supplier',
                        title=f"Review Supplier: {s['supplier_name']}",
                        description=(
                            f"On-time delivery rate: {s['on_time_rate']}% across {s['order_count']} orders. "
                            f"Total value: ${s['total_purchases']:,.2f}."
                        ),
                        priority='medium',
                        confidence=0.8,
                        action_type='create_task',
                        related_module='purchases',
                    )
                    created['recommendations'] += 1
        except Exception as e:
            logger.error(f"Supplier performance check failed: {e}")

    def _check_forecast_warnings(self, company, created):
        try:
            forecasts = demand_forecaster.forecast_all(company, 30)
            stockouts = [f for f in forecasts if f.get('days_until_stockout') is not None and f['days_until_stockout'] <= 7]
            if stockouts and not AIRecommendation.objects.filter(
                company=company, category='restock', status='pending',
                title__startswith='Urgent: Stockout', created_at__date=timezone.now().date()
            ).exists():
                names = ', '.join(f['product_name'] for f in stockouts[:3])
                AIRecommendation.objects.create(
                    company=company, category='restock',
                    title=f'Urgent: {len(stockouts)} Products at Risk of Stockout',
                    description=(
                        f'{len(stockouts)} products will run out within 7 days: {names}. '
                        'Immediate reorder action required.'
                    ),
                    priority='critical',
                    confidence=0.9,
                    action_type='create_purchase_draft',
                    related_module='inventory',
                )
                created['recommendations'] += 1
        except Exception as e:
            logger.error(f"Forecast warning check failed: {e}")

    def _update_health_score(self, company):
        try:
            health = health_scorer.calculate(company)
            AIBusinessHealth.objects.update_or_create(
                company=company,
                defaults={
                    'overall_score': health['overall_score'],
                    'overall_status': health['overall_status'],
                    'sales_score': health['sales_score'],
                    'inventory_score': health['inventory_score'],
                    'finance_score': health['finance_score'],
                    'customer_score': health['customer_score'],
                    'operations_score': health['operations_score'],
                },
            )
        except Exception as e:
            logger.error(f"Health score update failed: {e}")

    def prune_conversations(self, company, max_per_user=50):
        """Archive old conversations to manage memory."""
        try:
            from .models import AIConversation
            for user_id in AIConversation.objects.filter(
                company=company, is_active=True
            ).values_list('user_id', flat=True).distinct():
                convs = AIConversation.objects.filter(
                    company=company, user_id=user_id, is_active=True
                ).order_by('-updated_at')
                if convs.count() > max_per_user:
                    old_ids = convs[max_per_user:].values_list('pk', flat=True)
                    AIConversation.objects.filter(pk__in=list(old_ids)).update(is_active=False)
        except Exception as e:
            logger.error(f"Conversation pruning failed: {e}")


auto_insight_engine = AutoInsightEngine()
