import os

from django.conf import settings
from django.test import SimpleTestCase


def iter_template_files():
    for root in settings.TEMPLATES[0]['DIRS']:
        for dirpath, _dirs, files in os.walk(str(root)):
            for name in sorted(files):
                if name.endswith('.html'):
                    yield os.path.join(dirpath, name)


def multi_line_comment_spans(text):
    """Return (line_number, span_length) for every {# ... #} that crosses a
    newline.

    Django compiles its tag regex as `({%.*?%}|{{.*?}}|{#.*?#})` WITHOUT
    re.DOTALL, so `{# ... #}` only ever matches inside a single line. A
    comment written across several lines is not recognised as a tag and the
    whole thing - delimiters included - is emitted into the page as visible
    text. `{% comment %} ... {% endcomment %}` is the multi-line-safe form
    because it is parsed by the block-tag parser rather than the regex.
    """
    start, end = '{#', '#}'
    found = []
    pos = 0
    while True:
        i = text.find(start, pos)
        if i == -1:
            break
        j = text.find(end, i)
        if j == -1:
            break
        body = text[i:j + 2]
        if '\n' in body:
            found.append((text.count('\n', 0, i) + 1, body.count('\n') + 1))
        pos = j + 2
    return found


class TemplateCommentHygieneTests(SimpleTestCase):
    """No template may ship a multi-line {# ... #} comment.

    Regression cover for a bug that was live on the inventory dashboard:
    a four-line `{# ... #}` block was rendered to the page as visible text,
    because Django's tag regex has no re.DOTALL and therefore does not
    recognise a comment that spans a newline.
    """

    def test_no_template_has_a_multiline_brace_comment(self):
        offenders = {}
        for path in iter_template_files():
            with open(path, encoding='utf-8') as fh:
                text = fh.read()
            hits = multi_line_comment_spans(text)
            if hits:
                rel = os.path.relpath(path, settings.BASE_DIR)
                offenders[rel] = hits
        self.assertEqual(
            offenders, {},
            'these templates use a multi-line brace comment, which Django '
            'renders as visible text; use a {% comment %} block instead: '
            f'{offenders!r}',
        )

    def test_single_line_brace_comments_still_supported(self):
        # Guard the helper itself, so the test above cannot pass vacuously.
        self.assertEqual(multi_line_comment_spans('{# ok #}'), [])
        self.assertEqual(len(multi_line_comment_spans('{# a\nb #}')), 1)

    def test_inventory_dashboard_renders_no_comment_text(self):
        from django.template import Context, Template

        path = os.path.join(
            str(settings.TEMPLATES[0]['DIRS'][0]),
            'inventory', 'inventory_overview.html',
        )
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        out = Template(src).render(Context({
            'total_products': 1, 'total_units': 2, 'total_value': 3,
        }))
        # The comment text itself must not reach the page. A bare `{#`
        # substring check is deliberately avoided: CSS id selectors such as
        # `#sk-progress-bar{...}` contain it legitimately.
        self.assertNotIn('stat card was removed', out)
        self.assertNotIn('duplicated the', out)
        self.assertNotIn('low stock products', out)
        # The block comment tags must be consumed, not echoed.
        self.assertNotIn('{% comment %}', out)
        self.assertNotIn('{% endcomment %}', out)
