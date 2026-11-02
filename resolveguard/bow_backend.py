"""BOW's workbook fixtures behind the same deterministic permission boundary."""
from .backend import Backend
from .bow_data import load_dataset
from .contracts import Request,validated_result
from .bow_knowledge import BowPolicyIndex


class BowBackend(Backend):
    bank_id='BOW'

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.data,self.source=load_dataset()
        public=[s for s in self.bank.sessions if s['session_id']=='SESS-ANON']
        self.bank.customers=self.data['customers']
        self.bank.accounts=[dict(r,product='CHECKING') for r in self.data['accounts']]
        self.bank.transactions=self.data['transactions'];self.bank.cases=self.data['cases']
        self.bank.sessions=[dict(r,actor_type=r['actor_type'].upper(),revoked=r['status']=='REVOKED') for r in self.data['sessions']]+public
        self.bank.delegations=[{'delegation_id':r['delegation_id'],'representative_id':r['representative_id'],
            'customer_id':r['customer_id'],'account_ids':[r['account_id']],'actions':[r['allowed_action']],
            'expires_at':r['expires_at'],'revoked':r['status']!='ACTIVE'} for r in self.data['delegations']]
        self.bank.employees=[]
        self.demo_verified=False

    def assurance_error(self,request):
        if request.bank_id!=self.bank_id:return 'BANK_SCOPE_MISMATCH'
        error=super().assurance_error(request)
        if error:return error
        # Explicit demo risk rule: source AAL1 fixtures require the separate check.
        session=self.bank._session(request.session_id)
        if session and session['assurance']=='AAL1' and not self.demo_verified:return 'STEP_UP_REQUIRED'
        return None

    @validated_result('transaction')
    def transaction(self,request,transaction_id):
        result=super().transaction(request,transaction_id)
        if result['status']=='OK':
            tx=next(t for t in self.bank.transactions if t['transaction_id']==transaction_id)
            account=next(a for a in self.bank.accounts if a['account_id']==tx['account_id'])
            result['data'].update(bank_id='BOW',product_id=account['product_id'],account_display=account['masked_display'])
        return result

    def policy_index_for(self,request):
        accounts=set()
        if request.account_id:accounts.add(request.account_id)
        for ident in request.transaction_ids:
            accounts.update(t['account_id'] for t in self.bank.transactions if t['transaction_id']==ident)
        if request.case_id:
            accounts.update(c['account_id'] for c in self.bank.cases if c['case_id']==request.case_id)
        products={a['product_id'] for a in self.bank.accounts if a['account_id'] in accounts and self.allowed_account(request,a['account_id'])}
        return BowPolicyIndex(next(iter(products)) if len(products)==1 else None)
