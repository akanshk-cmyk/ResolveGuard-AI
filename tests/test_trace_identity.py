import unittest
from uuid import UUID
from resolveguard.telemetry import Trace,sanitize


class TraceIdentityTests(unittest.TestCase):
    def test_numeric_uuid_segments_do_not_break_trace_identity(self):
        trace=Trace();trace.id='12345678-1234-4234-9234-123456789012'
        with trace.span('test') as row:row['id']='abcdef12-1234-4234-9234-123456789012'
        value=trace.export()
        self.assertEqual(str(UUID(value['trace_id'])),trace.id)
        self.assertEqual(str(UUID(value['spans'][0]['id'])),row['id'])

    def test_uuid_identity_exception_does_not_reveal_account_or_card_fields(self):
        value=sanitize({'account_id':'12345678-1234-4234-9234-123456789012','message':'Card 4111 1111 1111 1111'})
        self.assertEqual(value['account_id'],'[REDACTED]')
        self.assertNotIn('4111',value['message'])
