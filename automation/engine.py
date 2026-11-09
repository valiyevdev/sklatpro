import hashlib
import logging
import re
import threading
import traceback
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger('automation.engine')


# ============================================================
# 1. EVENT BUS
# ============================================================

class EventBus:
    """
    Central event bus that creates AutomationEvent records and
    triggers matching automation rules.
    """

    def emit(self, event_type, company, object_type='', object_id='',
             data=None, source='system'):
        from automation.models import AutomationEvent
        try:
            event_id = self.generate_event_id(event_type, object_type, object_id)
            event = AutomationEvent.objects.create(
                company=company,
                event_type=event_type,
                event_id=event_id,
                object_type=object_type,
                object_id=str(object_id) if object_id else '',
                data=data or {},
                source=source,
            )
            engine = AutomationEngine()
            engine.process_event(event)
            return event
        except Exception:
            logger.exception('EventBus.emit failed for event_type=%s', event_type)
            return None

    def emit_if_not_exists(self, event_type, company, object_type='',
                           object_id='', data=None, source='system'):
        from automation.models import AutomationEvent
        try:
            event_id = self.generate_event_id(event_type, object_type, object_id)
            existing = AutomationEvent.objects.filter(
                company=company, event_id=event_id
            ).first()
            if existing:
                return existing
            event = AutomationEvent.objects.create(
                company=company,
                event_type=event_type,
                event_id=event_id,
                object_type=object_type,
                object_id=str(object_id) if object_id else '',
                data=data or {},
                source=source,
            )
            engine = AutomationEngine()
            engine.process_event(event)
            return event
        except Exception:
            logger.exception('EventBus.emit_if_not_exists failed')
            return None

    def generate_event_id(self, event_type, object_type, object_id):
        raw = f"{event_type}:{object_type}:{object_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:64]


# ============================================================
# 2. CONDITION EVALUATOR
# ============================================================

class ConditionEvaluator:
    """
    Evaluates nested condition trees against a context dict.
    Supports AND / OR logic groups with arbitrary nesting.
    """

    def evaluate(self, condition_tree, context):
        if not condition_tree:
            return True
        items = condition_tree.get('items', [])
        if not items:
            return True
        logic = condition_tree.get('logic', 'all').lower()

        results = []
        for item in items:
            if 'group' in item:
                results.append(self.evaluate(item['group'], context))
            elif 'field' in item:
                results.append(self.evaluate_single(item, context))
            else:
                results.append(True)

        if logic == 'any':
            return any(results)
        return all(results)

    def evaluate_single(self, condition, context):
        field = condition.get('field', '')
        operator = condition.get('operator', 'equals')
        expected = condition.get('value', '')
        actual = self.get_field_value(field, context)
        return self.apply_operator(actual, operator, expected)

    def get_field_value(self, field, context):
        parts = field.split('.')
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None) if hasattr(value, '__dict__') else None
            if value is None:
                return None
        return value

    def apply_operator(self, actual, operator, expected):
        if operator == 'is_empty':
            return actual is None or actual == '' or actual == 0
        if operator == 'is_not_empty':
            return actual is not None and actual != '' and actual != 0

        if actual is None:
            return False

        coerced_actual = self._coerce(actual)
        coerced_expected = self._coerce(expected)

        if operator == 'equals':
            return str(coerced_actual) == str(coerced_expected)
        if operator == 'not_equals':
            return str(coerced_actual) != str(coerced_expected)
        if operator in ('gt', 'gte', 'lt', 'lte'):
            try:
                num_actual = Decimal(str(coerced_actual))
                num_expected = Decimal(str(coerced_expected))
            except (InvalidOperation, ValueError, TypeError):
                num_actual = str(coerced_actual)
                num_expected = str(coerced_expected)
            if operator == 'gt':
                return num_actual > num_expected
            if operator == 'gte':
                return num_actual >= num_expected
            if operator == 'lt':
                return num_actual < num_expected
            if operator == 'lte':
                return num_actual <= num_expected
        if operator == 'contains':
            return str(coerced_expected).lower() in str(coerced_actual).lower()
        if operator == 'not_contains':
            return str(coerced_expected).lower() not in str(coerced_actual).lower()
        if operator == 'starts_with':
            return str(coerced_actual).lower().startswith(str(coerced_expected).lower())
        if operator == 'ends_with':
            return str(coerced_actual).lower().endswith(str(coerced_expected).lower())
        if operator == 'in_list':
            items = str(coerced_expected).split(',')
            return str(coerced_actual) in [i.strip() for i in items]
        if operator == 'not_in_list':
            items = str(coerced_expected).split(',')
            return str(coerced_actual) not in [i.strip() for i in items]
        if operator == 'between':
            parts = str(coerced_expected).split(',')
            if len(parts) == 2:
                try:
                    lo = Decimal(parts[0].strip())
                    hi = Decimal(parts[1].strip())
                    val = Decimal(str(coerced_actual))
                    return lo <= val <= hi
                except (InvalidOperation, ValueError, TypeError):
                    return False
        return False

    def _coerce(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float, Decimal)):
            return value
        return str(value) if value is not None else ''


