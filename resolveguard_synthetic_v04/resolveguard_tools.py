"""ResolveGuard synthetic tool layer. NOT production banking logic or legal advice.
Uses deterministic fixture APIs and optional LangChain FAISS retrieval adapters.
All synthetic rules intentionally need institution approval before any real use.
"""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

ROOT=Path(__file__).resolve().parent
FIXTURE_DIR=ROOT/'fixtures'
def load(name):return json.loads((FIXTURE_DIR/name).read_text())
KNOWLEDGE_BASES=load('knowledge_bases.json')
KB_TOOL_NAMES={x['name'] for x in KNOWLEDGE_BASES}
TOOL_TO_TAG={x['name']:x['tag'] for x in KNOWLEDGE_BASES}

class FixtureBank:
    def __init__(self, now='2026-10-30T13:00:00Z', outages=None):
        self.now=datetime.fromisoformat(now.replace('Z','+00:00'))
        self.outages=set(outages or ())
        self.customers=load('customers.json')
        self.accounts=load('accounts.json')
        self.transactions=load('transactions.json')
        self.cases=load('cases.json')
        self.sessions=load('sessions.json')
        self.delegations=load('delegations.json')
        self.employees=load('employee_scopes.json')
        self.services=load('service_identities.json')
        self.reports={};self.handoffs={};self.audit=[]
    def _after(self, date):return datetime.fromisoformat(date.replace('Z','+00:00'))>self.now
    def _session(self, sid):
        s=next((s for s in self.sessions if s['session_id']==sid),None)
        return s if s and s['authenticated'] and not s['revoked'] and self._after(s['expires_at']) else None
    def _permit(self, sid, account_id, action, case_id=None):
        s=self._session(sid)
        if not s:return False,'AUTHENTICATION_REQUIRED'
        actor=s['actor_type'];principal=s['principal_id']
        account=next((a for a in self.accounts if a['account_id']==account_id),None)
        if not account:return False,'RESOURCE_NOT_AUTHORIZED'
        if actor=='CUSTOMER':return (True,'ALLOW') if account['customer_id']==principal else (False,'RESOURCE_NOT_AUTHORIZED')
        if actor=='REPRESENTATIVE':
            valid=any(d['representative_id']==principal and not d['revoked'] and self._after(d['expires_at']) and account_id in d['account_ids'] and action in d['actions'] and d['customer_id']==account['customer_id'] for d in self.delegations)
            return (True,'ALLOW') if valid else (False,'DELEGATION_NOT_AUTHORIZED')
        if actor=='EMPLOYEE':
            valid=any(e['employee_id']==principal and account_id in e['allowed_accounts'] and action in e['actions'] and (not case_id or case_id in e['legitimate_case_ids']) for e in self.employees)
            return (True,'ALLOW') if valid else (False,'EMPLOYEE_SCOPE_DENIED')
        return False,'AUTHORIZATION_DENIED'
    def _check_agent(self,service_id,tool):
        service=next((s for s in self.services if s['service_id']==service_id),None)
        if not service or tool not in service['allowed_tools']:return False
        return True
    def _result(self,tool,status,reason,data=None):
        event={'tool':tool,'status':status,'reason_code':reason,'returned_fields':sorted((data or {}).keys())}
        self.audit.append(event)
        return {'status':status,'reason_code':reason,'data':data}
    def get_session_assurance(self,session_id,service_id='resolveguard-agent'):
        if not self._check_agent(service_id,'get_session_assurance'):return self._result('get_session_assurance','DENIED','SERVICE_NOT_AUTHORIZED')
        s=self._session(session_id)
        if not s:return self._result('get_session_assurance','DENIED','SESSION_INVALID')
        return self._result('get_session_assurance','OK','ALLOW',{'actor_type':s['actor_type'],'assurance':s['assurance'],'session_valid':True})
    def check_authority(self,session_id,account_id,action,service_id='resolveguard-agent'):
        if not self._check_agent(service_id,'check_authority'):return self._result('check_authority','DENIED','SERVICE_NOT_AUTHORIZED')
        valid,reason=self._permit(session_id,account_id,action)
        return self._result('check_authority','OK' if valid else 'DENIED',reason,{'authorized':True} if valid else None)
    def get_transaction(self,session_id,transaction_id,service_id='resolveguard-agent'):
        tool='get_transaction'
        if not self._check_agent(service_id,tool):return self._result(tool,'DENIED','SERVICE_NOT_AUTHORIZED')
        tx=next((t for t in self.transactions if t['transaction_id']==transaction_id),None)
        if not tx:return self._result(tool,'DENIED','RESOURCE_NOT_AUTHORIZED')
        ok,reason=self._permit(session_id,tx['account_id'],'TRANSACTION_READ')
        if not ok:return self._result(tool,'DENIED',reason)
        if tool in self.outages:return self._result(tool,'UNKNOWN','BACKEND_UNAVAILABLE')
        return self._result(tool,'OK','ALLOW',{k:tx[k] for k in ('transaction_id','posted_on','merchant','amount_cents','currency','status')})
    def get_case_status(self,session_id,case_id,service_id='resolveguard-agent'):
        tool='get_case_status'
        if not self._check_agent(service_id,tool):return self._result(tool,'DENIED','SERVICE_NOT_AUTHORIZED')
        case=next((c for c in self.cases if c['case_id']==case_id),None)
        if not case:return self._result(tool,'DENIED','RESOURCE_NOT_AUTHORIZED')
        ok,reason=self._permit(session_id,case['account_id'],'CASE_STATUS',case_id)
        if not ok:return self._result(tool,'DENIED',reason)
        if tool in self.outages:return self._result(tool,'UNKNOWN','BACKEND_UNAVAILABLE')
        return self._result(tool,'OK','ALLOW',{k:case[k] for k in ('case_id','case_type','status','created_at','owner_queue')})
    def record_error_report(self,session_id,report_id,customer_statement,service_id='resolveguard-agent'):
        tool='record_error_report'
        if not self._check_agent(service_id,tool):return self._result(tool,'DENIED','SERVICE_NOT_AUTHORIZED')
        if not isinstance(customer_statement,str) or not customer_statement.strip():return self._result(tool,'DENIED','EMPTY_REPORT')
        if report_id in self.reports:return self._result(tool,'OK','ALREADY_CAPTURED',{'report_id':report_id,'report_capture_status':'CAPTURED','regulatory_notice_status':'REVIEW_REQUIRED'})
        if tool in self.outages:return self._result(tool,'UNKNOWN','CAPTURE_UNCONFIRMED')
        # Deliberately separate durable report capture from identity and legal receipt adjudication.
        self.reports[report_id]={'report_id':report_id,'original_statement':customer_statement,'reported_at':self.now.isoformat(),'session_id':session_id,'report_capture_status':'CAPTURED','regulatory_notice_status':'REVIEW_REQUIRED','verification_status':'PENDING','investigation_status':'NOT_STARTED','customer_confirmation_status':'UNCONFIRMED'}
        return self._result(tool,'OK','CAPTURED',{'report_id':report_id,'report_capture_status':'CAPTURED','regulatory_notice_status':'REVIEW_REQUIRED','verification_status':'PENDING','investigation_status':'NOT_STARTED','customer_confirmation_status':'UNCONFIRMED'})
    def handoff_to_human(self,session_id,case_id,queue,service_id='resolveguard-agent'):
        tool='handoff_to_human'
        if not self._check_agent(service_id,tool):return self._result(tool,'DENIED','SERVICE_NOT_AUTHORIZED')
        case=next((c for c in self.cases if c['case_id']==case_id),None)
        if not case:return self._result(tool,'DENIED','RESOURCE_NOT_AUTHORIZED')
        ok,reason=self._permit(session_id,case['account_id'],'CASE_STATUS',case_id)
        if not ok:return self._result(tool,'DENIED',reason)
        if tool in self.outages:return self._result(tool,'UNKNOWN','QUEUE_UNAVAILABLE')
        if queue not in {'CUSTOMER_SUPPORT','FRAUD_OPERATIONS'}:return self._result(tool,'DENIED','QUEUE_NOT_APPROVED')
        handoff_id='HANDOFF-'+case_id
        self.handoffs[handoff_id]={'case_id':case_id,'queue':queue,'status':'ACKNOWLEDGED'}
        return self._result(tool,'OK','QUEUE_ACKNOWLEDGED',{'handoff_id':handoff_id,'handoff_status':'ACKNOWLEDGED'})

