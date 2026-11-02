"""Local synthetic emergency smoke test. No model calls or real card actions."""
import json
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    message='My debit card was stolen and someone is using it right now.'
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=15) as client:
        client.post('/api/session',json={}).raise_for_status()
        started=time.perf_counter()
        guest=client.post('/api/chat',json={'message':message,'bank_id':'BOW',
                         'request_key':'emergency-guest-'+uuid4().hex})
        guest.raise_for_status()
        guest=guest.json()
        guest_ms=round((time.perf_counter()-started)*1000,2)
        assert guest['report']['status']=='OK' and guest['auth_required'] and not guest['cards']
        assert 'generation' not in guest and guest['emergency']['card_lock']['state']!='LOCKED'
        client.post('/api/auth/demo-sign-in',json={'profile':'bow-customer-one','pending_id':guest['pending_id']}).raise_for_status()
        started=time.perf_counter()
        response=client.post('/api/auth/resume',json={'pending_id':guest['pending_id']})
        response.raise_for_status()
        result=response.json()
        verified_ms=round((time.perf_counter()-started)*1000,2)
        assert result['emergency']['card_lock']['state']=='LOCKED'
        assert result['emergency']['dispute']['status']=='OK'
        assert 'generation' not in result
        checks={'guest_report_preserved_before_auth':True,'guest_no_lock_or_private_cards':True,
                'original_request_resumed':result.get('resumed') is True,
                'authenticated_demo_lock_verified':True,'demo_fraud_ticket_saved':True,
                'model_generation_bypassed':True,'guest_latency_ms':guest_ms,'verified_latency_ms':verified_ms,
                'scope':'Synthetic BOW backend only. No real card frozen or official bank dispute filed.'}
        path=Path('artifacts/emergency_triage/live_local_smoke.json')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(checks,indent=2))


if __name__=='__main__':main()
