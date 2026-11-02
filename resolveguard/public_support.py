"""Guest-safe public evidence and deterministic account-access boundaries.

Public answers never invoke banking tools. A mistaken topic match cannot grant
record access: backend permissions independently govern every protected read.
"""
import json
import re
from datetime import date
from pathlib import Path
from typing import Literal
from pydantic import Field,ValidationError
from .contracts import StrictModel, DateText
from .presentation import GUIDANCE
from .retrieval import PolicyIndex

RATES=Path(__file__).resolve().parents[1]/'data/public_rates.json'
SIGN_IN_MESSAGE='Please sign in securely to view your account details.'
PUBLIC_IDS={'POL-FEE-001','POL-FEE-002','POL-TRAN-001','POL-DEMO-LIMIT','POL-DEMO-ATM','POL-DEMO-OVERDRAFT'}


class PublishedRate(StrictModel):
    product:str=Field(min_length=1,max_length=100)
    apy_percent:str=Field(pattern=r'^\d{1,3}(?:\.\d{1,6})?$')
    effective_date:DateText
    expires_at:DateText|None=None
    jurisdiction:Literal['US']='US'
    source_title:str=Field(min_length=1,max_length=300)
    source_url:str=Field(pattern=r'^https://[^\s]+$')
    approval_status:Literal['APPROVED_PUBLICATION','APPROVED_FOR_SYNTHETIC_TEST']
    version:str=Field(min_length=1,max_length=100)


def is_public_question(turn):
    """Explicit general questions stay public even with a stale UI selection."""
    text=turn.message.lower().strip()
    return (turn.action=='message' and bool(re.search(r'\b(what is|what are|how does|how do|explain|tell me|general|published|compare|comparison|difference|versus|vs|differ|better|cheaper)\b',text))
            and not re.search(r'\b(my|our|mine|charged|i was|i got|i paid|this transaction|this payment|this case)\b',text)
            and not re.search(r'\b(?:TXN|CASE|ACC)-[\w-]+',turn.message,re.I)
            and not turn.case_id and not turn.account_id)


def request_kind(turn):
    text=turn.message.lower()
    if turn.action!='message':return 'PROTECTED'
    if text.strip() in {'has it posted?','has it posted yet?','show that transaction','what about that transaction?',
                        'what is its status?','show that case','what about my case?'}:return 'PROTECTED'
    # Preserve possible error reports independently of authentication.
    from .model import TunedMockModel
    route=TunedMockModel(4).classify(turn.message)
    if route['potential_fraud_error']:return 'REPORT'
    from .request_context import transfer_requested, charge_inquiry
    if transfer_requested(text):return 'UNSUPPORTED'
    if charge_inquiry(text):return 'PROTECTED'
    from .comparisons import is_comparison
    if (is_comparison(text) and re.search(r'\b(my|our|mine|this payment|this transaction)\b',text)
            and re.search(r'\b(accounts?|payments?|transactions?|balances?|fees?|cases?)\b',text)):
        return 'PROTECTED'
    if is_public_question(turn):return 'PUBLIC'
    if turn.transaction_ids or turn.case_id or turn.account_id:return 'PROTECTED'
    if route['primary_intent'] in {'SUPPORT_CASE_REQUEST','CASE_STATUS'}:return 'PROTECTED'
    if re.search(r'\b(balance|transactions?|history|statement|account details|personal information|my account|my payments?|my fees?|charged|i paid|i got|i was)\b',text):return 'PROTECTED'
    if route['primary_intent']=='HUMAN_REQUEST':return 'SUPPORT'
    if route['primary_intent']=='UNSUPPORTED_REQUEST':return 'UNSUPPORTED'
    return 'PUBLIC'


