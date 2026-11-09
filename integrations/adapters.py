import uuid
import time
import hashlib
import hmac
import json
import logging
from abc import ABC, abstractmethod
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger('integrations')


def generate_correlation_id():
    return str(uuid.uuid4())


class BaseAdapter(ABC):
    """Base class for all integration adapters."""

    def __init__(self, connection):
        self.connection = connection
        self.config = connection.config or {}
        self._credentials = None

    @property
    def credentials(self):
        if self._credentials is None:
            self._credentials = {
                c.key_name: c.value for c in self.connection.credentials.all()
            }
        return self._credentials

    def get_credential(self, key, default=None):
        return self.credentials.get(key, default)

    def get_config(self, key, default=None):
        return self.config.get(key, default)

    @abstractmethod
    def test_connection(self):
        """Test the connection. Returns dict with status and message."""
        pass

    def health_check(self):
        """Check adapter health. Override for provider-specific checks."""
        return {'status': 'unknown', 'message': 'Health check not implemented'}

    def log(self, action, direction, status, **kwargs):
        """Create an integration log entry."""
        from .models import IntegrationLog
        correlation_id = kwargs.pop('correlation_id', generate_correlation_id())
        IntegrationLog.objects.create(
            company=self.connection.company,
            connection=self.connection,
            correlation_id=correlation_id,
            action=action,
            direction=direction,
            status=status,
            method=kwargs.pop('method', ''),
            endpoint_url=kwargs.pop('endpoint_url', ''),
            status_code=kwargs.pop('status_code', None),
            external_id=kwargs.pop('external_id', ''),
            internal_id=kwargs.pop('internal_id', ''),
            request_summary=kwargs.pop('request_summary', ''),
            response_summary=kwargs.pop('response_summary', ''),
            error_message=kwargs.pop('error_message', ''),
            error_category=kwargs.pop('error_category', ''),
            duration_ms=kwargs.pop('duration_ms', None),
        )

    def handle_success(self, action, direction, duration_ms=None, **kwargs):
        self.connection.success_count += 1
        self.connection.failure_count = max(0, self.connection.failure_count - 1)
        self.connection.last_error = ''
        self.connection.health_status = 'healthy'
        self.connection.save(update_fields=['success_count', 'failure_count', 'last_error', 'health_status'])
        self.log(action, direction, 'success', duration_ms=duration_ms, **kwargs)

    def handle_error(self, action, direction, error_message, error_category='internal_error', duration_ms=None, **kwargs):
        self.connection.failure_count += 1
        self.connection.last_error = error_message
        self.connection.save(update_fields=['failure_count', 'last_error'])
        self.log(action, direction, 'error', error_message=error_message, error_category=error_category, duration_ms=duration_ms, **kwargs)
        self._record_error(action, error_message, error_category)
        self._check_circuit_breaker()

    def _record_error(self, action, message, category):
        from .models import IntegrationError
        IntegrationError.objects.update_or_create(
            company=self.connection.company,
            connection=self.connection,
            error_type=action,
            status='open',
            defaults={
                'category': category,
                'message': message,
                'severity': 'high' if category in ('authentication', 'network') else 'medium',
                'retry_available': True,
            }
        )

    def _check_circuit_breaker(self):
        from .models import CircuitBreakerState
        state, _ = CircuitBreakerState.objects.get_or_create(connection=self.connection)
        state.failure_count += 1
        state.last_failure = timezone.now()
        if state.failure_count >= state.failure_threshold and state.state == 'closed':
            state.state = 'open'
            state.opened_at = timezone.now()
            self.connection.health_status = 'circuit_open'
            self.connection.circuit_open_until = timezone.now() + timedelta(seconds=state.recovery_timeout_seconds)
            self.connection.save(update_fields=['health_status', 'circuit_open_until'])
        state.save()


class PaymentAdapter(BaseAdapter):
    """Base adapter for payment providers."""

    def create_payment(self, amount, currency, order_id, description='', **kwargs):
        raise NotImplementedError

    def check_payment(self, payment_id):
        raise NotImplementedError

    def cancel_payment(self, payment_id):
        raise NotImplementedError

    def refund_payment(self, payment_id, amount=None):
        raise NotImplementedError

    def verify_webhook(self, payload, signature):
        return True


