"""Validate packaged evidence, render PDF in local Chromium and create the ZIP."""
import asyncio
import base64
import csv
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import websockets

from tools.build_week3_submission import OUT,metrics
from tools.prepare_dataset import read_sheet


async def render():
    browser=json.load(urllib.request.urlopen('http://127.0.0.1:9228/json/version'))
    async with websockets.connect(browser['webSocketDebuggerUrl']) as connection:
        await connection.send(json.dumps({'id':1,'method':'Target.createTarget','params':{'url':'about:blank'}}))
        while True:
            reply=json.loads(await connection.recv())
            if reply.get('id')==1:
                target=reply['result']['targetId'];break
    pages=json.load(urllib.request.urlopen('http://127.0.0.1:9228/json'))
    page=next(p for p in pages if p['id']==target)
    count=0
    async with websockets.connect(page['webSocketDebuggerUrl'],max_size=40000000) as connection:
        async def call(method,params=None):
            nonlocal count
            count+=1;ident=count
            await connection.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
            while True:
                reply=json.loads(await connection.recv())
                if reply.get('id')==ident:
                    if 'error' in reply:raise RuntimeError(reply['error']['message'])
                    return reply.get('result',{})

        async def evaluate(expression):
            result=await call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
            if 'exceptionDetails' in result:raise RuntimeError('Report browser evaluation failed')
            return result.get('result',{}).get('value')

        async def wait(expression):
            for _ in range(100):
                if await evaluate(expression):return
                await asyncio.sleep(.1)
            raise RuntimeError('Report did not finish loading')

        await call('Runtime.enable')
        await call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1050,'deviceScaleFactor':1,'mobile':False})
        await call('Page.navigate',{'url':'http://127.0.0.1:8772'})
        await wait("document.getElementById('case')?.value==='RG-033' && document.getElementById('before-status')?.textContent.startsWith('FAIL') && document.getElementById('after-status')?.textContent.startsWith('PASS')")
        screenshot=await call('Page.captureScreenshot',{'format':'png'})
        (OUT/'Submission_Overview.png').write_bytes(base64.b64decode(screenshot['data']))
        report=OUT/'report.html'
        content=report.read_text(encoding='utf-8')
        if 'id="screenshot-appendix"' not in content:
            content=content.replace('</main>','<section id="screenshot-appendix" style="break-before:page"><h2>Case-level evidence screenshot</h2><p>Stored RG-033 baseline failure and improved pass, with the same input. No live model is called by this viewer.</p><img src="Submission_Overview.png" alt="RG-033 stored baseline and improved comparison" style="width:100%"></section></main>')
            report.write_text(content,encoding='utf-8')
        await call('Page.navigate',{'url':'http://127.0.0.1:8772/report.html'})
        await wait("document.title==='ResolveGuard Week 3 Evaluation' && document.getElementById('screenshot-appendix') && Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)")
        pdf=await call('Page.printToPDF',{'printBackground':True,'paperWidth':8.27,'paperHeight':11.69,
            'marginTop':.45,'marginBottom':.45,'marginLeft':.45,'marginRight':.45,'preferCSSPageSize':True})
        (OUT/'Project_Summary_Report.pdf').write_bytes(base64.b64decode(pdf['data']))
        await call('Page.navigate',{'url':'http://127.0.0.1:8772'})


def validate():
    checks=[]
    workbook=OUT/'ResolveGuard_Week3_Evaluation.xlsx'
    with zipfile.ZipFile(workbook) as archive:
        assert archive.testzip() is None
        for name in archive.namelist():
            if name.endswith(('.xml','.rels')):ET.fromstring(archive.read(name))
        assert not any(b'<f>' in archive.read(name) for name in archive.namelist() if name.startswith('xl/worksheets/'))
    cases=read_sheet(workbook,'Cases 40')
    raw=read_sheet(workbook,'Raw Runs 240')
    assert len(cases)==41 and len(raw)==241
    assert len({row['A'] for row in cases[1:]})==40
    checks.append('Valid OOXML workbook: 40 unique case rows and 240 raw observations; formula-free literal cells.')
    with (OUT/'Scored_Cases_40.csv').open(encoding='utf-8-sig',newline='') as handle:
        csv_rows=list(csv.DictReader(handle))
    assert len(csv_rows)==40
    assert sum(row['Baseline PASS/FAIL']=='PASS' for row in csv_rows)==32
    assert sum(row['Improved PASS/FAIL']=='PASS' for row in csv_rows)==39
    assert [row['Case ID'] for row in csv_rows if row['Improved PASS/FAIL']=='FAIL']==['RG-056']
    checks.append('CSV and workbook cases: baseline 32/40, improved 39/40, RG-056 retained.')
    labels=json.loads((OUT/'evidence/evaluation_40.json').read_text(encoding='utf-8'))
    comparison=json.loads((OUT/'evidence/comparison.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(json.dumps(labels,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    assert digest==comparison['dataset_sha256']
    for version in ('v0','v4'):
        rows=json.loads((OUT/f'evidence/{version}_results.json').read_text(encoding='utf-8'))
        expected=next(e['metrics'] for e in comparison['experiments'] if e['version']==version)
        assert all(abs(value-expected[key])<1e-8 for key,value in metrics(rows).items())
        assert len((OUT/f'evidence/{version}_traces.jsonl').read_text(encoding='utf-8').splitlines())==120
    checks.append('Dataset fingerprint and all five metrics independently recomputed; 120 traces per version.')
    notebook=json.loads((OUT/'Evidence_Analysis.ipynb').read_text(encoding='utf-8'))
    assert len(notebook['cells'])==4
    assert all(cell['execution_count'] and cell['outputs'] and all(o['output_type']!='error' for o in cell['outputs']) for cell in notebook['cells'])
    checks.append('Four executed evidence-analysis cells contain outputs and no errors; agent was not rerun.')
    assert (OUT/'Project_Summary_Report.pdf').read_bytes().startswith(b'%PDF-')
    assert (OUT/'Submission_Overview.png').read_bytes().startswith(b'\x89PNG')
    status=json.loads((OUT/'Submission_Status.json').read_text(encoding='utf-8'))
    assert status['Loom_URL'] is None and status['human_labels']=='PENDING'
    checks.append('PDF and case screenshot created; missing Loom/human approval remains explicit.')
    files=[p for p in OUT.rglob('*') if p.is_file()]
    assert not any(p.name=='.env' or p.suffix in {'.sqlite3','.db'} for p in files)
    checks.append('Package contains no environment credentials or runtime banking databases.')
    (OUT/'Package_Validation.json').write_text(json.dumps({'passed':True,'checks':checks},indent=2)+'\n',encoding='utf-8')
    manifest={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in OUT.rglob('*') if p.is_file() and p.name not in {'MANIFEST_SHA256.json','ResolveGuard_Week3_Submission.zip'}}
    (OUT/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    target=OUT/'ResolveGuard_Week3_Submission.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for file in OUT.rglob('*'):
            if file.is_file() and file!=target:archive.write(file,file.relative_to(OUT))
    with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
    print(json.dumps({'checks':checks,'zip':str(target),'zip_bytes':target.stat().st_size},indent=2))


if __name__=='__main__':
    asyncio.run(render())
    validate()
