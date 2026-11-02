"""Reconcile supplied human feedback in documentation without rerunning agents."""
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / 'submission'
OUT = SUB / 'human_review_reconciliation'
BACKUP = SUB / 'archive' / 'before_human_review_reconciliation'
REF = 'artifacts/human_review_received/817cb87ce51af0d4'
NOTICE = '''## Human review receipt and integration status

Human feedback **was provided and recorded twice**: in chat (22 observations: 14 PASS, 6 FAIL, 2 PARTIAL PASS) and in the returned Excel workbook (28 live-app observations: 23 PASS, 2 FAIL, 3 PARTIAL PASS). These sets overlap and must not be added into 50 independent tests.

Receipt references: HR-CHAT-22 (`artifacts/human_feedback_20261101_batch02/Review_Summary.json`) and HR-XLSX-28 (`artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json`). The original returned workbook SHA-256 is `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`.

The reviewer confirmed "I tested the live app" and clarified that another customer's case was not shown; three partial passes concern denial wording. Two product-context failures remain reported. Feedback receipt and documentation integration are complete; implementing or accepting every feedback item is not implied.

Human-judge agreement is **not yet calculated on matched responses**: the human reviewed live replies while the judge graded different saved responses. This is not missing human feedback. Formal source-contract approval and exact-saved-response calibration are separate outstanding decisions. No agreement percentage is invented.

This confirms handover of human review feedback to the project record, **not** a bank-support handoff, callback, or operational acknowledgement. Those require separate backend evidence.
'''


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    with ZipFile(ROOT/'ResolveGuard_AI_Final_Evaluation_Submission.xlsx') as existing:
        if b'Human Review Receipt' in existing.read('xl/workbook.xml'):
            raise SystemExit('Receipt already integrated. Run python -m tools.verify_review_package to refresh and verify the package.')
    OUT.mkdir(parents=True, exist_ok=True)
    changes = []
    app_before = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT/'resolveguard').rglob('*.py')}

    def backup(p):
        target = BACKUP / p.relative_to(ROOT)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)

    def write(p, data):
        if p.exists():
            backup(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding='utf-8')
        changes.append(str(p.relative_to(ROOT)))

    status = {
        'human_feedback_status': 'PROVIDED_RECEIVED_AND_DOCUMENTED',
        'chat_review': {'reference': 'HR-CHAT-22', 'observations': 22, 'PASS':14, 'FAIL':6, 'PARTIAL_PASS':2,
                        'evidence':'artifacts/human_feedback_20261101_batch02/Review_Summary.json'},
        'excel_review': {'reference':'HR-XLSX-28', 'observations':28, 'PASS':23, 'FAIL':2, 'PARTIAL_PASS':3,
                         'evidence':REF+'/Clarified_Review_Analysis.json'},
        'overlap_note':'Do not sum these into 50 independent cases.',
        'review_target':'LIVE_CUSTOMER_APP',
        'human_judge_agreement': None,
        'agreement_status':'NOT_YET_CALCULATED_ON_MATCHED_RESPONSES',
        'reason':'Human live replies and judge saved replies are different targets, not absent human feedback.',
        'feedback_handover':'RECEIVED_AND_RECORDED_IN_PROJECT_DOCUMENTATION',
        'bank_support_handoff':'NOT_ESTABLISHED_BY_HUMAN_REVIEW_RECEIPT',
        'foreign_case_disclosure_observed':False,
        'source_contract_approval':'SEPARATE_NOT_ESTABLISHED',
        'open_feedback':'Two product-context FAIL observations and three denial-wording PARTIAL PASS observations.',
    }
    write(OUT/'REVIEW_STATUS.json', json.dumps(status, indent=2)+'\n')
    write(OUT/'HUMAN_REVIEW_RECEIPT.md', '# Human Review Receipt and Reconciliation\n\n'+NOTICE)

    docs = [ROOT/'README.md'] + list(SUB.glob('*.md')) + list((SUB/'portfolio_report_draft').glob('*.md'))
    docs += [p for p in (ROOT/'docs').rglob('*.md') if re.search(r'human|calibrat|judge', p.read_text(encoding='utf-8'), re.I)]
    for p in docs:
        if p.name in {'README_GitHub.md','ZIP_SHA256.txt'}: continue
        s = p.read_text(encoding='utf-8')
        s = s.replace('| Human–judge agreement | **Not measured** | Exact-example human labels absent |',
                      '| Human review | **Provided: chat and Excel** | 22 chat observations and 28 overlapping live-app Excel observations; both recorded |\n| Human–judge agreement | **Not yet calculated on matched responses** | Human reviewed live replies; judge graded different saved replies |')
        s = s.replace('Human agreement remains unmeasured because the returned review assessed live replies rather than the exact frozen calibration answers.',
                      'Human feedback was provided in chat and Excel and is recorded. Agreement is not yet calculated on matched responses because the human assessed live replies while the judge graded different saved replies.')
        s = s.replace('One executed judge; exact-answer human labels absent', 'Human feedback received in chat and Excel; matching saved-response calibration remains pending')
        s = s.replace('One judge executed; exact-answer human labels and second model absent', 'Human feedback received; exact-response pairing and second-model comparison remain pending')
        s = s.replace('The workbook and ZIP are saved snapshots that **predate the latest clarified 28-observation review and this README revision**.',
                      'The workbook and ZIP now include a human-review receipt addendum and the latest clarified review references. Historical evaluation rows remain unchanged.')
        s = s.replace('Use the supplemental report for those assessments; they have not been silently merged into frozen calibration labels.',
                      'Live-app assessments have not been merged into frozen calibration labels.')
        # A concise prominent correction controls older status language without rewriting historical findings.
        if '## Human review receipt and integration status' not in s:
            first, sep, rest = s.partition('\n')
            s = first+'\n\n'+NOTICE+'\n'+rest
        write(p, s)
    shutil.copyfile(ROOT/'README.md', SUB/'README_GitHub.md')
    changes.append('submission/README_GitHub.md')

    # Current status overlay: preserve original run labels and confusion counts.
    for rel in ['artifacts/remediation_20261101/calibration_status.json', 'artifacts/remediation_20261101/Status_Summary.json']:
        p = ROOT/rel
        d = json.loads(p.read_text(encoding='utf-8'))
        d['human_feedback_receipt'] = status
        write(p, json.dumps(d, indent=2)+'\n')

    # Add a receipt sheet to both submission workbook copies; original worksheets remain intact.
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    relns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    offns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    contentns = 'http://schemas.openxmlformats.org/package/2006/content-types'
    book = ROOT/'ResolveGuard_AI_Final_Evaluation_Submission.xlsx'
    backup(book)
    with ZipFile(book) as z: parts = {n:z.read(n) for n in z.namelist()}
    wb = ET.fromstring(parts['xl/workbook.xml']); sheets = wb.find('{'+ns+'}sheets')
    assert not any(e.get('name')=='Human Review Receipt' for e in sheets)
    sheetid = max(int(e.get('sheetId')) for e in sheets)+1
    rels = ET.fromstring(parts['xl/_rels/workbook.xml.rels'])
    rid = 'rIdHumanReviewReceipt'
    name = f'worksheets/sheet{sheetid}.xml'
    ET.SubElement(sheets,'{'+ns+'}sheet',{'name':'Human Review Receipt','sheetId':str(sheetid),'{'+offns+'}id':rid})
    ET.SubElement(rels,'{'+relns+'}Relationship',{'Id':rid,'Type':offns+'/worksheet','Target':name})
    ct = ET.fromstring(parts['[Content_Types].xml'])
    ET.SubElement(ct,'{'+contentns+'}Override',{'PartName':'/xl/'+name,'ContentType':'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'})
    sheet = ET.Element('{'+ns+'}worksheet'); data = ET.SubElement(sheet,'{'+ns+'}sheetData')
    rows = [('Field','Current verified status')]+[(k,json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v) for k,v in status.items()]
    for i, row in enumerate(rows,1):
        el = ET.SubElement(data,'{'+ns+'}row',{'r':str(i)})
        for col, value in zip('AB',row):
            c = ET.SubElement(el,'{'+ns+'}c',{'r':f'{col}{i}','t':'inlineStr'})
            ET.SubElement(ET.SubElement(c,'{'+ns+'}is'),'{'+ns+'}t').text=str(value)
    for key, el in [('xl/workbook.xml',wb),('xl/_rels/workbook.xml.rels',rels),('[Content_Types].xml',ct),('xl/'+name,sheet)]:
        parts[key] = ET.tostring(el,encoding='utf-8',xml_declaration=True)
    with ZipFile(book,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items(): z.writestr(n,b)
    changes.append(str(book.relative_to(ROOT)))
    backup(SUB/book.name); shutil.copyfile(book,SUB/book.name); changes.append('submission/'+book.name)

    # Word report: compact receipt replaces older interpretation without extending the six-section layout.
    doc = SUB/'portfolio_report_draft/ResolveGuard_Evaluation_Report_Draft.docx'
    backup(doc)
    with ZipFile(doc) as z: parts={n:z.read(n) for n in z.namelist()}
    w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    xml=ET.fromstring(parts['word/document.xml'])
    body=xml.find('{'+w+'}body')
    p=ET.Element('{'+w+'}p'); run=ET.SubElement(p,'{'+w+'}r')
    ET.SubElement(run,'{'+w+'}t').text=(
        'Human feedback received and documented: HR-CHAT-22 (22 observations: 14 PASS, 6 FAIL, 2 PARTIAL PASS) and HR-XLSX-28 '
        '(28 live-app observations: 23 PASS, 2 FAIL, 3 PARTIAL PASS). Sets overlap. Human-judge agreement is not yet calculated '
        'on matched responses; live human replies differ from saved judge replies. No foreign-case disclosure was observed '
        'in the clarified review. This is feedback handover, not confirmation of a bank-support handoff. See submission/human_review_reconciliation/REVIEW_STATUS.json.')
    body.insert(2,p)
    parts['word/document.xml']=ET.tostring(xml,encoding='utf-8',xml_declaration=True)
    with ZipFile(doc,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items(): z.writestr(n,b)
    changes.append(str(doc.relative_to(ROOT)))

    # HTML views render the updated sources.
    from markdown_it import MarkdownIt
    for md, dest in [(SUB/'SUBMISSION_SUMMARY.md',SUB/'index.html'),
                     (SUB/'portfolio_report_draft/ResolveGuard_Evaluation_Report_Draft.md',SUB/'portfolio_report_draft/index.html')]:
        links='<p><a href="ResolveGuard_AI_Final_Submission.zip">Submission ZIP</a> | <a href="human_review_reconciliation/HUMAN_REVIEW_RECEIPT.md">Human review receipt</a></p>' if dest.parent==SUB else '<p><a href="ResolveGuard_Evaluation_Report_Draft.docx">Word report</a></p>'
        write(dest,'<!doctype html><html lang="en"><meta charset="utf-8"><title>ResolveGuard evidence</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:30px auto}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}</style>'+links+MarkdownIt('commonmark').enable('table').render(md.read_text(encoding='utf-8'))+'</html>')

    # Keep future generated prose from claiming independent human review was never supplied.
    builder=ROOT/'tools/build_final_submission.py'
    s=builder.read_text(encoding='utf-8')
    s=s.replace('independent human review still pending', 'human feedback received in chat and Excel; matched-response calibration still pending')
    s=s.replace('Human calibration pending', 'Human feedback received; matched-response calibration pending')
    s=s.replace('Human agreement, TPR and TNR are therefore unavailable.', 'Human feedback was supplied in chat and Excel for live replies. Matched-response agreement, TPR and TNR remain unavailable.')
    write(builder,s)

    assert app_before=={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'resolveguard').rglob('*.py')}
    write(OUT/'CHANGE_LOG.md','# Documentation Reconciliation Change Log\n\n'+NOTICE+'\n## Updated assets\n\n'+ '\n'.join('- `'+p+'`' for p in changes)+'\n\nOriginal human submissions, original run outputs, and historical archives are preserved. Application Python files are byte-identical; no new agent, provider, or cloud evaluation was run. Word XML/package integrity is checked; visual pagination was not rendered.\n')

    # Refresh the existing curated ZIP from its allowlist, not by scanning private runtime files.
    zip_path=SUB/'ResolveGuard_AI_Final_Submission.zip'
    with ZipFile(zip_path) as z: old={n:z.read(n) for n in z.namelist()}
    names=set(old)-{'submission/MANIFEST_SHA256.json','submission/PACKAGE_VALIDATION.json'}
    names.update(p.replace('\\', '/') for p in changes)
    names.update(str(p.relative_to(ROOT)).replace('\\','/') for p in OUT.rglob('*') if p.is_file())
    names.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/REF).iterdir() if p.is_file())
    names.update(['artifacts/human_feedback_20261101_batch02/Review_Summary.json','artifacts/human_feedback_20261101_batch02/Human_Observations.json'])
    payload={n:(ROOT/n).read_bytes() if (ROOT/n).is_file() else old[n] for n in names}
    manifest={n:hashlib.sha256(b).hexdigest() for n,b in sorted(payload.items())}
    validation=json.loads((SUB/'PACKAGE_VALIDATION.json').read_text(encoding='utf-8'))
    validation.update(human_feedback_receipt=status,workbook_tabs=len(sheets),documentation_reconciled=True,
                      human_calibration='PENDING_MATCHED_RESPONSE_LABELS_NOT_MISSING_FEEDBACK',
                      historical_execution_evidence_preserved=True,
                      application_code_unchanged=True,
                      prior_startup_smoke_not_rerun=True)
    (SUB/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (SUB/'PACKAGE_VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')
    payload['submission/MANIFEST_SHA256.json']=(SUB/'MANIFEST_SHA256.json').read_bytes()
    payload['submission/PACKAGE_VALIDATION.json']=(SUB/'PACKAGE_VALIDATION.json').read_bytes()
    with ZipFile(zip_path,'w',ZIP_DEFLATED) as z:
        for n,b in sorted(payload.items()):z.writestr(n,b)
    with ZipFile(zip_path) as z:
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(n)).hexdigest()==v for n,v in manifest.items())
    (SUB/'ZIP_SHA256.txt').write_text(sha(zip_path)+'  '+zip_path.name+'\n',encoding='utf-8')
    for p in [book,doc]:
        with ZipFile(p) as z:
            assert z.testzip() is None
            for n in z.namelist():
                if n.endswith('.xml'): ET.fromstring(z.read(n))
    print(json.dumps({'updated_assets':len(changes),'workbook_tabs':len(sheets),'zip_files':len(payload),'zip_manifest':'PASS','application_code':'UNCHANGED','human_feedback':'PROVIDED_CHAT_AND_EXCEL','agreement':'NOT_YET_CALCULATED_ON_MATCHED_RESPONSES'},indent=2))


if __name__=='__main__':
    main()
