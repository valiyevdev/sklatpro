from django import template
from django.utils.safestring import mark_safe
from core.translations import get_translation, LANGUAGE_NAMES, LANGUAGE_LABELS, SUPPORTED_LANGUAGES

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, key):
    """Translate a key using the current language from context."""
    lang = context.get('current_language', 'uz')
    return get_translation(key, lang)


@register.simple_tag(takes_context=True)
def lang_code(context):
    """Return current language code."""
    return context.get('current_language', 'uz')


@register.simple_tag(takes_context=True)
def lang_name(context):
    """Return current language display name."""
    lang = context.get('current_language', 'uz')
    return LANGUAGE_NAMES.get(lang, "O'zbekcha")


@register.simple_tag(takes_context=True)
def lang_label(context):
    """Return current language short label."""
    lang = context.get('current_language', 'uz')
    return LANGUAGE_LABELS.get(lang, 'UZ')


@register.simple_tag(takes_context=True)
def get_languages(context):
    """Return list of all supported languages with labels."""
    return [
        {'code': code, 'name': LANGUAGE_NAMES[code], 'label': LANGUAGE_LABELS[code]}
        for code in SUPPORTED_LANGUAGES
    ]


@register.simple_tag(takes_context=True)
def current_lang(context):
    """Return current language code."""
    return context.get('current_language', 'uz')


@register.simple_tag(takes_context=True)
def is_current_lang(context, lang_code):
    """Check if the given language code is the current language."""
    return context.get('current_language', 'uz') == lang_code


@register.simple_tag(takes_context=True)
def lang_attrs(context):
    """Return HTML lang attribute for the current language."""
    lang = context.get('current_language', 'uz')
    attr_map = {
        'uz': 'uz',
        'uz_cyr': 'uz',
        'ru': 'ru',
        'en': 'en',
    }
    return attr_map.get(lang, 'uz')


def _group_number(value):
    """Return (is_numeric, space-grouped string) for a numeric value.

    Shared by `num` and `uzs` so the two filters can never drift apart.
    Non-numeric input is passed straight through, which keeps every caller
    safe on None/''/already-formatted strings.
    """
    if value is None or value == '':
        return True, ''
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False, value
    if number == int(number):
        return True, '{:,.0f}'.format(int(number)).replace(',', ' ')
    return True, '{:,.2f}'.format(number).replace(',', ' ')


@register.filter
def num(value):
    """Format a number with space thousands separators and NO currency
    suffix, e.g. 10000 -> '10 000', 1200 -> '1 200'. Use `uzs` for money.
    Stock counts are plain integers, so a currency suffix would be wrong."""
    _is_numeric, text = _group_number(value)
    return text


@register.filter
def uzs(value):
    """Format a numeric value as Uzbekistan som with space thousands
    separator, e.g. 10000 -> "10 000 so'm". Decimals only when required.

    The generated value is composed from digits, spaces and a constant
    suffix, so it is marked safe to keep the apostrophe readable in HTML.
    """
    is_numeric, text = _group_number(value)
    if not is_numeric or text == '':
        return text
    return mark_safe("{} so'm".format(text))