# ============================================================
# 3. ACTION EXECUTOR
# ============================================================

class ActionExecutor:
    """
    Executes a list of action configs. Each action is a dict with
    'type' and 'config' keys. Only predefined action types are allowed.
    """

    ACTION_HANDLERS = {
        'create_task': 'create_task_action',
        'send_notification': 'send_notification_action',
        'create_alert': 'create_alert_action',
        'add_comment': 'add_comment_action',
        'update_order_status': 'update_order_status_action',
        'create_webhook': 'create_webhook_action',
        'add_customer_tag': 'add_customer_tag_action',
        'create_reminder': 'create_reminder_action',
        'update_product_field': 'update_product_field_action',
    }

    def __init__(self):
        self.template_resolver = _TemplateResolver()

    def execute(self, actions, context, execution):
        results = []
        for action_config in actions:
            result = self.execute_single(action_config, context, execution)
            results.append(result)
        return results

    def execute_single(self, action_config, context, execution):
        action_type = action_config.get('type', '')
        config = action_config.get('config', {})

        handler_name = self.ACTION_HANDLERS.get(action_type)
        if not handler_name:
            return {
                'action_type': action_type,
                'status': 'skipped',
                'error': f'Unknown action type: {action_type}',
            }

        try:
            handler = getattr(self, handler_name, None)
            if not handler:
                return {
                    'action_type': action_type,
                    'status': 'skipped',
                    'error': f'Handler not found: {handler_name}',
                }
            result = handler(config, context)
            return {
                'action_type': action_type,
                'status': 'success',
                'result': result,
            }
        except Exception as exc:
            logger.exception('Action %s failed', action_type)
            return {
                'action_type': action_type,
                'status': 'failed',
                'error': str(exc),
            }

    def _resolve(self, template_str, context):
        return self.template_resolver.resolve(template_str, context)

    def _resolve_config(self, config, context):
        resolved = {}
        for key, value in config.items():
            if isinstance(value, str):
                resolved[key] = self._resolve(value, context)
            else:
                resolved[key] = value
        return resolved

    def _get_company(self, context):
        return context.get('company')

    def _get_user_by_role(self, company, role_slug):
        from users.models import User
        role_map = {
            'company_admin': 'COMPANY_ADMIN',
            'warehouse_manager': 'MANAGER',
            'account_manager': 'MANAGER',
            'dispatcher': 'STAFF',
            'accountant': 'STAFF',
            'sales_manager': 'MANAGER',
        }
        role = role_map.get(role_slug, role_slug.upper())
        return User.objects.filter(
            company=company, role=role, is_active=True
        ).first()

    def create_task_action(self, config, context):
        from spiskalar.models import Task
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)

        task_type_map = {
            'general': 'administrative',
            'picking': 'warehouse',
            'packing': 'warehouse',
            'delivery': 'warehouse',
            'restock': 'operational',
            'follow_up': 'customer',
            'approval': 'administrative',
        }
        task_type_raw = resolved.get('task_type', 'general')
        task_type = task_type_map.get(task_type_raw, 'custom')

        priority = resolved.get('priority', 'normal')
        if priority not in dict(Task.PRIORITY_CHOICES):
            priority = 'normal'

        due_date = None
        due_in_days = config.get('due_in_days', 1)
        try:
            due_in_days = int(due_in_days)
        except (TypeError, ValueError):
            due_in_days = 1
        due_date = timezone.now().date() + timedelta(days=due_in_days)

        assigned_to = None
        role = config.get('assigned_to_role', '')
        if role:
            assigned_to = self._get_user_by_role(company, role)

        task = Task.objects.create(
            company=company,
            title=resolved.get('title', 'Automation Task'),
            description=resolved.get('description', ''),
            task_type=task_type,
            priority=priority,
            assigned_to=assigned_to,
            due_date=due_date,
            created_by=None,
        )
        return {'task_id': str(task.pk), 'title': task.title}

    def send_notification_action(self, config, context):
        from notifications.models import Notification
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)

        notif_type = resolved.get('notification_type', 'system')
        valid_types = [c[0] for c in Notification.TYPE_CHOICES]
        if notif_type not in valid_types:
            notif_type = 'system'

        notify_role = config.get('notify_role', '')
        user = self._get_user_by_role(company, notify_role) if notify_role else None
        if not user:
            user = company.employees.filter(is_active=True).first()

        if not user:
            return {'error': 'No target user found'}

        notif = Notification.objects.create(
            company=company,
            user=user,
            title=resolved.get('title', 'Automation Notification'),
            message=resolved.get('message', ''),
            type=notif_type,
        )
        return {'notification_id': notif.pk}

    def create_alert_action(self, config, context):
        from notifications.models import Notification
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)

        severity = resolved.get('severity', 'info')
        severity_prefix = {'info': '[INFO]', 'warning': '[WARNING]', 'danger': '[ALERT]'}.get(severity, '')

        admin = company.employees.filter(is_active=True, role='COMPANY_ADMIN').first()
        if not admin:
            admin = company.employees.filter(is_active=True).first()
        if not admin:
            return {'error': 'No admin user found'}

        title = f"{severity_prefix} {resolved.get('title', 'Alert')}" if severity_prefix else resolved.get('title', 'Alert')
        notif = Notification.objects.create(
            company=company,
            user=admin,
            title=title,
            message=resolved.get('message', ''),
            type='system',
        )
        return {'notification_id': notif.pk, 'severity': severity}

    def add_comment_action(self, config, context):
        from spiskalar.models import Task, TaskComment
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)

        text = resolved.get('text', '')
        if not text:
            return {'error': 'Empty comment text'}

        task_id = context.get('task_id') or context.get('task', {})
        if isinstance(task_id, dict):
            task_id = task_id.get('id')

        if task_id:
            try:
                task = Task.objects.get(pk=task_id, company=company)
                comment = TaskComment.objects.create(
                    task=task,
                    user=None,
                    text=text,
                )
                return {'comment_id': comment.pk, 'task_id': str(task.pk)}
            except Task.DoesNotExist:
                pass

        from activity.models import Activity
        Activity.objects.create(
            company=company,
            activity_type='task_comment_added',
            description=text,
            user=None,
            related_object_type=config.get('object_type', ''),
            related_object_id=context.get('object_id'),
        )
        return {'activity_logged': True}

    def update_order_status_action(self, config, context):
        from orders.models import Order
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)
        new_status = resolved.get('new_status', '')

        order_id = context.get('order_id') or context.get('order', {})
        if isinstance(order_id, dict):
            order_id = order_id.get('id')
        if not order_id:
            return {'error': 'No order in context'}

        try:
            order = Order.objects.get(pk=order_id, company=company)
        except Order.DoesNotExist:
            return {'error': f'Order {order_id} not found'}

        if not order.can_transition(new_status):
            return {
                'error': f'Cannot transition from {order.status} to {new_status}',
                'allowed': Order.VALID_TRANSITIONS.get(order.status, []),
            }

        order.transition_to(new_status)
        return {'order_id': str(order.pk), 'new_status': new_status}

    def create_webhook_action(self, config, context):
        from integrations.models import IntegrationEvent
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)

        event = IntegrationEvent.objects.create(
            company=company,
            event_type=resolved.get('event_type', 'automation.event'),
            payload={
                'source': 'automation',
                'context': {k: str(v) for k, v in context.items() if k != 'company'},
            },
            source='automation',
        )
        return {'integration_event_id': str(event.pk)}

    def add_customer_tag_action(self, config, context):
        from crm.models import CustomerTag, CustomerTagAssignment
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)
        tag_name = resolved.get('tag_name', '').strip()
        if not tag_name:
            return {'error': 'Empty tag name'}

        customer_id = context.get('customer_id') or context.get('customer', {})
        if isinstance(customer_id, dict):
            customer_id = customer_id.get('id')
        if not customer_id:
            return {'error': 'No customer in context'}

        from sales.models import Customer
        try:
            customer = Customer.objects.get(pk=customer_id, company=company)
        except Customer.DoesNotExist:
            return {'error': f'Customer {customer_id} not found'}

        tag, _ = CustomerTag.objects.get_or_create(
            company=company, name=tag_name, defaults={'color': '#6366f1'}
        )
        assignment, created = CustomerTagAssignment.objects.get_or_create(
            customer=customer, tag=tag
        )
        return {
            'tag_id': tag.pk,
            'tag_name': tag.name,
            'created': created,
        }

    def create_reminder_action(self, config, context):
        from spiskalar.models import Task
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)

        remind_in_days = config.get('remind_in_days', 1)
        try:
            remind_in_days = int(remind_in_days)
        except (TypeError, ValueError):
            remind_in_days = 1

        due_date = timezone.now().date() + timedelta(days=remind_in_days)
        assigned_to = None
        role = config.get('assigned_to_role', '')
        if role:
            assigned_to = self._get_user_by_role(company, role)

        task = Task.objects.create(
            company=company,
            title=f"[Reminder] {resolved.get('title', 'Reminder')}",
            description=resolved.get('message', ''),
            task_type='operational',
            priority='normal',
            assigned_to=assigned_to,
            due_date=due_date,
            created_by=None,
        )
        return {'task_id': str(task.pk), 'title': task.title, 'due_date': str(due_date)}

    def update_product_field_action(self, config, context):
        from products.models import Product
        company = self._get_company(context)
        if not company:
            return {'error': 'No company in context'}
        resolved = self._resolve_config(config, context)

        field = resolved.get('field', '')
        value = resolved.get('value', '')
        allowed_fields = {'status', 'min_stock', 'notes'}
        if field not in allowed_fields:
            return {'error': f'Field {field} not allowed. Allowed: {allowed_fields}'}

        product_id = context.get('product_id') or context.get('product', {})
        if isinstance(product_id, dict):
            product_id = product_id.get('id')
        if not product_id:
            return {'error': 'No product in context'}

        try:
            product = Product.objects.get(pk=product_id, company=company)
        except Product.DoesNotExist:
            return {'error': f'Product {product_id} not found'}

        if field == 'min_stock':
            try:
                value = int(value)
            except (TypeError, ValueError):
                return {'error': f'Invalid value for min_stock: {value}'}

        setattr(product, field, value)
        product.save(update_fields=[field, 'updated_at'])
        return {'product_id': str(product.pk), 'field': field, 'value': str(value)}

    def resolve_template(self, template_str, context):
        return self.template_resolver.resolve(template_str, context)


