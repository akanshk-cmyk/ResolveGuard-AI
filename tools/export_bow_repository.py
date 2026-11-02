"""Export active, validated BOW fixtures without changing labels or runtime data."""
import csv
import hashlib
import html
import json
import shutil
import zipfile
from pathlib import Path

from resolveguard.bow_data import MODELS,ROOT as BOW_ROOT,load_dataset
from tools.build_week3_submission import ROOT,workbook
from tools.prepare_dataset import read_sheet

OUT=ROOT/'artifacts/bow_repository_export_20261101'
TABS=[
    ('BOW Products','products',11,'Checking, savings and card product definitions','Test product selection, fees, rates and rewards','Amounts are integer cents. All offers and APYs are fictional.'),
    ('BOW Policies','policies',19,'Fictional product policies and support terms','Define which policy should answer a question','Not official bank policy; approval is synthetic/test-only.'),
    ('BOW RAG Chunks','chunks',61,'Source-linked retrievable policy passages','Check retrieved evidence, product scope and dates','Chunk text hashes and parent-policy metadata are preserved.'),
    ('BOW Customers','customers',12,'Fictional customer identities','Test identity and ownership','Synthetic KYC labels are not real identity verification.'),
    ('BOW Accounts','accounts',12,'Customer-account-product relationships','Check account ownership and product selection','Account displays are masked. Backend permissions still apply.'),
    ('BOW Transactions','transactions',48,'Fictional payment records','Check exact merchant, signed amount, date and status','amount_cents is signed; posted_on is a source date, not a precise event timestamp.'),
    ('BOW Sessions','sessions',12,'Synthetic authentication/session fixtures','Test authentication, assurance and revocation','These are test fixtures, not live cookies, session tokens or credentials.'),
    ('BOW Cases','cases',12,'Seeded support cases and states','Test case lookup and authorized status access','Runtime-created cases are not merged into this fixture export.'),
    ('BOW Delegations','delegations',2,'Representative-authority fixtures','Test explicit delegated action scope','Family relationships alone grant no access.'),
    ('BOW Intake Events','intake_events',1,'Seeded report-intake event','Test capture and acknowledgement states','Separate from runtime reports, formal notice acceptance and investigation.'),
    ('BOW Eval Golden','evaluations',100,'Evaluation definitions and proposed expected outcomes','Run and review the banking evaluation suite','Source NOT_RUN values stay unchanged; this export does not run or approve evaluations.')]


def save_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def csv_file(path,rows):
    headers=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=headers)
        writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)


