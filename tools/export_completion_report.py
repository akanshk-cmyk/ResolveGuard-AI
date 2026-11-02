"""Render the local completion record without serving the project or secrets."""
import json
from pathlib import Path

from markdown_it import MarkdownIt


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    report = (root / "docs/LOCAL_COMPLETION_REPORT.md").read_text(encoding="utf-8")
    destination = root / "artifacts/alignment_review_20261031"
    destination.mkdir(parents=True, exist_ok=True)
    body = MarkdownIt("commonmark", {"html": False}).enable("table").render(report)
    body = body.replace('href="IMPLEMENTATION_ALIGNMENT_REVIEW.md"', 'href="review.html"')
    html = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>ResolveGuard local completion report</title><style>
body{font:16px/1.65 system-ui,sans-serif;color:#173b40;background:#f5f7f5;margin:0}
main{max-width:1100px;margin:auto;padding:28px}h1,h2{line-height:1.25}
table{display:block;overflow:auto;border-collapse:collapse;background:white}
th,td{padding:12px;border:1px solid #d3dfdc;min-width:150px;text-align:left;vertical-align:top}
pre{overflow:auto;padding:16px;background:#e8efed}code{overflow-wrap:anywhere}
a{color:#09665c}li{margin-bottom:8px}</style><main>""" + body + "</main></html>"
    (destination / "completion.html").write_text(html, encoding="utf-8")
    (destination / "completion.md").write_text(report, encoding="utf-8")
    summary = {
        "scope": "local synthetic demo; not production qualification",
        "main_tests": {"run": 272, "passed": 271, "skipped": 1},
        "fixture_tests_passed": 13,
        "browser_checks_passed": {"customer": 48, "operations": 7, "reviewer": 10},
        "security_cases_passed": 8,
        "suite_reports": {
            name: json.loads((root / f"artifacts/local_completion/{name}100_release_check/summary.json").read_text(encoding="utf-8"))
            for name in ("original", "bow")
        },
        "semantic_cases_measured": 12,
        "semantic_judge_passed": 12,
        "faithfulness_flags": ["SEM-003", "SEM-011"],
        "human_reference_approval": "PENDING",
        "excluded": ["LangSmith Cloud", "Replit deployment", "real bank integrations"],
        "urls": {"customer": "http://127.0.0.1:8765", "reviewer": "http://127.0.0.1:8766/reviewer", "report": "http://127.0.0.1:8769/completion.html"},
    }
    (root / "artifacts/local_completion/completion_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print("Saved completion.html, completion.md and completion_summary.json")


if __name__ == "__main__":
    main()