class BankAdapter(BaseAdapter):
    """Base adapter for bank integrations."""

    def get_balance(self, account_id=None):
        raise NotImplementedError

    def get_transactions(self, account_id=None, date_from=None, date_to=None):
        raise NotImplementedError

    def create_payment(self, amount, recipient, account_id=None, **kwargs):
        raise NotImplementedError

    def check_payment(self, payment_id):
        raise NotImplementedError


class SMSAdapter(BaseAdapter):
    """Base adapter for SMS providers."""

    def send_sms(self, phone_number, message, **kwargs):
        raise NotImplementedError

    def get_status(self, message_id):
        raise NotImplementedError


class EmailAdapter(BaseAdapter):
    """Base adapter for email providers."""

    def send_email(self, to, subject, body, html_body='', **kwargs):
        raise NotImplementedError

    def get_status(self, message_id):
        raise NotImplementedError


class TelegramAdapter(BaseAdapter):
    """Base adapter for Telegram integration."""

    def send_message(self, chat_id, message, **kwargs):
        raise NotImplementedError

    def get_updates(self, offset=None):
        raise NotImplementedError

    def send_order_notification(self, chat_id, order_data):
        raise NotImplementedError


class MarketplaceAdapter(BaseAdapter):
    """Base adapter for marketplace integrations."""

    def create_product(self, product_data):
        raise NotImplementedError

    def update_product(self, external_id, product_data):
        raise NotImplementedError

    def update_stock(self, external_id, quantity):
        raise NotImplementedError

    def update_price(self, external_id, price):
        raise NotImplementedError

    def get_orders(self, date_from=None, date_to=None):
        raise NotImplementedError

    def update_order_status(self, external_order_id, status):
        raise NotImplementedError


class LogisticsAdapter(BaseAdapter):
    """Base adapter for logistics/shipping providers."""

    def create_shipment(self, shipment_data):
        raise NotImplementedError

    def get_tracking(self, tracking_number):
        raise NotImplementedError

    def cancel_shipment(self, shipment_id):
        raise NotImplementedError

    def calculate_rate(self, origin, destination, weight, dimensions=None):
        raise NotImplementedError


class DocumentAdapter(BaseAdapter):
    """Base adapter for EDO/document exchange providers."""

    def send_document(self, document_data):
        raise NotImplementedError

    def get_status(self, external_doc_id):
        raise NotImplementedError

    def download_document(self, external_doc_id):
        raise NotImplementedError

    def cancel_document(self, external_doc_id):
        raise NotImplementedError

    def validate_document(self, document_data):
        raise NotImplementedError


class MarkingAdapter(BaseAdapter):
    """Base adapter for product marking providers."""

    def validate_code(self, code):
        raise NotImplementedError

    def register_code(self, code_data):
        raise NotImplementedError

    def get_status(self, code):
        raise NotImplementedError

    def submit_event(self, event_data):
        raise NotImplementedError


class OneCAdapter(BaseAdapter):
    """Base adapter for 1C integration."""

    def sync_products(self, products, direction='outbound'):
        raise NotImplementedError

    def sync_orders(self, orders, direction='outbound'):
        raise NotImplementedError

    def sync_customers(self, customers, direction='outbound'):
        raise NotImplementedError

    def sync_stock(self, stock_data, direction='outbound'):
        raise NotImplementedError

    def sync_payments(self, payments, direction='outbound'):
        raise NotImplementedError

    def get_exchange_data(self, data_type, last_sync=None):
        raise NotImplementedError


class AccountingAdapter(BaseAdapter):
    """Base adapter for accounting system integration."""

    def export_sales(self, sales_data, date_from=None, date_to=None):
        raise NotImplementedError

    def export_purchases(self, purchases_data, date_from=None, date_to=None):
        raise NotImplementedError

    def export_payments(self, payments_data, date_from=None, date_to=None):
        raise NotImplementedError

    def import_account_data(self, data_type):
        raise NotImplementedError


