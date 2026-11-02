"""Reconstruct controlled public answers and check exact displayed financial facts.

This is an enforceable template contract, not an uncalibrated model opinion.
"""
import re
from decimal import Decimal


def financial_facts(text):
    return {('USD', str(Decimal(value.replace(',', '')).normalize())) for value in re.findall(r'\$\s*([\d,]+(?:\.\d+)?)', text)} | {
        ('PERCENT', str(Decimal(value).normalize())) for value in re.findall(r'(?<!\w)(\d+(?:\.\d+)?)\s*%', text)}


def verify_answer(candidate, bank_id, as_of, message='', authorized_records=()):
    """Return reason codes; only backend callers provide authorized records."""
    if candidate.get('generation', {}).get('outcome') == 'APPROVED':
        from .reply_generation import canonical_candidate
        try:
            candidate = canonical_candidate(candidate)
        except (ValueError, KeyError, TypeError):
            return ['GENERATED_PRESENTATION_INVALID']
    response = candidate.get('response', '')
    reasons = []
    if candidate.get('generation',{}).get('data_scope')=='PRIVATE_READ':
        from .presentation import customer_copy
        if not authorized_records or response!=customer_copy({'records':list(authorized_records)}):
            reasons.append('PRIVATE_REPLY_DIFFERS_FROM_AUTHORIZED_RECORDS')
    if candidate.get('response_state') not in {'CLARIFICATION_REQUIRED'}:
        from .presentation import customer_copy
        for record in authorized_records:
            if record.get('kind')=='transaction' and ('The payment to' in response or financial_facts(response)):
                if customer_copy({'records':[record]}) not in response:
                    reasons.append('TRANSACTION_NARRATIVE_DIFFERS_FROM_RECORD')
    source_text = '\n'.join(s.get('summary', '') for s in candidate.get('source_details', []))
    evidence = source_text + '\n' + '\n'.join(str(r) for r in authorized_records)
    for card in candidate.get('cards', []):
        evidence += '\n' + card.get('amount', '')
    # Numeric checking is supplementary; the public template comparison below
    # also catches reversed conditions and a different product's correct number.
    if financial_facts(response) - financial_facts(evidence):
        # Some public amounts are authoritative catalog fields, not chunk prose.
        if bank_id == 'BOW':
            from .bow_knowledge import BowKnowledge
            k = BowKnowledge()
            ids = {s.get('product_id') for s in candidate.get('source_details', [])}
            for pid in ids:
                if pid in k.product_map:
                    evidence += '\n' + k.product_summary(k.product_map[pid])
                    from .presentation import format_money
                    evidence += '\n' + format_money(k.product_map[pid]['monthly_fee_cents_or_annual_card_fee_cents'])
        if financial_facts(response) - financial_facts(evidence):
            reasons.append('UNSUPPORTED_FINANCIAL_FACT')
    if candidate.get('response_state') == 'PUBLIC_GUIDANCE' and candidate.get('source_details'):
        question = candidate.get('answered_question') or message
        if bank_id == 'BOW':
            from .bow_knowledge import BowKnowledge
            from .comparisons import compare_products
            k = BowKnowledge()
            topic = candidate.get('question_topic')
            if not question:
                question = {'FEE': 'What is the monthly maintenance fee?', 'WAIVER': 'What are the fee waiver rules?',
                            'APY': 'What is the savings APY?', 'REWARDS': 'What are the rewards?',
                            'ELIGIBILITY': 'What is the eligibility?', 'FEATURES': 'What are the features?'}.get(topic, '')
            plan = candidate.get('comparison_plan', {})
            if plan.get('kind') == 'PRODUCTS':
                expected = compare_products(k, question, as_of, plan.get('product_ids'))
            else:
                expected = k.answer(question, candidate.get('selected_product_id'), as_of)
            if expected.get('response') != response:
                reasons.append('ANSWER_DIFFERS_FROM_APPROVED_TEMPLATE')
        elif question and candidate.get('selected_product_id'):
            from .public_support import LegacyPublicKnowledge
            expected, _ = LegacyPublicKnowledge().converse(question, None, as_of,
                {'product_id': candidate['selected_product_id'], 'product_confirmed': True})
            if expected.get('response') != response:
                reasons.append('ANSWER_DIFFERS_FROM_APPROVED_TEMPLATE')
    return reasons