# Exactly as the source pattern: independent KBs, optional FAISS, and
# content_and_artifact so the evaluation harness can examine individual source docs.
def build_kb_tool(spec,embeddings,k=5,product='ALL'):
    from langchain_community.vectorstores import FAISS
    from langchain_core.documents import Document
    from langchain_core.tools import StructuredTool
    relevant=[x for x in spec['docs'] if x['approval_status']=='APPROVED_FOR_SYNTHETIC_TEST' and x['product'] in ('ALL',product)]
    if not relevant:raise ValueError('No approved synthetic documents match this product')
    docs=[Document(page_content=x['text'],metadata={key:x[key] for key in ('doc_id','title','version','effective_date','jurisdiction','product','approval_status')}) for x in relevant]
    ret=FAISS.from_documents(docs,embeddings).as_retriever(search_kwargs={'k':min(k,len(docs))})
    def search(query:str):
        results=ret.invoke(query)
        formatted=['['+spec['tag']+' | '+d.metadata['doc_id']+' | '+d.metadata['version']+'] '+d.page_content for d in results]
        return '\n\n---\n\n'.join(formatted), [{'text':d.page_content,'metadata':d.metadata} for d in results]
    return StructuredTool.from_function(search,name=spec['name'],description=spec['description'],response_format='content_and_artifact')

def search_kb_offline(kb_name,query,product='ALL',k=5):
    """Deterministic smoke-test fallback, NOT equivalent to vector retrieval."""
    spec=next(s for s in KNOWLEDGE_BASES if s['name']==kb_name)
    tokens=set(query.lower().split())
    docs=[d for d in spec['docs'] if d['product'] in ('ALL',product) and d['approval_status']=='APPROVED_FOR_SYNTHETIC_TEST']
    ranked=sorted(docs,key=lambda d:len(tokens.intersection(set((d['title']+' '+d['text']).lower().split()))),reverse=True)
    return [{'doc_id':d['doc_id'],'text':d['text'],'tag':spec['tag'],'version':d['version']} for d in ranked[:k]]
