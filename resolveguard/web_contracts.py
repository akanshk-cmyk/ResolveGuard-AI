"""Customer HTTP request contracts, retaining the existing web import aliases."""
from typing import Literal
from .contracts import StrictModel, Identifier, Text
from .conversation import Turn

PROFILES={'customer-one':('SESS-001','Demo Customer One'),
          'customer-two':('SESS-002','Demo Customer Two'),
          'signed-out':('SESS-ANON','Signed-out visitor'),
          'expired':('SESS-EXPIRED','Sign-in expired'),
          'needs-verification':('SESS-STEPUP','Demo Customer One'),
          'bow-customer-one':('BOW-SESS-001','BOW Demo Customer 01'),
          'bow-customer-two':('BOW-SESS-002','BOW Demo Customer 02'),
          'bow-needs-verification':('BOW-SESS-003','BOW Demo Customer 03'),
          'bow-revoked':('BOW-SESS-009','BOW revoked session'),
          'bow-unauthenticated':('BOW-SESS-010','BOW signed-out sample')}


class DemoSettings(StrictModel):
    profile:Literal['customer-one','customer-two','signed-out','expired','needs-verification','bow-customer-one','bow-customer-two','bow-needs-verification','bow-revoked','bow-unauthenticated']='signed-out'
    queue_failure:Literal['none','primary','all']='none'


class WebTurn(Turn):
    thread_id:Identifier|None=None
    bank_id:Literal['LEGACY_DEMO','BOW']='LEGACY_DEMO'
    product_id:Identifier|None=None


class DemoVerification(StrictModel):
    action:Literal['confirm','cancel']


class DemoSignIn(StrictModel):
    profile:Literal['customer-one','customer-two','needs-verification','bow-customer-one','bow-customer-two','bow-needs-verification']='customer-one'
    pending_id:Identifier|None=None


class ResumeRequest(StrictModel):
    pending_id:Identifier


class NewConversationSettings(StrictModel):
    guest:bool=False  # Existing callers may retain their identity; the UI requests guest explicitly.


class DemoCallbackRequest(StrictModel):
    handoff_ref:Identifier
    request_key:Identifier
    consent:bool


class PublicContext(StrictModel):
    comparison_pending:bool=False
    comparison_product_ids:list[Identifier]=[]
    product_id:Identifier|None=None
    product_confirmed:bool=False
    last_topic:Literal['FEE','WAIVER','APY','REWARDS','ELIGIBILITY','FEATURES','UNKNOWN']|None=None
    pending_question:Text|None=None
    pending_category:Literal['checking','savings','debit_card','credit_card']|None=None
    pending_choices:list[Identifier]=[]

# Preserve historical pickling/type identity through resolveguard.web re-exports.
for _contract in (DemoSettings, WebTurn, DemoVerification, DemoSignIn,
                  ResumeRequest, NewConversationSettings, DemoCallbackRequest, PublicContext):
    _contract.__module__ = 'resolveguard.web'
del _contract
