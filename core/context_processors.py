import re
import json

from django.urls import reverse, NoReverseMatch

from .translations import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, LANGUAGE_NAMES, LANGUAGE_LABELS, TRANSLATIONS

# Keys actually consumed by client-side JS (window.t() in base/auth templates).
JS_TRANSLATION_KEYS = ('pw_weak', 'pw_fair', 'pw_strong', 'welcome_next', 'welcome_start', 'required_field_msg', 'weak_password', 'medium_password', 'strong_password')

# =========================================================================
# Sidebar active-state resolution.
#
# Exactly ONE canonical nav key is resolved per request from the resolved
# route identity (namespace + url_name). Templates compare a single
# `nav_active` value, so multiple sidebar items can never be highlighted
# simultaneously. Resolution is purely route-based and therefore fully
# language-independent.
#
# Order of resolution:
#   1. EXACT_NAV_ROUTES  – (namespace, url_name) -> nav key
#   2. NAV_FAMILY_RULES  – ordered (namespace, name-regex) -> nav key,
#                          used for detail/create/edit/delete variants
#   3. NAV_NS_FALLBACKS  – unmatched pages inside an app resolve to that
#                          app's canonical landing item
#   4. ''                – nothing highlighted
# =========================================================================

EXACT_NAV_ROUTES = {
    # Dashboard / POS
    ('', 'dashboard'): 'dashboard',
    ('pos', 'pos_dashboard'): 'pos',
    ('pos', 'workspace'): '',
    # Products / Scanner
    ('', 'product_list'): 'products',
    ('scanner', 'scanner_view'): 'scanner',
    # Inventory (core namespace)
    ('', 'inventory_overview'): 'inv_overview',
    ('', 'inventory_table'): 'inv_table',
    ('', 'low_stock_list'): 'low_stock',
    ('', 'out_of_stock_list'): 'out_stock',
    ('', 'movement_history'): 'movements',
    ('', 'transaction_list'): 'stock_io',
    ('', 'adjustment_list'): 'adjustments',
    ('', 'count_list'): 'counts',
    # Purchases
    ('purchases', 'purchase_dashboard'): 'purch_dashboard',
    ('purchases', 'purchase_list'): 'purchases',
    ('purchases', 'supplier_list'): 'suppliers',
    # Sales
    ('sales', 'sale_dashboard'): 'sale_dashboard',
    ('sales', 'sale_list'): 'sales',
    ('sales', 'customer_list'): 'customers',
    # Orders
    ('orders', 'order_dashboard'): 'order_dashboard',
    ('orders', 'order_list'): 'orders',
    # Tasks
    ('spiskalar', 'workspace'): 'task_workspace',
    ('spiskalar', 'dashboard'): 'task_dashboard',
    ('spiskalar', 'task_list'): 'tasks',
    # Contacts section
    ('crm', 'crm_dashboard'): 'crm',
    ('crm', 'customer_crm_list'): 'crm_customers',
    ('crm', 'segment_list'): 'crm_segments',
    ('crm', 'tag_list'): 'crm_tags',
    ('crm', 'rfm_analyze'): 'crm_rfm',
    ('contacts', 'contact_list'): 'contacts',
    ('warehouses', 'warehouse_list'): 'warehouses_nav',
    # Pricing
    ('pricing', 'pricing_dashboard'): 'pricing_engine',
    ('pricing', 'price_list_list'): 'price_lists',
    ('pricing', 'promotion_list'): 'promotions',
    ('pricing', 'coupon_list'): 'coupons',
    ('pricing', 'pricing_simulator'): 'pricing_simulator',
    # WMS (warehouses namespace)
    ('warehouses', 'wms_dashboard'): 'wms',
    ('warehouses', 'receiving_list'): 'wms_receiving',
    ('warehouses', 'putaway_list'): 'putaway',
    ('warehouses', 'picking_list'): 'picking',
    ('warehouses', 'packing_list'): 'packing',
    ('warehouses', 'shipment_list'): 'wms_shipments',
    ('warehouses', 'transfer_list'): 'transfers',
    ('warehouses', 'task_list'): 'wms_tasks',
    ('warehouses', 'batch_list'): 'batches',
    # Logistics
    ('logistics', 'logistics_dashboard'): 'log_dashboard',
    ('logistics', 'shipment_list'): 'log_shipments',
    ('logistics', 'delivery_list'): 'deliveries',
    ('logistics', 'dispatch_board'): 'dispatch',
    ('logistics', 'route_list'): 'routes_log',
    ('logistics', 'driver_list'): 'drivers',
    ('logistics', 'driver_mobile'): 'driver_mobile',
    ('logistics', 'vehicle_list'): 'vehicles',
    ('logistics', 'tracking_list'): 'tracking',
    ('logistics', 'cost_list'): 'costs',
    ('logistics', 'logistics_reports'): 'log_reports',
    # Finance
    ('finance', 'financial_dashboard'): 'fin_dash',
    ('finance', 'account_list'): 'fin_accounts',
    ('finance', 'transaction_list'): 'fin_transactions',
    ('finance', 'expense_list'): 'fin_expenses',
    ('finance', 'income_list'): 'fin_income',
    ('finance', 'budget_list'): 'fin_budgets',
    ('finance', 'reports_hub'): 'fin_reports',
    ('finance', 'customer_debt_list'): 'cust_debts',
    ('finance', 'supplier_debt_list'): 'supp_debts',
    # Reports
    ('reports', 'reports_index'): 'reports_index',
    ('reports', 'report_kpi'): 'report_kpi',
    ('reports', 'saved_report_list'): 'saved_reports',
    # Markings
    ('markings', 'marking_dashboard'): 'marking_dash',
    ('markings', 'gtin_list'): 'gtin',
    ('markings', 'marking_list'): 'marking_codes',
    ('markings', 'code_validate'): 'validate_code',
    ('markings', 'trace_product'): 'trace',
    # Documents
    ('documents', 'documents_dashboard'): 'documents_dash',
    ('documents', 'document_list'): 'document_list_nav',
    ('documents', 'document_template_list'): 'doc_templates',
    ('documents', 'edo_dashboard'): 'edo',
    # E-commerce
    ('ecommerce', 'dashboard'): 'ecom_dash',
    ('ecommerce', 'channel_list'): 'channels',
    ('ecommerce', 'integration_list'): 'ecom_integrations',
    ('ecommerce', 'payment_providers'): 'payments',
    ('ecommerce', 'shipping_methods'): 'shipping_methods',
    ('ecommerce', 'sync_jobs'): 'sync_jobs',
    ('ecommerce', 'integration_logs'): 'integration_logs',
    # AI
    ('sklat_ai', 'dashboard'): 'ai_dash',
    ('sklat_ai', 'chat'): 'ai_chat',
    ('sklat_ai', 'insights'): 'ai_insights',
    ('sklat_ai', 'forecasts'): 'ai_forecasts',
    ('sklat_ai', 'recommendations'): 'ai_recommendations',
    ('sklat_ai', 'action_center'): 'ai_action_center',
    ('sklat_ai', 'anomalies'): 'ai_anomalies',
    ('sklat_ai', 'analytics'): 'ai_analytics',
    ('sklat_ai', 'config'): 'ai_config',
    # Automation
    ('automation', 'dashboard'): 'auto_dash',
    ('automation', 'rule_list'): 'rules',
    ('automation', 'execution_list'): 'executions',
    ('automation', 'logs'): 'auto_logs',
    ('automation', 'templates'): 'templates_auto',
    ('automation', 'analytics'): 'auto_analytics',
    # Integrations hub
    ('integrations', 'dashboard'): 'intg_dash',
    ('integrations', 'integration_list'): 'all_integrations',
    ('integrations', 'provider_list'): 'providers',
    ('integrations', 'webhook_list'): 'webhooks',
    ('integrations', 'api_key_list'): 'api_keys',
    ('integrations', 'logs'): 'intg_logs',
    ('integrations', 'errors'): 'error_center',
    ('integrations', 'sync_jobs'): 'sync_center',
    # System
    ('notifications', 'notification_list'): 'notifications',
    ('activity', 'activity_timeline'): 'activity',
    ('users', 'employee_list'): 'users_nav',
    # Platform (super admin)
    ('saas_platform', 'dashboard'): 'platform_dash',
    ('saas_platform', 'company_list'): 'companies',
    ('saas_platform', 'subscription_plans'): 'plans',
    ('saas_platform', 'user_list'): 'platform_users',
    ('saas_platform', 'role_list'): 'roles',
    ('saas_platform', 'audit_log'): 'audit_platform',
    ('saas_platform', 'feature_flags'): 'flags',
    ('saas_platform', 'health_check'): 'health',
}

