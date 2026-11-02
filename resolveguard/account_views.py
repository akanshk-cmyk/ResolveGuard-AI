"""Account-list presentation services; backend authorization remains mandatory."""
from .contracts import Request
from .presentation import STATUS, format_money


def transaction_page(sid, backend, name, offset, limit, bank_id, *, access_state):
    if bank_id and bank_id!=backend.bank_id:return {'items':[],'total':0,'name':name,'offset':offset,'limit':limit,'bank_id':bank_id,'access_state':'AUTH_REQUIRED'}
    req=Request(message='List authorized synthetic transactions',request_key='list',session_id=sid,bank_id=backend.bank_id)
    items=[]
    for tx in backend.bank.transactions:
        result=backend.transaction(req,tx['transaction_id'])
        if result['status']=='OK':
            data=result['data']
            items.append({**data,'display_amount':format_money(data['amount_cents'],data['currency']),
                          'display_status':STATUS[data['status']].capitalize()})
    return {'items':items[offset:offset+limit],'name':name,'total':len(items),'offset':offset,'limit':limit,
            'access_state':access_state(sid,backend),'bank_id':backend.bank_id}


def case_page(sid, backend, name, offset, limit, bank_id, *, access_state, store):
    if bank_id and bank_id!=backend.bank_id:return {'items':[],'total':0,'offset':offset,'limit':limit,'bank_id':bank_id,'access_state':'AUTH_REQUIRED'}
    ids=[r['case_id'] for r in backend.bank.cases]
    with store.connect() as db:
        ids.extend(r['event_id'] for r in db.execute("SELECT event_id FROM events WHERE kind='case'"))
    items=[]
    for case_id in dict.fromkeys(ids):
        result=backend.case_status(Request(message='Check support request',request_key='case-list',session_id=sid,case_id=case_id,bank_id=backend.bank_id))
        if result['status']=='OK':items.append({**result['data'],'display_status':STATUS[result['data']['status']].capitalize()})
    return {'items':items[offset:offset+limit],'total':len(items),'offset':offset,'limit':limit,
            'access_state':access_state(sid,backend),'bank_id':backend.bank_id}
