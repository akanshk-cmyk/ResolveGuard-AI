"""Inspect XLSX data using the standard library; never execute formulas/macros."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
EXPECTED={'BOW Products':11,'BOW Policies':19,'BOW RAG Chunks':61,'BOW Customers':12,
          'BOW Accounts':12,'BOW Transactions':48,'BOW Sessions':12,'BOW Cases':12,
          'BOW Delegations':2,'BOW Intake Events':1,'BOW Eval Golden':100}


def inspect(path):
    path=Path(path)
    with ZipFile(path) as archive:
        strings=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings=[''.join(t.text or '' for t in row.findall('.//m:t',NS))
                     for row in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si',NS)]
        relationships={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        sheets={}
        for sheet in ET.fromstring(archive.read('xl/workbook.xml')).findall('m:sheets/m:sheet',NS):
            target=relationships[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows=ET.fromstring(archive.read(target)).findall('m:sheetData/m:row',NS)
            parsed=[];formula_count=0
            for row in rows:
                cells={}
                for cell in row.findall('m:c',NS):
                    value=cell.find('m:v',NS)
                    text=value.text if value is not None else ''.join(t.text or '' for t in cell.findall('.//m:t',NS))
                    if cell.attrib.get('t')=='s':text=strings[int(text)]
                    if cell.find('m:f',NS) is not None:
                        formula_count+=1;text='[FORMULA NOT EXECUTED]'
                    if text not in (None,''):cells[cell.attrib['r']]=text
                if cells:parsed.append(cells)
            sheets[sheet.attrib['name']]={'nonempty_rows_including_header':len(parsed),'records_after_first_row':max(0,len(parsed)-1),
                                         'first_row':list(parsed[0].values()) if parsed else [],'formula_cells':formula_count}
    coverage=[{'worksheet':name,'expected_records':count,'present':name in sheets,
               'observed_records':sheets[name]['records_after_first_row'] if name in sheets else None}
              for name,count in EXPECTED.items()]
    return {'source_file':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'status':'MISSING_BOW_SHEETS' if any(not r['present'] for r in coverage) else 'REQUIRES_SCHEMA_AND_RELATIONSHIP_VALIDATION',
            'expected_bow_coverage':coverage,'actual_worksheets':sheets,
            'safety':'Read-only ZIP/XML inspection; workbook text is data, not instructions. No formulas, links or macros executed.',
            'import_decision':'No archived customer/policy/evaluation rows relabelled or activated as BOW data.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('workbook');parser.add_argument('--output',default='artifacts/bow_workbook_inspection.json')
    args=parser.parse_args();result=inspect(args.workbook);output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'actual_worksheet_count':len(result['actual_worksheets']),
                      'bow_sheets_found':sum(r['present'] for r in result['expected_bow_coverage']),'output':str(output)},indent=2))