def main():
    data,manifest=load_dataset()  # Validates source hash, file hashes, Pydantic and relationships.
    directory=BOW_ROOT/manifest['source_sha256']
    assert all(len(data[key])==expected for _,key,expected,*_ in TABS)
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'json').mkdir();(OUT/'csv').mkdir()
    summary=[{'Excel tab':tab,'Records':len(data[key]),'What it contains':what,'When you use it':when,
              'Important notes':note,'Repository source':str((directory/(key+'.json')).relative_to(ROOT))}
             for tab,key,_,what,when,note in TABS]
    summary.extend([
        {'Excel tab':'Package scope','Records':290,'What it contains':'Repository-normalized active BOW fixtures only',
         'When you use it':'Review the source data actually loaded by the app',
         'Important notes':'No runtime reports, lock receipts, browser sessions, real customer data or credentials are exported.'},
        {'Excel tab':'Source workbook','Records':'','What it contains':manifest['source_file'],
         'When you use it':'Check original worksheets and archives against Original_Source_Workbook.xlsx',
         'Important notes':'Byte-identical original retained separately; archives are not activated as BOW data.'},
        {'Excel tab':'Source SHA256','Records':'','What it contains':manifest['source_sha256'],
         'When you use it':'Verify which active source version was exported','Important notes':'Resolved from data/bow/active.json; not a guessed Downloads copy.'},
        {'Excel tab':'Data meanings','Records':'','What it contains':'Fictional policies, rates and synthetic approvals',
         'When you use it':'Review bank/product scope, effective dates, expiry and approval status',
         'Important notes':'Not real banking offers or institution-approved terms. No human review status was changed.'},
        {'Excel tab':'Reading full text','Records':'','What it contains':'All original repository fields and values retained',
         'When you use it':'Expand row height to read long policy or chunk text in Excel',
         'Important notes':'CSV blanks represent null; JSON retains exact data types. Dates are the normalized repository values.'}])
    target=OUT/'ResolveGuard_BOW_Repository_Export.xlsx'
    workbook(target,[('00 Executive Summary',summary)]+[(tab,data[key]) for tab,key,*_ in TABS])
    dictionary=[]
    descriptions={
        'bank_id':'Bank boundary: BOW only.', 'product_id':'Product variant or explicit policy scope.',
        'customer_id':'Fictional customer identifier; used in ownership checks.',
        'account_id':'Account relationship identifier; access is checked by the backend.',
        'doc_id':'Parent policy identifier linking chunks to their source.',
        'chunk_id':'Stable retrieval passage identifier.',
        'effective_date':'Date from which these sample terms apply.',
        'expires_on':'Exclusive expiry boundary; null means no expiry supplied.',
        'access_level':'Public/internal/restricted retrieval boundary.',
        'approval_status':'Test-only synthetic approval, not bank approval.',
        'sha256_text':'Integrity hash of the exact chunk text.',
        'amount_cents':'Signed whole cents; preserve sign and currency.',
        'monthly_fee_cents_or_annual_card_fee_cents':'Whole cents; fee period depends on product type.',
        'execution_status':'Source worksheet status, not the result of a later evaluation run.',
        'masked_display':'Masked sample account display; not a full account number.',
        'allowed_action':'The specific action permitted by a representative-authority record.'}
    for tab,key,*_ in TABS:
        shutil.copyfile(directory/(key+'.json'),OUT/'json'/(key+'.json'))
        csv_file(OUT/'csv'/(key+'.csv'),data[key])
        properties=MODELS[key].model_json_schema().get('properties',{})
        for field in data[key][0]:
            values=[r.get(field) for r in data[key] if r.get(field) is not None]
            sample=values[0] if values else None
            datatype='true/false' if isinstance(sample,bool) else 'whole number' if isinstance(sample,int) else 'text' if isinstance(sample,str) else 'blank/null' if sample is None else 'structured data'
            dictionary.append({'Worksheet':tab,'Field':field,'Data type':datatype,
                'Allowed values':properties.get(field,{}).get('enum','See source schema / example'),
                'Example':sample,'Meaning':descriptions.get(field,field.replace('_',' ').capitalize())})
    csv_file(OUT/'Field_Dictionary.csv',dictionary)
    save_json(OUT/'Field_Dictionary.json',dictionary)
    save_json(OUT/'Export_Inventory.json',summary)
    shutil.copyfile(directory/'manifest.json',OUT/'Source_Manifest.json')
    shutil.copyfile(BOW_ROOT/'active.json',OUT/'Active_Source_Pointer.json')
    shutil.copyfile(directory/'source.xlsx',OUT/'Original_Source_Workbook.xlsx')
    checks=[]
    for tab,key,expected,*_ in TABS:
        parsed=read_sheet(target,tab)
        assert len(parsed)-1==expected
        headers=list(data[key][0])
        for exported,source in zip(parsed[1:],data[key]):
            for index,field in enumerate(headers,1):
                from tools.build_week3_submission import col
                value=source[field]
                expected_value='' if value is None else json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict)) else str(value)
                assert exported[col(index)]==expected_value,(tab,field)
        assert hashlib.sha256((OUT/'json'/(key+'.json')).read_bytes()).hexdigest()==manifest['data_sha256'][key]
        checks.append({'Worksheet':tab,'Records':expected,'All field values matched':True,'Source JSON hash matched':True})
    assert hashlib.sha256((OUT/'Original_Source_Workbook.xlsx').read_bytes()).hexdigest()==manifest['source_sha256']
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len([n for n in archive.namelist() if n.startswith('xl/worksheets/sheet')])==12
    save_json(OUT/'Export_Validation.json',{'passed':True,'data_rows':290,'worksheet_count':12,
        'source_sha256':manifest['source_sha256'],'checks':checks,'original_workbook_hash_matched':True,
        'evaluations_executed':False,'human_reviews_modified':False,'runtime_databases_exported':False})
    notes='''ResolveGuard BOW Repository Export — November 1, 2026

Open ResolveGuard_BOW_Repository_Export.xlsx. The first tab explains the other
eleven tabs, when to use them, counts, source paths and cautions.

This export follows the active repository source pointer and validates Pydantic
schemas, relationships, source workbook/file hashes and chunk integrity before
writing. Every data cell was then read back and checked against the source.

All data is fictional. Policies and approvals are test-only. This package does
not contain real bank terms, live session credentials or runtime banking events.
It does not run evaluations, approve labels or alter the source workbooks.

The 12-tab export uses the repository's normalized dates and source fields.
Original_Source_Workbook.xlsx is a separate byte-identical copy with its original
archived sheets. Archived records are not merged into the active export.

json/ contains exact active source files. csv/ contains review-friendly copies.
Field_Dictionary.csv explains field types, meanings and examples.
Source_Manifest.json retains source version, row lineage and normalization notes.
Export_Validation.json records the cell-by-cell and hash checks.

The 100 golden rows are scenario definitions, not 100 fresh scored results.
NOT_RUN source values stay unchanged; actual execution reports are separate.
Runtime-created support cases, card locks and fraud tickets are not fixture rows
and are deliberately not mixed into this source-data review package.
'''
    (OUT/'README.txt').write_text(notes,encoding='utf-8')
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(r.get(c,'')))+'</td>' for c in ('Excel tab','Records','What it contains','When you use it','Important notes'))+'</tr>' for r in summary[:11])
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ResolveGuard BOW Repository Export</title><style>body{font:16px/1.6 system-ui;color:#173b40;background:#f7faf8;margin:32px auto;max-width:1200px;padding:0 20px}table{border-collapse:collapse;background:white}td,th{border:1px solid #ccd9d4;padding:10px;text-align:left;vertical-align:top}.scroll{overflow:auto}a{color:#09665c}code{overflow-wrap:anywhere}</style><h1>ResolveGuard BOW Repository Export</h1><p>12 worksheets · 290 fictional source records · exported November 1, 2026.</p><p><a href="ResolveGuard_BOW_Repository_Export.xlsx">Download Excel workbook</a> · <a href="ResolveGuard_BOW_Export_Package.zip">Download full package</a> · <a href="Field_Dictionary.csv">Field dictionary</a> · <a href="Export_Validation.json">Validation results</a></p><p>Source: the active BOW repository snapshot. No runtime customer activity, credentials or newly generated test results are included. Fictional policies are not official bank terms.</p><div class="scroll"><table><thead><tr><th>Excel tab</th><th>Records</th><th>What it contains</th><th>When to use it</th><th>Notes</th></tr></thead><tbody>'''+rows+'''</tbody></table></div><p><a href="Original_Source_Workbook.xlsx">Original source workbook, including its archived sheets</a> · <a href="README.txt">Reading guide</a> · <a href="Source_Manifest.json">Source manifest and lineage</a></p><p>Source fingerprint: <code>'''+manifest['source_sha256']+'</code></p></html>'
    (OUT/'index.html').write_text(page,encoding='utf-8')
    hashes={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()}
    save_json(OUT/'MANIFEST_SHA256.json',hashes)
    package=OUT/'ResolveGuard_BOW_Export_Package.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in OUT.rglob('*'):
            if path.is_file() and path!=package:archive.write(path,path.relative_to(OUT))
    with zipfile.ZipFile(package) as archive:assert archive.testzip() is None
    print(json.dumps({'output':str(OUT),'worksheets':12,'data_rows':290,'counts':manifest['counts'],
                      'all_cell_values_verified':True,'source_sha256':manifest['source_sha256']},indent=2))


if __name__=='__main__':main()