# Ordered family rules: (namespace, url_name regex) -> nav key.
# Scoped by namespace so identical substrings in different apps can never
# cross-activate each other (e.g. inventory vs finance transaction lists).
NAV_FAMILY_RULES = [
    # Products & scanner (core)
    ('', r'^product_', 'products'),
    ('', r'^scanner_', 'scanner'),
    # Inventory detail/create/edit routes
    ('', r'^low_stock_', 'low_stock'),
    ('', r'^out_of_stock_', 'out_stock'),
    ('', r'^(movement|movement_)', 'movements'),
    ('', r'^transaction_', 'stock_io'),
    ('', r'^adjustment_', 'adjustments'),
    ('', r'^count(_item)?_', 'counts'),
    # Purchases
    ('purchases', r'^purchase_return_', 'purchases'),
    ('purchases', r'^purchase_', 'purchases'),
    ('purchases', r'^supplier_', 'suppliers'),
    # Sales (returns fold into sales; no dedicated sidebar item exists)
    ('sales', r'^sale_return_', 'sales'),
    ('sales', r'^sale_', 'sales'),
    ('sales', r'^customer_', 'customers'),
    # Orders
    ('orders', r'^order_', 'orders'),
    # Tasks
    ('spiskalar', r'^task_|^list_|^board_', 'tasks'),
    # Contacts section
    ('crm', r'^customer_crm_', 'crm_customers'),
    ('crm', r'^segment_', 'crm_segments'),
    ('crm', r'^tag_', 'crm_tags'),
    ('crm', r'^rfm_', 'crm_rfm'),
    ('contacts', r'^contact_', 'contacts'),
    ('warehouses', r'^warehouse_', 'warehouses_nav'),
    # Pricing
    ('pricing', r'^price_list_', 'price_lists'),
    ('pricing', r'^promotion_', 'promotions'),
    ('pricing', r'^coupon_', 'coupons'),
    # WMS structure pages belong to the Warehouses nav item
    ('warehouses', r'^(zone|location|stock_location)_', 'warehouses_nav'),
    ('warehouses', r'^receiving_', 'wms_receiving'),
    ('warehouses', r'^putaway_', 'putaway'),
    ('warehouses', r'^picking_', 'picking'),
    ('warehouses', r'^packing_', 'packing'),
    ('warehouses', r'^shipment_', 'wms_shipments'),
    ('warehouses', r'^transfer_', 'transfers'),
    ('warehouses', r'^task_', 'wms_tasks'),
    ('warehouses', r'^batch_', 'batches'),
    ('warehouses', r'^dispatch_', 'dispatch'),
    # Logistics
    ('logistics', r'^shipment_', 'log_shipments'),
    ('logistics', r'^delivery_', 'deliveries'),
    ('logistics', r'^route_', 'routes_log'),
    ('logistics', r'^driver_(?!mobile)', 'drivers'),
    ('logistics', r'^vehicle_', 'vehicles'),
    ('logistics', r'^tracking_', 'tracking'),
    ('logistics', r'^cost_', 'costs'),
    ('logistics', r'^location_update$', 'tracking'),
    # Finance — scoped so foreign substrings cannot activate these
    ('finance', r'^account_', 'fin_accounts'),
    ('finance', r'^transaction_', 'fin_transactions'),
    ('finance', r'^expense_category_', 'fin_expenses'),
    ('finance', r'^expense_', 'fin_expenses'),
    ('finance', r'^income_category_', 'fin_income'),
    ('finance', r'^income_', 'fin_income'),
    ('finance', r'^budget_', 'fin_budgets'),
    ('finance', r'^(report_|cash_flow|profit_loss|payables_aging|receivables_aging)', 'fin_reports'),
    ('finance', r'^customer_statement|^customer_debt_', 'cust_debts'),
    ('finance', r'^supplier_statement|^supplier_debt_', 'supp_debts'),
    # Reports module: every report_* detail page falls back to the index item
    ('reports', r'^saved_report_', 'saved_reports'),
    ('reports', r'^report_kpi', 'report_kpi'),
    ('reports', r'^report_|^export_', 'reports_index'),
    # Markings
    ('markings', r'^gtin_', 'gtin'),
    ('markings', r'^marking_(?!dashboard)', 'marking_codes'),
    ('markings', r'^code_validate', 'validate_code'),
    ('markings', r'^trace_|^traceability_', 'trace'),
    ('markings', r'^aggregation_', 'marking_codes'),
    # Documents
    ('documents', r'^document_template_', 'doc_templates'),
    ('documents', r'^edo_', 'edo'),
    ('documents', r'^document_', 'document_list_nav'),
    # E-commerce
    ('ecommerce', r'^channel_', 'channels'),
    ('ecommerce', r'^(channel_product|channel_stock)', 'channels'),
    ('ecommerce', r'^integration_(?!logs)', 'ecom_integrations'),
    ('ecommerce', r'^payment_', 'payments'),
    ('ecommerce', r'^shipping_method_', 'shipping_methods'),
    ('ecommerce', r'^sync_job', 'sync_jobs'),
    # AI (POST-only helper endpoints mapped for redirect consistency)
    ('sklat_ai', r'^generate_insight|^insight_', 'ai_insights'),
    ('sklat_ai', r'^execute_action|^action_', 'ai_action_center'),
    ('sklat_ai', r'^dismiss_recommendation|^recommendation_', 'ai_recommendations'),
    ('sklat_ai', r'^(chat|feedback|create_draft|validate_response|session)', 'ai_chat'),
    ('sklat_ai', r'^forecast_', 'ai_forecasts'),
    ('sklat_ai', r'^anomal', 'ai_anomalies'),
    ('sklat_ai', r'^config', 'ai_config'),
    # Automation
    ('automation', r'^rule_', 'rules'),
    ('automation', r'^execution_', 'executions'),
    ('automation', r'^template_', 'templates_auto'),
    # Integrations hub
    ('integrations', r'^provider_', 'providers'),
    ('integrations', r'^webhook', 'webhooks'),
    ('integrations', r'^api_key', 'api_keys'),
    ('integrations', r'^connection_', 'all_integrations'),
    ('integrations', r'^error_', 'error_center'),
    ('integrations', r'^(sync_job|object_mapping|circuit_breaker|event)', 'sync_center'),
    # System
    ('notifications', r'.*', 'notifications'),
    ('activity', r'.*', 'activity'),
    ('users', r'^(employee|user)_', 'users_nav'),
    # Platform
    ('saas_platform', r'^company_|^invite_', 'companies'),
    ('saas_platform', r'^(plan|subscription_)', 'plans'),
    ('saas_platform', r'^role_', 'roles'),
    ('saas_platform', r'^flag_|^feature_flag', 'flags'),
    ('saas_platform', r'^user_', 'platform_users'),
]

