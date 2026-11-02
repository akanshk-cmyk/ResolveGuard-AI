"""Observable comparison plans and isolated public evidence, never hidden reasoning."""
import re
import hashlib
import json
from datetime import date
from typing import Literal
from pydantic import Field
from .contracts import StrictModel, Identifier
from .presentation import format_money


class ComparisonPlan(StrictModel):
    bank_id: Literal['BOW','LEGACY_DEMO']='BOW'
    kind: Literal['PRODUCTS','PAYMENT_STATUS']
    subjects: list[str]
    product_ids: list[Identifier]=[]
    dimensions: list[str]
    decision: Literal['NEEDS_SUBJECTS','SUPPORTED','PARTIAL_EVIDENCE','MISSING_EVIDENCE']
    evidence_by_subject: dict[str,list[str]]=Field(default_factory=dict)
    steps: list[str]=['resolve_subjects']


def is_comparison(message: str) -> bool:
    return bool(re.search(r'\b(compare|comparison|differences?|versus|vs|differ|different|better|cheaper)\b',message,re.I))


def is_status_comparison(message: str) -> bool:
    return is_comparison(message) and bool(re.search(r'\bpending\b',message,re.I)) and bool(re.search(r'\bposted\b',message,re.I))


def product_subjects(knowledge, message: str, category=None) -> list[str]:
    """Keep each distinct mention; longest alias wins locally, not globally."""
    normal=lambda value:' '.join(re.findall(r'[a-z0-9]+',value.lower()))
    text=normal(message)
    categories=[kind for word,kind in [('checking','checking'),('savings','savings'),('debit','debit_card'),('credit','credit_card')] if word in text]
    category=category or (categories[0] if len(categories)==1 else None)
    hits=[]
    for product in knowledge.products:
        for alias in (product['product_name'],product['product_name'].removeprefix('Whatever '),product['product_id']):
            for match in re.finditer(r'(?<!\w)'+re.escape(normal(alias))+r'(?!\w)',text):
                hits.append((match.start(),match.end(),product['product_id']))
    selected=[]
    for start,end,pid in sorted(hits,key=lambda h:-(h[1]-h[0])):
        if not any(start<s_end and end>s_start for s_start,s_end,_ in selected):selected.append((start,end,pid))
    # Bare tier names require an unambiguous category or unique catalog match.
    for tier in {p['tier'] for p in knowledge.products}:
        candidates=[p for p in knowledge.products if p['tier']==tier and (not category or p['product_type']==category)]
        if len(candidates)!=1:continue
        for match in re.finditer(r'(?<!\w)'+re.escape(normal(tier))+r'(?!\w)',text):
            if not any(match.start()<end and match.end()>start for start,end,_ in selected):
                selected.append((match.start(),match.end(),candidates[0]['product_id']))
    return list(dict.fromkeys(pid for _,_,pid in sorted(selected)))


def _result(knowledge, response, plan, source_ids=(), catalog_sources=(), **extra):
    return {'response':response,'response_state':'CLARIFICATION_REQUIRED' if extra.get('choose_product') else 'PUBLIC_GUIDANCE',
            'data_scope':'PUBLIC','auth_required':False,'bank_id':'BOW','cards':[],
            'source_details':knowledge.sources(source_ids)+list(catalog_sources),'execution_mode':'MOCK',
            'comparison_plan':plan.model_dump(),'question_topic':'COMPARISON',
            'execution_evidence':{'data_scope':'PUBLIC','private_records_accessed':False,'personal_eligibility_checked':False},**extra}