# ============================================================
# 4. AUTOMATION ENGINE
# ============================================================

class AutomationEngine:
    """
    Core engine that processes events against automation rules.
    """

    def process_event(self, event):
        from automation.models import AutomationEvent, AutomationRule
        try:
            company = event.company
            rules = self.find_matching_rules(event, company)

            for rule in rules:
                if not self.check_idempotency(rule, event):
                    continue
                if not self.check_loop_depth(event, rule):
                    logger.warning(
                        'Loop depth exceeded for rule %s, event %s',
                        rule.pk, event.event_id,
                    )
                    continue
                if not self.check_rate_limit(rule):
                    logger.warning('Rate limit exceeded for rule %s', rule.pk)
                    continue

                execution = self.create_execution(rule, event)
                self._process_rule(rule, event, execution)

            event.processed = True
            event.processed_at = timezone.now()
            event.save(update_fields=['processed', 'processed_at'])

        except Exception:
            logger.exception('AutomationEngine.process_event failed')

    def _process_rule(self, rule, event, execution):
        try:
            evaluator = ConditionEvaluator()
            conditions = rule.conditions or {}
            context = self._build_context(event)

            matched = evaluator.evaluate(conditions, context)
            execution.conditions_matched = matched

            if not matched:
                self.update_execution_status(
                    execution, 'completed',
                    result_summary='Conditions not met',
                )
                return

            self.update_execution_status(execution, 'running')

            executor = ActionExecutor()
            action_results = executor.execute(rule.actions, context, execution)

            succeeded = sum(1 for r in action_results if r.get('status') == 'success')
            failed = sum(1 for r in action_results if r.get('status') == 'failed')
            skipped = sum(1 for r in action_results if r.get('status') == 'skipped')

            if failed > 0 and succeeded > 0:
                status = 'partial'
            elif failed > 0 and succeeded == 0:
                status = 'failed'
            else:
                status = 'completed'

            execution.action_results = action_results
            self.update_execution_status(
                execution, status,
                actions_total=len(action_results),
                actions_succeeded=succeeded,
                actions_failed=failed,
                actions_skipped=skipped,
                result_summary=f'{succeeded} succeeded, {failed} failed, {skipped} skipped',
            )

            rule.execution_count += 1
            rule.last_executed = timezone.now()
            if failed > 0:
                rule.error_count += 1
            rule.save(update_fields=['execution_count', 'last_executed', 'error_count'])

        except Exception as exc:
            logger.exception('Rule execution failed for rule %s', rule.pk)
            self.update_execution_status(
                execution, 'failed',
                error_message=str(exc),
                error_details={'traceback': traceback.format_exc()},
            )
            rule.error_count += 1
            rule.save(update_fields=['error_count'])

    def _build_context(self, event):
        context = {
            'company': event.company,
            'event_type': event.event_type,
            'object_type': event.object_type,
            'object_id': event.object_id,
        }
        if event.data:
            for key, value in event.data.items():
                context[key] = value

        if event.object_type and event.object_id:
            obj_data = get_context_for_object(
                event.object_type, event.object_id, event.company
            )
            context.update(obj_data)

        return context

    def find_matching_rules(self, event, company):
        from automation.models import AutomationRule
        return AutomationRule.objects.filter(
            company=company,
            status='active',
            trigger_type=event.event_type,
        ).order_by('-priority', 'created_at')

    def check_idempotency(self, rule, event):
        from automation.models import AutomationExecution
        key = f"{rule.pk}:{event.event_id}"
        exists = AutomationExecution.objects.filter(
            rule=rule, idempotency_key=key,
            status__in=['completed', 'running', 'pending'],
        ).exists()
        return not exists

    def check_loop_depth(self, event, rule):
        max_depth = rule.max_execution_depth or 5
        return event.processing_depth < max_depth

    def check_rate_limit(self, rule):
        if not rule.rate_limit_per_hour:
            return True
        from automation.models import AutomationExecution
        one_hour_ago = timezone.now() - timedelta(hours=1)
        count = AutomationExecution.objects.filter(
            rule=rule,
            created_at__gte=one_hour_ago,
            status__in=['completed', 'running', 'partial'],
        ).count()
        return count < rule.rate_limit_per_hour

    def create_execution(self, rule, event, dry_run=False):
        from automation.models import AutomationExecution
        execution = AutomationExecution.objects.create(
            rule=rule,
            event_id=event.event_id,
            event_type=event.event_type,
            object_type=event.object_type,
            object_id=event.object_id,
            company=event.company,
            status='pending',
            execution_depth=event.processing_depth,
            idempotency_key=f"{rule.pk}:{event.event_id}",
            dry_run=dry_run,
        )
        return execution

    def update_execution_status(self, execution, status, **kwargs):
        execution.status = status
        now = timezone.now()

        if status == 'running' and not execution.started_at:
            execution.started_at = now
        if status in ('completed', 'failed', 'partial', 'cancelled', 'skipped'):
            execution.completed_at = now
            if execution.started_at:
                delta = now - execution.started_at
                execution.duration_ms = int(delta.total_seconds() * 1000)

        for key, value in kwargs.items():
            if hasattr(execution, key):
                setattr(execution, key, value)

        update_fields = ['status', 'started_at', 'completed_at', 'duration_ms']
        for key in kwargs:
            update_fields.append(key)
        update_fields = list(set(update_fields))
        execution.save(update_fields=update_fields)


