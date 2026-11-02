import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolveguard_tools import FixtureBank,KNOWLEDGE_BASES,search_kb_offline
class BankToolTests(unittest.TestCase):
 def setUp(self):self.b=FixtureBank()
 def test_own_transaction(self):self.assertEqual(self.b.get_transaction('SESS-001','TXN-001-01')['status'],'OK')
 def test_cross_account(self):self.assertEqual(self.b.get_transaction('SESS-001','TXN-002-01')['status'],'DENIED')
 def test_cross_case(self):self.assertEqual(self.b.get_case_status('SESS-001','CASE-002')['status'],'DENIED')
 def test_expired(self):self.assertEqual(self.b.get_transaction('SESS-EXPIRED','TXN-001-01')['status'],'DENIED')
 def test_revoked(self):self.assertEqual(self.b.get_transaction('SESS-REVOKED','TXN-001-01')['status'],'DENIED')
 def test_representative_limited(self):
  self.assertEqual(self.b.get_case_status('SESS-REP','CASE-002')['status'],'OK')
  self.assertEqual(self.b.get_transaction('SESS-REP','TXN-002-01')['status'],'DENIED')
 def test_representative_revoked(self):self.assertEqual(self.b.get_case_status('SESS-REP','CASE-003')['status'],'DENIED')
 def test_agent_service(self):self.assertEqual(self.b.get_transaction('SESS-001','TXN-001-01',service_id='unknown')['status'],'DENIED')
 def test_report_preserved_without_legal_claim(self):
  r=self.b.record_error_report('SESS-ANON','REPORT-001','I did not authorize this debit')
  self.assertEqual(r['data']['regulatory_notice_status'],'REVIEW_REQUIRED')
  self.assertEqual(self.b.record_error_report('SESS-ANON','REPORT-001','Retry')['reason_code'],'ALREADY_CAPTURED')
 def test_report_outage(self):self.assertEqual(FixtureBank(outages=['record_error_report']).record_error_report('SESS-ANON','R-2','Unknown charge')['status'],'UNKNOWN')
 def test_handoff_denied(self):self.assertEqual(self.b.handoff_to_human('SESS-001','CASE-002','CUSTOMER_SUPPORT')['status'],'DENIED')
 def test_handoff_outage(self):self.assertEqual(FixtureBank(outages=['handoff_to_human']).handoff_to_human('SESS-001','CASE-001','CUSTOMER_SUPPORT')['status'],'UNKNOWN')
 def test_kb(self):self.assertGreater(len(KNOWLEDGE_BASES),5);self.assertTrue(search_kb_offline('search_fee_policies','monthly fee',product='CHECKING'))
if __name__=='__main__':unittest.main()
