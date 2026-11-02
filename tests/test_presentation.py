import unittest
from resolveguard.presentation import customer_copy


class PresentationTests(unittest.TestCase):
    def test_money_preserves_integer_boundaries_and_does_not_guess_currency(self):
        from resolveguard.presentation import format_money
        self.assertEqual(format_money(2**63-1),'$92,233,720,368,547,758.07 USD')
        self.assertEqual(format_money(-(2**63)),'-$92,233,720,368,547,758.08 USD')
        self.assertEqual(format_money(1),'$0.01 USD')
        self.assertEqual(format_money(0),'$0.00 USD')
        with self.assertRaises(ValueError):format_money(100,'JPY')
        with self.assertRaises(ValueError):format_money(True)

    def test_saved_report_does_not_imply_support_delivery_or_card_block(self):
        text = customer_copy({'report': {'status': 'OK', 'event_id': 'REPORT-1'},
                              'handoff': {'handoff_status': 'UNAVAILABLE'}})
        self.assertIn('Your report is saved', text)
        self.assertIn('does not block your card', text)
        self.assertIn('could not connect', text)
        self.assertNotIn('team has received', text)

    def test_unknown_report_and_delivery_do_not_claim_success(self):
        text = customer_copy({'report': {'status': 'UNKNOWN'},
                              'handoff': {'handoff_status': 'UNKNOWN'}})
        self.assertIn('could not confirm that your report was saved', text)
        self.assertIn('could not confirm that your request reached', text)
        self.assertNotIn('Your report is saved', text)

    def test_delivery_does_not_imply_person_is_reviewing(self):
        text = customer_copy({'handoff': {'handoff_status': 'ACKNOWLEDGED'}})
        self.assertIn('does not mean a person has started reviewing', text)
        self.assertNotIn('ACKNOWLEDGED', text)

    def test_denied_access_does_not_render_stale_records(self):
        text = customer_copy({'response_state': 'ACCESS_DENIED', 'records': [
            {'kind': 'transaction', 'merchant': 'PRIVATE'}]})
        self.assertNotIn('PRIVATE', text)

    def test_closed_case_is_not_described_as_resolved(self):
        text = customer_copy({'records': [{'kind': 'case', 'case_id': 'CASE-1', 'status': 'CLOSED'}]})
        self.assertIn('closed', text)
        self.assertNotIn('resolved', text)
