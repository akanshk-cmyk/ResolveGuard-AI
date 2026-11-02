"""Strict Pydantic boundaries. Validation is not authorization or commit proof."""
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import wraps
from typing import Annotated, Literal, Union, get_args

from pydantic import (
    AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter,
    field_validator, model_validator,
)

Intent = Literal[
    'FEE_INQUIRY', 'POLICY_LOOKUP', 'TRANSACTION_INQUIRY', 'CASE_STATUS',
    'FRAUD_ERROR_REPORT', 'SUPPORT_CASE_REQUEST', 'HUMAN_REQUEST',
    'UNSUPPORTED_REQUEST', 'OTHER_OR_UNCLEAR',
]
INTENTS = frozenset(get_args(Intent))


def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError('Must contain non-whitespace text')
    return value  # Original report wording must not be silently stripped.


def array_to_tuple(value):
    """Accept JSON arrays or Python tuples, never strings or arbitrary iterables."""
    return tuple(value) if isinstance(value, list) else value


def iso_date(value: str) -> str:
    date.fromisoformat(value)
    return value


def aware_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Timestamp must include a timezone')
    return value


Identifier = Annotated[str, Field(min_length=1, max_length=200, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]*$')]
Text = Annotated[str, Field(min_length=1, max_length=20000), AfterValidator(nonblank)]
DateText = Annotated[str, Field(pattern=r'^\d{4}-\d{2}-\d{2}$'), AfterValidator(iso_date)]
Timestamp = Annotated[str, Field(min_length=20, max_length=40), AfterValidator(aware_timestamp)]
TransactionIds = Annotated[tuple[Identifier, ...], BeforeValidator(array_to_tuple), Field(max_length=20)]
ReceiverFields = Annotated[tuple[Literal['case_id', 'report_id'], ...], BeforeValidator(array_to_tuple), Field(max_length=2)]
ReportId = Annotated[str, Field(pattern=r'^DEMO-REPORT-[0-9a-f]{16}$')]
CaseEventId = Annotated[str, Field(pattern=r'^DEMO-CASE-[0-9a-f]{16}$')]
HandoffId = Annotated[str, Field(pattern=r'^DEMO-HANDOFF-[0-9a-f]{16}$')]


class StrictModel(BaseModel):
    model_config = ConfigDict(
        strict=True, extra='forbid', validate_default=True,
        hide_input_in_errors=True, revalidate_instances='always',
    )


class Request(StrictModel):
    """Trusted caller supplies fixture identity; chat text cannot set authority."""
    model_config = ConfigDict(frozen=True)
    message: Text
    request_key: Identifier
    session_id: Identifier = 'SESS-001'
    transaction_ids: TransactionIds = ()
    case_id: Identifier | None = None
    account_id: Identifier | None = None
    confirmed: bool = False
    service_id: Identifier = 'resolveguard-agent'
    product: Literal['CHECKING', 'DEBIT_CHECKING'] = 'DEBIT_CHECKING'
    jurisdiction: Literal['US'] = 'US'

    @field_validator('transaction_ids')
    @classmethod
    def unique_transactions(cls, value):
        if len(set(value)) != len(value):
            raise ValueError('Select each transaction at most once')
        return value

    @classmethod
    def from_dict(cls, value):
        return cls.model_validate(value)


class Route(StrictModel):
    model_config = ConfigDict(frozen=True)
    primary_intent: Intent
    potential_fraud_error: bool
    human_requested: bool
    urgent: bool  # Missing flags are invalid, not implicitly False.

    @model_validator(mode='after')
    def fraud_intent_requires_signal(self):
        if self.primary_intent == 'FRAUD_ERROR_REPORT' and not self.potential_fraud_error:
            raise ValueError('Fraud/error primary intent requires its independent safety flag')
        return self


class Faults(StrictModel):
    """Mutable, assignment-validated simulator controls; never model-generated."""
    model_config = ConfigDict(validate_assignment=True)
    transaction_timeout: bool = False
    case_timeout: bool = False
    intake_timeout: bool = False
    intake_commit_then_timeout: bool = False
    case_commit_then_timeout: bool = False
    primary_queue_down: bool = False
    backup_queue_down: bool = False
    handoff_timeout: bool = False
    receiver_denied: bool = False
    receiver_fields: ReceiverFields = ('case_id', 'report_id')
    handoff_status_query: bool = False
    step_up_verified: bool = False


class TransactionData(StrictModel):
    transaction_id: Identifier
    posted_on: DateText
    merchant: Annotated[str, Field(min_length=1, max_length=300), AfterValidator(nonblank)]
    amount_cents: Annotated[int, Field(ge=-(2**63), le=2**63-1)]
    currency: Literal['USD']
    status: Literal['PENDING', 'POSTED', 'REVERSED', 'DECLINED']


class CaseData(StrictModel):
    case_id: Identifier
    case_type: Identifier
    status: Literal['OPEN', 'IN_REVIEW', 'WAITING_FOR_CUSTOMER', 'RESOLVED', 'CLOSED']
    created_at: Timestamp
    owner_queue: Literal['CUSTOMER_SUPPORT', 'FRAUD_OPERATIONS']


class ReadFailure(StrictModel):
    status: Literal['DENIED', 'UNKNOWN']
    reason_code: Identifier | None = None
    data: None = None  # Non-success reads cannot carry protected data.


class TransactionSuccess(StrictModel):
    status: Literal['OK']
    reason_code: Identifier | None = None
    data: TransactionData


class CaseReadSuccess(StrictModel):
    status: Literal['OK']
    reason_code: Identifier | None = None
    data: CaseData


class WriteFailure(StrictModel):
    status: Literal['DENIED', 'UNKNOWN', 'CONFLICT']
    reason_code: Identifier | None = None


class ConfirmationRequired(StrictModel):
    status: Literal['CONFIRMATION_REQUIRED']


class CapturedReport(StrictModel):
    status: Literal['OK']
    report_capture_status: Literal['CAPTURED']
    regulatory_notice_status: Literal['REVIEW_REQUIRED']
    reported_at: Timestamp
    verification_status: Literal['VERIFIED', 'PENDING']
    investigation_status: Literal['NOT_STARTED']
    customer_confirmation_status: Literal['UNCONFIRMED']
    event_id: ReportId
    replayed: bool


class CommittedCase(StrictModel):
    status: Literal['OK']
    case_status: Literal['OPEN']
    committed_at: Timestamp
    event_id: CaseEventId
    replayed: bool


class HandoffPayload(StrictModel):
    case_id: Identifier | None = None
    report_id: ReportId | None = None


class AcknowledgedHandoff(StrictModel):
    status: Literal['OK']
    handoff_status: Literal['ACKNOWLEDGED']
    queue: Literal['CUSTOMER_SUPPORT', 'FRAUD_OPERATIONS', 'FRAUD_BACKUP']
    alternate_route: bool
    payload: HandoffPayload
    event_id: HandoffId
    replayed: bool


class BlockedHandoff(StrictModel):
    status: Literal['DENIED']
    handoff_status: Literal['BLOCKED']
    reason_code: Identifier | None = None
    payload: HandoffPayload | None = None

    @model_validator(mode='after')
    def no_payload(self):
        if self.payload is not None and self.payload.model_dump(exclude_unset=True):
            raise ValueError('A blocked handoff cannot carry a payload')
        return self


class UnknownHandoff(StrictModel):
    status: Literal['UNKNOWN']
    handoff_status: Literal['UNAVAILABLE', 'DELIVERY_UNKNOWN']
    reason_code: Identifier | None = None
    payload: HandoffPayload | None = None

    @model_validator(mode='after')
    def no_unconfirmed_payload(self):
        if self.payload is not None and self.payload.model_dump(exclude_unset=True):
            raise ValueError('An unconfirmed handoff cannot expose a payload')
        return self


class HandoffConflict(StrictModel):
    status: Literal['CONFLICT']
    reason_code: Identifier


class PolicyChunk(StrictModel):
    doc_id: Identifier
    title: Text
    version: Identifier
    product: Literal['ALL', 'CHECKING', 'DEBIT_CHECKING']
    jurisdiction: Literal['US']
    effective_date: DateText
    expires_at: DateText | None
    approval_status: Literal['APPROVED_FOR_SYNTHETIC_TEST']
    chunk_id: Identifier
    section: Text
    text: Text
    token_count_approx: Annotated[int, Field(gt=0)]
    oversize_preserved: bool
    score: Annotated[float, Field(gt=0, allow_inf_nan=False)]


class RetrievedPolicies(StrictModel):
    status: Literal['OK']
    chunks: Annotated[list[PolicyChunk], Field(min_length=1, max_length=5)]


class MissingPolicies(StrictModel):
    status: Literal['NOT_FOUND', 'CONFLICT']
    chunks: Annotated[list[PolicyChunk], Field(max_length=0)]
    reason_code: Identifier | None = None


class Explanation(StrictModel):
    response: Annotated[str, Field(min_length=1, max_length=65536), AfterValidator(nonblank)]


TransactionResult = Annotated[Union[TransactionSuccess, ReadFailure], Field(discriminator='status')]
CaseReadResult = Annotated[Union[CaseReadSuccess, ReadFailure], Field(discriminator='status')]
ReportResult = Annotated[Union[CapturedReport, WriteFailure], Field(discriminator='status')]
CaseWriteResult = Annotated[Union[CommittedCase, WriteFailure, ConfirmationRequired], Field(discriminator='status')]
HandoffResult = Annotated[Union[AcknowledgedHandoff, BlockedHandoff, UnknownHandoff, HandoffConflict], Field(discriminator='status')]
PolicyResult = Annotated[Union[RetrievedPolicies, MissingPolicies], Field(discriminator='status')]

RESULT_ADAPTERS = {
    'transaction': TypeAdapter(TransactionResult),
    'case_read': TypeAdapter(CaseReadResult),
    'report': TypeAdapter(ReportResult),
    'case_write': TypeAdapter(CaseWriteResult),
    'handoff': TypeAdapter(HandoffResult),
    'policy': TypeAdapter(PolicyResult),
}


def validate_result(kind, value):
    """Preserve dictionary interfaces only after strict boundary validation."""
    return RESULT_ADAPTERS[kind].validate_python(value).model_dump(exclude_unset=True)


def validated_result(kind):
    def decorate(function):
        @wraps(function)
        def wrapper(self, request, *args, **kwargs):
            request = Request.model_validate(request)
            return validate_result(kind, function(self, request, *args, **kwargs))
        return wrapper
    return decorate


class ReportPayload(StrictModel):
    original_statement: Text
    reported_transaction_ids: Annotated[list[Identifier], Field(max_length=20)]


class CasePayload(StrictModel):
    statement: Text
    account_id: Identifier


class DeliveryPayload(StrictModel):
    payload: HandoffPayload
    queue: Literal['CUSTOMER_SUPPORT', 'FRAUD_OPERATIONS', 'FRAUD_BACKUP']


STORED_SUCCESS_MODELS = {'report': CapturedReport, 'case': CommittedCase, 'handoff': AcknowledgedHandoff}
PAYLOAD_MODELS = {'report': ReportPayload, 'case': CasePayload, 'handoff': DeliveryPayload}


def validate_stored_event(kind, result):
    # The event table is commit evidence, not a cache of uncertain tool responses.
    # Missing lookups return UNKNOWN outside this validator.
    return STORED_SUCCESS_MODELS[kind].model_validate(result).model_dump(exclude_unset=True)


@dataclass
class WorkflowState:
    """Graph-internal mutable state; its inputs cross validated boundaries."""
    request: Request
    route: Route | None = None
    report: dict = field(default_factory=dict)
    records: list[dict] = field(default_factory=list)
    policies: list[dict] = field(default_factory=list)
    handoff: dict = field(default_factory=dict)
    case: dict = field(default_factory=dict)
    tools: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    response_state: str = 'UNVERIFIED'
    response: str = ''
    model_context: dict = field(default_factory=dict)
    output_verified: bool = False