def _public_evidence_answer(message,as_of,product_name=None,product_scope=None):
    text=message.lower();today=date.fromisoformat(as_of)
    sources=[]
    if re.search(r'\b(rate|rates|interest|apy)\b',text):
        candidates=[]
        product='savings' if 'savings' in text else 'checking' if 'checking' in text else None
        for raw in json.loads(RATES.read_text(encoding='utf-8'))['published_rates']:
            try:rate=PublishedRate.model_validate(raw)
            except ValidationError:continue
            if product_name and rate.product!=product_name:continue
            if not product or product not in rate.product.lower():continue
            if date.fromisoformat(rate.effective_date)>today:continue
            if rate.expires_at and today>=date.fromisoformat(rate.expires_at):continue
            candidates.append(rate)
        if len(candidates)==1:
            rate=candidates[0];sample=rate.approval_status=='APPROVED_FOR_SYNTHETIC_TEST'
            response=f"{'Sample rate only: ' if sample else ''}{rate.product}: {rate.apy_percent}% APY, effective {rate.effective_date}. This is public product information; sign-in is not required."
            sources=[{'title':rate.source_title,'summary':response,'reference':rate.source_url,'url':rate.source_url,
                      'version':rate.version,'effective_date':rate.effective_date,
                      'notice':'Fictional test rate, not a real bank offer.' if sample else 'Published public product information.'}]
        else:
            response=f"No approved, current published {product+' ' if product else ''}rate is configured in this demo. Please check your bank's published rate sheet. You do not need to sign in to ask about public rates."
    else:
        ids=[]
        if 'waiv' in text:ids=['POL-FEE-001','POL-FEE-002']
        elif 'atm' in text:ids=['POL-DEMO-ATM']
        elif 'overdraft' in text:ids=['POL-DEMO-OVERDRAFT']
        elif 'fee' in text or 'charge' in text:ids=['POL-FEE-001','POL-FEE-002']
        elif 'pending' in text or 'posted' in text:ids=['POL-TRAN-001']
        elif 'limit' in text:ids=['POL-DEMO-LIMIT']
        chunks=PolicyIndex().chunks
        for key in ids:
            eligible=[c for c in chunks if c['doc_id']==key and key in PUBLIC_IDS
                      and (product_scope is None or c['product']=='ALL' or c['product']=={'checking':'CHECKING','debit_card':'DEBIT_CHECKING','savings':'SAVINGS'}[product_scope])
                      and c['approval_status']=='APPROVED_FOR_SYNTHETIC_TEST'
                      and c['jurisdiction']=='US' and c['version'] in {'demo-v1','demo-extension-v1'}
                      and c['effective_date'] and date.fromisoformat(c['effective_date'])<=today
                      and (not c['expires_at'] or today<date.fromisoformat(c['expires_at']))]
            if len({c['version'] for c in eligible})!=1:continue
            if eligible:
                c=eligible[0]
                sources.append({'title':c['title'],'summary':GUIDANCE[key],'reference':c['chunk_id'],
                                'version':c['version'],'effective_date':c['effective_date'],
                                'notice':'Public sample guidance for the demo, not approved real bank terms.'})
        response='\n\n'.join(s['summary'] for s in sources)
        if not response:
            response='The supplied evidence does not contain current terms for that product and question. I cannot confirm a fee, rate or condition from it.'
    return {'response':response,'response_state':'PUBLIC_GUIDANCE','data_scope':'PUBLIC','auth_required':False,
            'cards':[],'source_details':sources,'presentation_version':'guest-first-v1','execution_mode':'MOCK'}


