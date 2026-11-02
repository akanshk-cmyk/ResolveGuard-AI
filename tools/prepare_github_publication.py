"""Create a curated public copy without changing the working app or credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, is_zipfile
import hashlib
import io
import json
import re
import shutil

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'publication/ResolveGuard-AI'
ROOT_FILES={'.env.example','.gitignore','.python-version','.replit','main.py','pyproject.toml','uv.lock',
            'README.md','LOCAL_DEMO.md','requirements.txt','requirements-evals.txt','requirements.lock.txt',
            'ResolveGuard_AI_Final_PRD_v0.4_Risk_Remediated.pdf','ResolveGuard_AI_BRD_Agent_Observability_v1.0.pdf',
            'ResolveGuard_AI_Comprehensive_Evals_v0.4_Risk_Remediated.xlsx','ResolveGuard_AI_Final_Evaluation_Submission.xlsx'}
FOLDERS=['resolveguard','tests','tools','docs','data','prompts','resolveguard_synthetic_v04',
         'resolveguard_demo_baseline','demo','submission','artifacts','.github']
EXTENSIONS={'.py','.ps1','.json','.jsonl','.csv','.xlsx','.ipynb','.md','.pdf','.png','.jpg','.jpeg','.svg',
            '.txt','.html','.css','.js','.mmd','.docx','.yml','.yaml'}
EXCLUDED_PARTS={'__pycache__','.venv','.uv-cache','.git','isolated-state','github_publication'}


def selected(path):
    rel=path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS or 'browser-profile' in part.lower() for part in rel.parts):return False
    if path.name.startswith(('~$','.env')) and path.name!='.env.example':return False
    if path.name.startswith(('submission_server','app.stdout','app.stderr','dashboard.stdout','dashboard.stderr')):return False
    if path.suffix=='.zip':
        return rel.as_posix() in {'submission/ResolveGuard_AI_Final_Submission.zip',
            'submission/final_project_summary/ResolveGuard_Final_Project_Summary_Pack.zip',
            'artifacts/refactor_20261101_01/source_checkpoint.zip'}
    return path.suffix.lower() in EXTENSIONS


def private_values():
    """Known local key values are used only in-memory for leak checking."""
    path=ROOT/'.env'
    if not path.is_file():return []
    values=[]
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key,sep,value=line.partition('=')
        if sep and key.strip() in {'NEBIUS_API_KEY','LANGSMITH_API_KEY','RESOLVEGUARD_DASHBOARD_TOKEN'}:
            value=value.strip().strip('\"\'')
            if len(value)>=16:values.append(value.encode())
    return values


def scan(data,label,keys,findings,depth=0):
    if any(key in data for key in keys):findings.append({'file':label,'reason':'KNOWN_LOCAL_SECRET_MATCH'})
    if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data):
        findings.append({'file':label,'reason':'PRIVATE_KEY_PATTERN'})
    if depth<3 and data.startswith(b'PK') and is_zipfile(io.BytesIO(data)):
        with ZipFile(io.BytesIO(data)) as z:
            if z.testzip() is not None:raise RuntimeError('Archive CRC failed: '+label)
            for entry in z.infolist():
                if entry.is_dir():continue
                leaf=Path(entry.filename.replace('\\','/')).name
                if leaf=='.env' or leaf.startswith('.env.') and leaf!='.env.example':
                    findings.append({'file':label+'!'+entry.filename,'reason':'PRIVATE_ENV_FILE'})
                if entry.file_size>100*1024*1024:raise RuntimeError('Archive entry requires manual review: '+label)
                scan(z.read(entry),label+'!'+entry.filename,keys,findings,depth+1)


def main():
    if DEST.exists():raise SystemExit('Publication directory already exists; preserve it and use a new versioned target.')
    files=[ROOT/name for name in ROOT_FILES if (ROOT/name).is_file()]
    for folder in FOLDERS:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and selected(p))
    keys=private_values();findings=[]
    for p in files:
        if p.stat().st_size>95*1024*1024:raise RuntimeError('File exceeds publication size policy: '+p.relative_to(ROOT).as_posix())
        scan(p.read_bytes(),p.relative_to(ROOT).as_posix(),keys,findings)
    if findings:
        out=ROOT/'artifacts/github_publication';out.mkdir(exist_ok=True)
        (out/'blocked_files.json').write_text(json.dumps(findings,indent=2)+'\n',encoding='utf-8')
        raise SystemExit('Publication blocked by '+str(len(findings))+' scoped security findings; values not printed.')
    for p in files:
        target=DEST/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    readme=DEST/'README.md';text=readme.read_text(encoding='utf-8')
    text=text.replace('https://github.com/<YOUR-USERNAME>/<YOUR-REPOSITORY>.git','https://github.com/akanshk-cmyk/ResolveGuard-AI.git').replace('cd <YOUR-REPOSITORY>','cd ResolveGuard-AI')
    readme.write_text(text,encoding='utf-8')
    manifest={p.relative_to(DEST).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob('*') if p.is_file()}
    (DEST/'PUBLICATION_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    total=sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())
    report={'owner':'akanshk-cmyk','repository':'ResolveGuard-AI','requested_visibility':'public',
        'remote_publication':'PENDING_AUTHORIZED_GITHUB_ACCESS','selected_files':len(manifest),
        'size_mb':round(total/1048576,2),'known_secret_scan':'PASS','nested_archive_scan':'PASS',
        'excluded':['.env','local databases','browser profiles','runtime logs','caches','Office lockfiles'],
        'application_changed':False,'public_copy':str(DEST),'scope':'Exact local key matching and private-key/env-file checks; not universal privacy detection'}
    out=ROOT/'artifacts/github_publication';out.mkdir(exist_ok=True)
    (out/'preparation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
