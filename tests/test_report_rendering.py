"""Characterise the existing exporter contracts before sharing their renderer."""
import copy
import subprocess
import sys
import unittest
from pathlib import Path

from tools.build_bow_review import table as bow_table
from tools.build_review_pack import table as original_table


class ReportRenderingTests(unittest.TestCase):
    renderers = (original_table, bow_table)

    def test_exporters_keep_their_distinct_empty_results(self):
        self.assertEqual(original_table([]), '<p>No records.</p>')
        self.assertEqual(
            bow_table([]),
            '<div class="scroll"><table><thead><tr></tr></thead>'
            '<tbody></tbody></table></div>',
        )

    def test_headers_and_values_escape_html_without_changing_unicode(self):
        rows = [{'customer_name': 'Caf\u00e9 <script> & "quoted" \'name\''}]
        expected = (
            '<div class="scroll"><table><thead><tr><th>customer name</th></tr>'
            '</thead><tbody><tr><td>Caf\u00e9 &lt;script&gt; &amp; &quot;quoted&quot; '
            '&#x27;name&#x27;</td></tr></tbody></table></div>'
        )
        for render in self.renderers:
            with self.subTest(renderer=render.__module__):
                self.assertEqual(render(rows), expected)

    def test_heterogeneous_rows_keep_column_order_and_distinct_false_zero_null(self):
        rows = [{'second': False, 'first': 0}, {'third': None, 'first': -425}]
        expected = (
            '<div class="scroll"><table><thead><tr><th>second</th><th>first</th>'
            '<th>third</th></tr></thead><tbody><tr><td>False</td><td>0</td><td></td>'
            '</tr><tr><td></td><td>-425</td><td></td></tr></tbody></table></div>'
        )
        for render in self.renderers:
            with self.subTest(renderer=render.__module__):
                self.assertEqual(render(rows), expected)

    def test_nested_values_keep_json_format_and_do_not_mutate_records(self):
        rows = [{'details': {'label': 'Caf\u00e9', 'items': ['<b>', None, True]}}]
        before = copy.deepcopy(rows)
        expected = (
            '<div class="scroll"><table><thead><tr><th>details</th></tr></thead>'
            '<tbody><tr><td>{&quot;label&quot;: &quot;Caf\u00e9&quot;, &quot;items&quot;: '
            '[&quot;&lt;b&gt;&quot;, null, true]}</td></tr></tbody></table></div>'
        )
        for render in self.renderers:
            with self.subTest(renderer=render.__module__):
                self.assertEqual(render(rows), expected)
                self.assertEqual(rows, before)

    def test_exporter_imports_work_in_isolated_script_mode(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('build_review_pack.py', 'build_bow_review.py'):
            path = root / 'tools' / name
            code = (
                'import runpy, sys; '
                f'sys.path.insert(0, {str(path.parent)!r}); '
                f'runpy.run_path({str(path)!r}, run_name="__import_check__")'
            )
            with self.subTest(exporter=name):
                result = subprocess.run(
                    [sys.executable, '-I', '-B', '-c', code],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
