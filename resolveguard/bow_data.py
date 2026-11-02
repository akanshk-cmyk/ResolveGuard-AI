"""Validated BOW fixtures, isolated from the archived ResolveGuard baseline."""
import hashlib
import json
from pathlib import Path
from typing import Literal
from pydantic import Field,model_validator
from .contracts import StrictModel,Identifier,Text,DateText,Timestamp

ROOT=Path(__file__).resolve().parents[1]/'data/bow'


class Product(StrictModel):
    product_id:Identifier
    product_name:Text
    product_type:Literal['checking','savings','debit_card','credit_card']
    tier:Text
    monthly_fee_cents_or_annual_card_fee_cents:int=Field(ge=0)
    currency:Literal['USD']
    waiver_or_fee_terms:Text
    illustrative_apy_percent:str=Field(pattern=r'^\d+\.\d+$')
    reward_structure:Text
    eligibility:Text
    access_level:Literal['PUBLIC']
    effective_date:DateText


class Policy(StrictModel):
    doc_id:Identifier
    bank_id:Literal['BOW']
    bank_name:Text
    product_id:Identifier
    topic:Text
    document_type:Literal['synthetic_policy']
    effective_date:DateText
    expires_on:DateText|None
    access_level:Literal['PUBLIC','INTERNAL','RESTRICTED']
    approval_status:Literal['SYNTHETIC_APPROVED_FOR_TEST_ONLY']
    refresh_rule:Text
    jurisdiction:Literal['US']
    currency:Literal['USD']
    policy_text:Text
    legal_class:Literal['SYNTHETIC_ONLY']
    disclaimer:Literal['NO_REAL_BANK_POLICY']

    @model_validator(mode='after')
    def valid_window(self):
        if self.expires_on and self.expires_on<=self.effective_date:raise ValueError('Invalid policy validity window')
        return self


class Chunk(StrictModel):
    chunk_id:Identifier
    doc_id:Identifier
    bank_id:Literal['BOW']
    product_id:Identifier
    topic:Text
    access_level:Literal['PUBLIC','INTERNAL','RESTRICTED']
    approval_status:Literal['SYNTHETIC_APPROVED_FOR_TEST_ONLY']
    effective_date:DateText
    expires_on:DateText|None
    refresh_rule:Text
    sha256_text:str=Field(pattern=r'^[0-9a-f]{64}$')
    chunk_text:Text

    @model_validator(mode='after')
    def correct_hash(self):
        if hashlib.sha256(self.chunk_text.encode()).hexdigest()!=self.sha256_text:raise ValueError('BOW chunk hash mismatch')
        return self


class Customer(StrictModel):
    customer_id:Identifier
    display_name:Text
    kyc_status:Literal['SYNTHETIC_VERIFIED','REVIEW']
    synthetic:Literal[True]


class Account(StrictModel):
    account_id:Identifier
    customer_id:Identifier
    product_id:Identifier
    status:Literal['OPEN','CLOSED','FROZEN']
    currency:Literal['USD']
    masked_display:str=Field(pattern=r'^[\u2022*]{2,4}\d{4}$')
    bank_id:Literal['BOW']


class Transaction(StrictModel):
    transaction_id:Identifier
    account_id:Identifier
    posted_on:DateText
    merchant:Text
    amount_cents:int
    currency:Literal['USD']
    status:Literal['POSTED','PENDING','REVERSED','DECLINED']
    bank_id:Literal['BOW']
    synthetic:Literal[True]


class Session(StrictModel):
    session_id:Identifier
    principal_id:Identifier
    actor_type:Literal['customer']
    authenticated:bool
    assurance:Literal['AAL1','AAL2']
    status:Literal['ACTIVE','REVOKED']
    expires_at:Timestamp
    synthetic:Literal[True]


class Case(StrictModel):
    case_id:Identifier
    account_id:Identifier
    case_type:Identifier
    status:Literal['OPEN','PENDING_REVIEW','IN_REVIEW','WAITING_FOR_CUSTOMER','RESOLVED','CLOSED']
    created_at:Timestamp
    owner_queue:Literal['BOW-SUPPORT','BOW-FRAUD']
    synthetic:Literal[True]


class Delegation(StrictModel):
    delegation_id:Identifier
    representative_id:Identifier
    customer_id:Identifier
    account_id:Identifier
    allowed_action:Literal['CASE_STATUS','TRANSACTION_READ']
    status:Literal['ACTIVE','REVOKED']
    expires_at:Timestamp
    synthetic:Literal[True]


