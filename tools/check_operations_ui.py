"""Local-only browser smoke check against an already running dashboard and CDP."""
import asyncio
import base64
import json
import os
import urllib.request
from pathlib import Path
import websockets
from resolveguard.eval_config import ROOT, load_eval_environment


async def main():
    load_eval_environment()
    pages = json.load(urllib.request.urlopen('http://127.0.0.1:9228/json'))
    page = next(p for p in pages if p['type']=='page')
    errors, checks = [], []
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=10_000_000) as ws:
        counter = 0
        async def command(method, params=None):
            nonlocal counter
            counter += 1
            ident = counter
            await ws.send(json.dumps({'id':ident, 'method':method, 'params':params or {}}))
            while True:
                message = json.loads(await ws.recv())
                if message.get('method')=='Runtime.exceptionThrown':
                    errors.append('BROWSER_RUNTIME_EXCEPTION')
                if message.get('id')==ident:
                    if 'error' in message:
                        raise RuntimeError('Browser command failed')
                    return message.get('result', {})
        await command('Runtime.enable')
        await command('Page.navigate', {'url':'http://127.0.0.1:8766'})
        for _ in range(40):
            ready = await command('Runtime.evaluate', {'expression':"Boolean(document.getElementById('access'))", 'returnByValue':True})
            if ready.get('result', {}).get('value'): break
            await asyncio.sleep(.1)
        token = json.dumps(os.environ['RESOLVEGUARD_DASHBOARD_TOKEN'])
        script = '''(async () => {
          const checks = [];
          const denied = await fetch('/api/operations');
          checks.push({name:'unauthenticated API blocked',passed:denied.status===401});
          document.getElementById('token').value=TOKEN;
          document.getElementById('access').requestSubmit();
          for(let i=0;i<100 && !document.querySelector('#trends tr');i++) await new Promise(r=>setTimeout(r,100));
          checks.push({name:'historical trends rendered',passed:document.querySelectorAll('#trends tr').length>0});
          checks.push({name:'baseline selectors populated',passed:document.getElementById('baseline').options.length>0});
          checks.push({name:'comparison and fingerprints rendered',passed:document.getElementById('details').textContent.includes('dataset_sha256')});
          checks.push({name:'token input cleared',passed:document.getElementById('token').value===''});
          checks.push({name:'generation panel distinguishes unavailable measurements',passed:document.getElementById('generation').textContent.includes('unknown measurements') || document.getElementById('generation').textContent.includes('generation attempts')});
          document.getElementById('trace').click();
          for(let i=0;i<50 && !document.getElementById('traces').textContent;i++) await new Promise(r=>setTimeout(r,100));
          checks.push({name:'trace history rendered',passed:document.getElementById('traces').textContent.includes('spans')});
          return checks;
        })()'''.replace('TOKEN', token)
        result = await command('Runtime.evaluate', {'expression':script, 'awaitPromise':True, 'returnByValue':True})
        checks = result.get('result', {}).get('value', [])
        await command('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        overflow = await command('Runtime.evaluate', {'expression':'document.documentElement.scrollWidth <= innerWidth', 'returnByValue':True})
        checks.append({'name':'mobile page fits viewport','passed':overflow['result']['value']})
        await command('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
        screenshot = await command('Page.captureScreenshot', {'format':'png'})
        (ROOT/'artifacts/observability_dashboard.png').write_bytes(base64.b64decode(screenshot['data']))
        report = {'checks':checks, 'runtime_errors':errors, 'passed':bool(checks) and all(c['passed'] for c in checks) and not errors}
        (ROOT/'artifacts/observability_browser_checks.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
        return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
