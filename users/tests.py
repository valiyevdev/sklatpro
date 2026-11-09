import json
import re
import shutil
import subprocess
import tempfile

from unittest import skipUnless

from django.template.loader import render_to_string
from django.test import SimpleTestCase

HAS_NODE = shutil.which('node') is not None

# Only executable JavaScript is worth parsing; src= blocks live in a file and
# type="application/json" blocks are data, not code.
SCRIPT_RE = re.compile(r'<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>', re.S | re.I)

TEMPLATES = [
    'registration/password_reset_complete.html',
    'registration/password_reset_confirm.html',
]


def inline_scripts(html):
    """Return the body of every inline JavaScript block in the page."""
    bodies = []
    for match in SCRIPT_RE.finditer(html):
        attrs = (match.group('attrs') or '').lower()
        if 'src=' in attrs:
            continue
        if 'application/json' in attrs or 'text/template' in attrs:
            continue
        body = match.group('body')
        if body.strip():
            bodies.append(body)
    return bodies


def node_syntax_error(code):
    """Return a Node syntax error message for `code`, or None if it parses."""
    handle = tempfile.NamedTemporaryFile('w', suffix='.js',
                                         delete=False, encoding='utf-8')
    try:
        handle.write(code)
        handle.close()
        proc = subprocess.run(['node', '--check', handle.name],
                              capture_output=True, text=True)
    finally:
        import os
        os.unlink(handle.name)
    if proc.returncode == 0:
        return None
    lines = [ln.strip() for ln in proc.stderr.splitlines()
             if 'Error' in ln or ln.strip().startswith('^')]
    return ' | '.join(lines[:3])


class RegistrationTemplateScriptTests(SimpleTestCase):
    """The password-reset pages must hand the browser valid JavaScript.

    Regression cover for a real defect: the translation payload was
    injected as `window.SKLAT_T={{ translations_json|safe }};`, which puts a
    Django tag in JavaScript *code* position. VS Code (and any linter that
    parses the file before Django renders it) reported "Property assignment
    expected" / "Declaration or statement expected" there. It is also fragile
    at runtime, because raw JSON can contain a `</script>` sequence that
    terminates the block early. Wrapping it as
    `JSON.parse('{{ translations_json|escapejs }}')` keeps the tag inside a
    string literal, so it parses both before and after rendering, and
    escapejs stops the payload from breaking out of the string.
    """

    def render(self, template):
        return render_to_string(template, {
            'csrf_token': 'test-csrf-token-123',
            'current_language': 'uz',
            'translations_json': json.dumps({'replenish': "To'ldirish"}),
        })

    # ---------- the specific defect ----------

    def test_translation_payload_is_not_in_code_position(self):
        for name in TEMPLATES:
            with self.subTest(template=name):
                html = self.render(name)
                self.assertNotIn('window.SKLAT_T={{', html)
                self.assertIn('window.SKLAT_T=JSON.parse(', html)

    def test_no_unrendered_template_tags_reach_the_page(self):
        for name in TEMPLATES:
            with self.subTest(template=name):
                html = self.render(name)
                self.assertNotIn('{{', html)
                self.assertNotIn('{%', html)

    def test_translation_payload_survives_as_valid_json(self):
        for name in TEMPLATES:
            with self.subTest(template=name):
                html = self.render(name)
                match = re.search(
                    r"window\.SKLAT_T=JSON\.parse\('(?P<payload>.*?)'\)",
                    html, re.S,
                )
                self.assertIsNotNone(match, 'SKLAT_T assignment not found')
                # Undo exactly what Django's escapejs does to the payload.
                payload = (match.group('payload')
                           .replace('\\u0022', '"')
                           .replace('\\u0027', "'")
                           .replace('\\u003C', '<')
                           .replace('\\u003E', '>')
                           .replace('\\u0026', '&')
                           .replace('\\/', '/'))
                self.assertEqual(json.loads(payload), {'replenish': "To'ldirish"})

    def test_client_side_translation_helper_is_defined(self):
        # window.t() is used by the auth pages; it must survive the change.
        for name in TEMPLATES:
            with self.subTest(template=name):
                html = self.render(name)
                self.assertIn('window.t=function(key,fallback)', html)

    @skipUnless(HAS_NODE, 'node is not installed')
    def test_rendered_script_blocks_are_valid_javascript(self):
        for name in TEMPLATES:
            blocks = inline_scripts(self.render(name))
            self.assertTrue(blocks, 'no inline script found in %s' % name)
            for i, block in enumerate(blocks, 1):
                with self.subTest(template=name, block=i):
                    error = node_syntax_error(block)
                    self.assertIsNone(
                        error,
                        '%s script block %d is not valid JavaScript: %s'
                        % (name, i, error),
                    )

    @skipUnless(HAS_NODE, 'node is not installed')
    def test_source_script_blocks_parse_before_rendering(self):
        """What an editor sees.

        VS Code checks the file as written, with the Django tags still in
        place, so this is the check that maps to the "Problems" tab. It
        catches a tag landing in code position even when the rendered page
        happens to be fine.
        """
        from django.conf import settings
        import os

        for name in TEMPLATES:
            path = os.path.join(str(settings.TEMPLATES[0]['DIRS'][0]),
                                *name.split('/'))
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            blocks = inline_scripts(src)
            self.assertTrue(blocks, 'no inline script found in %s' % name)
            for i, block in enumerate(blocks, 1):
                with self.subTest(template=name, block=i):
                    error = node_syntax_error(block)
                    self.assertIsNone(
                        error,
                        '%s source script block %d does not parse: %s'
                        % (name, i, error),
                    )
