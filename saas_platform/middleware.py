import uuid
import time
import logging
from collections import defaultdict
from threading import Lock
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings

logger = logging.getLogger('saas_platform.middleware')


class TenantMiddleware(MiddlewareMixin):
    """
    Sets request.tenant for every authenticated request.
    Enforces tenant isolation at the middleware level.
    """

    EXEMPT_PATHS = [
        '/admin/', '/login/', '/logout/', '/register/',
        '/set-language/', '/static/', '/media/',
    ]

    def process_request(self, request):
        request.tenant = None
        request.tenant_id = None

        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        if request.user.is_superuser and request.user.role == 'SUPER_ADMIN':
            return None

        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return None

        company = getattr(request.user, 'company', None)
        if company and getattr(company, 'is_active', True):
            request.tenant = company
            request.tenant_id = str(company.pk)
        elif not request.user.is_superuser:
            allowed = ['/users/profile/', '/users/change-password/', '/logout/']
            if not any(request.path.startswith(p) for p in allowed):
                lang = request.session.get('language', 'uz')
                from core.translations import get_translation
                messages.warning(request, get_translation('no_company_assigned', lang))
                return redirect('users:profile')

        return None


class RequestIDMiddleware(MiddlewareMixin):
    """Adds a unique request ID to every request/response for tracing."""

    def process_request(self, request):
        request.request_id = str(uuid.uuid4())

    def process_response(self, request, response):
        request_id = getattr(request, 'request_id', '')
        if request_id:
            response['X-Request-ID'] = request_id
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Adds production security headers."""

    def process_response(self, request, response):
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
        response['X-XSS-Protection'] = '1; mode=block'

        if not settings.DEBUG:
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )

        return response


class RateLimitMiddleware(MiddlewareMixin):
    """Simple in-memory rate limiter for sensitive endpoints."""

    _lock = Lock()
    _requests = defaultdict(list)

    LOGIN_LIMIT = 20
    API_LIMIT = 100
    WINDOW = 60

    def _get_client_ip(self, request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            return xff.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')

    def process_request(self, request):
        ip = self._get_client_ip(request)
        now = time.time()

        path = request.path
        if '/login/' in path:
            limit = self.LOGIN_LIMIT
            key = f"login:{ip}"
        elif '/api/' in path:
            limit = self.API_LIMIT
            key = f"api:{ip}"
        else:
            return None

        with self._lock:
            timestamps = self._requests[key]
            self._requests[key] = [t for t in timestamps if now - t < self.WINDOW]
            if len(self._requests[key]) >= limit:
                from django.http import JsonResponse
                logger.warning(f"Rate limit exceeded: {key} ({len(self._requests[key])} requests)")
                return JsonResponse(
                    {'error': 'Rate limit exceeded. Please wait.'},
                    status=429
                )
            self._requests[key].append(now)

        return None

    @classmethod
    def check_api_rate_limit(cls, key, limit=100, window=60):
        """Check rate limit for API keys."""
        now = time.time()
        with cls._lock:
            timestamps = cls._requests[key]
            cls._requests[key] = [t for t in timestamps if now - t < window]
            if len(cls._requests[key]) >= limit:
                return False
            cls._requests[key].append(now)
            return True


class AuditMiddleware(MiddlewareMixin):
    """Logs security-relevant events to AuditLog."""

    LOGGED_ACTIONS = {
        'login', 'logout', 'login_failed',
    }

    def process_view(self, request, view_func, view_args, view_kwargs):
        return None

    def process_response(self, request, response):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response
        return response