# Unmatched pages inside an app resolve to that app's canonical item.
NAV_NS_FALLBACKS = {
    'pos': 'pos',
    'scanner': 'scanner',
    'purchases': 'purch_dashboard',
    'sales': 'sale_dashboard',
    'orders': 'order_dashboard',
    'spiskalar': 'task_workspace',
    'crm': 'crm',
    'contacts': 'contacts',
    'pricing': 'pricing_engine',
    'warehouses': 'wms',
    'logistics': 'log_dashboard',
    'finance': 'fin_dash',
    'reports': 'reports_index',
    'markings': 'marking_dash',
    'documents': 'documents_dash',
    'ecommerce': 'ecom_dash',
    'sklat_ai': 'ai_dash',
    'automation': 'auto_dash',
    'integrations': 'intg_dash',
    'notifications': 'notifications',
    'activity': 'activity',
    'storefront': '',
}

_compiled_family_rules = [
    (ns, re.compile(pat), key) for ns, pat, key in NAV_FAMILY_RULES
]

# nav key -> (namespace, url_name) of the section's own landing page.
# Derived by inverting EXACT_NAV_ROUTES, which holds exactly one route per
# nav key, so a key's landing route is whatever route maps to it directly.
NAV_SECTION_ROOTS = {}
for (_ns, _name), _key in EXACT_NAV_ROUTES.items():
    if _key:
        NAV_SECTION_ROOTS[_key] = (_ns, _name)


