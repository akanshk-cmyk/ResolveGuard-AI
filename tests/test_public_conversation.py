import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from resolveguard.web import create_app


class PublicConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'public.sqlite3'
        self.client=TestClient(create_app(self.path));self.client.__enter__();self.client.post('/api/session',json={})
    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
    def ask(self,message,key,**extra):
        return self.client.post('/api/chat',json={'message':message,'request_key':key,'bank_id':'BOW',**extra})

    def test_fee_and_waiver_questions_have_different_focused_answers(self):
        fee=self.ask('What is the monthly maintenance fee for Plus Checking?','fee',product_id='BOW-CHK-002').json()
        waiver=self.ask('What are the fee waiver rules?','waiver',product_id='BOW-CHK-002').json()
        self.assertIn('$12.00',fee['response']);self.assertIn('$2,000',fee['response'])
        self.assertIn('$10,000',fee['response'])
        self.assertIn('$2,000',waiver['response']);self.assertIn('$10,000',waiver['response'])
        self.assertNotIn('cashback',fee['response']);self.assertNotIn('cashback',waiver['response'])
        self.assertNotEqual(fee['response'],waiver['response'])

    def test_savings_question_overrides_stale_checking_selection_and_offers_three_choices(self):
        result=self.ask('What is the current savings interest rate?','rates',product_id='BOW-CHK-002').json()
        self.assertIn('Which savings account',result['response'])
        self.assertEqual({p['product_id'] for p in result['product_choices']},{'BOW-SAV-001','BOW-SAV-002','BOW-SAV-003'})
        self.assertFalse(result['auth_required']);self.assertIsNone(result['selected_product_id'])

    def test_typed_short_product_reply_answers_original_savings_question(self):
        self.ask('What is the current savings interest rate?','question',product_id='BOW-CHK-002')
        result=self.ask('Starter Savings','choice').json()
        self.assertIn('2.00%',result['response'])
        self.assertEqual(result['answered_question'],'What is the current savings interest rate?')
        self.assertEqual(result['selected_product_id'],'BOW-SAV-001')
        self.assertNotIn('monthly maintenance',result['response'])

    def test_product_button_payload_resumes_question_and_retry_is_stable(self):
        self.ask('What is the savings APY?','question')
        choice={'product_id':'BOW-SAV-002'}
        first=self.ask('Whatever High-Five Savings','choice',**choice).json()
        retry=self.ask('Whatever High-Five Savings','choice',**choice).json()
        self.assertEqual(first,retry);self.assertIn('3.50%',first['response'])
        self.assertEqual(self.ask('Starter Savings','choice').status_code,409)

    def test_ordinal_reply_and_followup_fee_keep_the_selected_savings_product(self):
        self.ask('What is the savings APY?','question')
        selected=self.ask('the first one'.removeprefix('the '),'first').json()
        self.assertIn('2.00%',selected['response'])
        fee=self.ask('And the monthly fee?','followup').json()
        self.assertIn('$0.00',fee['response']);self.assertIn('Starter Savings',fee['response'])

    def test_explicit_product_in_chat_overrides_sidebar_without_cross_product_blending(self):
        result=self.ask('What is the monthly fee for Everyday Checking?','explicit',product_id='BOW-CHK-002').json()
        self.assertIn('$6.00',result['response']);self.assertNotIn('$12.00',result['response'])
        self.assertEqual(result['selected_product_id'],'BOW-CHK-001')

    def test_public_product_choice_with_stale_payment_selection_does_not_access_account(self):
        self.ask('What is the savings APY?','question')
        result=self.ask('Starter Savings','choice',transaction_ids=['BOW-TXN-002-01']).json()
        self.assertFalse(result['auth_required']);self.assertEqual(result['cards'],[])
        self.assertIn('2.00%',result['response'])

    def test_public_context_is_browser_bound_and_survives_restart(self):
        self.ask('What is the savings APY?','question')
        with TestClient(create_app(self.path)) as restarted:
            restarted.cookies.update(self.client.cookies)
            result=restarted.post('/api/chat',json={'message':'Starter','request_key':'reply','bank_id':'BOW'}).json()
            self.assertIn('2.00%',result['response'])
        with TestClient(self.client.app) as other:
            other.post('/api/session',json={})
            result=other.post('/api/chat',json={'message':'What is the monthly fee?','request_key':'other','bank_id':'BOW'}).json()
            self.assertTrue(result['choose_product'])

    def test_new_question_replaces_pending_clarification_and_reset_clears_product(self):
        self.ask('What is the savings APY?','question')
        changed=self.ask('What are the checking fee waiver rules?','change').json()
        self.assertTrue(all(p['product_id'].startswith('BOW-CHK') for p in changed['product_choices']))
        reply=self.ask('Plus Checking','choice').json()
        self.assertIn('$2,000',reply['response']);self.assertNotIn('APY',reply['response'])
        self.client.post('/api/conversation/reset',json={})
        self.assertTrue(self.ask('What is the monthly fee?','after-reset').json()['choose_product'])

    def test_private_request_does_not_consume_public_choice_or_skip_sign_in(self):
        self.ask('What is the savings APY?','question')
        private=self.ask('Show my recent transactions','private').json()
        self.assertTrue(private['auth_required']);self.assertEqual(private['cards'],[])

    def test_unrelated_question_does_not_return_an_account_summary(self):
        result=self.ask('What is the weather tomorrow?','unrelated',product_id='BOW-CHK-002').json()
        self.assertNotIn('$12',result['response']);self.assertEqual(result['source_details'],[])
