"""Opt-in classification adapter. Construction is inert; tests use MockTransport."""
import json
import os
from pathlib import Path
import httpx
from .contracts import Route
from .telemetry import sanitize
from .configuration import DEFAULT_CHAT_MODEL, NEBIUS_CHAT_ENDPOINT


class ProviderUnavailable(RuntimeError):
    pass


class NebiusModel:
    name=DEFAULT_CHAT_MODEL
    prompt_version='bank-router-v4-security'
    is_mock=False

    def __init__(self,*,enabled=False,api_key=None,transport=None,timeout=20):
        self.enabled=enabled;self._key=api_key;self._transport=transport;self.timeout=timeout
        self.usage=[]

    def classify(self,message):
        if not self.enabled:
            raise ProviderUnavailable('Provider calls are disabled')
        key=self._key or os.environ.get('NEBIUS_API_KEY')
        if not key:raise ProviderUnavailable('NEBIUS_API_KEY is not configured')
        prompt=(Path(__file__).resolve().parents[1]/'prompts/router_v4.txt').read_text(encoding='utf-8-sig')
        payload={'model':self.name,'temperature':0,'max_tokens':512,
                 'messages':[{'role':'system','content':prompt},{'role':'user','content':sanitize(message)}],
                 'response_format':{'type':'json_schema','json_schema':{
                     'name':'resolveguard_route','strict':True,'schema':Route.model_json_schema()}}}
        try:
            with httpx.Client(transport=self._transport,timeout=self.timeout,follow_redirects=False) as client:
                response=client.post(NEBIUS_CHAT_ENDPOINT,
                                     headers={'Authorization':'Bearer '+key},json=payload)
            if response.status_code!=200:
                raise ProviderUnavailable('Provider request failed with HTTP '+str(response.status_code))
            body=response.json()
            usage=body.get('usage',{})
            a,b=usage.get('prompt_tokens'),usage.get('completion_tokens')
            if type(a) is int and type(b) is int and a>=0 and b>=0:
                self.usage.append({'input_tokens':a,'output_tokens':b,
                                   'estimated_cost_usd':(a*.15+b*.50)/1_000_000,
                                   'price_basis':'Published list-rate assumption as of 2026-10-30; not an invoice'})
            choice=body['choices'][0]
            if choice.get('finish_reason')!='stop' or choice['message'].get('refusal'):
                raise ProviderUnavailable('Provider did not return a completed routing decision')
            return Route.model_validate_json(choice['message']['content']).model_dump()
        except ProviderUnavailable:
            raise
        except Exception:
            # Provider bodies, credentials and malformed model text never become logs.
            raise ProviderUnavailable('Provider response was unavailable or invalid') from None

    def explain(self,context,approved_response):
        # First integration deliberately limits the model to classification.
        # Important action claims remain deterministic and evidence-backed.
        return approved_response