# ============================================================
# 5. SCHEDULER
# ============================================================

class Scheduler:
    """
    Handles scheduled automation rule execution.
    """

    def get_due_scheduled_rules(self):
        from automation.models import AutomationSchedule
        now = timezone.now()
        schedules = AutomationSchedule.objects.filter(
            is_active=True,
            next_run__lte=now,
            rule__status='active',
        ).select_related('rule')
        return schedules

    def update_next_run(self, schedule):
        from automation.models import AutomationSchedule
        now = timezone.now()
        config = schedule.config or {}

        if schedule.schedule_type == 'daily':
            hour = config.get('hour', 0)
            minute = config.get('minute', 0)
            next_day = now + timedelta(days=1)
            schedule.next_run = next_day.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        elif schedule.schedule_type == 'weekly':
            weekday = config.get('weekday', 0)
            hour = config.get('hour', 0)
            minute = config.get('minute', 0)
            days_ahead = weekday - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_date = now + timedelta(days=days_ahead)
            schedule.next_run = next_date.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        elif schedule.schedule_type == 'monthly':
            day = config.get('day', 1)
            hour = config.get('hour', 0)
            minute = config.get('minute', 0)
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            actual_day = min(day, 28)
            schedule.next_run = next_month.replace(
                day=actual_day, hour=hour, minute=minute, second=0, microsecond=0
            )
        elif schedule.schedule_type == 'interval':
            minutes = config.get('interval_minutes', 60)
            schedule.next_run = now + timedelta(minutes=minutes)
        else:
            schedule.next_run = now + timedelta(hours=1)

        schedule.last_run = now
        schedule.save(update_fields=['next_run', 'last_run', 'updated_at'])

    def run_scheduled(self, rule):
        from automation.models import AutomationEvent
        try:
            event = AutomationEvent.objects.create(
                company=rule.company,
                event_type=rule.trigger_type,
                event_id=f"scheduled:{rule.pk}:{timezone.now().isoformat()}",
                object_type='scheduled_rule',
                object_id=str(rule.pk),
                data={'scheduled': True, 'rule_id': str(rule.pk)},
                source='scheduler',
            )
            engine = AutomationEngine()
            engine.process_event(event)

            if hasattr(rule, 'schedule'):
                schedule = rule.schedule
                self.update_next_run(schedule)
        except Exception:
            logger.exception('Scheduled execution failed for rule %s', rule.pk)


