"""Generate the project summary Word document using standard-library OOXML."""
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED
from html import escape
import json
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'submission/project_summary_report'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
ET.register_namespace('w',W)
ET.register_namespace('r',R)


def element(parent,name,attrs=None,text=None):
    el=ET.SubElement(parent,'{'+W+'}'+name,{'{'+W+'}'+k:str(v) for k,v in (attrs or {}).items()})
    if text is not None:el.text=text
    return el


def paragraph(parent,text='',style=None):
    p=element(parent,'p')
    if style:element(element(p,'pPr'),'pStyle',{'val':style})
    run=element(p,'r');t=element(run,'t',text=text.replace('`',''))
    t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    return p


def table(parent,lines):
    rows=[[v.strip() for v in line.strip().strip('|').split('|')] for line in lines]
    rows=[r for r in rows if not all(re.fullmatch(r':?-+:?',c) for c in r)]
    tbl=element(parent,'tbl');pr=element(tbl,'tblPr')
    element(pr,'tblW',{'w':'5000','type':'pct'})
    borders=element(pr,'tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        element(borders,edge,{'val':'single','sz':4,'color':'D5DFE1'})
    margins=element(pr,'tblCellMar')
    for side in ['top','left','bottom','right']:element(margins,side,{'w':65,'type':'dxa'})
    for i,row in enumerate(rows):
        tr=element(tbl,'tr');props=element(tr,'trPr');element(props,'cantSplit')
        if i==0:element(props,'tblHeader')
        for value in row:
            tc=element(tr,'tc');tcp=element(tc,'tcPr')
            if i==0:element(tcp,'shd',{'fill':'E7F1EF','val':'clear'})
            p=paragraph(tc,value,'TableText')
            if i==0:element(element(p.find('{'+W+'}r'),'rPr'),'b')
    paragraph(parent)


def main():
    source=OUT/'ResolveGuard_Project_Summary_Report.md';text=source.read_text(encoding='utf-8')
    doc=ET.Element('{'+W+'}document');body=element(doc,'body');lines=text.splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if line=='<!-- PAGEBREAK -->':
            p=element(body,'p');element(element(p,'r'),'br',{'type':'page'})
        elif line.startswith('|'):
            group=[]
            while i<len(lines) and lines[i].strip().startswith('|'):group.append(lines[i]);i+=1
            table(body,group);continue
        elif line.startswith('# '):paragraph(body,line[2:],'Title')
        elif line.startswith('## '):paragraph(body,line[3:],'Heading1')
        elif line.startswith('### '):paragraph(body,line[4:],'Heading2')
        elif line:paragraph(body,line)
        i+=1
    sect=element(body,'sectPr')
    element(sect,'headerReference',{'type':'default'}).set('{'+R+'}id','rIdHeader')
    element(sect,'footerReference',{'type':'default'}).set('{'+R+'}id','rIdFooter')
    element(sect,'pgSz',{'w':11906,'h':16838})
    element(sect,'pgMar',{'top':800,'right':850,'bottom':800,'left':850,'header':350,'footer':350})
    styles=f'''<w:styles xmlns:w="{W}"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="20"/><w:color w:val="243B45"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="90" w:line="240" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style><w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:keepNext/><w:spacing w:after="180"/></w:pPr><w:rPr><w:b/><w:sz w:val="34"/><w:color w:val="176B63"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:spacing w:before="140" w:after="90"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="25"/><w:color w:val="176B63"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:keepNext/><w:spacing w:before="100" w:after="70"/></w:pPr><w:rPr><w:b/><w:sz w:val="21"/></w:rPr></w:style><w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:pPr><w:spacing w:after="35" w:line="220" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="18"/></w:rPr></w:style></w:styles>'''
    header=ET.Element('{'+W+'}hdr');paragraph(header,'RESOLVEGUARD AI  |  PROJECT SUMMARY  |  SYNTHETIC BANKING')
    footer=ET.Element('{'+W+'}ftr');p=paragraph(footer,'Evidence snapshot: November 1, 2026  |  Page ')
    field=element(p,'fldSimple',{'instr':'PAGE'});element(element(field,'r'),'t',text='1')
    content='''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'''
    for name,kind in [('document','document.main'),('styles','styles'),('header1','header'),('footer1','footer')]:
        content+=f'<Override PartName="/word/{name}.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml"/>'
    content+='</Types>'
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    relationships=f'<Relationships xmlns="{relns}">'
    for ident,kind,target in [('rIdStyles','styles','styles.xml'),('rIdHeader','header','header1.xml'),('rIdFooter','footer','footer1.xml')]:relationships+=f'<Relationship Id="{ident}" Type="{R}/{kind}" Target="{target}"/>'
    relationships+='</Relationships>'
    parts={'[Content_Types].xml':content.encode(),'_rels/.rels':f'<Relationships xmlns="{relns}"><Relationship Id="rId1" Type="{R}/officeDocument" Target="word/document.xml"/></Relationships>'.encode(),
        'word/document.xml':ET.tostring(doc,encoding='utf-8',xml_declaration=True),'word/styles.xml':styles.encode(),
        'word/_rels/document.xml.rels':relationships.encode(),
        'word/header1.xml':ET.tostring(header,encoding='utf-8',xml_declaration=True),
        'word/footer1.xml':ET.tostring(footer,encoding='utf-8',xml_declaration=True)}
    target=source.with_name('ResolveGuard_Project_Summary_Report_Updated.docx')
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items():z.writestr(n,b)
    with ZipFile(target) as z:
        assert z.testzip() is None
        for n in z.namelist():ET.fromstring(z.read(n))
        xml=ET.fromstring(z.read('word/document.xml'))
        alltext=' '.join(t.text or '' for t in xml.iter('{'+W+'}t'))
        assert all(f'{n}. ' in alltext for n in range(1,14))
        assert '[Insert GitHub Repository Link]' in alltext
        assert 'HR-CHAT-22' in alltext and 'HR-XLSX-28' in alltext
        assert 'https://' not in alltext
    from markdown_it import MarkdownIt
    (OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>ResolveGuard Project Summary Report</title><style>body{font:16px/1.6 system-ui;max-width:1080px;margin:30px auto;padding:20px}td,th{border:1px solid #ddd;padding:7px}table{border-collapse:collapse}h2{color:#176b63}</style><p><a href="'+target.name+'">Download updated Word report</a></p>'+MarkdownIt('commonmark').enable('table').render(text)+'</html>',encoding='utf-8')
    validation={'file':target.name,'zip_crc':'PASS','all_xml':'PASS','required_sections':13,
        'link_placeholders_preserved':True,'both_human_reviews_acknowledged':True,'explicit_page_breaks':text.count('<!-- PAGEBREAK -->'),
        'pagination':'Not rendered in Word; final page count may vary','new_evaluation_calls':False}
    (OUT/'VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(validation,indent=2))


if __name__=='__main__':main()
