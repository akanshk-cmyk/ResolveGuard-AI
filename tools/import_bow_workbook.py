"""Import only named BOW worksheets; preserve source bytes and archive separation."""
import argparse
from collections import Counter
from datetime import datetime,timedelta,timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.inspect_bow_workbook import EXPECTED,NS

ROOT=Path(__file__).resolve().parents[1]
NAMES={'BOW Products':'products','BOW Policies':'policies','BOW RAG Chunks':'chunks','BOW Customers':'customers',
       'BOW Accounts':'accounts','BOW Transactions':'transactions','BOW Sessions':'sessions','BOW Cases':'cases',
       'BOW Delegations':'delegations','BOW Intake Events':'intake_events','BOW Eval Golden':'evaluations'}


def read_rows(path):
    result={};lineage={}
    with ZipFile(path) as z:
        strings=[''.join(t.text or '' for t in row.findall('.//m:t',NS)) for row in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)] if 'xl/sharedStrings.xml' in z.namelist() else []
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        props=wb.find('m:workbookPr',NS)
        base=datetime(1904,1,1,tzinfo=timezone.utc) if props is not None and props.attrib.get('date1904') in ('1','true') else datetime(1899,12,30,tzinfo=timezone.utc)
        rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in wb.findall('m:sheets/m:sheet',NS):
            if sheet.attrib['name'] not in NAMES:continue
            name=NAMES[sheet.attrib['name']]
            target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows=ET.fromstring(z.read(target)).findall('m:sheetData/m:row',NS)
            headers=None;records=[];source_rows=[]
            for row in rows:
                values={}
                for cell in row.findall('m:c',NS):
                    if cell.find('m:f',NS) is not None:raise ValueError('Formula in BOW source data; not executed or imported')
                    column=''.join(c for c in cell.attrib['r'] if c.isalpha())
                    v=cell.find('m:v',NS);text=v.text if v is not None else ''.join(t.text or '' for t in cell.findall('.//m:t',NS))
                    if cell.attrib.get('t')=='s':text=strings[int(text)]
                    if cell.attrib.get('t')=='b':text=text=='1'
                    values[column]=text
                if not any(v not in (None,'') for v in values.values()):continue
                if headers is None:
                    headers={c:v for c,v in values.items() if v}
                    if len(set(headers.values()))!=len(headers):raise ValueError('Duplicate headers')
                    continue
                record={field:values.get(column) for column,field in headers.items()}
                for key,value in list(record.items()):
                    if value in (None,''):
                        record[key]=None
                    elif key in ('amount_cents','monthly_fee_cents_or_annual_card_fee_cents'):
                        number=Decimal(str(value))
                        if number!=number.to_integral_value():raise ValueError('Fractional cents')
                        record[key]=int(number)
                    elif key in ('synthetic','authenticated'):
                        if type(value) is bool:continue
                        if str(value).lower() not in ('true','false','1','0'):raise ValueError('Invalid boolean')
                        record[key]=str(value).lower() in ('true','1')
                    elif key in ('expires_at','created_at','captured_at'):
                        try:
                            microseconds=int((Decimal(str(value))*Decimal(86400000000)).to_integral_value())
                            dt=base+timedelta(microseconds=microseconds)
                        except Exception:
                            dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
                            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
                        record[key]=dt.isoformat()
                    else:record[key]=str(value)
                records.append(record);source_rows.append({'worksheet':sheet.attrib['name'],'row':int(row.attrib['r'])})
            if len(records)!=EXPECTED[sheet.attrib['name']]:raise ValueError('Unexpected record count: '+sheet.attrib['name'])
            result[name]=records;lineage[name]=source_rows
    if set(result)!=set(NAMES.values()):raise ValueError('Required BOW worksheet missing; archive worksheets are not substitutes')
    return result,lineage


def validate(data):
    from resolveguard.bow_data import validate_dataset
    validate_dataset(data)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('workbook');args=parser.parse_args()
    source=Path(args.workbook);digest=hashlib.sha256(source.read_bytes()).hexdigest()
    data,lineage=read_rows(source);validate(data)
    target=ROOT/'data/bow'/digest;target.mkdir(parents=True,exist_ok=True)
    def immutable_write(path,text):
        encoded=text.encode('utf-8')
        if path.exists():
            if path.read_text(encoding='utf-8')!=text:raise ValueError('Existing source snapshot differs; do not overwrite active evidence')
        else:path.write_bytes(encoded)
    for name,records in data.items():
        immutable_write(target/(name+'.json'),json.dumps(records,indent=2,ensure_ascii=False)+'\n')
    if (target/'source.xlsx').exists():
        if hashlib.sha256((target/'source.xlsx').read_bytes()).hexdigest()!=digest:raise ValueError('Existing workbook snapshot hash mismatch')
    else:shutil.copy2(source,target/'source.xlsx')
    manifest={'source_file':source.name,'source_sha256':digest,'bank_id':'BOW','counts':{k:len(v) for k,v in data.items()},
       'data_sha256':{name:hashlib.sha256((target/(name+'.json')).read_bytes()).hexdigest() for name in data},
       'lineage':lineage,'archive_worksheets':'Not activated or merged; preserved in the exact XLSX source copy.',
       'formula_policy':'No formulas/macros/links executed; formula cells in imported tables are rejected.',
       'timestamp_assumption':'Excel serial timestamps and timezone-less expiry dates are interpreted as UTC for this synthetic demo; original source bytes are preserved.',
       'evaluation_status':'100 source scenarios imported as NOT_RUN. The Golden worksheet name is not human approval or proof of execution.',
       'approval':'SYNTHETIC_APPROVED_FOR_TEST_ONLY is a fictional test label, not institution approval.',
       'evaluation_categories':dict(Counter(r['category'] for r in data['evaluations']))}
    immutable_write(target/'manifest.json',json.dumps(manifest,indent=2)+'\n')
    pointer=ROOT/'data/bow/active.json';temporary=pointer.with_suffix('.tmp')
    temporary.write_text(json.dumps({'bank_id':'BOW','source_sha256':digest},indent=2)+'\n',encoding='utf-8');temporary.replace(pointer)
    print(json.dumps({'active_directory':str(target),'counts':manifest['counts'],'status':'VALIDATED_SYNTHETIC_IMPORT'},indent=2))


if __name__=='__main__':main()