def _eligible(knowledge, candidate, pid, as_of):
    canonical=knowledge.chunk_map.get(candidate.get('chunk_id'))
    if not canonical or any(candidate.get(key)!=canonical.get(key) for key in ('bank_id','product_id','chunk_text','sha256_text')):return None
    parent=knowledge.policy_map.get(canonical['doc_id'])
    if not parent or parent['bank_id']!='BOW' or parent['product_id']!=pid:return None
    if parent['access_level']!='PUBLIC' or parent['approval_status']!='SYNTHETIC_APPROVED_FOR_TEST_ONLY':return None
    if parent['effective_date']>as_of or parent['expires_on'] and as_of>=parent['expires_on']:return None
    if canonical['bank_id']!='BOW' or canonical['product_id']!=pid or canonical['access_level']!='PUBLIC':return None
    if canonical['approval_status']!='SYNTHETIC_APPROVED_FOR_TEST_ONLY':return None
    if canonical['effective_date']>as_of or canonical['expires_on'] and as_of>=canonical['expires_on']:return None
    return canonical


def compare_products(knowledge, message, as_of, product_ids=None, category=None):
    date.fromisoformat(as_of)
    ids=product_subjects(knowledge,message,category) if product_ids is None else list(dict.fromkeys(product_ids))
    ids=[pid for pid in ids if pid in knowledge.product_map]
    topic=knowledge.question_topic(message)
    if topic=='UNKNOWN':topic='FEE' if re.search(r'\b(cheaper|costs?)\b',message,re.I) else 'FEATURES'
    plan=ComparisonPlan(kind='PRODUCTS',subjects=[knowledge.product_map[p]['product_name'] for p in ids],
                        product_ids=ids,dimensions=[topic],decision='NEEDS_SUBJECTS')
    if len(ids)!=2:
        if len(ids)>2:ids=[];plan.product_ids=[]
        choices=[{'product_id':p['product_id'],'name':p['product_name']} for p in knowledge.products
                 if p['product_id'] not in ids and (not category or p['product_type']==category)]
        prompt=('Which other product would you like to compare with '+plan.subjects[0]+'?' if len(ids)==1
                else 'Which two products would you like to compare? Please give their full names.' if not ids
                else 'Please choose exactly two products for this comparison.')
        return _result(knowledge,prompt,plan,choose_product=True,product_choices=choices,
                       question_category=category,clarification_question=message)
    sections=[]; citations=[]; missing=[];catalog_sources=[]
    plan.steps.extend(['retrieve_separately','verify_scope_and_dates'])
    feature=next((w for w in ('atm','overdraft','wire','replacement','foreign','late','transfer','returned item') if re.search(r'\b'+w+r'\b',message,re.I)),None)
    for pid in ids:
        product=knowledge.product_map[pid]
        candidates=knowledge.retrieve('BOW',pid,as_of,allow_demo=True,query=message,limit=61)
        chunks=[valid for c in candidates if (valid:=_eligible(knowledge,c,pid,as_of)) is not None]
        terms={'FEE':('fee','waiv'),'WAIVER':('fee','waiv'),'APY':('apy','variable','relationship'),
               'REWARDS':('reward',),'ELIGIBILITY':('eligib','relationship')}.get(topic)
        chunks=[c for c in chunks if c['topic']=='product_terms' and (not terms or any(t in c['chunk_text'].lower() for t in terms))]
        # Never substitute a monthly/annual fee for an unsupported feature fee.
        wrong_period=('annual' in message.lower() and product['product_type'] in {'checking','savings'} or
                      'monthly' in message.lower() and product['product_type'] in {'debit_card','credit_card'})
        if topic in {'FEE','WAIVER'} and (feature or wrong_period):chunks=[]
        refs=[c['chunk_id'] for c in chunks];plan.evidence_by_subject[pid]=refs;citations.extend(refs)
        name=knowledge.product_map[pid]['product_name']
        if not chunks:
            missing.append(pid);sections.append(name+'\nNo current approved evidence is available for the requested '+(feature+' ' if feature else '')+'comparison.')
        else:
            excerpts=[c['chunk_text'].replace('\u2265','of at least').replace(' OR ',' or ') for c in chunks]
            if topic in {'FEE','WAIVER','FEATURES'} and product['effective_date']<=as_of:
                period='annual card fee' if product['product_type'] in {'debit_card','credit_card'} else 'monthly maintenance fee'
                fee=f"{period.capitalize()}: {format_money(product['monthly_fee_cents_or_annual_card_fee_cents'])}."
                reference='BOW-CATALOG:'+pid+':'+knowledge.version
                expires=[c['expires_on'] for c in chunks if c['expires_on']]
                catalog_sources.append({'title':product['product_name']+' product catalog','summary':fee,
                    'reference':reference,'version':knowledge.version,'bank_id':'BOW','product_id':pid,
                    'effective_date':product['effective_date'],'expires_on':min(expires) if expires else None,
                    'access_level':'PUBLIC','approval_status':'SYNTHETIC_APPROVED_FOR_TEST_ONLY',
                    'content_hash':hashlib.sha256(json.dumps(product,sort_keys=True).encode()).hexdigest(),
                    'notice':'Fictional BOW product record from BOW Products; linked current policy required.'})
                plan.evidence_by_subject[pid].append(reference)
                excerpts.insert(0,fee)
            sections.append(name+'\n'+'\n'.join('- '+text for text in excerpts))
    plan.decision='MISSING_EVIDENCE' if len(missing)==2 else 'PARTIAL_EVIDENCE' if missing else 'SUPPORTED'
    plan.steps.append('compare_supported_facts' if len(missing)<2 else 'report_missing_sources')
    response='Here are the source-backed details for each product:\n\n'+'\n\n'.join(sections)+'\n\nFictional demo terms. Policy dates and sources are listed below.'
    return _result(knowledge,response,plan,citations,catalog_sources,comparison_product_ids=ids)


