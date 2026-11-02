"""Mock adapter only. It never reads case IDs, expected labels or evaluator data."""
import re
from .contracts import Route
from .intake_signals import asserted_payment_error


class MockModel:
    prompt_version = 'mock-router-error-intake-v2'
    name = 'mock-rules-v0'
    is_mock = True

    def classify(self, message):
        t = message.lower()
        fraud = asserted_payment_error(message) or any(p in t for p in ('did not authorize', 'didn\'t authorize', 'unauthorized',
                                    'do not recognize', 'don\'t recognize', 'not recognize',
                                    'stolen', 'suspicious', 'amount is wrong', 'wrong amount',
                                    'charged twice', 'two different debit', 'fraud report'))
        human = any(p in t for p in ('human', 'speak to', 'talk to', 'support agent',
                                    'receiving agent', 'different role', 'transfer this case'))
        urgent = any(p in t for p in ('stolen', 'right now', 'urgent', 'signing in', 'freeze'))
        if urgent and any(p in t for p in ('card', 'account', 'fraud')):
            fraud = True
        if fraud:
            intent = 'FRAUD_ERROR_REPORT'
        elif 'one-time code' in t or 'otp' in t:
            intent = 'OTHER_OR_UNCLEAR'
        elif any(p in t for p in ('transfer money', 'send money', 'reset my password', 'issue a refund')):
            intent = 'UNSUPPORTED_REQUEST'
        elif human:
            intent = 'HUMAN_REQUEST'
        elif any(p in t for p in ('open a case', 'create a case', 'submit a case', 'support case',
                                  'submit my request', 'submit the case')):
            intent = 'SUPPORT_CASE_REQUEST'
        elif 'case' in t or 'claim status' in t or 'handoff' in t or 'dispute status' in t:
            intent = 'CASE_STATUS'
        elif re.search(r'\b(compare|comparison|differences?|versus|vs|differ|better|cheaper)\b',t) and not re.search(r'\b(my|our|mine|this payment|this transaction)\b',t):
            intent = 'POLICY_LOOKUP'
        elif any(p in t for p in ('policy', 'rules', 'terms', 'how do', 'how can', 'what is', 'what are')):
            intent = 'POLICY_LOOKUP'
        elif 'fee' in t:
            intent = 'FEE_INQUIRY'
        elif any(p in t for p in ('transaction', 'debit', 'balance', 'payment', 'charge', 'activity', 'history')):
            intent = 'TRANSACTION_INQUIRY'
        else:
            intent = 'OTHER_OR_UNCLEAR'
        return Route(primary_intent=intent, potential_fraud_error=fraud,
                     human_requested=human, urgent=urgent).model_dump()

    def explain(self, context, approved_response):
        # Mirrors the future adapter contract without pretending to be a real LLM.
        return approved_response


class ScriptedMockModel(MockModel):
    """Fault-injection adapter for tests; never used to generate evaluation truth."""
    name = 'scripted-mock-test-only'

    def __init__(self, route=None, response=None, error=False):
        self.route_override = route
        self.response_override = response
        self.error = error
        self.seen_contexts = []

    def classify(self, message):
        if self.error:
            raise RuntimeError('Injected model failure')
        return self.route_override if self.route_override is not None else super().classify(message)

    def explain(self, context, approved_response):
        self.seen_contexts.append(context)
        return self.response_override if self.response_override is not None else approved_response


class TunedMockModel(MockModel):
    """Four isolated rule changes for teaching measured iteration, not GLM tuning."""
    def __init__(self,stage=0):
        if stage not in range(5):raise ValueError('Mock stage must be 0 through 4')
        self.stage=stage;self.name=f'mock-rules-v{stage}';self.prompt_version=self.name+'-local-risk-coverage-v3'

    def classify(self,message):
        result=super().classify(message);text=message.lower()
        if self.stage>=1 and any(s in text for s in ('that was not me','withdrawal was not me','was used','not my purchase')):
            result.update(primary_intent='FRAUD_ERROR_REPORT',potential_fraud_error=True)
        if self.stage>=2 and any(s in text for s in ('real person','support person','fraud support','transfer me','connect me to a person')):
            result['human_requested']=True
            if not result['potential_fraud_error'] and result['primary_intent'] not in {'CASE_STATUS','SUPPORT_CASE_REQUEST','TRANSACTION_INQUIRY','FEE_INQUIRY'}:result['primary_intent']='HUMAN_REQUEST'
        if self.stage>=3 and not result['potential_fraud_error'] and any(s in text for s in ('create a ticket','clicked submit twice','submit again')):
            result['primary_intent']='SUPPORT_CASE_REQUEST'
        if self.stage>=4 and not result['potential_fraud_error'] and 'policy' not in text and any(s in text for s in ('full balance','transaction history')):
            result['primary_intent']='TRANSACTION_INQUIRY'
        if self.stage>=4:
            if not result['potential_fraud_error'] and re.search(r'\b(this did not help|that did not help|still need help|still not fixed|still confused)\b',text):
                result.update(primary_intent='HUMAN_REQUEST',human_requested=True)
            if not result['potential_fraud_error']:
                if re.search(r'\b(?:service fees|overdraft fee|statement fee)\b',text) and re.search(r'\b(?:my|appeared|charged|i see)\b',text):result['primary_intent']='FEE_INQUIRY'
                if any(s in text for s in ('submitted an issue','pressed create case again')):result['primary_intent']='SUPPORT_CASE_REQUEST'
                if any(s in text for s in ('card purchases','all accounts','account details','full debit card number','acc-b data','records outside','disputed charges')):result['primary_intent']='TRANSACTION_INQUIRY'
                if any(s in text for s in ('authorization was revoked','case after','case attachments','her checking account case','different logged-in user','new chat after another user','error notice','reported an error yesterday')):result['primary_intent']='CASE_STATUS'
                if 'hidden refund tool' in text:result['primary_intent']='UNSUPPORTED_REQUEST'
                if 'write a letter' in text and 'report' in text:result['primary_intent']='POLICY_LOOKUP'
                if 'help-center page' in text:result['primary_intent']='POLICY_LOOKUP'
            if text.startswith(('did you block','have you blocked')):result.update(primary_intent='CASE_STATUS',potential_fraud_error=False)
        return Route.model_validate(result).model_dump()
