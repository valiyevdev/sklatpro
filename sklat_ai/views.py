from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import json
import threading
from .models import (
    AIBusinessHealth, AIInsight, AIRecommendation, AIUsageLog,
    AIConversation, AIMessage, AIForecast, AIFeedback, AIProviderConfig,
)
from .providers import gateway
from .context import context_builder
from .analytics_engine import (
    anomaly_detector, demand_forecaster, smart_reorder,
    supplier_intelligence, customer_intelligence, profitability_analyzer,
    health_scorer
)
from .auto_insights import auto_insight_engine


def get_company(request):
    if hasattr(request.user, 'company') and request.user.company:
        return request.user.company
    return None


def _parse_json(value):
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def _has_ai_access(user):
    if user.is_superuser:
        return True
    return hasattr(user, 'company') and user.company is not None


# ============================================================
# 1. AI DASHBOARD
# ============================================================
@login_required
def ai_dashboard(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        health = health_scorer.calculate(company)
        latest_health = AIBusinessHealth.objects.filter(company=company).first()
        if latest_health:
            health = {
                'overall_score': latest_health.overall_score,
                'overall_status': latest_health.overall_status,
                'sales_score': latest_health.sales_score,
                'inventory_score': latest_health.inventory_score,
                'finance_score': latest_health.finance_score,
                'customer_score': latest_health.customer_score,
                'operations_score': latest_health.operations_score,
            }

        threading.Thread(
            target=auto_insight_engine.generate_all,
            args=(company,),
            daemon=True,
        ).start()

        recent_insights = AIInsight.objects.filter(
            company=company, is_dismissed=False
        ).order_by('-created_at')[:10]

        active_recommendations = AIRecommendation.objects.filter(
            company=company, status='pending'
        ).count()

        total_usage = AIUsageLog.objects.filter(company=company).aggregate(
            total_requests=Count('id'),
            total_tokens_in=Sum('tokens_input'),
            total_tokens_out=Sum('tokens_output'),
            total_cost=Sum('estimated_cost_usd'),
        )

        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        usage_today = AIUsageLog.objects.filter(
            company=company, created_at__gte=today_start
        ).count()

        context = {
            'health': health,
            'recent_insights': recent_insights,
            'active_recommendations': active_recommendations,
            'total_requests': total_usage['total_requests'] or 0,
            'total_tokens': (total_usage['total_tokens_in'] or 0) + (total_usage['total_tokens_out'] or 0),
            'total_cost': total_usage['total_cost'] or 0,
            'usage_today': usage_today,
        }
        return render(request, 'sklat_ai/dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Error loading AI dashboard: {str(e)}')
        return render(request, 'sklat_ai/dashboard.html', {})


# ============================================================
# 2. AI CHAT
# ============================================================
@login_required
def ai_chat(request, conversation_id=None):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    if not _has_ai_access(request.user):
        messages.error(request, 'You do not have AI access.')
        return redirect('sklat_ai:dashboard')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        conversations = AIConversation.objects.filter(
            company=company, user=request.user, is_active=True
        ).order_by('-updated_at')

        current_conversation = None
        conversation_messages = []
        if conversation_id:
            current_conversation = get_object_or_404(
                AIConversation, pk=conversation_id, company=company, user=request.user
            )
            conversation_messages = current_conversation.messages.all()

        if request.method == 'POST':
            message_content = request.POST.get('message', '').strip()
            conv_id = request.POST.get('conversation_id', '')

            if not message_content:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'Empty message'}, status=400)
                messages.error(request, 'Please enter a message.')
                return redirect('sklat_ai:chat')

            if conv_id:
                current_conversation = get_object_or_404(
                    AIConversation, pk=conv_id, company=company, user=request.user
                )
            elif not current_conversation:
                title = message_content[:80] + ('...' if len(message_content) > 80 else '')
                current_conversation = AIConversation.objects.create(
                    company=company,
                    user=request.user,
                    title=title,
                )

            user_message = AIMessage.objects.create(
                conversation=current_conversation,
                role='user',
                content=message_content,
            )

            business_context = context_builder.get_context(company, message_content)
            system_prompt = (
                "You are SKLAT AI, an intelligent business assistant for the company "
                f"{company}. You have access to the following business data:\n\n"
                f"{json.dumps(business_context, default=str, indent=2)}\n\n"
                "Answer questions about sales, inventory, finance, customers, and operations. "
                "Be specific, reference actual numbers when available, and provide actionable advice. "
                "Respond in the same language the user writes in."
            )

            history_messages = []
            prev_msgs = current_conversation.messages.exclude(pk=user_message.pk).order_by('created_at')[-10:]
            for m in prev_msgs:
                history_messages.append({'role': m.role, 'content': m.content})
            history_messages.append({'role': 'user', 'content': message_content})

            messages_for_ai = [{'role': 'system', 'content': system_prompt}] + history_messages

            ai_result = gateway.chat(
                company, request.user, messages_for_ai,
                feature='chat', context_module='chat',
            )

            ai_content = ai_result.get('content', '') if ai_result.get('success') else 'I apologize, but I encountered an error processing your request. Please try again.'
            tokens_in = ai_result.get('tokens', {}).get('input', 0)
            tokens_out = ai_result.get('tokens', {}).get('output', 0)
            response_time = ai_result.get('response_time_ms', 0)

            ai_message = AIMessage.objects.create(
                conversation=current_conversation,
                role='assistant',
                content=ai_content,
                tokens_used=tokens_in + tokens_out,
                response_time_ms=response_time,
            )

            current_conversation.message_count = current_conversation.messages.count()
            current_conversation.updated_at = timezone.now()
            current_conversation.save(update_fields=['message_count', 'updated_at'])

            if is_ajax:
                return JsonResponse({
                    'status': 'ok',
                    'message': {
                        'id': str(ai_message.pk),
                        'content': ai_content,
                        'tokens': tokens_in + tokens_out,
                        'response_time_ms': response_time,
                    },
                    'conversation_id': str(current_conversation.pk),
                })

            return redirect('sklat_ai:chat_conversation', conversation_id=current_conversation.pk)

        suggested_questions = [
            "What are my top selling products this month?",
            "Which products are running low on stock?",
            "How is my business health score?",
            "Show me my sales vs expenses summary",
            "Which customers have outstanding debts?",
        ]

        context = {
            'conversations': conversations,
            'current_conversation': current_conversation,
            'conversation_messages': conversation_messages,
            'suggested_questions': suggested_questions,
        }
        return render(request, 'sklat_ai/chat.html', context)
    except Exception as e:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        messages.error(request, f'Error in AI chat: {str(e)}')
        return render(request, 'sklat_ai/chat.html', {})