# ============================================================
# 6. HELPER FUNCTIONS
# ============================================================

def trigger_event(event_type, company_id, object_type='', object_id='', data=None):
    from users.models import Company
    try:
        company = Company.objects.get(pk=company_id)
    except Company.DoesNotExist:
        logger.error('Company %s not found', company_id)
        return None
    bus = EventBus()
    return bus.emit(event_type, company, object_type, object_id, data)


def get_context_for_object(object_type, object_id, company):
    context = {}
    try:
        model_map = {
            'product': ('products.models', 'Product'),
            'order': ('orders.models', 'Order'),
            'sale': ('sales.models', 'Sale'),
            'customer': ('sales.models', 'Customer'),
            'task': ('spiskalar.models', 'Task'),
            'purchase': ('purchases.models', 'Purchase'),
            'payment': ('finance.models', 'Payment'),
            'expense': ('finance.models', 'Expense'),
            'delivery': ('logistics.models', 'Delivery'),
            'shipment': ('logistics.models', 'Shipment'),
        }

        if object_type not in model_map:
            return context

        module_path, model_name = model_map[object_type]
        import importlib
        module = importlib.import_module(module_path)
        model = getattr(module, model_name)

        obj = model.objects.filter(pk=object_id, company=company).first()
        if not obj:
            return context

        prefix = object_type
        context[f'{prefix}_id'] = str(obj.pk)

        if hasattr(obj, 'name'):
            context[f'{prefix}.name'] = obj.name
            context[f'{prefix}_name'] = obj.name

        if hasattr(obj, 'status'):
            context[f'{prefix}.status'] = obj.status
            context[f'{prefix}_status'] = obj.status

        if hasattr(obj, 'title'):
            context[f'{prefix}.title'] = obj.title
            context[f'{prefix}_title'] = obj.title

        if hasattr(obj, 'total'):
            context[f'{prefix}.total'] = str(obj.total)
            context[f'{prefix}_total'] = str(obj.total)

        if hasattr(obj, 'quantity'):
            context[f'{prefix}.quantity'] = obj.quantity
            context[f'{prefix}_quantity'] = obj.quantity

        if hasattr(obj, 'price'):
            context[f'{prefix}.price'] = str(obj.price)
            context[f'{prefix}_price'] = str(obj.price)

        if hasattr(obj, 'priority'):
            context[f'{prefix}.priority'] = obj.priority
            context[f'{prefix}_priority'] = obj.priority

        if hasattr(obj, 'payment_status'):
            context[f'{prefix}.payment_status'] = obj.payment_status

        if hasattr(obj, 'due_date') and obj.due_date:
            context[f'{prefix}.due_date'] = str(obj.due_date)
            context[f'{prefix}_due_date'] = str(obj.due_date)

        if hasattr(obj, 'created_at'):
            context[f'{prefix}.created_at'] = str(obj.created_at)

        if hasattr(obj, 'reference'):
            context[f'{prefix}.reference'] = obj.reference
            context[f'{prefix}_reference'] = obj.reference

        if hasattr(obj, 'sku'):
            context[f'{prefix}.sku'] = obj.sku
            context[f'{prefix}_sku'] = obj.sku

        if hasattr(obj, 'customer') and obj.customer:
            context['customer_id'] = str(obj.customer.pk)
            context['customer.name'] = obj.customer.name
            context['customer_name'] = obj.customer.name

        if hasattr(obj, 'product') and obj.product:
            context['product_id'] = str(obj.product.pk)
            context['product.name'] = obj.product.name
            context['product_name'] = obj.product.name
            context['product.quantity'] = obj.product.quantity
            context['product.sku'] = obj.product.sku

        context.update({
            f'{prefix}.{k}': str(v) if not isinstance(v, (int, float, bool)) else v
            for k, v in vars(obj).items()
            if not k.startswith('_')
            and not callable(v)
            and v is not None
        })

    except Exception:
        logger.exception('get_context_for_object failed for %s/%s', object_type, object_id)

    return context