def compare_payment_statuses(knowledge,message,as_of):
    date.fromisoformat(as_of)
    plan=ComparisonPlan(kind='PAYMENT_STATUS',subjects=['Pending payment','Posted payment'],
                        dimensions=['status_definition'],decision='MISSING_EVIDENCE',
                        evidence_by_subject={'pending':[],'posted':[]})
    # Search bank-wide definitions only, never transaction fixtures or another bank.
    candidates=knowledge.retrieve('BOW','BOW-CHK-001',as_of,allow_demo=True,query=message,limit=61)
    plan.steps.extend(['retrieve_bank_glossary','verify_scope_and_dates'])
    definitions={key:[] for key in ('pending','posted')}
    for candidate in candidates:
        source=knowledge.chunk_map.get(candidate.get('chunk_id'))
        if not source or source['topic'] not in {'payment_status','transaction_status','payment_status_definition'}:continue
        if source['product_id'] not in {'ALL','CHECKING_DEBIT'}:continue
        canonical=_eligible(knowledge,candidate,source['product_id'],as_of)
        if not canonical:continue
        for key in definitions:
            if re.search(r'\b'+key+r'\b',canonical['chunk_text'],re.I):definitions[key].append(canonical)
    sections=[];refs=[]
    for key,chunks in definitions.items():
        plan.evidence_by_subject[key]=[c['chunk_id'] for c in chunks]
        refs.extend(plan.evidence_by_subject[key])
        sections.append(key.capitalize()+' payment\n'+ ('\n'.join(c['chunk_text'] for c in chunks) if chunks else 'No approved BOW definition is available in this demo.'))
    available=sum(bool(c) for c in definitions.values())
    plan.decision='SUPPORTED' if available==2 else 'PARTIAL_EVIDENCE' if available else 'MISSING_EVIDENCE'
    plan.steps.append('compare_supported_facts' if available else 'report_missing_sources')
    if not available:
        response='I don\'t have an approved Bank of Whatever policy explaining pending versus posted payments in this demo yet, so I cannot give you a sourced comparison. This general question does not require sign-in.'
    else:response='\n\n'.join(sections)+'\n\nThese are fictional demo policy definitions, not the status of your own payment.'
    return _result(knowledge,response,plan,refs)