class Intake(StrictModel):
    event_id:Identifier
    customer_id:Identifier
    report_capture_status:Literal['REPORT_CAPTURED']
    captured_at:Timestamp
    regulatory_notice_status:Literal['NOTICE_REVIEW_REQUIRED']
    investigation_status:Literal['NOT_STARTED']
    synthetic:Literal[True]


class Evaluation(StrictModel):
    eval_id:Identifier
    category:Text
    customer_prompt:Text
    expected_bank_id:Literal['BOW']
    expected_product_id:Identifier
    expected_intent:Text
    auth_expectation:Text
    expected_tools:Text|None
    forbidden_tools:Text|None
    safety_flags:Text|None
    expected_outcome:Text
    execution_status:Literal['NOT_RUN']
    risk_level:Text
    provenance:Literal['SYNTHETIC_ONLY']


MODELS={'products':Product,'policies':Policy,'chunks':Chunk,'customers':Customer,'accounts':Account,
        'transactions':Transaction,'sessions':Session,'cases':Case,'delegations':Delegation,'intake_events':Intake,'evaluations':Evaluation}


def validate_dataset(data):
    for name,model in MODELS.items():
        for row in data[name]:model.model_validate(row)
    products={r['product_id'] for r in data['products']};customers={r['customer_id'] for r in data['customers']}
    accounts={r['account_id']:r for r in data['accounts']};policies={r['doc_id']:r for r in data['policies']}
    for name,id_field in [('products','product_id'),('policies','doc_id'),('chunks','chunk_id'),('customers','customer_id'),
        ('accounts','account_id'),('transactions','transaction_id'),('sessions','session_id'),('cases','case_id'),('evaluations','eval_id')]:
        ids=[r[id_field] for r in data[name]]
        if len(ids)!=len(set(ids)) or any(not (v.startswith('BOW-') or v.startswith('POL-BOW-')) for v in ids):raise ValueError('Duplicate or wrong-bank identifier')
    for r in accounts.values():
        if r['customer_id'] not in customers or r['product_id'] not in products:raise ValueError('Broken account relationship')
    for name in ('transactions','cases','delegations'):
        for r in data[name]:
            if r['account_id'] not in accounts:raise ValueError('Broken account reference')
    for r in data['delegations']:
        if r['customer_id']!=accounts[r['account_id']]['customer_id']:raise ValueError('Delegation owner mismatch')
    for r in data['sessions']:
        if r['principal_id'] not in customers:raise ValueError('Broken session principal')
    for r in data['intake_events']:
        if r['customer_id'] not in customers:raise ValueError('Broken intake customer')
    for r in data['chunks']:
        parent=policies.get(r['doc_id'])
        if not parent:raise ValueError('Missing chunk parent')
        for key in ('bank_id','product_id','topic','access_level','approval_status','effective_date','expires_on','refresh_rule'):
            if r[key]!=parent[key]:raise ValueError('Chunk/parent scope mismatch: '+key)
        if r['chunk_text'] not in parent['policy_text']:raise ValueError('Chunk not in source policy')
    scopes=products|{'ALL','ALL_SAVINGS','CHECKING_DEBIT'}
    if any(r['product_id'] not in scopes for r in data['policies']):raise ValueError('Unknown policy product scope')
    dates={r['product_id']:r['effective_date'] for r in data['products']}
    if any(r['product_id'] in dates and r['effective_date']!=dates[r['product_id']] for r in data['policies']):
        raise ValueError('Product/policy effective-date mismatch')
    if any(r['expected_product_id'] not in products for r in data['evaluations']):raise ValueError('Unknown evaluation product')
    return data


def load_dataset():
    pointer=json.loads((ROOT/'active.json').read_text(encoding='utf-8'))
    digest=pointer['source_sha256']
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Invalid source pointer')
    directory=ROOT/digest
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if hashlib.sha256((directory/'source.xlsx').read_bytes()).hexdigest()!=digest:raise ValueError('Source workbook hash mismatch')
    for name in MODELS:
        if hashlib.sha256((directory/(name+'.json')).read_bytes()).hexdigest()!=manifest['data_sha256'][name]:raise ValueError('Imported data hash mismatch')
    data={name:json.loads((directory/(name+'.json')).read_text(encoding='utf-8')) for name in MODELS}
    return validate_dataset(data),manifest
