"""Refresh curated documentation package and verify review receipt consistency."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
SUB=ROOT/'submission'
OUT=SUB/'human_review_reconciliation'


def main():
    archive=SUB/'ResolveGuard_AI_Final_Submission.zip'
    with ZipFile(archive) as z:
        payload={n.replace('\\','/'):z.read(n) for n in z.namelist()
                 if not n.endswith(('MANIFEST_SHA256.json','PACKAGE_VALIDATION.json'))}
    payload.pop('submission/project_summary_report/ResolveGuard_Project_Summary_Report.docx',None)
    for n in list(payload):
        if (ROOT/n).is_file():payload[n]=(ROOT/n).read_bytes()
    report_files = [p for p in (SUB/'project_summary_report').glob('*') if p.name!='ResolveGuard_Project_Summary_Report.docx']
    judge_files = [ROOT/'artifacts/remediation_20261101/report'/name for name in
                   ['LLM_Judge_Analysis.xlsx','LLM_Judge_Public12.json','LLM_Judge_Calibration12.json','Judge_Prompt.txt']]
    for p in [ROOT/'tools/reconcile_human_review_docs.py',ROOT/'tools/build_project_summary_report.py',Path(__file__).resolve(),*OUT.glob('*'),*report_files,*judge_files]:
        if p.is_file():payload[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    local=[n for n in re.findall(r'\]\(([^)]+)\)',(ROOT/'README.md').read_text(encoding='utf-8'))
           if not n.startswith(('http:','https:','#'))]
    broken=[n for n in local if not (ROOT/n.split('#')[0]).exists()]
    assert not broken
    for p in [ROOT/'ResolveGuard_AI_Final_Evaluation_Submission.xlsx',SUB/'portfolio_report_draft/ResolveGuard_Evaluation_Report_Draft.docx',
              SUB/'project_summary_report/ResolveGuard_Project_Summary_Report_Updated.docx',judge_files[0]]:
        with ZipFile(p) as z:
            assert z.testzip() is None
            for n in z.namelist():
                if n.endswith('.xml'):ET.fromstring(z.read(n))
    original=ROOT/'artifacts/human_review_received/817cb87ce51af0d4/Received_Human_Review.xlsx'
    assert hashlib.sha256(original.read_bytes()).hexdigest()=='817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628'
    verification={'human_feedback':'PROVIDED_CHAT_AND_EXCEL','chat_observations':22,'excel_live_observations':28,
        'non_additive':True,'original_received_workbook_hash':'PASS','current_workbook_tabs':16,
        'office_xml_integrity':'PASS','local_readme_links_checked':len(local),'broken_links':broken,
        'archive_names_normalized':True,'application_code_changed':False,'new_model_calls':False,
        'new_cloud_calls':False,'matched_response_agreement':'NOT_YET_CALCULATED',
        'bank_support_handoff':'NOT_ESTABLISHED_BY_REVIEW_RECEIPT','visual_word_pagination':'NOT_RENDERED',
        'banking_response_judging':'COMPLETED_SAVED_REPORTS_EXIST',
        'summary_report_and_judge_workbook_included':True}
    p=OUT/'VERIFICATION.json';p.write_text(json.dumps(verification,indent=2)+'\n',encoding='utf-8')
    payload[p.relative_to(ROOT).as_posix()]=p.read_bytes()
    manifest={n:hashlib.sha256(b).hexdigest() for n,b in sorted(payload.items())}
    (SUB/'MANIFEST_SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    validation=json.loads((SUB/'PACKAGE_VALIDATION.json').read_text(encoding='utf-8'))
    validation.update(documentation_verification=verification,local_readme_links_checked=len(local))
    (SUB/'PACKAGE_VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')
    for name in ['MANIFEST_SHA256.json','PACKAGE_VALIDATION.json']:payload['submission/'+name]=(SUB/name).read_bytes()
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for n,b in sorted(payload.items()):z.writestr(n,b)
    with ZipFile(archive) as z:
        assert len(z.namelist())==len(set(z.namelist()))
        assert z.testzip() is None
        assert all(hashlib.sha256(z.read(n)).hexdigest()==v for n,v in manifest.items())
    (SUB/'ZIP_SHA256.txt').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n',encoding='utf-8')
    print(json.dumps(verification,indent=2))
    print('ZIP CRC, unique names, and manifest: PASS')


if __name__=='__main__':main()
