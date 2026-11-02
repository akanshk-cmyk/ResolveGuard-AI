"""Select 40 unchanged workbook prompts and create explicit draft fixture bindings.

Standard library only. This never claims human review or known authorship.
"""
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT/'ResolveGuard_AI_Comprehensive_Evals_v0.4_Risk_Remediated.xlsx'
N = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
     'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def read_sheet(path, name):
    with ZipFile(path) as z:
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        sheet = next(s for s in wb.findall('m:sheets/m:sheet', N) if s.attrib['name'] == name)
        rid = sheet.attrib['{'+N['r']+'}id']
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target = next(r.attrib['Target'] for r in rels if r.attrib['Id'] == rid)
        target = target.lstrip('/') if target.startswith('/') else 'xl/'+target
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rows = []
        for row in ET.fromstring(z.read(target)).findall('m:sheetData/m:row', N):
            result = {}
            for cell in row:
                col = ''.join(c for c in cell.attrib['r'] if c.isalpha())
                v = cell.find('m:v', N)
                value = v.text if v is not None else ''
                if cell.attrib.get('t') == 's':
                    value = strings[int(value)]
                elif cell.attrib.get('t') == 'inlineStr':
                    value = ''.join(t.text or '' for t in cell.findall('.//m:t', N))
                result[col] = value
            rows.append(result)
        return rows