# ============================================================
# 7. TEMPLATE RESOLVER (internal helper)
# ============================================================

class _TemplateResolver:
    _PATTERN = re.compile(r'\{\{(.+?)\}\}')

    def resolve(self, template_str, context):
        if not template_str or '{{' not in str(template_str):
            return template_str

        def replacer(match):
            field_path = match.group(1).strip()
            value = self._get_nested(field_path, context)
            return str(value) if value is not None else ''

        return self._PATTERN.sub(replacer, str(template_str))

    def _get_nested(self, field_path, context):
        parts = field_path.split('.')
        value = context
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None) if hasattr(value, '__dict__') else None
            if value is None:
                return None
        return value


# ============================================================
# 8. PREDEFINED AUTOMATION TEMPLATES
# ============================================================

AUTOMATION_TEMPLATES = [
    {
        'name': 'Low Stock Alert',
        'description': 'Automatically notify when a product falls below minimum stock level. Creates a restock task and sends an alert to the warehouse manager.',
        'trigger_type': 'inventory.stock_below_minimum',
        'conditions': {
            'logic': 'all',
            'items': [
                {'field': 'product.quantity', 'operator': 'lte', 'value': '{{product.min_stock}}'},
            ],
        },
        'actions': [
            {
                'type': 'create_alert',
                'config': {
                    'title': 'Low Stock: {{product.name}}',
                    'message': 'Product {{product.name}} (SKU: {{product.sku}}) has {{product.quantity}} units remaining, which is below minimum stock.',
                    'severity': 'warning',
                },
            },
            {
                'type': 'create_task',
                'config': {
                    'title': 'Restock {{product.name}}',
                    'description': 'Product {{product.name}} (SKU: {{product.sku}}) needs restocking. Current quantity: {{product.quantity}}.',
                    'task_type': 'restock',
                    'priority': 'high',
                    'assigned_to_role': 'warehouse_manager',
                    'due_in_days': 2,
                },
            },
        ],
        'priority': 'high',
    },
    {
        'name': 'Order Fulfillment',
        'description': 'When an order is confirmed, automatically create picking and packing tasks for the warehouse team.',
        'trigger_type': 'order.confirmed',
        'conditions': {
            'logic': 'all',
            'items': [
                {'field': 'order.status', 'operator': 'equals', 'value': 'confirmed'},
            ],
        },
        'actions': [
            {
                'type': 'create_task',
                'config': {
                    'title': 'Pick Order {{order.reference}}',
                    'description': 'Pick items for order {{order.reference}}. Total items to pick.',
                    'task_type': 'picking',
                    'priority': 'high',
                    'assigned_to_role': 'warehouse_manager',
                    'due_in_days': 1,
                },
            },
            {
                'type': 'send_notification',
                'config': {
                    'title': 'New Order to Fulfill',
                    'message': 'Order {{order.reference}} has been confirmed and requires picking.',
                    'notification_type': 'new_order',
                    'notify_role': 'warehouse_manager',
                },
            },
        ],
        'priority': 'high',
    },
    {
        'name': 'Overdue Customer',
        'description': 'When a customer has an overdue payment, create a follow-up task for the account manager.',
        'trigger_type': 'sale.payment_overdue',
        'conditions': {
            'logic': 'all',
            'items': [
                {'field': 'sale.payment_status', 'operator': 'in_list', 'value': 'unpaid,partial'},
            ],
        },
        'actions': [
            {
                'type': 'create_task',
                'config': {
                    'title': 'Follow up on overdue payment - {{customer.name}}',
                    'description': 'Customer {{customer.name}} has an overdue payment for sale. Contact them to arrange payment.',
                    'task_type': 'follow_up',
                    'priority': 'high',
                    'assigned_to_role': 'account_manager',
                    'due_in_days': 1,
                },
            },
            {
                'type': 'send_notification',
                'config': {
                    'title': 'Payment Overdue',
                    'message': 'Sale payment from {{customer.name}} is overdue. Immediate follow-up required.',
                    'notification_type': 'payment_overdue',
                    'notify_role': 'account_manager',
                },
            },
        ],
        'priority': 'high',
    },
    {
        'name': 'Failed Delivery',
        'description': 'When a delivery fails, notify the dispatcher and create a reschedule task.',
        'trigger_type': 'logistics.delivery_failed',
        'conditions': {
            'logic': 'all',
            'items': [
                {'field': 'event_type', 'operator': 'equals', 'value': 'logistics.delivery_failed'},
            ],
        },
        'actions': [
            {
                'type': 'create_task',
                'config': {
                    'title': 'Reschedule failed delivery for order {{order.reference}}',
                    'description': 'A delivery attempt has failed. Contact the customer and reschedule.',
                    'task_type': 'delivery',
                    'priority': 'urgent',
                    'assigned_to_role': 'dispatcher',
                    'due_in_days': 0,
                },
            },
            {
                'type': 'send_notification',
                'config': {
                    'title': 'Delivery Failed',
                    'message': 'Delivery for order {{order.reference}} has failed and requires immediate attention.',
                    'notification_type': 'system',
                    'notify_role': 'dispatcher',
                },
            },
        ],
        'priority': 'critical',
    },
    {
        'name': 'Payment Reminder',
        'description': 'Scheduled daily check for upcoming payment due dates. Creates reminders for accounts payable.',
        'trigger_type': 'schedule.daily',
        'conditions': {
            'logic': 'all',
            'items': [],
        },
        'actions': [
            {
                'type': 'send_notification',
                'config': {
                    'title': 'Daily Payment Check',
                    'message': 'Review pending payments and supplier due dates for today.',
                    'notification_type': 'system',
                    'notify_role': 'accountant',
                },
            },
        ],
        'priority': 'normal',
    },
]