class CustomAPIAdapter(BaseAdapter):
    """Base adapter for custom API integrations."""

    def make_request(self, method, endpoint, data=None, headers=None, **kwargs):
        raise NotImplementedError

    def test_connection(self):
        try:
            result = self.make_request('GET', self.get_config('test_endpoint', '/'))
            return {'status': 'connected', 'message': 'Connection successful'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}


class WebhookSigner:
    """Sign and verify webhook payloads."""

    @staticmethod
    def sign(payload, secret, algorithm='sha256'):
        if isinstance(payload, dict):
            payload = json.dumps(payload, sort_keys=True, default=str)
        payload_bytes = payload.encode('utf-8') if isinstance(payload, str) else payload
        signature = hmac.new(secret.encode('utf-8'), payload_bytes, getattr(hashlib, algorithm)).hexdigest()
        return f"{algorithm}={signature}"

    @staticmethod
    def verify(payload, signature, secret, algorithm='sha256'):
        expected = WebhookSigner.sign(payload, secret, algorithm)
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def generate_secret():
        return secrets.token_hex(32)


import secrets


class WebhookDispatcher:
    """Dispatch outgoing webhooks with retries."""

    def __init__(self, endpoint):
        self.endpoint = endpoint

    def dispatch(self, event_type, payload):
        from .models import WebhookEvent
        event_id = generate_correlation_id()
        idempotency_key = f"{event_type}_{event_id}"

        event = WebhookEvent.objects.create(
            endpoint=self.endpoint,
            event_id=event_id,
            event_type=event_type,
            schema_version='1.0',
            direction='outgoing',
            status='processing',
            payload=payload,
            idempotency_key=idempotency_key,
            last_attempt=timezone.now(),
        )

        secret = self.endpoint.secret
        if secret:
            signature = WebhookSigner.sign(payload, secret)
        else:
            signature = ''

        try:
            import urllib.request
            import urllib.error

            data = json.dumps({
                'event_id': event_id,
                'event_type': event_type,
                'schema_version': '1.0',
                'timestamp': timezone.now().isoformat(),
                'data': payload,
                'signature': signature,
            }).encode('utf-8')

            headers = {
                'Content-Type': 'application/json',
                'X-Webhook-Event-ID': event_id,
                'X-Webhook-Event-Type': event_type,
                'X-Webhook-Signature': signature,
            }
            headers.update(self.endpoint.headers or {})

            req = urllib.request.Request(self.endpoint.url, data=data, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                event.response_status = response.status
                event.response_body = response.read().decode('utf-8', errors='replace')[:2000]
                event.status = 'processed'
                event.processed_at = timezone.now()
                event.duration_ms = int((timezone.now() - event.last_attempt).total_seconds() * 1000)
                event.save()
                self.endpoint.last_triggered = timezone.now()
                self.endpoint.last_success = timezone.now()
                self.endpoint.failure_count = 0
                self.endpoint.save(update_fields=['last_triggered', 'last_success', 'failure_count'])
                return True

        except Exception as e:
            event.attempt_count += 1
            event.error_message = str(e)[:2000]
            event.last_attempt = timezone.now()
            if event.attempt_count < event.max_attempts:
                event.status = 'retrying'
                event.next_retry = timezone.now() + timedelta(minutes=event.attempt_count * 5)
            else:
                event.status = 'failed'
            event.save()
            self.endpoint.failure_count += 1
            self.endpoint.last_error = str(e)[:500]
            self.endpoint.save(update_fields=['failure_count', 'last_error'])
            return False


class AdapterRegistry:
    """Registry for provider adapters."""
    _adapters = {}

    @classmethod
    def register(cls, provider_code, adapter_class):
        cls._adapters[provider_code] = adapter_class

    @classmethod
    def get(cls, provider_code):
        return cls._adapters.get(provider_code)

    @classmethod
    def get_all(cls):
        return dict(cls._adapters)

    @classmethod
    def get_adapter(cls, connection):
        adapter_class = cls._adapters.get(connection.provider.code)
        if adapter_class:
            return adapter_class(connection)
        return None
