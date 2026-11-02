"""Export a local, readable review pack without credentials or browser bindings."""
import csv
import hashlib
import html
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'review_pack'


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def save(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def table(rows):
    if not rows:
        return '<p>No records.</p>'
    keys = list(dict.fromkeys(k for row in rows for k in row))
    def cell(value):
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        return html.escape(str(value if value is not None else ''))
    return '<div class="scroll"><table><thead><tr>' + ''.join('<th>' + cell(k.replace('_', ' ')) + '</th>' for k in keys) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell(row.get(k)) + '</td>' for k in keys) + '</tr>' for row in rows) + '</tbody></table></div>'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fixtures = {p.stem: read(p.relative_to(ROOT)) for p in (ROOT / 'resolveguard_synthetic_v04/fixtures').glob('*.json')}
    extra = read('data/supplemental_fixtures.json')
    combined = {}
    for name, rows in fixtures.items():
        if name != 'knowledge_bases':
            combined[name] = [dict(r, review_origin='Originally supplied fixture') for r in rows]
            combined[name] += [dict(r, review_origin='Added during implementation') for r in extra.get(name, [])]
    combined['assurance_events'] = [dict(r, review_origin='Added during implementation') for r in extra['assurance_events']]
    from resolveguard.presentation import GUIDANCE
    policies = [dict(doc, knowledge_base=group['name'], review_origin='Originally supplied fixture')
                for group in fixtures['knowledge_bases'] for doc in group['docs']]
    policies += [dict(doc, knowledge_base='Demo extensions', review_origin='Added during implementation') for doc in extra['policies']]
    for policy in policies:
        policy['customer_wording'] = GUIDANCE.get(policy['doc_id'], '')
        policy['review_status'] = 'Human approval not recorded; synthetic-test label is not bank policy approval'
    save('all_policies.json', policies)
    save('all_customer_and_access_data.json', combined)
    for name, rows in {**combined, 'policies': policies}.items():
        with (OUT / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as file:
            keys = list(dict.fromkeys(k for row in rows for k in row))
            writer = csv.DictWriter(file, fieldnames=keys)
            writer.writeheader()
            writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()} for row in rows)
    # Exact source copies make it possible to review wording and provenance.
    sources = []
    for folder in ('resolveguard_synthetic_v04/fixtures', 'resolveguard_demo_baseline', 'data', 'prompts'):
        sources.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and p.suffix in {'.json', '.csv', '.txt', '.md'})
    sources += [ROOT / p for p in ('README.md', 'LOCAL_DEMO.md', 'docs/AGENT_REVIEW_ADMIN_SPEC.md',
                'docs/CUSTOMER_CHAT_UI_SPEC.md', 'docs/CUSTOMER_CHAT_UI_REVIEW.md', 'docs/GUEST_FIRST_AUTH.md', 'artifacts/pydantic_contracts.json',
                'artifacts/policy_chunks.json', 'artifacts/implementation_increment_report.json',
                'artifacts/mock_iterations_final/comparison.json', 'resolveguard/presentation.py',
                'resolveguard/contracts.py', 'resolveguard/retrieval.py', 'resolveguard/workflow.py',
                'resolveguard/backend.py', 'resolveguard/conversation.py', 'resolveguard/web.py')]
    copied = []
    for source in sources:
        if source.exists():
            relative = source.relative_to(ROOT)
            destination = OUT / 'sources' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(str(relative).replace('\\', '/'))
    runtime = {}
    for name in ('web.sqlite3', 'demo.sqlite3'):
        path = ROOT / 'artifacts' / name
        if not path.exists():
            continue
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')  # A consistent read-only snapshot, including committed WAL records.
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        exported = {}
        for name_table in ('events', 'turns', 'drafts', 'conversation_threads'):
            if name_table not in tables:
                continue
            columns = [r['name'] for r in db.execute('PRAGMA table_info(' + name_table + ')') if r['name'] != 'binding']
            rows = [dict(r) for r in db.execute('SELECT ' + ','.join(columns) + ' FROM ' + name_table)]
            for row in rows:
                for key in ('payload', 'result'):
                    if row.get(key):
                        row[key] = json.loads(row[key])
            exported[name_table] = rows
        exported['browser_sessions'] = {'count': db.execute('SELECT COUNT(*) FROM web_sessions').fetchone()[0] if 'web_sessions' in tables else 0,
                                        'note': 'Cookies, token hashes and browser bindings excluded.'}
        db.close()
        runtime[name] = exported
    save('saved_demo_activity.json', runtime)
    dataset = read('data/evaluation_40.json')
    counts = {name: len(rows) for name, rows in combined.items()}
    counts['policies'] = len(policies)
    counts['evaluation_cases'] = len(dataset['cases'])
    inventory = []
    for folder in ('artifacts', 'data', 'resolveguard_demo_baseline', 'resolveguard_synthetic_v04', 'prompts'):
        for path in (ROOT / folder).rglob('*'):
            if not path.is_file() or OUT in path.parents or path.name.startswith('ResolveGuard_review_pack') or any(part.startswith('ui-browser-profile') for part in path.parts):
                continue
            if path.suffix not in {'.json', '.jsonl', '.csv', '.txt', '.md', '.sqlite3', '.checkpoints'}:
                continue
            database = path.suffix in {'.sqlite3', '.checkpoints'}
            inventory.append({'file': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
                              'sha256': None if database else hashlib.sha256(path.read_bytes()).hexdigest(),
                              'note': 'Live database: no file hash; review exported snapshot where available' if database else ''})
    # UTC is explicit so the export does not depend on the host's timezone database.
    now = datetime.now(timezone.utc).isoformat()
    save('manifest.json', {'created_at_utc': now, 'user_timezone': 'America/Los_Angeles', 'counts': counts, 'copied_source_files': copied,
         'inventory': inventory, 'exclusions': ['Actual .env files and credentials', 'Browser cookie values, token hashes and bindings',
         'Raw database/checkpoint files (selected demo tables exported as JSON instead)', 'Full historical evaluation traces and isolated run databases (listed in inventory, retained at original paths)',
         'Original PDFs and workbook (retained unchanged at workspace root)']})
    sections = ['<h1>ResolveGuard review pack</h1><p>Local snapshot: ' + html.escape(now) + '</p>',
        '<p>All seeded customer records are fictional. Saved activity includes demo messages entered during testing. '
        'A KYC VERIFIED value is a test assumption, not proof of identity. APPROVED_FOR_SYNTHETIC_TEST does not mean an approved bank policy. '
        'No human approval is implied. Credentials and browser sign-in bindings are excluded.</p>',
        '<h2>What is included</h2>' + table([{'category': k, 'records': v} for k, v in counts.items()]),
        '<p><a href="manifest.json">Full file inventory and checksums</a> | <a href="all_customer_and_access_data.json">All customer and access data</a> | '
        '<a href="saved_demo_activity.json">Saved demo activity</a> | <a href="sources/data/review_40.csv">40-case review worksheet</a></p>',
        '<h2>Policies: original text and customer wording</h2><p>Review both versions. The added $1,000 purchase limit and $3.50 ATM fee are invented demo values. The supplied $12 monthly fee is also a demo value.</p>']
    for p in policies:
        sections.append('<details open><summary>' + html.escape(p['doc_id'] + ' - ' + p['title']) + '</summary>' + table([p]) + '</details>')
    for name in ('customers', 'accounts', 'transactions', 'cases', 'sessions', 'delegations', 'employee_scopes', 'service_identities', 'assurance_events'):
        sections.append('<h2>' + html.escape(name.replace('_', ' ').title()) + '</h2><p><a href="' + name + '.csv">Open spreadsheet-friendly CSV</a></p>' + table(combined[name]))
    cases = [{'case': c['case_id'], 'question': c['inputs']['message'],
              'review': c.get('provenance', {}).get('review_status', 'See source review worksheet'),
              'expected_intent': c['expected']['primary_intent']} for c in dataset['cases']]
    sections.append('<h2>Evaluation questions</h2><p>40 draft cases: 20 happy paths, 12 edge cases, 6 anticipated failures and 2 adversarial cases. Expected answers and original prompt provenance still need review.</p>' + table(cases))
    sections.append('<h2>Other metadata and design rules</h2><p>Copied files include planning assumptions, policy chunks, Pydantic schemas, routing prompts, workflow rules and mock evaluation results. '
                    'The app currently uses a mock model; Nebius and LangSmith Cloud have not been used. Earlier design notes may describe proposed rather than implemented behavior.</p><ul>')
    sections += ['<li><a href="sources/' + html.escape(p, quote=True) + '">' + html.escape(p) + '</a></li>' for p in copied]
    sections.append('</ul><h2>Review decisions needed</h2><ul><li>Accept or change each policy and its customer wording.</li><li>Check customer/account ownership and access restrictions.</li>'
                    '<li>Confirm which identity checks the real application will use.</li><li>Review the 40 questions, expected outcomes and provenance.</li>'
                    '<li>Separate proposed assumptions from behavior demonstrated by the mock app.</li></ul>')
    document = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ResolveGuard review pack</title><style>body{font:16px system-ui;line-height:1.5;max-width:1400px;margin:32px auto;padding:0 24px;color:#243635}h1,h2{color:#12645c}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #cbd8d5;padding:10px;text-align:left;vertical-align:top;white-space:pre-wrap;min-width:110px}th{background:#eef5f2}.scroll{overflow:auto;margin:16px 0}details{margin:20px 0}summary{font-weight:600;cursor:pointer}a{color:#075eaa}</style>' + ''.join(sections) + '</html>'
    (OUT / 'index.html').write_text(document, encoding='utf-8')
    archive = shutil.make_archive(str(ROOT / 'artifacts/ResolveGuard_review_pack'), 'zip', OUT)
    print(json.dumps({'review_page': str(OUT / 'index.html'), 'zip': archive, 'counts': counts, 'source_files': len(copied),
                      'runtime_tables': {k: {t: len(v) for t, v in data.items() if isinstance(v, list)} for k, data in runtime.items()}}, indent=2))


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    main()