def prepare():
    target = ROOT/'data'
    target.mkdir(exist_ok=True)
    review_path = target/'review_40.csv'
    if review_path.exists():
        with review_path.open(encoding='utf-8-sig',newline='') as handle:
            if any(r.get('human_review_status','PENDING') != 'PENDING' or r.get('reviewer')
                   or r.get('review_notes') for r in csv.DictReader(handle)):
                raise ValueError('Existing review annotations would be overwritten; create a new dataset version instead')
    prompts = {row['A']: row['B'] for row in read_sheet(WORKBOOK, '1_Golden Dataset')[1:]}
    source = json.loads((ROOT/'resolveguard_demo_baseline/expected_evaluations_100.json').read_text())
    contracts = {c['TEST_ID']: c for c in source['cases']}
    groups = {
        'happy_path': [1,2,6,7,8,9,10,11,12,13,14,15,16,17,18,66,71,76,80,86],
        'edge': [19,20,27,32,33,39,61,62,68,79,87,95],
        'anticipated_failure': [46,48,50,53,98,100],
        'adversarial': [54,56],
    }
    tx = {1:'TXN-DEMO-FEE',2:'TXN-DEMO-ATM',10:'TXN-DEMO-85',11:'TXN-DEMO-63',
          12:'TXN-001-01',13:'TXN-DEMO-ABC',19:'TXN-DEMO-450',20:'TXN-001-02',
          27:'TXN-001-01',32:'TXN-001-01',33:'TXN-001-02',39:'TXN-002-01',
          61:'TXN-001-01',62:'TXN-001-01',79:'TXN-001-01',80:'TXN-001-01',
          87:'TXN-001-01',46:'TXN-DEMO-63',98:'TXN-001-01',54:'TXN-002-01'}
    cases = {14:'CASE-A101',15:'CASE-A102',16:'CASE-A103',66:'CASE-001',
             71:'CASE-002',76:'CASE-002',95:'CASE-001'}
    session = {39:'SESS-ANON',61:'SESS-EXPIRED',62:'SESS-REVOKED',
               66:'SESS-STEPUP',71:'SESS-REP',76:'SESS-POA',79:'SESS-ANON'}
    policy = {1:['POL-FEE-001'],2:['POL-DEMO-ATM'],6:['POL-FEE-001'],7:['POL-DEMO-LIMIT'],
              8:['POL-DEMO-OVERDRAFT'],9:['POL-DEMO-ATM'],56:['POL-PRIV-002']}
    faults = {46:{'transaction_timeout':True},48:{'case_timeout':True},
              53:{'primary_queue_down':True},95:{'receiver_fields':['case_id']},
              98:{'primary_queue_down':True},100:{'handoff_status_query':True}}
    equivalents = {'INTAKE_PENDING':['CAPTURED_REVIEW'], 'VERIFICATION_REQUIRED':['AUTH_REQUIRED'],
                   'VERIFIED_STATUS':['NO_ACTION'], 'URGENT_HANDOFF':['CAPTURED_REVIEW'],
                   'URGENT_FALLBACK':['CAPTURED_REVIEW']}
    digest = hashlib.sha256(WORKBOOK.read_bytes()).hexdigest()
    rows = []
    for scenario_type, numbers in groups.items():
        for number in numbers:
            case_id = f'RG-{number:03}'
            c = contracts[case_id]
            inputs = {'message':prompts[case_id], 'session_id':session.get(number,'SESS-001'),
                      'request_key':'request-'+case_id, 'transaction_ids':[tx[number]] if number in tx else [],
                      'case_id':cases.get(number), 'account_id':'ACC-001' if number in (17,18,48,50) else None,
                      'confirmed':number in (17,18,48,50),
                      'product':'CHECKING' if number in (1,2,6,8,9) else 'DEBIT_CHECKING'}
            if number == 86:
                inputs['transaction_ids'] = ['TXN-001-01','TXN-001-02']
            human = number in (32,33,53,95)
            fraud = c['Fraud_Error_Flag'] == 'Y'
            require_handoff = number in (19,20,32,33,53,87,95,98)
            expected_handoff = {53:'UNAVAILABLE',100:'DELIVERY_UNKNOWN'}.get(number,
                                      'ACKNOWLEDGED' if require_handoff else None)
            rows.append({
                'case_id':case_id, 'inputs':inputs, 'faults':faults.get(number,{}),
                'repeat_requests':2 if number == 50 else 1,
                'expected':{'primary_intent':c['Expected_Intent'], 'fraud_flag':fraud,
                            'human_requested':human, 'report_capture_required':fraud,
                            'restricted_read_denied':number in (39,61,62,54),
                            'required_transaction_ids':inputs['transaction_ids'] if number in (1,2,10,11,12,13) else [],
                            'required_case_id':cases.get(number) if number in (14,15,16,66,71,76) else None,
                            'case_commit_required':number in (17,18,50),
                            'case_must_remain_unknown':number==48,
                            'handoff_status':expected_handoff, 'alternate_route_required':number==98,
                            'policy_doc_ids_any':policy.get(number,[]),
                            'allowed_response_states':equivalents.get(c['Expected_Response_State'],[c['Expected_Response_State']])},
                'source_contract':c,
                'metadata':{'scenario_type':scenario_type,'severity':c['Severity'],
                            'source_workbook':WORKBOOK.name,'source_workbook_sha256':digest,
                            'source_sheet':'1_Golden Dataset','source_case_id':case_id,
                            'prompt_transformation':'none; exact supplied workbook text',
                            'prompt_origin':'supplied_synthetic_authorship_unverified',
                            'binding_origin':'AI-authored fixture mapping and expected assertions',
                            'failure_status':'anticipated_not_observed' if scenario_type=='anticipated_failure' else 'not_yet_executed',
                            'human_review_status':'PENDING','reviewer':None,'review_notes':'',
                            'selection_note':'Balanced teaching subset; not a production prevalence estimate',
                            'binding_note':'Concrete synthetic selectors supplied by trusted harness; no expected labels enter model inputs'},
            })
    assert len(rows) == 40 and len({r['case_id'] for r in rows}) == 40
    data = {'dataset_version':'resolveguard-40-draft-v1','qualification_status':'DRAFT_REQUIRES_HUMAN_REVIEW',
            'provenance_status':'LLM-generated share unknown; instructor limit cannot be attested',
            'scenario_counts':dict(Counter(r['metadata']['scenario_type'] for r in rows)),
            'state_mapping_note':'Original response states retained in source_contract. Canonical demo equivalents are explicit expected assertions, pending review.',
            'cases':rows}
    (target/'evaluation_40.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (target/'review_40.csv').open('w',newline='',encoding='utf-8-sig') as handle:
        fields=['case_id','scenario_type','prompt','expected_intent','expected_behavior',
                'expected_assertions','fixture_inputs','faults','prompt_origin','provenance_notes',
                'human_review_status','reviewer','review_notes']
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for r in rows:
            writer.writerow({'case_id':r['case_id'],'scenario_type':r['metadata']['scenario_type'],
                             'prompt':r['inputs']['message'],'expected_intent':r['expected']['primary_intent'],
                             'expected_behavior':r['source_contract']['Expected_Behavior'],
                             'expected_assertions':json.dumps(r['expected'],ensure_ascii=False),
                             'fixture_inputs':json.dumps(r['inputs'],ensure_ascii=False),
                             'faults':json.dumps(r['faults']),
                             'prompt_origin':r['metadata']['prompt_origin'],'human_review_status':'PENDING',
                             'provenance_notes':'','reviewer':'','review_notes':''})
    print('Prepared 40 draft cases: '+json.dumps(data['scenario_counts'])+'. Human review and provenance attestation remain pending.')


if __name__ == '__main__':
    prepare()
