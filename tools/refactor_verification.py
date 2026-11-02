"""Local refactor checkpoints: preserve source/evidence and record actual checks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/refactor_20261101_01'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_files():
    for folder in ['data','prompts','resolveguard_synthetic_v04/fixtures','artifacts']:
        for p in (ROOT/folder).rglob('*'):
            if not p.is_file() or any('profile' in x.lower() or x=='__pycache__' for x in p.parts):continue
            if OUT in p.parents:continue
            if p.suffix.lower() not in {'.json','.jsonl','.csv','.xlsx','.ipynb','.md','.pdf','.png','.txt'}:continue
            if p.suffix.lower()=='.txt' and ('stdout' in p.name or 'stderr' in p.name):continue
            yield p


def checkpoint():
    OUT.mkdir(parents=True,exist_ok=False)
    source=[]
    for folder in ['resolveguard','tests','tools']:
        source.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.js','.css','.html','.png','.ps1'})
    source.extend(ROOT/name for name in ['main.py','pyproject.toml','uv.lock','.gitignore','.env.example','.python-version','README.md'])
    with ZipFile(OUT/'source_checkpoint.zip','w',ZIP_DEFLATED) as z:
        for p in source:z.write(p,p.relative_to(ROOT).as_posix())
    manifest={p.relative_to(ROOT).as_posix():digest(p) for p in protected_files()}
    (OUT/'protected_evidence_sha256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (OUT/'source_sha256.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():digest(p) for p in source},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'checkpoint':'CREATED','source_files':len(source),'protected_files':len(manifest),'secrets_included':False}))


def run(label,commands):
    env=dict(os.environ,RESOLVEGUARD_REPLY_MODE='off',LANGSMITH_TRACING='false',RESOLVEGUARD_CLOUD_TRACING='false',PYTHONIOENCODING='utf-8')
    env.pop('NEBIUS_API_KEY',None);env.pop('LANGSMITH_API_KEY',None)
    rows=[]
    for name,args in commands:
        log=OUT/(label+'_'+name+'.log');started=time.monotonic()
        with log.open('w',encoding='utf-8') as handle:
            proc=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT,timeout=600)
        output=log.read_text(encoding='utf-8');found=re.search(r'Ran (\d+) tests?',output)
        skipped=re.search(r'skipped=(\d+)',output)
        row={'name':name,'command':['python',*args],'exit_code':proc.returncode,'elapsed_seconds':round(time.monotonic()-started,3),
             'tests_run':int(found[1]) if found else None,'skipped':int(skipped[1]) if skipped else 0,'log':log.relative_to(ROOT).as_posix()}
        if row['tests_run'] is not None and proc.returncode==0:row['passed']=row['tests_run']-row['skipped']
        rows.append(row)
        print(json.dumps(row),flush=True)
    (OUT/(label+'_checks.json')).write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    return 0 if all(r['exit_code']==0 for r in rows) else 1


def verify_evidence():
    original=json.loads((OUT/'protected_evidence_sha256.json').read_text(encoding='utf-8'))
    changed=[p for p,h in original.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=h]
    report={'protected_files':len(original),'changed_or_missing':changed,'status':'PASS' if not changed else 'FAIL'}
    (OUT/'evidence_integrity.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report));return not changed


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['checkpoint','baseline','final','evidence'])
    args=parser.parse_args()
    if args.phase=='checkpoint':checkpoint();return 0
    if args.phase=='evidence':return 0 if verify_evidence() else 1
    return run(args.phase,[('main_tests',['-m','unittest','discover','-s','tests','-q']),
                           ('fixture_tests',['-m','unittest','discover','-s','resolveguard_synthetic_v04/tests','-q']),
                           ('original100',['-m','resolveguard.full_evaluation','--suite','original','--output',str(OUT/(args.phase+'_original100'))]),
                           ('bow100',['-m','resolveguard.full_evaluation','--suite','bow','--output',str(OUT/(args.phase+'_bow100'))])])


if __name__=='__main__':raise SystemExit(main())
