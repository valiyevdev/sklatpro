from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from .models import (
    AutomationRule, AutomationExecution,
    TRIGGER_CATEGORIES, TRIGGER_CHOICES,
    ACTION_TYPES, ACTION_TYPE_CHOICES, OPERATOR_CHOICES,
)
from . import engine


def get_company(request):
    if request.user.is_superuser:
        return getattr(request.user, 'company', None)
    return getattr(request.user, 'company', None)


def _parse_json(value):
    import json
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


# ============================================================
# 1. AUTOMATION DASHBOARD
# ============================================================
@login_required
def automation_dashboard(request):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        rules = AutomationRule.objects.filter(company=company)
        executions = AutomationExecution.objects.filter(company=company)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        executions_today = executions.filter(created_at__gte=today_start)

        active_rules = rules.filter(status='active').count()
        total_executions_today = executions_today.count()
        successful_today = executions_today.filter(status='completed').count()
        failed_today = executions_today.filter(status='failed').count()
        partial_today = executions_today.filter(status='partial').count()
        skipped_today = executions_today.filter(status='skipped').count()
        disabled_rules = rules.filter(status='disabled').count()

        recent_failures = (
            executions
            .filter(status='failed')
            .select_related('rule')
            .order_by('-created_at')[:10]
        )

        healthy_rules = rules.filter(status='active', health_status='healthy').count()
        warning_rules = rules.filter(status='active', health_status='warning').count()
        failing_rules = rules.filter(status='active', health_status='error').count()

        context = {
            'active_rules': active_rules,
            'disabled_rules': disabled_rules,
            'total_executions_today': total_executions_today,
            'successful_today': successful_today,
            'failed_today': failed_today,
            'partial_today': partial_today,
            'skipped_today': skipped_today,
            'recent_failures': recent_failures,
            'healthy_rules': healthy_rules,
            'warning_rules': warning_rules,
            'failing_rules': failing_rules,
        }
        return render(request, 'automation/dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Error loading dashboard: {str(e)}')
        return render(request, 'automation/dashboard.html', {})


# ============================================================
# 2. RULE LIST
# ============================================================
@login_required
def rule_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        rules = AutomationRule.objects.filter(company=company)

        status_filter = request.GET.get('status', '')
        module_filter = request.GET.get('module', '')
        trigger_filter = request.GET.get('trigger', '')
        priority_filter = request.GET.get('priority', '')
        search = request.GET.get('q', '')

        if status_filter:
            rules = rules.filter(status=status_filter)
        if trigger_filter:
            rules = rules.filter(trigger_type=trigger_filter)
        if priority_filter:
            rules = rules.filter(priority=priority_filter)
        if module_filter:
            module_triggers = []
            for cat_key, cat_data in TRIGGER_CATEGORIES.items():
                for trig_code, _ in cat_data['triggers']:
                    if trig_code.startswith(module_filter + '.'):
                        module_triggers.append(trig_code)
            if module_triggers:
                rules = rules.filter(trigger_type__in=module_triggers)
            else:
                rules = rules.none()
        if search:
            rules = rules.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(trigger_type__icontains=search)
            )

        rules = rules.annotate(action_count=Count('actions')).order_by('-created_at')

        paginator = Paginator(rules, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'page_obj': page_obj,
            'rules': page_obj,
            'status_filter': status_filter,
            'module_filter': module_filter,
            'trigger_filter': trigger_filter,
            'priority_filter': priority_filter,
            'search': search,
            'status_choices': AutomationRule.STATUS_CHOICES,
            'priority_choices': AutomationRule.PRIORITY_CHOICES,
            'trigger_categories': TRIGGER_CATEGORIES,
            'trigger_choices': TRIGGER_CHOICES,
        }
        return render(request, 'automation/rule_list.html', context)
    except Exception as e:
        messages.error(request, f'Error loading rules: {str(e)}')
        return render(request, 'automation/rule_list.html', {'rules': []})


