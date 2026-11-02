import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from resolveguard.nebius import NebiusModel,ProviderUnavailable
from resolveguard.backend import Backend
from resolveguard.storage import Store
from resolveguard.contracts import Request
from resolveguard.workflow import Workflow


class NebiusAdapterTests(unittest.TestCase):
    def test_disabled_adapter_never_opens_socket_even_with_key(self):
        with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')) as connect:
            with self.assertRaises(ProviderUnavailable):NebiusModel(api_key='test-key').classify('hello')
        connect.assert_not_called()

    def test_schema_usage_and_secret_minimization_with_fake_transport(self):
        captured=[]
        route={'primary_intent':'FRAUD_ERROR_REPORT','potential_fraud_error':True,'human_requested':False,'urgent':False}
        def respond(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(route)}}],
                                           'usage':{'prompt_tokens':100,'completion_tokens':20}})
        model=NebiusModel(enabled=True,api_key='test-key',transport=httpx.MockTransport(respond))
        with tempfile.TemporaryDirectory() as temp:
            output=Workflow(Backend(Store(Path(temp)/'x.sqlite3')),model).run(Request(
                message='I did not authorize this debit. My OTP is 123456',request_key='x'))
        self.assertEqual(output['input_tokens'],100)
        self.assertEqual(output['output_tokens'],20)
        self.assertEqual(output['execution_mode'],'NEBIUS')
        self.assertNotIn('123456',json.dumps(captured))
        self.assertNotIn('test-key',json.dumps(output))
        self.assertEqual(captured[0]['response_format']['type'],'json_schema')
        self.assertEqual(len(captured),1)

    def test_provider_error_or_bad_schema_does_not_discard_report(self):
        for status,body in [(500,{'error':'private provider body'}),(200,{'choices':[]} )]:
            transport=httpx.MockTransport(lambda request:httpx.Response(status,json=body))
            model=NebiusModel(enabled=True,api_key='test-key',transport=transport)
            with tempfile.TemporaryDirectory() as temp:
                output=Workflow(Backend(Store(Path(temp)/'x.sqlite3')),model).run(Request(
                    message='I did not authorize this debit',request_key='x'))
            self.assertEqual(output['report']['report_capture_status'],'CAPTURED')
            self.assertNotIn('private provider body',json.dumps(output))


if __name__=='__main__':unittest.main()
