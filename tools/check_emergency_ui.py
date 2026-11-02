"""Synthetic emergency browser check on the existing local app and CDP browser."""
import asyncio
import json
import urllib.request
from pathlib import Path

import websockets


async def main():
    pages=json.load(urllib.request.urlopen('http://127.0.0.1:9228/json'))
    page=next(p for p in pages if p['type']=='page')
    counter=0
    errors=[]
    async with websockets.connect(page['webSocketDebuggerUrl'],max_size=10000000) as ws:
        async def command(method,params=None):
            nonlocal counter
            counter+=1
            ident=counter
            await ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
            while True:
                message=json.loads(await ws.recv())
                if message.get('method')=='Runtime.exceptionThrown':errors.append('BROWSER_EXCEPTION')
                if message.get('id')==ident:return message.get('result',{})

        async def js(code):
            result=await command('Runtime.evaluate',{'expression':code,'awaitPromise':True,'returnByValue':True})
            if 'exceptionDetails' in result:raise RuntimeError('Emergency browser check failed')
            return result.get('result',{}).get('value')

        await command('Runtime.enable')
        await command('Page.navigate',{'url':'http://127.0.0.1:8765'})
        for _ in range(100):
            if await js("typeof startSession==='function' && Boolean(document.getElementById('profile'))"):break
            await asyncio.sleep(.1)
        result=await js("""(async()=>{
          const checks=[]; const original=window.fetch;
          window.fetch=async(...args)=>{const response=await original(...args);
            if(String(args[0]).includes('/api/chat'))window.emergencyResult=await response.clone().json(); return response;};
          document.getElementById('profile').value='signed-out'; await startSession();
          await send('My debit card was stolen and someone is using it right now.','message',false,{bank_id:'BOW',transaction_ids:[]});
          checks.push({name:'Guest report saved with secure sign-in continuation',passed:emergencyResult.report?.status==='OK'&&emergencyResult.auth_required===true});
          checks.push({name:'Guest card lock remains unconfirmed',passed:emergencyResult.emergency.card_lock.state!=='LOCKED'});
          checks.push({name:'Guest emergency bypasses model framing',passed:!emergencyResult.generation});
          document.getElementById('profile').value='customer-one'; await startSession();
          await send('My debit card was stolen and someone is using it right now.','message',false,{transaction_ids:[]});
          checks.push({name:'Verified demo lock and ticket rendered separately',passed:document.getElementById('outcome').innerText.includes('Locked - backend confirmed')&&document.getElementById('outcome').innerText.includes('Open for review - demo')});
          checks.push({name:'Calm emergency response replaces generic model preamble',passed:emergencyResult.response.startsWith("I'm sorry this is happening.")&&!emergencyResult.generation});
          checks.push({name:'No real-bank action or refund guarantee claimed',passed:emergencyResult.response.includes('No real bank card was changed')&&emergencyResult.response.includes('No refund amount or date is guaranteed')});
          document.getElementById('profile').value='signed-out'; await startSession();
          checks.push({name:'Sign-out clears protected lock display',passed:!document.getElementById('outcome').innerText.includes('Locked - backend confirmed')});
          window.fetch=original; return checks;
        })()""")
    report={'checks':result,'browser_errors':errors,'passed':all(c['passed'] for c in result) and not errors}
    path=Path('artifacts/emergency_triage/browser_checks.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(asyncio.run(main()))