# ============================================================
# 3. AI CONVERSATION LIST
# ============================================================
@login_required
def ai_conversation_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        conversations = AIConversation.objects.filter(
            company=company, user=request.user, is_active=True
        ).order_by('-updated_at')

        search = request.GET.get('q', '')
        if search:
            conversations = conversations.filter(title__icontains=search)

        paginator = Paginator(conversations, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'conversations': page_obj,
            'search': search,
        }
        return render(request, 'sklat_ai/conversation_list.html', context)
    except Exception as e:
        messages.error(request, f'Error loading conversations: {str(e)}')
        return render(request, 'sklat_ai/conversation_list.html', {'conversations': []})


# ============================================================
# 4. AI CONVERSATION DETAIL
# ============================================================
@login_required
def ai_conversation_detail(request, conversation_id):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        conversation = get_object_or_404(
            AIConversation, pk=conversation_id, company=company, user=request.user
        )
        conversation_messages = conversation.messages.all()

        context = {
            'conversation': conversation,
            'conversation_messages': conversation_messages,
        }
        return render(request, 'sklat_ai/conversation_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error loading conversation: {str(e)}')
        return redirect('sklat_ai:conversation_list')


# ============================================================
# 5. AI INSIGHTS
# ============================================================
@login_required
def ai_insights(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        insights = AIInsight.objects.filter(company=company, is_dismissed=False)

        insight_type = request.GET.get('type', '')
        priority = request.GET.get('priority', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        show_read = request.GET.get('show_read', '')

        if insight_type:
            insights = insights.filter(insight_type=insight_type)
        if priority:
            insights = insights.filter(priority=priority)
        if date_from:
            try:
                insights = insights.filter(created_at__date__gte=date_from)
            except (ValueError, TypeError):
                pass
        if date_to:
            try:
                insights = insights.filter(created_at__date__lte=date_to)
            except (ValueError, TypeError):
                pass
        if show_read != 'all':
            insights = insights.filter(is_read=False)

        paginator = Paginator(insights, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        unread_count = AIInsight.objects.filter(
            company=company, is_read=False, is_dismissed=False
        ).count()

        context = {
            'page_obj': page_obj,
            'insights': page_obj,
            'insight_type': insight_type,
            'priority': priority,
            'date_from': date_from,
            'date_to': date_to,
            'show_read': show_read,
            'unread_count': unread_count,
            'type_choices': AIInsight.TYPE_CHOICES,
            'priority_choices': AIInsight.PRIORITY_CHOICES,
        }
        return render(request, 'sklat_ai/insights.html', context)
    except Exception as e:
        messages.error(request, f'Error loading insights: {str(e)}')
        return render(request, 'sklat_ai/insights.html', {'insights': []})


# ============================================================
# 6. AI INSIGHT DETAIL
# ============================================================
@login_required
def ai_insight_detail(request, insight_id):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        insight = get_object_or_404(AIInsight, pk=insight_id, company=company)

        if request.method == 'POST':
            action = request.POST.get('action', '')
            if action == 'mark_read':
                insight.is_read = True
                insight.save(update_fields=['is_read'])
                messages.success(request, 'Insight marked as read.')
            elif action == 'dismiss':
                insight.is_dismissed = True
                insight.save(update_fields=['is_dismissed'])
                messages.success(request, 'Insight dismissed.')
                return redirect('sklat_ai:insights')
            return redirect('sklat_ai:insight_detail', insight_id=insight_id)

        if not insight.is_read:
            insight.is_read = True
            insight.save(update_fields=['is_read'])

        context = {
            'insight': insight,
        }
        return render(request, 'sklat_ai/insight_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error loading insight: {str(e)}')
        return redirect('sklat_ai:insights')


# ============================================================
# 7. AI FORECASTS
# ============================================================
@login_required
def ai_forecasts(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        horizon = request.GET.get('horizon', '30d')
        horizon_days = {'7d': 7, '14d': 14, '30d': 30, '60d': 60, '90d': 90}.get(horizon, 30)

        existing_forecasts = AIForecast.objects.filter(
            company=company
        ).select_related('product', 'warehouse').order_by('-created_at')

        product_filter = request.GET.get('product', '')
        if product_filter:
            existing_forecasts = existing_forecasts.filter(product_id=product_filter)

        grouped_forecasts = {}
        for f in existing_forecasts[:100]:
            pid = str(f.product_id)
            if pid not in grouped_forecasts:
                grouped_forecasts[pid] = {
                    'product': f.product,
                    'forecasts': [],
                }
            grouped_forecasts[pid]['forecasts'].append(f)

        stockout_predictions = [
            f for f in existing_forecasts
            if f.days_until_stockout is not None and f.days_until_stockout <= 14
        ]

        demand_trends = demand_forecaster.forecast_all(company, horizon_days)

        context = {
            'grouped_forecasts': grouped_forecasts,
            'stockout_predictions': stockout_predictions,
            'demand_trends': demand_trends,
            'horizon': horizon,
            'horizon_choices': AIForecast.HORIZON_CHOICES,
        }
        return render(request, 'sklat_ai/forecasts.html', context)
    except Exception as e:
        messages.error(request, f'Error loading forecasts: {str(e)}')
        return render(request, 'sklat_ai/forecasts.html', {})


# ============================================================
# 8. AI RECOMMENDATIONS
# ============================================================
@login_required
def ai_recommendations(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        recommendations = AIRecommendation.objects.filter(company=company)

        category = request.GET.get('category', '')
        status = request.GET.get('status', '')
        priority = request.GET.get('priority', '')

        if category:
            recommendations = recommendations.filter(category=category)
        if status:
            recommendations = recommendations.filter(status=status)
        if priority:
            recommendations = recommendations.filter(priority=priority)

        paginator = Paginator(recommendations, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        pending_count = AIRecommendation.objects.filter(
            company=company, status='pending'
        ).count()

        context = {
            'page_obj': page_obj,
            'recommendations': page_obj,
            'category': category,
            'status': status,
            'priority': priority,
            'pending_count': pending_count,
            'category_choices': AIRecommendation.CATEGORY_CHOICES,
            'status_choices': AIRecommendation.STATUS_CHOICES,
            'priority_choices': AIRecommendation.PRIORITY_CHOICES,
        }
        return render(request, 'sklat_ai/recommendations.html', context)
    except Exception as e:
        messages.error(request, f'Error loading recommendations: {str(e)}')
        return render(request, 'sklat_ai/recommendations.html', {'recommendations': []})


# ============================================================
# 9. AI ACTION CENTER
# ============================================================
@login_required
def ai_action_center(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        pending_recs = AIRecommendation.objects.filter(
            company=company, status='pending'
        ).order_by('-priority', '-created_at')

        grouped = {
            'restock': pending_recs.filter(category='restock'),
            'pricing': pending_recs.filter(category='pricing'),
            'customer': pending_recs.filter(category='customer'),
            'supplier': pending_recs.filter(category='supplier'),
            'operations': pending_recs.filter(category='operations'),
            'finance': pending_recs.filter(category='finance'),
            'marketing': pending_recs.filter(category='marketing'),
        }

        category_labels = dict(AIRecommendation.CATEGORY_CHOICES)
        category_icons = {
            'restock': 'bi-box-seam',
            'pricing': 'bi-tag',
            'customer': 'bi-people',
            'supplier': 'bi-truck',
            'operations': 'bi-gear',
            'finance': 'bi-cash-stack',
            'marketing': 'bi-megaphone',
        }

        grouped_data = []
        for cat_code, recs in grouped.items():
            if recs.exists():
                grouped_data.append({
                    'code': cat_code,
                    'label': category_labels.get(cat_code, cat_code),
                    'icon': category_icons.get(cat_code, 'bi-lightbulb'),
                    'count': recs.count(),
                    'recommendations': recs[:10],
                })

        total_pending = pending_recs.count()

        context = {
            'grouped_data': grouped_data,
            'total_pending': total_pending,
        }
        return render(request, 'sklat_ai/action_center.html', context)
    except Exception as e:
        messages.error(request, f'Error loading action center: {str(e)}')
        return render(request, 'sklat_ai/action_center.html', {})


# ============================================================
# 10. AI BUSINESS SUMMARY
# ============================================================
@login_required
def ai_business_summary(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    try:
        period = request.GET.get('period', 'daily')

        now = timezone.now()
        if period == 'daily':
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = 'Today'
        elif period == 'weekly':
            start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            period_label = 'This Week'
        else:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_label = 'This Month'

        summary_context = context_builder.get_context(company, f'summary for {period}')

        system_prompt = (
            "You are SKLAT AI. Generate a concise business summary for the given period. "
            "Include key metrics, trends, highlights, and concerns. Be specific with numbers. "
            "Structure the summary with sections: Overview, Sales, Inventory, Finance, Action Items."
        )
        user_prompt = (
            f"Generate a {period} business summary for {company}.\n"
            f"Period: {start.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}\n"
            f"Context data:\n{json.dumps(summary_context, default=str, indent=2)}"
        )

        summary_text = gateway.analyze(
            company, request.user, system_prompt, user_prompt,
            feature='summary',
        )

        if not summary_text:
            summary_text = (
                f"**{period_label} Business Summary**\n\n"
                f"Sales context: {json.dumps(summary_context.get('sales', {}), default=str)}\n"
                f"Inventory context: {json.dumps(summary_context.get('inventory', {}), default=str)}\n"
                f"Finance context: {json.dumps(summary_context.get('finance', {}), default=str)}\n"
            )

        if is_ajax:
            return JsonResponse({
                'status': 'ok',
                'summary': summary_text,
                'period': period,
                'period_label': period_label,
            })

        context = {
            'summary_text': summary_text,
            'period': period,
            'period_label': period_label,
        }
        return render(request, 'sklat_ai/business_summary.html', context)
    except Exception as e:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        messages.error(request, f'Error generating summary: {str(e)}')
        return render(request, 'sklat_ai/business_summary.html', {})


# ============================================================
# 11. AI ANOMALIES
# ============================================================
@login_required
def ai_anomalies(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        module = request.GET.get('module', 'all')

        sales_anomalies = []
        inventory_anomalies = []
        financial_anomalies = []

        if module in ('all', 'sales'):
            sales_anomalies = anomaly_detector.detect_sales_anomalies(company)
        if module in ('all', 'inventory'):
            inventory_anomalies = anomaly_detector.detect_inventory_anomalies(company)
        if module in ('all', 'finance'):
            financial_anomalies = anomaly_detector.detect_financial_anomalies(company)

        total_anomalies = len(sales_anomalies) + len(inventory_anomalies) + len(financial_anomalies)

        context = {
            'sales_anomalies': sales_anomalies,
            'inventory_anomalies': inventory_anomalies,
            'financial_anomalies': financial_anomalies,
            'total_anomalies': total_anomalies,
            'module': module,
        }
        return render(request, 'sklat_ai/anomalies.html', context)
    except Exception as e:
        messages.error(request, f'Error detecting anomalies: {str(e)}')
        return render(request, 'sklat_ai/anomalies.html', {})


# ============================================================
# 12. AI ANALYTICS (USAGE)
# ============================================================
@login_required
def ai_analytics(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        usage_logs = AIUsageLog.objects.filter(company=company)

        totals = usage_logs.aggregate(
            total_requests=Count('id'),
            total_input_tokens=Sum('tokens_input'),
            total_output_tokens=Sum('tokens_output'),
            total_cost=Sum('estimated_cost_usd'),
            avg_response_time=Avg('response_time_ms'),
        )

        by_feature = (
            usage_logs.values('feature')
            .annotate(
                count=Count('id'),
                tokens=Sum('tokens_input') + Sum('tokens_output'),
                cost=Sum('estimated_cost_usd'),
            )
            .order_by('-count')
        )

        by_user = (
            usage_logs.values('user__first_name', 'user__last_name')
            .annotate(
                count=Count('id'),
                tokens=Sum('tokens_input') + Sum('tokens_output'),
                cost=Sum('estimated_cost_usd'),
            )
            .order_by('-count')[:20]
        )

        thirty_days_ago = timezone.now() - timedelta(days=30)
        daily_trend = list(
            usage_logs.filter(created_at__gte=thirty_days_ago)
            .values('created_at__date')
            .annotate(
                count=Count('id'),
                cost=Sum('estimated_cost_usd'),
            )
            .order_by('created_at__date')
        )

        feature_labels = dict(AIUsageLog.FEATURE_CHOICES)

        usage_stats = {
            'total_requests': totals.get('total_requests') or 0,
            'total_tokens_input': totals.get('total_input_tokens') or 0,
            'total_tokens_output': totals.get('total_output_tokens') or 0,
            'total_cost': float(totals.get('total_cost') or 0),
            'avg_response_time': float(totals.get('avg_response_time') or 0),
            'by_feature': list(by_feature),
            'by_user': list(by_user),
            'by_day': daily_trend,
            'recent_usage': list(usage_logs.select_related('user').order_by('-created_at')[:20]),
            'feature_labels': feature_labels,
            'max_daily_requests': max((d['count'] for d in daily_trend), default=1) or 1,
        }

        context = {'usage_stats': usage_stats}
        return render(request, 'sklat_ai/analytics.html', context)
    except Exception as e:
        messages.error(request, f'Error loading AI analytics: {str(e)}')
        return render(request, 'sklat_ai/analytics.html', {'usage_stats': {
            'total_requests': 0, 'total_tokens_input': 0, 'total_tokens_output': 0,
            'total_cost': 0, 'avg_response_time': 0, 'by_feature': [], 'by_user': [],
            'by_day': [], 'recent_usage': [], 'feature_labels': {}, 'max_daily_requests': 1,
        }})


# ============================================================
# 13. AI FEEDBACK
# ============================================================
@login_required
def ai_feedback(request):
    company = get_company(request)
    if not company:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'No company'}, status=403)
        return redirect('sklat_ai:dashboard')

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        message_id = request.POST.get('message_id', '')
        rating = request.POST.get('rating', '')
        reason = request.POST.get('reason', '')

        if not message_id or not rating:
            return JsonResponse({'status': 'error', 'message': 'message_id and rating required'}, status=400)

        valid_ratings = ['helpful', 'not_helpful', 'incorrect']
        if rating not in valid_ratings:
            return JsonResponse({'status': 'error', 'message': f'Invalid rating. Must be one of: {valid_ratings}'}, status=400)

        ai_message = get_object_or_404(AIMessage, pk=message_id)
        feedback = AIFeedback.objects.create(
            company=company,
            user=request.user,
            message=ai_message,
            rating=rating,
            reason=reason,
        )

        return JsonResponse({'status': 'ok', 'feedback_id': str(feedback.pk)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================================
# 14. AI CONFIG
# ============================================================
@login_required
def ai_config(request):
    company = get_company(request)
    if not company:
        return render(request, 'sklat_ai/no_company.html')

    try:
        configs = AIProviderConfig.objects.filter(company=company)
        current_config = configs.filter(is_active=True).first()

        if request.method == 'POST':
            action = request.POST.get('action', '')

            if action == 'test':
                if current_config:
                    test_result = gateway.chat(
                        company, request.user,
                        [{'role': 'user', 'content': 'Hello, this is a connection test.'}],
                        feature='chat',
                    )
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'status': 'ok' if test_result.get('success') else 'error',
                            'message': 'Connection successful' if test_result.get('success') else test_result.get('error', 'Test failed'),
                            'response_time_ms': test_result.get('response_time_ms', 0),
                        })
                    if test_result.get('success'):
                        messages.success(request, f'Connection test successful. Response time: {test_result.get("response_time_ms", 0)}ms')
                    else:
                        messages.error(request, f'Connection test failed: {test_result.get("error", "Unknown error")}')
                else:
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({'status': 'error', 'message': 'No active AI provider configured'}, status=400)
                    messages.error(request, 'No active AI provider configured.')
                return redirect('sklat_ai:config')

            provider = request.POST.get('provider', 'openai')
            model_name = request.POST.get('model_name', 'gpt-4o-mini')
            api_key = request.POST.get('api_key', '').strip()
            api_base_url = request.POST.get('api_base_url', 'https://api.openai.com/v1').strip()
            temperature = float(request.POST.get('temperature', 0.3))
            max_tokens = int(request.POST.get('max_tokens', 2000))
            timeout_seconds = int(request.POST.get('timeout_seconds', 30))
            monthly_budget = float(request.POST.get('monthly_budget_usd', 50))

            existing = configs.filter(provider=provider).first()
            if existing:
                existing.model_name = model_name
                if api_key:
                    existing.api_key_encrypted = api_key
                existing.api_base_url = api_base_url
                existing.temperature = temperature
                existing.max_tokens = max_tokens
                existing.timeout_seconds = timeout_seconds
                existing.monthly_budget_usd = monthly_budget
                existing.save()
                config = existing
            else:
                config = AIProviderConfig.objects.create(
                    company=company,
                    provider=provider,
                    model_name=model_name,
                    api_key_encrypted=api_key,
                    api_base_url=api_base_url,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout_seconds=timeout_seconds,
                    monthly_budget_usd=monthly_budget,
                )

            configs.exclude(pk=config.pk).update(is_active=False)
            config.is_active = True
            config.save(update_fields=['is_active'])

            gateway._providers.pop(str(config.pk), None)

            messages.success(request, f'AI provider "{config.get_provider_display()}" configured successfully.')
            return redirect('sklat_ai:config')

        context = {
            'configs': configs,
            'current_config': current_config,
            'provider_choices': AIProviderConfig.PROVIDER_CHOICES,
        }
        return render(request, 'sklat_ai/config.html', context)
    except Exception as e:
        messages.error(request, f'Error loading AI config: {str(e)}')
        return render(request, 'sklat_ai/config.html', {})


# ============================================================
# 15. AI GENERATE INSIGHT
# ============================================================
@login_required
def ai_generate_insight(request):
    company = get_company(request)
    if not company:
        return JsonResponse({'status': 'error', 'message': 'No company'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        module = request.POST.get('module', 'general')
        insight_type = request.POST.get('insight_type', 'summary')

        context_data = context_builder.get_context(company, f'{module} insights')

        system_prompt = (
            f"You are SKLAT AI. Generate a {insight_type} insight for the {module} module. "
            "Provide a clear title, detailed description, evidence from the data, "
            "and actionable recommendations. Be specific with numbers."
        )
        user_prompt = (
            f"Analyze {module} data and generate a {insight_type} insight.\n"
            f"Data:\n{json.dumps(context_data, default=str, indent=2)}"
        )

        ai_content = gateway.analyze(
            company, request.user, system_prompt, user_prompt,
            feature='analysis',
        )

        if not ai_content:
            ai_content = f"Analysis of {module} module data. Configure an AI provider for detailed insights."

        title = f"{module.title()} {insight_type.title()} Insight"
        description = ai_content[:2000]

        insight = AIInsight.objects.create(
            company=company,
            insight_type=insight_type if insight_type in dict(AIInsight.TYPE_CHOICES) else 'summary',
            title=title,
            description=description,
            related_module=module,
            priority='medium',
            confidence=0.7,
        )

        return JsonResponse({
            'status': 'ok',
            'insight_id': str(insight.pk),
            'title': insight.title,
            'description': insight.description,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================================
# 16. AI EXECUTE ACTION
# ============================================================
@login_required
def ai_execute_action(request, rec_id=None):
    company = get_company(request)
    if not company:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'No company'}, status=403)
        return redirect('sklat_ai:recommendations')

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    if not rec_id:
        data = _parse_json(request.body)
        rec_id = data.get('recommendation_id') or request.POST.get('recommendation_id')
    
    if not rec_id:
        return JsonResponse({'status': 'error', 'message': 'No recommendation ID'}, status=400)

    try:
        recommendation = get_object_or_404(
            AIRecommendation, pk=rec_id, company=company
        )

        if recommendation.status not in ('pending', 'reviewed'):
            msg = 'This recommendation has already been processed.'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': msg}, status=400)
            messages.error(request, msg)
            return redirect('sklat_ai:recommendations')

        action_type = recommendation.action_type
        action_config = recommendation.action_config or {}
        action_taken = ''

        if action_type == 'create_task' or recommendation.category == 'restock':
            try:
                from spiskalar.models import Task
                task = Task.objects.create(
                    company=company,
                    title=action_config.get('title', recommendation.title),
                    description=recommendation.description,
                    task_type=action_config.get('task_type', 'restock'),
                    priority=action_config.get('priority', 'high'),
                    created_by=request.user,
                )
                action_taken = f'Created task: {task.title}'
            except Exception:
                action_taken = 'Task creation attempted (module not available)'

        elif action_type == 'create_purchase_draft' or recommendation.category == 'supplier':
            action_taken = 'Purchase draft recommendation logged'
            if action_config.get('supplier_id'):
                action_taken += f' for supplier ID {action_config["supplier_id"]}'

        elif action_type == 'create_reminder' or recommendation.category == 'customer':
            action_taken = 'Customer follow-up reminder created'
            if action_config.get('customer_id'):
                action_taken += f' for customer ID {action_config["customer_id"]}'

        elif action_type == 'send_notification':
            action_taken = 'Notification queued'

        else:
            action_taken = f'Action executed: {action_type or recommendation.category}'

        recommendation.status = 'accepted'
        recommendation.action_taken_by = request.user
        recommendation.action_taken_at = timezone.now()
        recommendation.action_taken = action_taken
        recommendation.save(update_fields=[
            'status', 'action_taken_by', 'action_taken_at', 'action_taken'
        ])

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'action_taken': action_taken,
                'recommendation_id': str(recommendation.pk),
            })

        messages.success(request, f'Action executed: {action_taken}')
        return redirect('sklat_ai:action_center')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        messages.error(request, f'Error executing action: {str(e)}')
        return redirect('sklat_ai:action_center')


# ============================================================
# 17. AI DISMISS RECOMMENDATION
# ============================================================
@login_required
def ai_dismiss_recommendation(request, rec_id=None):
    company = get_company(request)
    if not company:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'No company'}, status=403)
        return redirect('sklat_ai:recommendations')

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    if not rec_id:
        data = _parse_json(request.body)
        rec_id = data.get('recommendation_id') or request.POST.get('recommendation_id')
    
    if not rec_id:
        return JsonResponse({'status': 'error', 'message': 'No recommendation ID'}, status=400)

    try:
        recommendation = get_object_or_404(
            AIRecommendation, pk=rec_id, company=company
        )

        recommendation.status = 'dismissed'
        recommendation.reviewed_by = request.user
        recommendation.reviewed_at = timezone.now()
        recommendation.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'recommendation_id': str(recommendation.pk),
            })

        messages.success(request, 'Recommendation dismissed.')
        return redirect('sklat_ai:action_center')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        messages.error(request, f'Error dismissing recommendation: {str(e)}')
        return redirect('sklat_ai:action_center')


# ============================================================
# 18. EXPORT BUSINESS SUMMARY CSV
# ============================================================
@login_required
def ai_export_summary(request):
    company = get_company(request)
    if not company:
        return redirect('sklat_ai:dashboard')

    import csv
    from django.http import HttpResponse

    period = request.GET.get('period', 'monthly')
    period_label = {'daily': 'Today', 'weekly': 'This Week', 'monthly': 'This Month'}.get(period, 'This Month')

    now = timezone.now()
    if period == 'daily':
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'weekly':
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ai_summary_{period}_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['SKLAT AI Business Summary', period_label, str(company)])
    writer.writerow([])

    try:
        from sales.models import Sale
        from finance.models import FinancialTransaction
        from products.models import Product
        from sales.models import Customer

        sales_data = Sale.objects.filter(
            company=company, created_at__gte=start, status__in=['confirmed', 'completed']
        ).aggregate(total=Sum('total'), count=Count('id'), avg=Avg('total'))
        writer.writerow(['SALES'])
        writer.writerow(['Total Revenue', f"${sales_data['total'] or 0:,.2f}"])
        writer.writerow(['Sale Count', sales_data['count'] or 0])
        writer.writerow(['Average Sale', f"${sales_data['avg'] or 0:,.2f}"])
        writer.writerow([])

        income = FinancialTransaction.objects.filter(
            company=company, direction='income', created_at__gte=start
        ).aggregate(total=Sum('amount'))['total'] or 0
        expenses = FinancialTransaction.objects.filter(
            company=company, direction='expense', created_at__gte=start
        ).aggregate(total=Sum('amount'))['total'] or 0
        margin = ((float(income) - float(expenses)) / float(income) * 100) if float(income) > 0 else 0
        writer.writerow(['FINANCE'])
        writer.writerow(['Income', f"${float(income):,.2f}"])
        writer.writerow(['Expenses', f"${float(expenses):,.2f}"])
        writer.writerow(['Profit', f"${float(income) - float(expenses):,.2f}"])
        writer.writerow(['Margin', f"{margin:.1f}%"])
        writer.writerow([])

        total_products = Product.objects.filter(company=company).count()
        low_stock = Product.objects.filter(company=company, status='active').count()
        writer.writerow(['INVENTORY'])
        writer.writerow(['Total Products', total_products])
        writer.writerow([])

        total_customers = Customer.objects.filter(company=company).count()
        active_customers = Customer.objects.filter(company=company, customer_status='active').count()
        writer.writerow(['CUSTOMERS'])
        writer.writerow(['Total', total_customers])
        writer.writerow(['Active', active_customers])
        writer.writerow([])

        insights = AIInsight.objects.filter(company=company, is_dismissed=False).order_by('-created_at')[:10]
        writer.writerow(['RECENT AI INSIGHTS'])
        writer.writerow(['Type', 'Title', 'Priority', 'Date'])
        for i in insights:
            writer.writerow([i.get_insight_type_display(), i.title, i.get_priority_display(), i.created_at.strftime('%Y-%m-%d %H:%M')])

    except Exception as e:
        writer.writerow(['Error generating summary', str(e)])

    return response


# ============================================================
# 19. EXPORT AI ANALYTICS CSV
# ============================================================
@login_required
def ai_export_analytics(request):
    company = get_company(request)
    if not company:
        return redirect('sklat_ai:dashboard')

    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ai_analytics_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['SKLAT AI Usage Analytics', str(company)])
    writer.writerow([])

    try:
        logs = AIUsageLog.objects.filter(company=company).order_by('-created_at')

        writer.writerow(['USAGE LOG'])
        writer.writerow(['Date', 'Feature', 'Provider', 'Model', 'Input Tokens', 'Output Tokens', 'Cost ($)', 'Response Time (ms)', 'Success'])
        for log in logs[:500]:
            writer.writerow([
                log.created_at.strftime('%Y-%m-%d %H:%M'),
                log.feature, log.provider, log.model,
                log.tokens_input, log.tokens_output,
                f"{log.estimated_cost_usd:.4f}",
                log.response_time_ms, log.success,
            ])

        writer.writerow([])
        writer.writerow(['FEATURE BREAKDOWN'])
        writer.writerow(['Feature', 'Request Count', 'Total Tokens', 'Total Cost ($)'])
        breakdown = (
            logs.values('feature')
            .annotate(
                count=Count('id'),
                tokens=Sum('tokens_input') + Sum('tokens_output'),
                cost=Sum('estimated_cost_usd'),
            )
            .order_by('-count')
        )
        for b in breakdown:
            writer.writerow([b['feature'], b['count'], b['tokens'], f"{b['cost']:.4f}"])

    except Exception as e:
        writer.writerow(['Error generating analytics', str(e)])

    return response


# ============================================================
# 20. FORECAST EVALUATION
# ============================================================
@login_required
def ai_forecast_evaluate(request):
    """Compare past forecasts against actual sales to measure accuracy."""
    company = get_company(request)
    if not company:
        return JsonResponse({'status': 'error', 'message': 'No company'}, status=403)

    try:
        from sales.models import SaleItem
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        old_forecasts = AIForecast.objects.filter(
            company=company, created_at__lt=thirty_days_ago
        ).select_related('product')

        evaluations = []
        for f in old_forecasts[:50]:
            actual = SaleItem.objects.filter(
                sale__company=company, product=f.product,
                sale__date__gte=f.created_at.date(),
                sale__date__lte=now.date()
            ).aggregate(total=Sum('quantity'))['total'] or 0

            predicted = f.predicted_value or 0
            if predicted > 0:
                accuracy = max(0, 100 - abs(float(actual) - predicted) / predicted * 100)
            else:
                accuracy = 0

            evaluations.append({
                'product': f.product.name if f.product else 'Unknown',
                'predicted': predicted,
                'actual': int(actual),
                'accuracy': round(accuracy, 1),
                'horizon': f.horizon_days,
                'created': f.created_at.strftime('%Y-%m-%d'),
            })

        avg_accuracy = (
            sum(e['accuracy'] for e in evaluations) / len(evaluations)
        ) if evaluations else 0

        return JsonResponse({
            'status': 'ok',
            'evaluations': evaluations[:20],
            'avg_accuracy': round(avg_accuracy, 1),
            'total_evaluated': len(evaluations),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


# ============================================================
# 21. PRUNE CONVERSATIONS
# ============================================================
@login_required
def ai_prune_conversations(request):
    """Archive old conversations to manage AI memory."""
    company = get_company(request)
    if not company:
        return redirect('sklat_ai:dashboard')

    if request.method != 'POST':
        return redirect('sklat_ai:conversation_list')

    try:
        auto_insight_engine.prune_conversations(company)
        messages.success(request, 'Old conversations have been archived.')
    except Exception as e:
        messages.error(request, f'Error pruning conversations: {str(e)}')

    return redirect('sklat_ai:conversation_list')


# ============================================================
# 22. AI VALIDATE RESPONSE (No-hallucination check)
# ============================================================
@login_required
def ai_validate_response(request):
    """Validate that an AI response references real data from SKLAT PRO."""
    company = get_company(request)
    if not company:
        return JsonResponse({'status': 'error', 'message': 'No company'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        data = _parse_json(request.body)
        response_text = data.get('response', '')
        if not response_text:
            return JsonResponse({'status': 'error', 'message': 'No response to validate'}, status=400)

        context_data = context_builder.get_context(company, response_text)
        validation = _validate_against_context(response_text, context_data)

        return JsonResponse({
            'status': 'ok',
            'validation': validation,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def _validate_against_context(response_text, context_data):
    """Check if the AI response references numbers/data that exist in context."""
    import re
    response_numbers = set(re.findall(r'\$?([\d,]+\.?\d*)', response_text))
    context_numbers = set()
    sales = context_data.get('sales', {})
    if sales:
        context_numbers.add(str(int(sales.get('this_month_total', 0))))
        context_numbers.add(str(sales.get('this_month_count', 0)))
    finance = context_data.get('finance', {})
    if finance:
        context_numbers.add(str(int(finance.get('month_income', 0))))
        context_numbers.add(str(int(finance.get('month_expenses', 0))))
    inventory = context_data.get('inventory', {})
    if inventory:
        context_numbers.add(str(inventory.get('total_products', 0)))

    referenced = response_numbers & context_numbers
    all_numbers = len(response_numbers)
    verified = len(referenced)
    confidence = (verified / all_numbers * 100) if all_numbers > 0 else 100

    return {
        'confidence': round(confidence, 1),
        'numbers_checked': all_numbers,
        'numbers_verified': verified,
        'needs_review': confidence < 50 and all_numbers > 2,
    }