# ============================================================
# 3. RULE CREATE
# ============================================================
@login_required
def rule_create(request):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        if request.method == 'POST':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            trigger_type = request.POST.get('trigger_type', '')
            priority = request.POST.get('priority', 'normal')
            conditions_logic = request.POST.get('conditions_logic', 'all')
            conditions_raw = request.POST.get('conditions', '{}')
            actions_raw = request.POST.get('actions', '[]')
            schedule_type = request.POST.get('schedule_type', '')
            rate_limit = request.POST.get('rate_limit_per_hour', '100')
            activate = request.POST.get('activate') == 'on'

            conditions = _parse_json(conditions_raw)
            actions_list = _parse_json(actions_raw)
            if not isinstance(actions_list, list):
                actions_list = []

            rule = AutomationRule.objects.create(
                company=company,
                name=name,
                description=description,
                trigger_type=trigger_type,
                priority=priority,
                conditions=conditions,
                conditions_logic=conditions_logic,
                actions=actions_list,
                schedule_type=schedule_type,
                rate_limit_per_hour=int(rate_limit) if rate_limit else 100,
                status='active' if activate else 'draft',
                created_by=request.user,
                updated_by=request.user,
            )

            messages.success(request, f'Rule "{rule.name}" created successfully.')
            return redirect('automation:rule_detail', pk=rule.pk)

        context = {
            'trigger_categories': TRIGGER_CATEGORIES,
            'trigger_choices': TRIGGER_CHOICES,
            'action_types': ACTION_TYPES,
            'action_type_choices': ACTION_TYPE_CHOICES,
            'operator_choices': OPERATOR_CHOICES,
            'priority_choices': AutomationRule.PRIORITY_CHOICES,
            'schedule_choices': [('', 'Event-based'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('interval', 'Interval'), ('cron', 'Cron')],
        }
        return render(request, 'automation/rule_create.html', context)
    except Exception as e:
        messages.error(request, f'Error creating rule: {str(e)}')
        return redirect('automation:rule_list')


# ============================================================
# 4. RULE DETAIL
# ============================================================
@login_required
def rule_detail(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        rule = get_object_or_404(AutomationRule, pk=pk, company=company)
        recent_executions = rule.executions.all()[:20]
        action_details = []
        for action_cfg in rule.actions:
            action_type = action_cfg.get('type', '')
            type_info = ACTION_TYPES.get(action_type, {})
            action_details.append({
                'type': action_type,
                'label': type_info.get('label', action_type),
                'icon': type_info.get('icon', 'bi-gear'),
                'config': action_cfg.get('config', {}),
            })

        context = {
            'rule': rule,
            'recent_executions': recent_executions,
            'action_details': action_details,
            'trigger_display': rule.get_trigger_display(),
        }
        return render(request, 'automation/rule_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error loading rule: {str(e)}')
        return redirect('automation:rule_list')


# ============================================================
# 5. RULE EDIT
# ============================================================
@login_required
def rule_edit(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        rule = get_object_or_404(AutomationRule, pk=pk, company=company)

        if request.method == 'POST':
            rule.name = request.POST.get('name', rule.name).strip()
            rule.description = request.POST.get('description', rule.description).strip()
            rule.trigger_type = request.POST.get('trigger_type', rule.trigger_type)
            rule.priority = request.POST.get('priority', rule.priority)
            rule.conditions_logic = request.POST.get('conditions_logic', rule.conditions_logic)
            rule.conditions = _parse_json(request.POST.get('conditions', '{}'))
            rule.actions = _parse_json(request.POST.get('actions', '[]'))
            if not isinstance(rule.actions, list):
                rule.actions = []
            rule.schedule_type = request.POST.get('schedule_type', rule.schedule_type)
            rate_limit = request.POST.get('rate_limit_per_hour', str(rule.rate_limit_per_hour))
            rule.rate_limit_per_hour = int(rate_limit) if rate_limit else rule.rate_limit_per_hour
            rule.updated_by = request.user
            rule.version += 1

            history_entry = {
                'version': rule.version - 1,
                'edited_by': str(request.user),
                'edited_at': timezone.now().isoformat(),
                'changes': f'Updated to version {rule.version}',
            }
            history = list(rule.version_history)
            history.append(history_entry)
            rule.version_history = history
            rule.save()

            messages.success(request, f'Rule "{rule.name}" updated to version {rule.version}.')
            return redirect('automation:rule_detail', pk=rule.pk)

        context = {
            'rule': rule,
            'trigger_categories': TRIGGER_CATEGORIES,
            'trigger_choices': TRIGGER_CHOICES,
            'action_types': ACTION_TYPES,
            'action_type_choices': ACTION_TYPE_CHOICES,
            'operator_choices': OPERATOR_CHOICES,
            'priority_choices': AutomationRule.PRIORITY_CHOICES,
        }
        return render(request, 'automation/rule_edit.html', context)
    except Exception as e:
        messages.error(request, f'Error editing rule: {str(e)}')
        return redirect('automation:rule_list')


# ============================================================
# 6. RULE TOGGLE STATUS
# ============================================================
@login_required
def rule_toggle_status(request, pk):
    company = get_company(request)
    if not company:
        return redirect('automation:rule_list')

    try:
        rule = get_object_or_404(AutomationRule, pk=pk, company=company)

        if request.method != 'POST':
            return redirect('automation:rule_detail', pk=pk)

        new_status = request.POST.get('status', '')
        valid_transitions = {
            'activate': 'active',
            'pause': 'paused',
            'disable': 'disabled',
        }

        target_status = valid_transitions.get(new_status)
        if target_status:
            rule.status = target_status
            rule.updated_by = request.user
            rule.save(update_fields=['status', 'updated_by'])
            messages.success(request, f'Rule "{rule.name}" is now {target_status}.')
        else:
            messages.error(request, 'Invalid status transition.')

    except Exception as e:
        messages.error(request, f'Error updating rule status: {str(e)}')

    return redirect('automation:rule_detail', pk=pk)


# ============================================================
# 7. RULE DELETE
# ============================================================
@login_required
def rule_delete(request, pk):
    company = get_company(request)
    if not company:
        return redirect('automation:rule_list')

    try:
        rule = get_object_or_404(AutomationRule, pk=pk, company=company)

        if request.method != 'POST':
            return redirect('automation:rule_detail', pk=pk)

        if rule.status not in ('draft', 'disabled'):
            messages.error(request, 'Only draft or disabled rules can be deleted.')
            return redirect('automation:rule_detail', pk=pk)

        name = rule.name
        rule.delete()
        messages.success(request, f'Rule "{name}" deleted successfully.')
        return redirect('automation:rule_list')

    except Exception as e:
        messages.error(request, f'Error deleting rule: {str(e)}')
        return redirect('automation:rule_list')


# ============================================================
# 8. RULE TEST (DRY RUN)
# ============================================================
@login_required
def rule_test(request, pk):
    company = get_company(request)
    if not company:
        return redirect('automation:rule_list')

    try:
        rule = get_object_or_404(AutomationRule, pk=pk, company=company)

        if request.method != 'POST':
            return redirect('automation:rule_detail', pk=pk)

        result = engine.test_rule(rule, company)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'result': result})

        messages.success(request, 'Rule test completed. Check the results below.')
        return render(request, 'automation/rule_detail.html', {
            'rule': rule,
            'result': result,
        })

    except Exception as e:
        messages.error(request, f'Error testing rule: {str(e)}')
        return redirect('automation:rule_detail', pk=pk)


# ============================================================
# 9. RULE DUPLICATE
# ============================================================
@login_required
def rule_duplicate(request, pk):
    company = get_company(request)
    if not company:
        return redirect('automation:rule_list')

    try:
        rule = get_object_or_404(AutomationRule, pk=pk, company=company)

        if request.method != 'POST':
            return redirect('automation:rule_detail', pk=pk)

        new_rule = AutomationRule.objects.create(
            company=company,
            name=f'{rule.name} (Copy)',
            description=rule.description,
            trigger_type=rule.trigger_type,
            trigger_config=rule.trigger_config,
            conditions=rule.conditions,
            conditions_logic=rule.conditions_logic,
            actions=rule.actions,
            schedule_type=rule.schedule_type,
            schedule_config=rule.schedule_config,
            rate_limit_per_hour=rule.rate_limit_per_hour,
            priority=rule.priority,
            status='draft',
            created_by=request.user,
            updated_by=request.user,
        )

        messages.success(request, f'Rule duplicated as "{new_rule.name}".')
        return redirect('automation:rule_edit', pk=new_rule.pk)

    except Exception as e:
        messages.error(request, f'Error duplicating rule: {str(e)}')
        return redirect('automation:rule_list')


# ============================================================
# 10. RULE VERSION HISTORY
# ============================================================
@login_required
def rule_version_history(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        rule = get_object_or_404(AutomationRule, pk=pk, company=company)
        history = list(rule.version_history)
        history.reverse()

        context = {
            'rule': rule,
            'history': history,
            'current_version': rule.version,
        }
        return render(request, 'automation/rule_versions.html', context)
    except Exception as e:
        messages.error(request, f'Error loading version history: {str(e)}')
        return redirect('automation:rule_detail', pk=pk)


# ============================================================
# 11. EXECUTION LIST
# ============================================================
@login_required
def execution_list(request):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        executions = AutomationExecution.objects.filter(company=company).select_related('rule')

        rule_filter = request.GET.get('rule', '')
        status_filter = request.GET.get('status', '')
        event_type = request.GET.get('event_type', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        search = request.GET.get('q', '')

        if rule_filter:
            executions = executions.filter(rule_id=rule_filter)
        if status_filter:
            executions = executions.filter(status=status_filter)
        if event_type:
            executions = executions.filter(event_type=event_type)
        if date_from:
            try:
                executions = executions.filter(created_at__date__gte=date_from)
            except (ValueError, TypeError):
                pass
        if date_to:
            try:
                executions = executions.filter(created_at__date__lte=date_to)
            except (ValueError, TypeError):
                pass
        if search:
            executions = executions.filter(
                Q(rule__name__icontains=search) |
                Q(event_type__icontains=search) |
                Q(object_type__icontains=search) |
                Q(object_id__icontains=search)
            )

        paginator = Paginator(executions, 25)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        rules = AutomationRule.objects.filter(company=company)

        context = {
            'page_obj': page_obj,
            'executions': page_obj,
            'rule_filter': rule_filter,
            'status_filter': status_filter,
            'event_type': event_type,
            'date_from': date_from,
            'date_to': date_to,
            'search': search,
            'rules': rules,
            'status_choices': AutomationExecution.STATUS_CHOICES,
        }
        return render(request, 'automation/execution_list.html', context)
    except Exception as e:
        messages.error(request, f'Error loading executions: {str(e)}')
        return render(request, 'automation/execution_list.html', {'executions': []})


# ============================================================
# 12. EXECUTION DETAIL
# ============================================================
@login_required
def execution_detail(request, pk):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        execution = get_object_or_404(
            AutomationExecution.objects.select_related('rule'),
            pk=pk, company=company
        )

        context = {
            'execution': execution,
            'rule': execution.rule,
        }
        return render(request, 'automation/execution_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error loading execution: {str(e)}')
        return redirect('automation:execution_list')


# ============================================================
# 13. EXECUTION RETRY
# ============================================================
@login_required
def execution_retry(request, pk):
    company = get_company(request)
    if not company:
        return redirect('automation:execution_list')

    try:
        execution = get_object_or_404(AutomationExecution, pk=pk, company=company)

        if request.method != 'POST':
            return redirect('automation:execution_detail', pk=pk)

        if execution.status not in ('failed', 'partial'):
            messages.error(request, 'Only failed or partial executions can be retried.')
            return redirect('automation:execution_detail', pk=pk)

        rule = execution.rule
        if rule.status != 'active':
            messages.error(request, 'Cannot retry: the associated rule is not active.')
            return redirect('automation:execution_detail', pk=pk)

        new_execution = AutomationExecution.objects.create(
            rule=rule,
            company=company,
            event_id=execution.event_id,
            event_type=execution.event_type,
            object_type=execution.object_type,
            object_id=execution.object_id,
            status='pending',
            triggered_by=request.user,
            dry_run=execution.dry_run,
            result_summary=f'Retry of execution {execution.pk}',
        )

        messages.success(request, 'Execution queued for retry.')
        return redirect('automation:execution_detail', pk=new_execution.pk)

    except Exception as e:
        messages.error(request, f'Error retrying execution: {str(e)}')
        return redirect('automation:execution_list')


# ============================================================
# 14. AUTOMATION LOGS
# ============================================================
@login_required
def automation_logs(request):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        logs = AutomationExecution.objects.filter(company=company).select_related('rule')

        rule_filter = request.GET.get('rule', '')
        event_type = request.GET.get('event_type', '')
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

        if rule_filter:
            logs = logs.filter(rule_id=rule_filter)
        if event_type:
            logs = logs.filter(event_type=event_type)
        if status_filter:
            logs = logs.filter(status=status_filter)
        if date_from:
            try:
                logs = logs.filter(created_at__date__gte=date_from)
            except (ValueError, TypeError):
                pass
        if date_to:
            try:
                logs = logs.filter(created_at__date__lte=date_to)
            except (ValueError, TypeError):
                pass

        paginator = Paginator(logs, 30)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        rules = AutomationRule.objects.filter(company=company)

        context = {
            'page_obj': page_obj,
            'logs': page_obj,
            'rule_filter': rule_filter,
            'event_type': event_type,
            'status_filter': status_filter,
            'date_from': date_from,
            'date_to': date_to,
            'rules': rules,
            'status_choices': AutomationExecution.STATUS_CHOICES,
        }
        return render(request, 'automation/logs.html', context)
    except Exception as e:
        messages.error(request, f'Error loading logs: {str(e)}')
        return render(request, 'automation/logs.html', {'logs': []})


# ============================================================
# 15. AUTOMATION TEMPLATES
# ============================================================
@login_required
def automation_templates(request):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        templates = [
            {
                'id': 'low_stock_alert',
                'name': 'Low Stock Alert',
                'description': 'Automatically create a restock task and send a notification when a product falls below its minimum stock level.',
                'trigger_type': 'inventory.stock_below_minimum',
                'trigger_label': 'Stock Below Minimum',
                'actions': [
                    {'type': 'create_task', 'label': 'Create Restock Task', 'config': {'title': 'Restock {{product.name}}', 'task_type': 'restock', 'priority': 'high', 'due_in_days': 2}},
                    {'type': 'send_notification', 'label': 'Notify Warehouse Manager', 'config': {'title': 'Low Stock Alert', 'message': '{{product.name}} is below minimum stock.', 'notify_role': 'warehouse_manager'}},
                    {'type': 'add_customer_tag', 'label': 'Tag Product', 'config': {'tag_name': 'needs_restock'}},
                ],
                'conditions': {'logic': 'all', 'items': [{'field': 'product.current_stock', 'operator': 'lt', 'value': 'product.min_stock'}]},
            },
            {
                'id': 'order_fulfillment',
                'name': 'Order Fulfillment',
                'description': 'When an order is confirmed, create a picking task and notify the warehouse team.',
                'trigger_type': 'order.confirmed',
                'trigger_label': 'Order Confirmed',
                'actions': [
                    {'type': 'create_task', 'label': 'Create Picking Task', 'config': {'title': 'Pick order {{order.order_number}}', 'task_type': 'picking', 'priority': 'normal', 'assigned_to_role': 'warehouse_manager', 'due_in_days': 1}},
                    {'type': 'send_notification', 'label': 'Notify Warehouse', 'config': {'title': 'New Order to Pick', 'message': 'Order {{order.order_number}} confirmed and ready for picking.', 'notify_role': 'warehouse_manager'}},
                ],
                'conditions': {'logic': 'all', 'items': []},
            },
            {
                'id': 'overdue_customer',
                'name': 'Overdue Customer Follow-Up',
                'description': 'When a customer\'s payment is overdue, create a follow-up task and send a reminder.',
                'trigger_type': 'customer.debt_overdue',
                'trigger_label': 'Customer Debt Overdue',
                'actions': [
                    {'type': 'create_task', 'label': 'Create Follow-Up Task', 'config': {'title': 'Follow up with {{customer.name}} - overdue payment', 'task_type': 'follow_up', 'priority': 'high', 'assigned_to_role': 'account_manager', 'due_in_days': 1}},
                    {'type': 'send_notification', 'label': 'Notify Accounting', 'config': {'title': 'Overdue Payment', 'message': 'Customer {{customer.name}} has an overdue payment of {{customer.debt_amount}}.', 'notify_role': 'accountant'}},
                    {'type': 'add_comment', 'label': 'Add Note', 'config': {'text': 'Auto: Overdue payment follow-up initiated', 'object_type': 'customer'}},
                ],
                'conditions': {'logic': 'all', 'items': []},
            },
            {
                'id': 'failed_delivery',
                'name': 'Failed Delivery Alert',
                'description': 'When a delivery fails, create a redelivery task, notify the dispatcher, and update the order status.',
                'trigger_type': 'logistics.delivery_failed',
                'trigger_label': 'Delivery Failed',
                'actions': [
                    {'type': 'create_task', 'label': 'Create Redelivery Task', 'config': {'title': 'Redeliver order {{order.order_number}}', 'task_type': 'delivery', 'priority': 'urgent', 'assigned_to_role': 'dispatcher', 'due_in_days': 1}},
                    {'type': 'send_notification', 'label': 'Notify Dispatcher', 'config': {'title': 'Delivery Failed', 'message': 'Delivery for order {{order.order_number}} failed. Reason: {{delivery.failure_reason}}', 'notify_role': 'dispatcher'}},
                    {'type': 'update_order_status', 'label': 'Update Order', 'config': {'new_status': 'processing'}},
                ],
                'conditions': {'logic': 'all', 'items': []},
            },
            {
                'id': 'payment_reminder',
                'name': 'Payment Reminder',
                'description': 'Send an automatic payment reminder when a sale payment becomes overdue.',
                'trigger_type': 'sale.payment_overdue',
                'trigger_label': 'Sale Payment Overdue',
                'actions': [
                    {'type': 'send_notification', 'label': 'Notify Customer', 'config': {'title': 'Payment Reminder', 'message': 'Your payment for order {{sale.invoice_number}} is overdue. Amount: {{sale.total_amount}}', 'notification_type': 'payment_overdue'}},
                    {'type': 'create_reminder', 'label': 'Create Reminder', 'config': {'title': 'Follow up payment for {{sale.invoice_number}}', 'remind_in_days': 3, 'assigned_to_role': 'account_manager'}},
                    {'type': 'add_comment', 'label': 'Log Reminder Sent', 'config': {'text': 'Auto: Payment reminder sent to customer', 'object_type': 'sale'}},
                ],
                'conditions': {'logic': 'all', 'items': []},
            },
        ]

        template_id = request.GET.get('use', '')
        if template_id:
            selected = next((t for t in templates if t['id'] == template_id), None)
            if selected:
                return redirect(
                    f"{reverse('automation:rule_create')}"
                    f"?trigger_type={selected['trigger_type']}"
                    f"&name={selected['name']}"
                    f"&description={selected['description']}"
                    f"&template={selected['id']}"
                )

        context = {
            'templates': templates,
        }
        return render(request, 'automation/templates.html', context)
    except Exception as e:
        messages.error(request, f'Error loading templates: {str(e)}')
        return render(request, 'automation/templates.html', {'templates': []})


# ============================================================
# 16. AUTOMATION ANALYTICS
# ============================================================
@login_required
def automation_analytics(request):
    company = get_company(request)
    if not company:
        return render(request, 'automation/no_company.html')

    try:
        rules = AutomationRule.objects.filter(company=company)
        executions = AutomationExecution.objects.filter(company=company)

        total_executions = executions.count()
        completed_executions = executions.filter(status='completed').count()
        failed_executions = executions.filter(status='failed').count()
        success_rate = (completed_executions / total_executions * 100) if total_executions > 0 else 0
        failure_rate = (failed_executions / total_executions * 100) if total_executions > 0 else 0

        avg_duration = executions.filter(
            duration_ms__isnull=False
        ).aggregate(avg=Avg('duration_ms'))['avg'] or 0

        most_used_rules = (
            rules
            .filter(execution_count__gt=0)
            .order_by('-execution_count')[:10]
        )

        failed_rules = (
            rules
            .filter(error_count__gt=0)
            .order_by('-error_count')[:10]
        )

        action_distribution = {}
        for rule in rules:
            for action_cfg in rule.actions:
                action_type = action_cfg.get('type', 'unknown')
                action_distribution[action_type] = action_distribution.get(action_type, 0) + 1
        action_distribution = sorted(action_distribution.items(), key=lambda x: x[1], reverse=True)
        action_distribution_details = []
        for action_type, count in action_distribution:
            type_info = ACTION_TYPES.get(action_type, {})
            action_distribution_details.append({
                'type': action_type,
                'label': type_info.get('label', action_type),
                'count': count,
            })

        context = {
            'total_executions': total_executions,
            'completed_executions': completed_executions,
            'failed_executions': failed_executions,
            'success_rate': round(success_rate, 1),
            'failure_rate': round(failure_rate, 1),
            'avg_duration': round(avg_duration, 0),
            'most_used_rules': most_used_rules,
            'failed_rules': failed_rules,
            'action_distribution': action_distribution_details,
            'total_rules': rules.count(),
            'active_rules': rules.filter(status='active').count(),
        }
        return render(request, 'automation/analytics.html', context)
    except Exception as e:
        messages.error(request, f'Error loading analytics: {str(e)}')
        return render(request, 'automation/analytics.html', {})
