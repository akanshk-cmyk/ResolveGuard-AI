import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from resolveguard.bow_knowledge import BowKnowledge
from resolveguard.model import TunedMockModel
from resolveguard.web import create_app


class ComparisonTests(unittest.TestCase):
    def setUp(self):self.k=BowKnowledge()

    def test_unequal_length_names_are_both_retained(self):
        result=self.k.answer('Compare Everyday Checking and Plus Checking monthly fees',None,'2026-10-31')
        plan=result['comparison_plan']
        self.assertEqual(plan['product_ids'],['BOW-CHK-001','BOW-CHK-002'])
        self.assertEqual(plan['decision'],'SUPPORTED')
        self.assertIn('$6.00',result['response']);self.assertIn('$12.00',result['response'])
        for pid,refs in plan['evidence_by_subject'].items():
            self.assertTrue(refs)
            for ref in refs:
                source=next(s for s in result['source_details'] if s['reference']==ref)
                self.assertEqual(source['product_id'],pid);self.assertEqual(source['bank_id'],'BOW')

    def test_mixed_categories_and_bare_tier_disambiguation(self):
        result=self.k.answer('Compare Premier Checking versus Starter Savings',None,'2026-10-31')
        self.assertEqual(len(result['comparison_plan']['product_ids']),2)
        short=self.k.answer('Compare Everyday and Plus checking',None,'2026-10-31')
        self.assertEqual(short['comparison_plan']['decision'],'SUPPORTED')
        ambiguous=self.k.answer('Compare Plus and Premier',None,'2026-10-31')
        self.assertTrue(ambiguous['choose_product']);self.assertEqual(ambiguous['source_details'],[])

    def test_missing_side_never_uses_other_products_terms(self):
        original=self.k.retrieve
        def wrong_side(bank,pid,*args,**kwargs):
            return original(bank,'BOW-CHK-001',*args,**kwargs) if pid=='BOW-CHK-002' else original(bank,pid,*args,**kwargs)
        with patch.object(self.k,'retrieve',side_effect=wrong_side):
            result=self.k.answer('Compare Everyday Checking and Plus Checking fees',None,'2026-10-31')
        self.assertEqual(result['comparison_plan']['decision'],'PARTIAL_EVIDENCE')
        self.assertEqual(result['comparison_plan']['evidence_by_subject']['BOW-CHK-002'],[])
        self.assertNotIn('$12',result['response'])

    def test_expired_or_forged_sources_fail_closed(self):
        expired=self.k.answer('Compare Everyday Checking vs Plus Checking fees',None,'2027-01-01')
        self.assertEqual(expired['comparison_plan']['decision'],'MISSING_EVIDENCE')
        self.assertEqual(expired['source_details'],[]);self.assertNotIn('$',expired['response'])
        forged=copy.deepcopy(next(c for c in self.k.chunks if c['product_id']=='BOW-CHK-001'))
        forged['chunk_text']='A made-up $9999 fee.'
        with patch.object(self.k,'retrieve',return_value=[forged]):
            result=self.k.answer('Compare Everyday Checking vs Plus Checking fees',None,'2026-10-31')
        self.assertNotIn('9999',result['response']);self.assertEqual(result['source_details'],[])

    def test_unsupported_feature_and_wrong_fee_period_never_borrow_monthly_fee(self):
        for question in ('Compare ATM fees for Everyday Checking and Plus Checking',
                         'Compare annual fees for Everyday Checking versus Plus Checking'):
            result=self.k.answer(question,None,'2026-10-31')
            self.assertEqual(result['source_details'],[]);self.assertNotIn('$6',result['response'])

    def test_bow_status_gap_is_explicit_without_other_bank_evidence(self):
        result=self.k.answer('What is the difference between a pending and posted payment?',None,'2026-10-31')
        self.assertEqual(result['comparison_plan']['kind'],'PAYMENT_STATUS')
        self.assertEqual(result['comparison_plan']['decision'],'MISSING_EVIDENCE')
        self.assertNotIn('fees, fee waivers',result['response'])
        self.assertEqual(result['source_details'],[]);self.assertFalse(result['auth_required'])

    def test_status_definitions_can_only_come_from_eligible_bow_glossary(self):
        chunks=[]
        for index,text in enumerate(('Pending: test authorization not finalized.','Posted: test payment processing completed.')):
            chunk=copy.deepcopy(next(c for c in self.k.chunks if c['product_id']=='ALL'))
            parent=copy.deepcopy(self.k.policy_map[chunk['doc_id']])
            chunk.update(chunk_id=f'POL-BOW-TEST-STATUS-C{index}',doc_id=f'POL-BOW-TEST-STATUS-{index}',
                         topic='payment_status',chunk_text=text,sha256_text=hashlib.sha256(text.encode()).hexdigest())
            parent.update(doc_id=chunk['doc_id'],topic='payment_status',policy_text=text)
            self.k.chunk_map[chunk['chunk_id']]=chunk;self.k.policy_map[chunk['doc_id']]=parent
            chunks.append(chunk)
        with patch.object(self.k,'retrieve',return_value=chunks):
            result=self.k.answer('Compare pending vs posted payments',None,'2026-10-31')
        self.assertEqual(result['comparison_plan']['decision'],'SUPPORTED')
        self.assertIn('test authorization',result['response']);self.assertEqual(len(result['source_details']),2)

    def test_foreign_bank_comparison_never_uses_bow_terms(self):
        result=self.k.answer('Compare Plus Checking with Chase checking',None,'2026-10-31')
        self.assertEqual(result['source_details'],[]);self.assertNotIn('$12',result['response'])

    def test_classifier_preserves_fraud_priority(self):
        model=TunedMockModel(4)
        self.assertEqual(model.classify('Compare pending vs posted payments')['primary_intent'],'POLICY_LOOKUP')
        self.assertTrue(model.classify('Compare these payments: I was charged twice')['potential_fraud_error'])


class ComparisonConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.client=TestClient(create_app(Path(self.temp.name)/'chat.sqlite3'))
        self.client.__enter__();self.client.post('/api/session',json={})
    def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
    def ask(self,text,key,bank='BOW',**kwargs):
        response=self.client.post('/api/chat',json={'message':text,'request_key':key,'bank_id':bank,**kwargs})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()
    def test_guest_comparison_and_missing_subject_resume(self):
        first=self.ask('Compare Everyday Checking fees','start')
        self.assertTrue(first['choose_product']);self.assertEqual(first['source_details'],[])
        answer=self.ask('Plus Checking','reply')
        self.assertFalse(answer['auth_required']);self.assertEqual(answer['cards'],[])
        self.assertEqual(answer['comparison_plan']['decision'],'SUPPORTED')
        self.assertIn('$6.00',answer['response']);self.assertIn('$12.00',answer['response'])
    def test_category_and_two_product_replies(self):
        self.ask('Compare products','start')
        choices=self.ask('Checking account','category')
        self.assertEqual(len(choices['product_choices']),3)
        one=self.ask('Everyday Checking','one');self.assertTrue(one['choose_product'])
        two=self.ask('Plus Checking','two');self.assertEqual(two['comparison_plan']['decision'],'SUPPORTED')
    def test_new_question_interrupts_pending_comparison(self):
        self.ask('Compare Everyday Checking','start')
        answer=self.ask('What is the savings APY for Starter Savings?','new-topic')
        self.assertIn('2.00%',answer['response']);self.assertNotIn('comparison_plan',answer)
    def test_status_definition_is_public_but_personal_status_is_protected(self):
        answer=self.ask('What is the difference between a pending and posted payment?','general')
        self.assertFalse(answer['auth_required']);self.assertEqual(answer['comparison_plan']['kind'],'PAYMENT_STATUS')
        private=self.ask('Compare my pending and posted payments','private')
        self.assertTrue(private['auth_required']);self.assertEqual(private['cards'],[])
    def test_legacy_status_uses_legacy_source_only(self):
        answer=self.ask('Explain the difference between pending and posted payments','legacy',bank='LEGACY_DEMO')
        self.assertFalse(answer['auth_required'])
        self.assertTrue(any(s['reference'].startswith('POL-TRAN-001:') for s in answer['source_details']))


if __name__=='__main__':unittest.main()
