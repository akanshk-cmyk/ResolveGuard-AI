"""Dependency-free syntax and scoped publication checks; never prints secrets."""
import argparse
import ast
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
TOKEN_PATTERNS=[
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'\b(?:ghp_|gho_|github_pat_)[A-Za-z0-9_]{36,}\b'),
    re.compile(r'\b(?:sk-proj-|lsv2_pt_)[A-Za-z0-9_-]{32,}\b'),
]


def inspect():
    syntax_errors=[];credential_findings=[];files=0
    candidates=[ROOT/'main.py',ROOT/'.env.example',ROOT/'README.md']
    for folder in ['resolveguard','tests','tools','docs','.github']:
        candidates.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                          and p.suffix.lower() in {'.py','.md','.txt','.html','.js','.css','.yaml','.yml'})
    for path in candidates:
        text=path.read_text(encoding='utf-8-sig');files+=1
        if path.suffix=='.py':
            try:ast.parse(text,filename=str(path))
            except SyntaxError as exc:syntax_errors.append({'file':path.relative_to(ROOT).as_posix(),'line':exc.lineno})
        for number,line in enumerate(text.splitlines(),1):
            if any(pattern.search(line) for pattern in TOKEN_PATTERNS):
                credential_findings.append({'file':path.relative_to(ROOT).as_posix(),'line':number})
    example=(ROOT/'.env.example').read_text(encoding='utf-8')
    unsafe_examples=[]
    for line in example.splitlines():
        key,sep,value=line.partition('=')
        if sep and key.strip() in {'NEBIUS_API_KEY','LANGSMITH_API_KEY','RESOLVEGUARD_DASHBOARD_TOKEN'} and value.strip():
            unsafe_examples.append(key.strip())
    ignores=(ROOT/'.gitignore').read_text(encoding='utf-8').splitlines()
    required={'.env','.venv/','*.sqlite3','*.log','~$*'}
    missing=sorted(required-set(ignores))
    return {'files_checked':files,'python_syntax_errors':syntax_errors,
            'credential_pattern_findings':credential_findings,'unsafe_example_key_names':unsafe_examples,
            'missing_ignore_rules':missing,
            'scope':'Source/config/docs and known credential patterns only; not universal PII detection or a vulnerability database audit',
            'status':'PASS' if not (syntax_errors or credential_findings or unsafe_examples or missing) else 'FAIL'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output');args=parser.parse_args()
    report=inspect()
    if args.output:Path(args.output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
