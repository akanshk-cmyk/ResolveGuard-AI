"""Explicit paid, synthetic private-framing smoke test against the local app."""
import json
from pathlib import Path
from uuid import uuid4

import httpx


def main():
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=20) as client:
        health=client.get('/api/health')
        health.raise_for_status()
        assert health.json()['reply_mode']=='public_private'
        response=client.post('/api/session',json={'profile':'bow-customer-one'})
        response.raise_for_status()
        response=client.get('/api/transactions',params={'bank_id':'BOW'})
        response.raise_for_status()
        transaction=response.json()['items'][0]['transaction_id']
        response=client.post('/api/chat',json={'message':'Show this transaction',
            'bank_id':'BOW','transaction_ids':[transaction],'request_key':'private-live-'+uuid4().hex})
        response.raise_for_status()
        body=response.json()
        generation=body.get('generation',{})
        result={'reply_mode':health.json()['reply_mode'],'response_state':body.get('response_state'),
                'generation':{k:generation.get(k) for k in ('outcome','data_scope','failure_code',
                    'error_type','generation_latency_ms','requested_model','returned_model',
                    'input_tokens','output_tokens')},
                'account_facts_sent_to_provider':False,
                'note':'Provider prompt uses numbered placeholders; actual account facts are inserted locally.'}
        path=Path('artifacts/public_generation/private_live_smoke.json')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
        return 0 if generation.get('outcome')=='APPROVED' else 1


if __name__=='__main__':raise SystemExit(main())
