import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from resolveguard.web import create_app


class ProductVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.client=TestClient(create_app(Path(self.temp.name)/'verification.sqlite3'));self.client.__enter__()
        self.client.post('/api/session',json={})
    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
    def ask(self,message,key,bank='BOW',**extra):
        return self.client.post('/api/chat',json={'message':message,'request_key':key,'bank_id':bank,**extra}).json()

    def test_unconfirmed_sidebar_hint_cannot_trigger_premature_terms(self):
        with patch('resolveguard.bow_knowledge.BowKnowledge.retrieve') as retrieval:
            result=self.ask('What is the monthly maintenance fee?','fee',product_id='BOW-CHK-002')
        retrieval.assert_not_called()
        self.assertEqual(result['response_state'],'CLARIFICATION_REQUIRED')
        self.assertNotIn('$',result['response']);self.assertEqual(result['source_details'],[])

    def test_checking_category_requires_tier_then_resumes_original_question(self):
        self.ask('What is the monthly maintenance fee?','fee')
        category=self.ask('Checking account','category')
        self.assertTrue(category['choose_product']);self.assertNotIn('$',category['response'])
        self.assertEqual(len(category['product_choices']),3)
        answer=self.ask('Plus Checking','tier')
        self.assertIn('$12.00',answer['response']);self.assertEqual(answer['selected_product_id'],'BOW-CHK-002')
        waiver=self.ask('What are the fee waiver rules?','waiver')
        self.assertIn('$2,000',waiver['response']);self.assertIn('$10,000',waiver['response'])
        self.assertNotIn('$1,500',waiver['response'])

    def test_multiple_product_topics_all_clarify_before_policy_terms(self):
        for i,message in enumerate(['What is the monthly fee?','What are the waiver rules?','What is the savings APY?',
                                    'What rewards are available?','What are the eligibility conditions?']):
            self.client.post('/api/public/reset',json={})
            result=self.ask(message,f'question-{i}')
            self.assertTrue(result['choose_product'],message)
            self.assertEqual(result['source_details'],[])

    def test_original_demo_also_clarifies_and_never_invents_balance_threshold(self):
        with patch('resolveguard.public_support._public_evidence_answer') as evidence:
            first=self.ask('What are the fee waiver rules?','waiver',bank='LEGACY_DEMO')
        evidence.assert_not_called();self.assertTrue(first['choose_product'])
        result=self.ask('Checking account','choice',bank='LEGACY_DEMO')
        self.assertIn('does not specify',result['response'])
        self.assertNotIn('$1,500',result['response']);self.assertNotIn('$1500',result['response'])

    def test_original_savings_product_does_not_borrow_checking_fee(self):
        self.ask('What is the monthly maintenance fee?','fee',bank='LEGACY_DEMO')
        answer=self.ask('Original demo savings account','choice',bank='LEGACY_DEMO')
        self.assertNotIn('$12',answer['response']);self.assertEqual(answer['source_details'],[])

    def test_confirmed_product_still_does_not_establish_personal_eligibility(self):
        result=self.ask('Do I qualify for the fee waiver for Plus Checking?','personal-eligibility')
        self.assertIn('account deposits or balances',result['response'])
        self.assertIn('does not check your personal eligibility',result['response'])
        references={s['reference'] for s in result['source_details']}
        self.assertTrue({'POL-BOW-PRIVACY-C02','POL-BOW-PRIVACY-C03'} <= references)
        self.assertFalse(result['execution_evidence']['personal_eligibility_checked'])
        self.assertEqual(result['cards'],[])

    def test_fee_answer_includes_correct_tier_waiver_conditions(self):
        answer=self.ask('What is the monthly maintenance fee for Everyday Checking?','complete-fee')
        self.assertIn('$6.00',answer['response'])
        self.assertIn('$750',answer['response']);self.assertIn('$1,500',answer['response'])
        self.assertNotIn('$2,000',answer['response']);self.assertNotIn('$10,000',answer['response'])
        self.assertFalse(answer['auth_required'])

    def test_unavailable_privacy_policy_does_not_generate_uncited_guidance(self):
        from resolveguard.bow_knowledge import BowKnowledge
        knowledge=BowKnowledge()
        retrieve=knowledge.retrieve
        def without_privacy(*args,**kwargs):
            return [c for c in retrieve(*args,**kwargs) if c['topic']!='data_privacy']
        with patch.object(knowledge,'retrieve',side_effect=without_privacy):
            answer=knowledge.answer('How can I waive my fee for Everyday Checking?','BOW-CHK-001','2026-10-31')
        self.assertNotIn('Never share',answer['response'])
        self.assertNotIn('requires secure sign-in',answer['response'])
        self.assertIn('does not check your personal eligibility',answer['response'])
        self.assertFalse(answer['execution_evidence']['private_records_accessed'])

    def test_new_conversation_requires_confirmation_again(self):
        self.ask('What is the fee for Everyday Checking?','explicit')
        self.client.post('/api/conversation/reset',json={})
        again=self.ask('What is the monthly fee?','fresh',product_id='BOW-CHK-001')
        self.assertTrue(again['choose_product']);self.assertNotIn('$6',again['response'])

    def test_specific_fee_features_do_not_borrow_monthly_account_rules(self):
        for i,message in enumerate(['What is the ATM fee for Plus Checking?',
                                    'What are the overdraft waiver rules for Plus Checking?',
                                    'What is the annual fee for Everyday Checking?']):
            result=self.ask(message,f'feature-{i}')
            self.assertNotIn('$12',result['response']);self.assertNotIn('$6',result['response'])
            self.assertNotIn('$2,000',result['response']);self.assertEqual(result['source_details'],[])

    def test_card_atm_answer_stays_conditional_without_inventing_a_charge(self):
        result=self.ask('What is the ATM fee for Whatever Debit?','atm')
        self.assertIn('charges may apply',result['response'])
        self.assertIn('No charge amount',result['response'])
        self.assertNotIn('$3.50',result['response'])

    def test_original_demo_atm_fee_does_not_become_monthly_fee(self):
        self.ask('What is the ATM fee?','atm',bank='LEGACY_DEMO')
        result=self.ask('Checking account','choice',bank='LEGACY_DEMO')
        self.assertIn('$3.50',result['response']);self.assertNotIn('$12',result['response'])
