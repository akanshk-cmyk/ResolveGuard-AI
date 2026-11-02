"""HTML table rendering shared by review exporters."""
from collections.abc import Mapping, Sequence
import html
import json


def _cell_text(value: object) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return html.escape('' if value is None else str(value))


def render_table(
    rows: Sequence[Mapping[str, object]],
    *,
    empty_html: str | None = None,
) -> str:
    """Preserve source column order, value formatting and exporter empty states."""
    if empty_html is not None and not rows:
        return empty_html

    columns = list(dict.fromkeys(key for row in rows for key in row))
    header = ''.join(
        '<th>' + _cell_text(key.replace('_', ' ')) + '</th>'
        for key in columns
    )
    body = ''.join(
        '<tr>'
        + ''.join('<td>' + _cell_text(row.get(key)) + '</td>' for key in columns)
        + '</tr>'
        for row in rows
    )
    return (
        '<div class="scroll"><table><thead><tr>'
        + header
        + '</tr></thead><tbody>'
        + body
        + '</tbody></table></div>'
    )