def resolve_nav_key(namespace, url_name):
    """Deterministically resolve exactly ONE sidebar nav key for a route."""
    if not url_name:
        return ''
    exact_key = EXACT_NAV_ROUTES.get((namespace or '', url_name))
    if exact_key is not None:
        return exact_key
    ns = namespace or ''
    for rule_ns, pattern, key in _compiled_family_rules:
        if rule_ns == ns and pattern.search(url_name):
            return key
    return NAV_NS_FALLBACKS.get(ns, '')


def resolve_section_root(nav_key):
    """Return the ('ns:name') URL name of a section's own landing page."""
    route = NAV_SECTION_ROOTS.get(nav_key or '')
    if not route:
        return ''
    ns, name = route
    return '%s:%s' % (ns, name) if ns else name


def language_context_processor(request):
    """Add language context to all templates."""
    lang = getattr(request, 'LANGUAGE_CODE', DEFAULT_LANGUAGE)
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    # Small translation dict for client-side JS access.
    # Full translations are rendered server-side via the {% t %} tag;
    # shipping all keys as JSON on every page would bloat every response.
    translated = {}
    for key in JS_TRANSLATION_KEYS:
        langs = TRANSLATIONS.get(key)
        if langs:
            translated[key] = langs.get(lang, langs.get(DEFAULT_LANGUAGE, key))

    resolver_match = getattr(request, 'resolver_match', None)
    nav_active = ''
    namespace = url_name = ''
    if resolver_match is not None:
        namespace = getattr(resolver_match, 'namespace', '') or ''
        url_name = getattr(resolver_match, 'url_name', None)
        nav_active = resolve_nav_key(namespace, url_name)

    # Is this the section's own landing page (reached straight from the
    # sidebar) or a nested view inside it? Only nested views get a back arrow.
    is_section_root = bool(nav_active) and (namespace, url_name) == NAV_SECTION_ROOTS.get(nav_active, (None, None))

    # Where the back arrow should send the user. Falls back to the app root
    # when the section has no resolvable landing URL (e.g. unmapped routes).
    back_url = ''
    if nav_active and not is_section_root:
        target = resolve_section_root(nav_active)
        if target:
            try:
                back_url = reverse(target)
            except NoReverseMatch:
                back_url = ''

    return {
        'current_language': lang,
        'supported_languages': [
            {'code': code, 'name': LANGUAGE_NAMES[code], 'label': LANGUAGE_LABELS[code]}
            for code in SUPPORTED_LANGUAGES
        ],
        'translations_json': json.dumps(translated, ensure_ascii=False),
        'nav_active': nav_active,
        'is_section_root': is_section_root,
        'back_url': back_url,
    }