def get_automation_templates():
    return AUTOMATION_TEMPLATES


def create_from_template(template_index, company, user):
    from automation.models import AutomationRule

    if template_index < 0 or template_index >= len(AUTOMATION_TEMPLATES):
        return None, 'Invalid template index'

    template = AUTOMATION_TEMPLATES[template_index]

    rule = AutomationRule.objects.create(
        company=company,
        name=template['name'],
        description=template['description'],
        trigger_type=template['trigger_type'],
        conditions=template['conditions'],
        actions=template['actions'],
        priority=template.get('priority', 'normal'),
        status='active',
        created_by=user,
        updated_by=user,
        is_template=False,
    )
    return rule, None


# ============================================================
# 9. TEST RULE (DRY RUN)
# ============================================================

def test_rule(rule, company):
    """Dry-run test: evaluates conditions and previews actions without executing."""
    result = {
        'rule_name': rule.name,
        'trigger_type': rule.trigger_type,
        'conditions_evaluated': False,
        'conditions_result': False,
        'conditions_details': [],
        'actions_preview': [],
        'would_execute': False,
    }

    evaluator = ConditionEvaluator()

    if rule.conditions and rule.conditions.get('items'):
        result['conditions_evaluated'] = True
        context = {
            'company': {'id': company.id, 'name': str(company)},
            'rule': {'name': rule.name, 'trigger': rule.trigger_type},
        }
        matched = evaluator.evaluate(rule.conditions, context)
        result['conditions_result'] = matched
        result['would_execute'] = matched or not rule.conditions.get('items')
    else:
        result['conditions_result'] = True
        result['would_execute'] = True

    for action in rule.actions:
        action_type = action.get('type', 'unknown')
        from .models import ACTION_TYPES
        action_def = ACTION_TYPES.get(action_type, {})
        config = action.get('config', {})
        result['actions_preview'].append({
            'type': action_type,
            'label': action_def.get('label', action_type),
            'config': config,
            'would_execute': True,
        })

    return result