class LegacyPublicKnowledge:
    """Require a confirmed original-demo product before policy retrieval."""
    conversation_version='strict-product-v2-comparisons'

    def __init__(self):
        import hashlib
        self.version=hashlib.sha256((RATES.read_text(encoding='utf-8')+json.dumps(PolicyIndex().chunks,sort_keys=True)).encode()).hexdigest()
        self.products=[{'product_id':'LEGACY-CHECKING','name':'Original demo checking account','category':'checking'},
                       {'product_id':'LEGACY-DEBIT','name':'Original demo debit card','category':'debit_card'}]
        for raw in json.loads(RATES.read_text(encoding='utf-8'))['published_rates']:
            try:rate=PublishedRate.model_validate(raw)
            except ValidationError:continue
            if not any(p['name']==rate.product for p in self.products):
                self.products.append({'product_id':'LEGACY-RATE-'+hashlib.sha256(rate.product.encode()).hexdigest()[:12],
                                      'name':rate.product,'category':'savings','rate_product':rate.product})
        if not any(p['category']=='savings' for p in self.products):
            self.products.append({'product_id':'LEGACY-SAVINGS','name':'Original demo savings account','category':'savings'})

    def converse(self,message,product_id,as_of,context=None):
        context=dict(context or {});text=message.lower().strip()
        from .comparisons import is_status_comparison,ComparisonPlan
        if is_status_comparison(message):
            output=_public_evidence_answer(message,as_of)
            refs=[s['reference'] for s in output['source_details']]
            output['comparison_plan']=ComparisonPlan(bank_id='LEGACY_DEMO',kind='PAYMENT_STATUS',
                subjects=['Pending payment','Posted payment'],dimensions=['status_definition'],
                decision='SUPPORTED' if refs else 'MISSING_EVIDENCE',
                evidence_by_subject={'pending':refs,'posted':refs}).model_dump()
            output['answered_question']=message
            return output,{}
        named=[p for p in self.products if p['name'].lower() in text]
        pending=context.get('pending_question')
        category=('savings' if 'saving' in text or 'interest' in text or 'apy' in text else
                  'debit_card' if 'debit' in text or 'card' in text else 'checking' if 'checking' in text else None)
        category_only=text in {'checking','checking account','original demo checking account','savings','saving account','savings account','original demo savings account','debit card','original demo debit card'}
        candidates=[p for p in self.products if not category or p['category']==category]
        if category_only and len(candidates)==1:named=candidates
        ordinal={'1':0,'first':0,'first one':0,'2':1,'second':1,'second one':1,'3':2,'third':2,'third one':2}.get(text)
        if pending and ordinal is not None:
            choices=context.get('pending_choices',[])
            if ordinal<len(choices):named=[p for p in self.products if p['product_id']==choices[ordinal]]
        selection=bool(named) and (category_only or text==named[0]['name'].lower() or ordinal is not None)
        question=pending if pending and selection else message
        selected=named[0] if len(named)==1 else next((p for p in self.products if p['product_id']==context.get('product_id')),None) if context.get('product_confirmed') else None
        desired='savings' if any(w in question.lower() for w in ('saving','interest','apy')) else None
        if selected and desired and selected['category']!=desired:selected=None
        if not selected:
            choices=[p for p in self.products if not (desired or category) or p['category']==(desired or category)]
            return ({'response':'To make sure I find the right terms, which specific account or product are you asking about? Choose one below, or type its name.',
                     'response_state':'CLARIFICATION_REQUIRED','data_scope':'PUBLIC','auth_required':False,'cards':[],'source_details':[],
                     'choose_product':True,'product_choices':[{'product_id':p['product_id'],'name':p['name']} for p in choices],
                     'question_category':desired or category,'selected_product_id':None,'answered_question':question},
                    {'pending_question':question,'pending_category':desired or category,'pending_choices':[p['product_id'] for p in choices]})
        q=question.lower()
        if selected['category']!='checking' and any(w in q for w in ('monthly maintenance','monthly service','fee waiver')) and selected['category']!='savings':
            output={'response':'That product does not have an applicable monthly account-fee policy in the supplied evidence. Which checking account do you mean?',
                    'response_state':'CLARIFICATION_REQUIRED','data_scope':'PUBLIC','auth_required':False,'cards':[],'source_details':[]}
        else:
            prefix='savings' if selected['category']=='savings' else 'checking' if selected['category']=='checking' else 'debit card'
            output=_public_evidence_answer(prefix+' '+question,as_of,selected.get('rate_product'),selected['category'])
            if 'waiv' in q and selected['category']=='checking' and output['source_details']:
                output['response']='The original-demo checking policy requires a verified product-level eligibility check, but it does not specify balance or deposit thresholds. I cannot invent those limits or confirm your eligibility. The missing evidence is the approved waiver criteria and the account facts those criteria require; please do not share private account details in chat.'
            elif any(term in q for term in ('monthly','maintenance','service fee')) and 'fee' in q and selected['category']=='checking' and output['source_details']:
                output['response']='For the original-demo checking account, the supplied schedule says a $12 monthly fee may apply. This public policy does not establish whether it applies to your own account.'
                output['source_details']=[s for s in output['source_details'] if s['reference'].startswith('POL-FEE-001:')]
        output.update(selected_product_id=selected['product_id'],answered_question=question,bank_id='LEGACY_DEMO')
        return output,{'product_id':selected['product_id'],'product_confirmed':True}


def public_answer(message,as_of):
    return LegacyPublicKnowledge().converse(message,None,as_of)[0]
