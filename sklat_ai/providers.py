import os
import json
import time
import hashlib
import threading
import logging
from collections import defaultdict
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


class AIProviderBase:
    """Base class for AI providers."""
    
    def __init__(self, config):
        self.config = config
    
    def chat(self, messages, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError
    
    def analyze(self, system_prompt, user_prompt, **kwargs) -> str:
        raise NotImplementedError
    
    def summarize(self, text, **kwargs) -> str:
        raise NotImplementedError


class OpenAIProvider(AIProviderBase):
    """OpenAI-compatible provider."""
    
    def chat(self, messages, **kwargs):
        try:
            import urllib.request
            import urllib.error
            
            api_key = self.config.api_key_encrypted or os.environ.get('OPENAI_API_KEY', '')
            if not api_key:
                return {'success': False, 'error': 'No API key configured', 'content': '', 'tokens': {'input': 0, 'output': 0}}
            
            url = f"{self.config.api_base_url}/chat/completions"
            payload = {
                'model': self.config.model_name,
                'messages': messages,
                'temperature': kwargs.get('temperature', self.config.temperature),
                'max_tokens': kwargs.get('max_tokens', self.config.max_tokens),
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('Authorization', f'Bearer {api_key}')
            
            start = time.time()
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                result = json.loads(response.read().decode('utf-8'))
            
            elapsed_ms = int((time.time() - start) * 1000)
            
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            usage = result.get('usage', {})
            
            return {
                'success': True,
                'content': content,
                'tokens': {
                    'input': usage.get('prompt_tokens', 0),
                    'output': usage.get('completion_tokens', 0),
                },
                'response_time_ms': elapsed_ms,
                'model': result.get('model', self.config.model_name),
            }
        
        except Exception as e:
            logger.error(f"OpenAI provider error: {e}")
            return {'success': False, 'error': str(e), 'content': '', 'tokens': {'input': 0, 'output': 0}}
    
    def analyze(self, system_prompt, user_prompt, **kwargs):
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ]
        result = self.chat(messages, **kwargs)
        return result.get('content', '') if result.get('success') else ''
    
    def summarize(self, text, **kwargs):
        system = "You are a business analyst. Summarize the following data concisely in the user's language."
        return self.analyze(system, text, **kwargs)


class LocalModelProvider(AIProviderBase):
    """Local model provider - uses rule-based analysis when no LLM is available."""
    
    def chat(self, messages, **kwargs):
        user_msg = messages[-1]['content'] if messages else ''
        content = self._rule_based_response(user_msg, messages)
        return {
            'success': True,
            'content': content,
            'tokens': {'input': 0, 'output': 0},
            'response_time_ms': 10,
            'model': 'local-rule-based',
        }
    
    def analyze(self, system_prompt, user_prompt, **kwargs):
        return self._rule_based_response(user_prompt, [{'role': 'user', 'content': user_prompt}])
    
    def summarize(self, text, **kwargs):
        return self._rule_based_response(f"Summarize: {text}", [{'role': 'user', 'content': text}])
    
    def _rule_based_response(self, query, messages):
        q = query.lower()
        if any(w in q for w in ['stock', 'zaxira', 'запас', 'inventory']):
            return "Based on inventory data analysis, I recommend checking low-stock products in the Inventory module."
        if any(w in q for w in ['sale', 'sotuv', 'продаж', 'revenue']):
            return "Sales analysis is available in the Reports module. Please check the Sales Summary report for detailed metrics."
        if any(w in q for w in ['customer', 'mijoz', 'клиент']):
            return "Customer analytics are available in the CRM module. Check Customer 360 view for comprehensive customer data."
        if any(w in q for w in ['profit', 'foyda', 'прибыль', 'margin']):
            return "Financial analytics including profit margins are in the Finance module. Check the Finance Summary report."
        return "I can help analyze your business data. Please ask about sales, inventory, customers, finance, or other business areas. For detailed AI analysis, configure an AI provider in Settings."


class AIGateway:
    """Central AI gateway - manages providers, context, rate limiting, budget tracking."""
    
    _rate_lock = threading.Lock()
    _rate_counters = defaultdict(list)
    _budget_cache = {}
    _budget_cache_time = {}
    _context_cache = {}
    _context_cache_time = {}

    RATE_LIMIT_PER_MINUTE = 30
    BUDGET_CHECK_INTERVAL = 300
    CONTEXT_CACHE_TTL = 300

    def __init__(self):
        self._providers = {}
        self._provider_classes = {
            'openai': OpenAIProvider,
            'anthropic': OpenAIProvider,
            'local': LocalModelProvider,
            'custom': OpenAIProvider,
        }

    def _check_rate_limit(self, user_id):
        now = time.time()
        with self._rate_lock:
            key = str(user_id)
            timestamps = self._rate_counters[key]
            self._rate_counters[key] = [t for t in timestamps if now - t < 60]
            if len(self._rate_counters[key]) >= self.RATE_LIMIT_PER_MINUTE:
                return False
            self._rate_counters[key].append(now)
            return True

    def _check_budget(self, company):
        from .models import AIProviderConfig, AIUsageLog
        now = timezone.now()
        cache_key = str(company.pk)
        cached_time = self._budget_cache_time.get(cache_key, 0)
        if time.time() - cached_time < self.BUDGET_CHECK_INTERVAL and cache_key in self._budget_cache:
            return self._budget_cache[cache_key]

        config = AIProviderConfig.objects.filter(company=company, is_active=True).first()
        monthly_budget = float(config.monthly_budget_usd) if config else 50.0
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        spent = float(AIUsageLog.objects.filter(
            company=company, created_at__gte=month_start
        ).aggregate(total=Sum('estimated_cost_usd'))['total'] or 0)

        remaining = monthly_budget - spent
        under_budget = remaining > 0
        self._budget_cache[cache_key] = under_budget
        self._budget_cache_time[cache_key] = time.time()
        return under_budget

    def _get_cached_context(self, company, query):
        now = time.time()
        cache_key = f"{company.pk}:{hashlib.md5(query.encode()).hexdigest()}"
        cached = self._context_cache.get(cache_key)
        cached_time = self._context_cache_time.get(cache_key, 0)
        if cached and now - cached_time < self.CONTEXT_CACHE_TTL:
            return cached
        return None

    def _set_cached_context(self, company, query, context):
        cache_key = f"{company.pk}:{hashlib.md5(query.encode()).hexdigest()}"
        self._context_cache[cache_key] = context
        self._context_cache_time[cache_key] = time.time()

    def get_provider(self, company):
        """Get the active AI provider for a company."""
        from .models import AIProviderConfig
        
        config = AIProviderConfig.objects.filter(company=company, is_active=True).first()
        if not config:
            config = AIProviderConfig.objects.filter(is_active=True).first()
        
        if not config:
            return LocalModelProvider(None)
        
        cache_key = str(config.pk)
        if cache_key in self._providers:
            return self._providers[cache_key]
        
        provider_class = self._provider_classes.get(config.provider, LocalModelProvider)
        provider = provider_class(config)
        self._providers[cache_key] = provider
        return provider
    
    def chat(self, company, user, messages, feature='chat', context_module='', **kwargs):
        """Send a chat request through the gateway with rate limiting and budget checks."""
        if not self._check_rate_limit(user.pk):
            return {
                'success': False, 'error': 'Rate limit exceeded. Please wait a moment.',
                'content': 'You have reached the maximum number of AI requests per minute. Please wait a moment before trying again.',
                'tokens': {'input': 0, 'output': 0}, 'response_time_ms': 0,
            }

        if not self._check_budget(company):
            return {
                'success': False, 'error': 'Monthly AI budget exceeded.',
                'content': 'Your monthly AI usage budget has been reached. Please contact your administrator to increase the budget.',
                'tokens': {'input': 0, 'output': 0}, 'response_time_ms': 0,
            }

        provider = self.get_provider(company)
        
        start = time.time()
        result = provider.chat(messages, **kwargs)
        elapsed_ms = int((time.time() - start) * 1000)
        
        self._log_usage(company, user, feature, provider, result, elapsed_ms)
        self._budget_cache_time.pop(str(company.pk), None)
        
        return result
    
    def analyze(self, company, user, system_prompt, user_prompt, feature='analysis', **kwargs):
        """Analyze data using AI with rate limiting and budget checks."""
        if not self._check_rate_limit(user.pk):
            return 'Rate limit exceeded. Please wait a moment.'
        if not self._check_budget(company):
            return 'Monthly AI budget exceeded.'

        provider = self.get_provider(company)
        
        start = time.time()
        content = provider.analyze(system_prompt, user_prompt, **kwargs)
        elapsed_ms = int((time.time() - start) * 1000)
        
        result = {'success': bool(content), 'content': content, 'tokens': {'input': 0, 'output': 0}}
        self._log_usage(company, user, feature, provider, result, elapsed_ms)
        self._budget_cache_time.pop(str(company.pk), None)
        
        return content
    
    def generate_insight(self, company, user, insight_type, title, description, evidence=None, recommendations=None, **kwargs):
        """Generate and store an AI insight."""
        from .models import AIInsight
        
        insight = AIInsight.objects.create(
            company=company,
            insight_type=insight_type,
            title=title,
            description=description,
            evidence=evidence or {},
            recommendations=recommendations or [],
            confidence=kwargs.get('confidence', 0.0),
            related_module=kwargs.get('related_module', ''),
            related_object_type=kwargs.get('related_object_type', ''),
            related_object_id=kwargs.get('related_object_id', ''),
            data_period_start=kwargs.get('period_start'),
            data_period_end=kwargs.get('period_end'),
            priority=kwargs.get('priority', 'medium'),
        )
        return insight
    
    def _log_usage(self, company, user, feature, provider, result, elapsed_ms):
        """Log AI usage for cost tracking."""
        from .models import AIUsageLog
        
        tokens = result.get('tokens', {})
        config = getattr(provider, 'config', None)
        
        cost = Decimal('0.00')
        if config and tokens:
            input_tokens = tokens.get('input', 0)
            output_tokens = tokens.get('output', 0)
            if 'gpt-4' in (config.model_name or ''):
                cost = Decimal(str(input_tokens * 0.00003 + output_tokens * 0.00006))
            elif 'gpt-3.5' in (config.model_name or ''):
                cost = Decimal(str(input_tokens * 0.0000015 + output_tokens * 0.000002))
            else:
                cost = Decimal(str((input_tokens + output_tokens) * 0.000001))
        
        AIUsageLog.objects.create(
            company=company,
            user=user,
            feature=feature,
            provider=config.provider if config else 'local',
            model=config.model_name if config else 'local',
            tokens_input=tokens.get('input', 0),
            tokens_output=tokens.get('output', 0),
            estimated_cost_usd=cost,
            response_time_ms=elapsed_ms,
            success=result.get('success', False),
            error_message=result.get('error', ''),
        )


# Singleton
gateway = AIGateway()
