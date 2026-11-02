"""Check clean startup/reset in the existing local browser; no paid model calls."""
import asyncio
import base64
import json
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

import websockets


async def main():
    pages=json.load(urllib.request.urlopen('http://127.0.0.1:9228/json'))
    old_page=next(p for p in pages if p['type']=='page')
    owned=False
    async with websockets.connect(old_page['webSocketDebuggerUrl']) as previous:
        await previous.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':'Boolean(window.onboardingOriginalFetch)','returnByValue':True}}))
        while True:
            reply=json.loads(await previous.recv())
            if reply.get('id')==1:
                owned=reply.get('result',{}).get('result',{}).get('value',False);break
    browser=json.load(urllib.request.urlopen('http://127.0.0.1:9228/json/version'))
    async with websockets.connect(browser['webSocketDebuggerUrl']) as connection:
        await connection.send(json.dumps({'id':1,'method':'Target.createTarget','params':{'url':'about:blank'}}))
        while True:
            reply=json.loads(await connection.recv())
            if reply.get('id')==1:target=reply['result']['targetId'];break
        if owned:
            # Discard only our earlier instrumented headless test page.
            await connection.send(json.dumps({'id':2,'method':'Target.closeTarget','params':{'targetId':old_page['id']}}))
            while json.loads(await connection.recv()).get('id')!=2:pass
    pages=json.load(urllib.request.urlopen('http://127.0.0.1:9228/json'))
    page=next(p for p in pages if p['id']==target)
    counter=0
    errors=[]
    paths=[]
    async with websockets.connect(page['webSocketDebuggerUrl'],max_size=12000000) as ws:
        async def command(method,params=None):
            nonlocal counter
            counter+=1;ident=counter
            await ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
            while True:
                message=json.loads(await ws.recv())
                if message.get('method')=='Runtime.exceptionThrown':errors.append('BROWSER_EXCEPTION')
                if message.get('method')=='Network.requestWillBeSent':
                    url=message['params']['request']['url']
                    if url.startswith('http://127.0.0.1:8765'):paths.append(urlsplit(url).path)
                if message.get('id')==ident:return message.get('result',{})

        async def js(expression):
            result=await command('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True})
            if 'exceptionDetails' in result:
                from resolveguard.telemetry import sanitize
                detail=result['exceptionDetails'].get('exception',{}).get('description','Evaluation failed').splitlines()[0]
                raise RuntimeError('Onboarding browser evaluation failed: '+sanitize(detail))
            return result.get('result',{}).get('value')

        async def ready(previous_id):
            for _ in range(100):
                if await js("window.onboardingDocumentId!=="+json.dumps(previous_id)+" && document.readyState==='complete' && typeof entryReady!=='undefined' && entryReady && !busy && !changingSession"):return
                await asyncio.sleep(.1)
            raise AssertionError('Welcome did not become ready')

        await command('Runtime.enable')
        await command('Page.enable')
        await command('Network.enable')
        previous=await js('window.onboardingDocumentId||null')
        await command('Page.navigate',{'url':'http://127.0.0.1:8765'})
        await ready(previous)
        startup_paths=list(paths)
        checks=await js("""(async()=>{
          const checks=[];
          checks.push({name:'One clean welcome and four quick actions',passed:document.querySelectorAll('#messages .welcome').length===1&&document.getElementById('welcome-message').textContent.startsWith("Hello! I'm your ResolveGuard assistant.")&&document.querySelectorAll('[data-quick-action]').length===4});
          checks.push({name:'Startup is guest with no account cards or outcome',passed:access==='AUTH_REQUIRED'&&document.getElementById('customer').textContent==='Guest'&&!document.querySelector('#messages .record-card')&&document.getElementById('outcome').hidden});
          checks.push({name:'Composer is focused and quick actions enabled',passed:document.activeElement.id==='message'&&Array.from(document.querySelectorAll('[data-quick-action]')).every(b=>!b.disabled)});
          document.getElementById('profile').value='customer-one';await startSession();
          showResult({response:'Old execution state for reset check',response_state:'AUTHORIZED_READ',data_scope:'RESTRICTED',cards:[{kind:'transaction',reference:'old',title:'Old payment',amount:'$19.95 USD',status:'Posted',date:'2026-10-30',date_label:'Date'}],draft:{draft_id:'old-draft',summary:'Old draft',expires_at:'2027-01-01T00:00:00Z'}});
          authPending='old-pending';document.getElementById('message').value='Old unsent text';document.getElementById('retry').hidden=false;
          await reset();
          const current=await api('/api/session');
          checks.push({name:'New conversation revokes identity and clears pending state',passed:current.profile==='signed-out'&&current.thread_id===null&&current.pending_id===null&&thread===null&&draft===null&&pending===null&&authPending===null});
          checks.push({name:'New conversation removes old output and restores landing',passed:!document.getElementById('messages').innerText.includes('Old execution state')&&!document.querySelector('#messages .record-card')&&document.getElementById('draft').hidden&&document.getElementById('message').value===''&&knowledgeBank==='BOW'&&document.getElementById('bow-product').value===''&&document.querySelectorAll('#messages .welcome').length===1});
          document.getElementById('profile').value='customer-one';await startSession();
          const originalFetch=window.fetch;
          window.fetch=(...args)=>String(args[0])==='/api/conversation/reset'?Promise.reject(new TypeError('Simulated local reset failure')):originalFetch(...args);
          await reset();
          const notSent=await send('Show my recent transactions');
          checks.push({name:'Reset failure blocks sending and old-identity polling',passed:!entryReady&&notSent===false&&document.getElementById('send').disabled&&!document.getElementById('new-chat').disabled&&document.getElementById('customer').textContent==='Guest'});
          window.fetch=originalFetch;await reset();
          checks.push({name:'New conversation safely retries failed initialization',passed:entryReady&&!document.getElementById('send').disabled&&access==='AUTH_REQUIRED'});
          document.getElementById('profile').value='customer-one';await startSession();
          showResult({response:'Old reply before reload',data_scope:'RESTRICTED',cards:[]});
          return checks;
        })()""")
        checks.append({'name':'Startup requests no saved reply or model response','passed':'/api/conversation' not in startup_paths and '/api/chat' not in startup_paths})
        previous=await js("window.onboardingDocumentId='before-reload';window.onboardingDocumentId")
        paths.clear()
        await command('Page.reload',{'ignoreCache':True})
        await ready(previous)
        checks.append({'name':'Page reload starts guest without restoring old output','passed':await js("access==='AUTH_REQUIRED'&&document.querySelectorAll('#messages .welcome').length===1&&!document.getElementById('messages').innerText.includes('Old reply')") and '/api/conversation' not in paths and '/api/chat' not in paths})
        await command('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        checks.append({'name':'Guest landing has no mobile horizontal overflow','passed':await js('document.documentElement.scrollWidth<=innerWidth')})
        await command('Emulation.setDeviceMetricsOverride',{'width':1366,'height':1000,'deviceScaleFactor':1,'mobile':False})
        await js('window.scrollTo(0,0)')
        shot=await command('Page.captureScreenshot',{'format':'png','captureBeyondViewport':True})
        out=Path('artifacts/onboarding');out.mkdir(parents=True,exist_ok=True)
        (out/'welcome.png').write_bytes(base64.b64decode(shot['data']))
    report={'passed':all(c['passed'] for c in checks) and not errors,'checks':checks,'browser_errors':errors,
            'model_calls_made':False,'scope':'Synthetic local onboarding and reset'}
    (out/'browser_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
