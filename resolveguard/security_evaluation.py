"""Credential-free web security journey evaluations, separate from banking labels."""
import json
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from .security_routing import assess_security, VERSION
from .web import create_app


def evaluate_security(output):
    cases = json.loads((Path(__file__).resolve().parents[1]/'data/adversarial_evaluation.json').read_text())
    rows = []
    with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp)/'security.sqlite3')) as client:
        client.post('/api/session', json={})
        for case in cases:
            assessment = assess_security(case['message'])
            response = client.post('/api/chat', json={'message': case['message'], 'request_key': case['id'], 'bank_id': 'BOW'})
            actual = response.json()
            checks = {'http_ok': response.status_code == 200,
                      'security_action': assessment.recommended_action == case['action'],
                      'security_flags': set(assessment.security_flags) == set(case['flags']),
                      'no_private_cards': not actual.get('cards')}
            if case['action'] == 'BLOCK_RESTRICTED_REQUEST':
                checks['blocked_without_auth_resume'] = actual.get('response_state') == 'SECURITY_BLOCKED' and not actual.get('auth_required') and not actual.get('pending_id')
            elif case.get('preserve_report'):
                checks['intake_preserved'] = actual.get('report', {}).get('status') == 'OK'
            elif case['id'] == 'ADV-003':
                checks['normal_sign_in'] = actual.get('auth_required') is True
            else:
                checks['public_education'] = actual.get('response_state') == 'PUBLIC_SECURITY_INFORMATION' and not actual.get('auth_required')
            rows.append({'case_id': case['id'], 'checks': checks, 'passed': all(checks.values()),
                         'response_state': actual.get('response_state')})
    report = {'version': VERSION, 'mode': 'synthetic-local-no-provider', 'total': len(rows),
              'passed': sum(row['passed'] for row in rows), 'cases': rows}
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
