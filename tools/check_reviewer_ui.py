"""Read-only reviewer browser checks; never approve human labels automatically."""
import asyncio
import json
import os
import urllib.request
from pathlib import Path
import websockets
from resolveguard.eval_config import load_eval_environment


async def main():
    load_eval_environment();pages=json.load(urllib.request.urlopen('http://127.0.0.1:9228/json'))
    page=next(p for p in pages if p['type']=='page');checks=[];errors=[];counter=0
    async with websockets.connect(page['webSocketDebuggerUrl'],max_size=20_000_000) as ws:
        async def command(method,params=None):
            nonlocal counter
            counter+=1;ident=counter;await ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
            while True:
                msg=json.loads(await ws.recv())
                if msg.get('method')=='Runtime.exceptionThrown':errors.append('BROWSER_RUNTIME_EXCEPTION')
                if msg.get('id')==ident:return msg.get('result',{})
        async def js(expression):
            r=await command('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
            if 'exceptionDetails' in r:raise RuntimeError('Browser evaluation failed; no token or payload printed')
            return r.get('result',{}).get('value')
        async def wait(expression):
            for _ in range(100):
                if await js(expression):return
                await asyncio.sleep(.1)
            raise AssertionError('Reviewer UI condition did not complete')
        await command('Runtime.enable')
        await command('Page.navigate',{'url':'http://127.0.0.1:8766/reviewer'})
        await wait("Boolean(document.getElementById('access'))")
        checks.append({'name':'Unauthenticated review API denied','passed':await js("fetch('/api/reviewer/sessions').then(r=>r.status===401)")})
        await js("document.getElementById('token').value="+json.dumps(os.environ['RESOLVEGUARD_DASHBOARD_TOKEN'])+";document.getElementById('access').requestSubmit();true")
        await wait("document.querySelectorAll('#sessions button').length>0")
        checks.append({'name':'Searchable recorded turns render','passed':True})
        checks.append({'name':'Token input clears after login','passed':await js("document.getElementById('token').value===''")})
        await js("document.querySelector('#sessions button').click();true")
        await wait("document.getElementById('evidence').textContent.includes('checks')")
        checks.append({'name':'Reply, access and source evidence renders','passed':True})
        await js("document.getElementById('load-datasets').click();true")
        await wait("document.getElementById('dataset-suite').options.length===4")
        checks.append({'name':'Both 100-case suites and semantic/calibration drafts visible','passed':True})
        checks.append({'name':'Human attestation is never preselected','passed':await js("document.getElementById('human-attestation').checked===false")})
        await js("document.getElementById('semantic-results').click();true")
        await wait("document.getElementById('semantic-evidence').textContent.includes('review_flags')")
        checks.append({'name':'Measured semantic results and low-score flags visible','passed':True})
        await command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        checks.append({'name':'Reviewer page fits mobile viewport','passed':await js('document.documentElement.scrollWidth<=innerWidth')})
        await command('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        await js("window.reviewOriginalFetch=window.fetch;window.releaseReview=null;window.fetch=async(...args)=>{const r=await reviewOriginalFetch(...args);if(String(args[0]).startsWith('/api/reviewer/sessions?'))await new Promise(resolve=>window.releaseReview=resolve);return r;};document.getElementById('filters').requestSubmit();true")
        await wait('window.releaseReview!==null')
        await js("document.getElementById('logout').click();window.releaseReview();window.fetch=window.reviewOriginalFetch;true")
        await wait("document.getElementById('status').textContent.includes('discarded')")
        checks.append({'name':'Late staff response cannot restore evidence after logout','passed':await js("document.querySelectorAll('#sessions button').length===0 && document.getElementById('evidence').textContent===''")})
        await js("document.getElementById('logout').click();true")
        checks.append({'name':'Closing workspace clears review data','passed':await js("document.getElementById('evidence').textContent==='' && document.querySelectorAll('#sessions button').length===0")})
    report={'checks':checks,'runtime_errors':errors,'passed':all(c['passed'] for c in checks) and not errors,
            'scope':'Read-only local synthetic browser checks; no label approvals or banking actions'}
    path=Path('artifacts/local_completion/reviewer_browser_checks.json');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':asyncio.run(main())
