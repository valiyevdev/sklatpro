import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(is_safe=True)
def tojson(value, encoder=None):
    """Serialize a value to a JSON literal for inline use in a <script> block.

    Django shipped a built-in ``tojson`` filter up to 1.8 and removed it in
    1.9 (superseded by ``json_script``). Templates in this project still use
    the old behaviour of embedding a raw JSON literal straight into
    JavaScript, so it is re-provided here.

    The payload is escaped so that it can never terminate the surrounding
    ``<script>`` element (``</script>`` -> ``<\\/script>``) and cannot
    inject markup, while still being valid JSON that ``JSON.parse``
    accepts.
    """
    dumped = json.dumps(value, ensure_ascii=False, cls=encoder)
    dumped = (
        dumped.replace("&", "\\u0026")
        .replace("<", "\\u003C")
        .replace(">", "\\u003E")
    )
    return mark_safe(dumped)
