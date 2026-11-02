"""Build the final evidence-backed report and figures without agent execution."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
from collections import Counter
import hashlib
import os
import json
import re
from PIL import Image, ImageDraw, ImageFont
from tools.build_project_summary_report import W, R, element, paragraph, table

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'submission/final_project_summary'
ASSETS=OUT/'assets'


def font(size,bold=False):
    return ImageFont.truetype('C:/Windows/Fonts/'+('segoeuib.ttf' if bold else 'segoeui.ttf'),size)


def label(draw,xy,text,size=27,fill='#163D43',bold=False):
    x,y=xy
    for line in text.split('\n'):
        bounds=draw.textbbox((0,0),line,font=font(size,bold))
        draw.text((x-(bounds[2]-bounds[0])/2,y),line,font=font(size,bold),fill=fill)
        y+=size+7


def figures():
    ASSETS.mkdir(parents=True,exist_ok=True)
    im=Image.new('RGB',(1400,560),'white');d=ImageDraw.Draw(im)
    def box(rect,text,fill='#EDF5F3',size=27):
        d.rounded_rectangle(rect,18,fill=fill,outline='#176B63',width=3)
        lines=text.count('\n')+1
        label(d,((rect[0]+rect[2])/2,(rect[1]+rect[3]-(size+7)*lines)/2),text,size)
    def arrow(points):
        d.line(points,fill='#176B63',width=4)
        x,y=points[-1];px,py=points[-2]
        if abs(x-px)>abs(y-py):d.polygon([(x,y),(x-12,y-7),(x-12,y+7)],fill='#176B63')
        else:d.polygon([(x,y),(x-7,y-12),(x+7,y-12)],fill='#176B63')
    box((15,165,210,270),'Customer\nchat')
    box((265,165,490,270),'Intent +\nsafety routing')
    box((550,35,925,155),'Public policy search\nBank / product / date')
    box((550,290,925,410),'Sign-in + authorization\nScoped synthetic tools')
    box((1000,165,1380,285),'Evidence checks\nOptional model framing\nPre-send QA + reply',size=26)
    arrow([(210,217),(265,217)])
    arrow([(490,217),(520,217),(520,95),(550,95)])
    arrow([(490,217),(520,217),(520,350),(550,350)])
    arrow([(925,95),(960,95),(960,215),(1000,215)])
    arrow([(925,350),(960,350),(960,245),(1000,245)])
    box((1000,355,1380,445),'Resolution / handoff\nVerified next steps')
    arrow([(1190,285),(1190,355)])
    d.rounded_rectangle((20,480,1380,550),12,fill='#EEF0F6')
    label(d,(700,493),'Post-session QA + local traces observe outcomes; urgent theft has a separate deterministic path.',24)
    im.save(ASSETS/'architecture.png')
    im=Image.new('RGB',(1400,250),'white');d=ImageDraw.Draw(im)
    names=['Golden cases','Baseline','Find mistakes','Group failures','Improve','Retest','Human review','Regression']
    for i,name in enumerate(names):
        row=i//4;col=i%4;x=col*345+15;y=row*125+12
        d.rounded_rectangle((x,y,x+305,y+92),12,fill='#EDF5F3',outline='#176B63',width=2)
        label(d,(x+152,y+27),name,28)
        if col<3:
            d.line((x+310,y+46,x+335,y+46),fill='#176B63',width=3)
            d.polygon([(x+335,y+46),(x+325,y+40),(x+325,y+52)],fill='#176B63')
    im.save(ASSETS/'lifecycle.png')
    im=Image.new('RGB',(1400,340),'white');d=ImageDraw.Draw(im)
    for i,(name,a,b) in enumerate([('Intent accuracy',85,100),('Journey pass',80,97.5),('Fraud recall',80,100)]):
        y=45+i*90;d.text((12,y+10),name,font=font(29),fill='#163D43')
        for offset,val,color in [(0,a,'#8799A3'),(34,b,'#176B63')]:
            d.rounded_rectangle((355,y+offset,355+val*8.4,y+offset+25),5,fill=color)
            d.text((370+val*8.4,y+offset-7),str(val)+'%',font=font(27,True),fill='#163D43')
    d.text((355,0),'Initial mock rules',font=font(25),fill='#697B85')
    d.text((700,0),'Improved mock rules',font=font(25),fill='#176B63')
    im.save(ASSETS/'scorecard.png')


def picture(body,key,index):
    dimensions={'architecture':(1400,560),'lifecycle':(1400,250),'scorecard':(1400,340)}
    width,height=dimensions[key];cx=6250000;cy=int(cx*height/width)
    p=element(body,'p');element(element(p,'pPr'),'jc',{'val':'center'})
    run=element(p,'r');drawing=ET.SubElement(run,'{'+W+'}drawing')
    xml=f'''<wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" xmlns:r="{R}" distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{index}" name="{key}" descr="{key} diagram based on implemented workflow and saved evaluation evidence"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="{key}.png"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rIdFigure{index}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline>'''
    drawing.append(ET.fromstring(xml))


def evidence_register():
    entries=[
      ('E1','Historical metrics and RG-020 before/after','artifacts/mock_iterations_final/comparison.json','experiments v0-v4; RG-020 repeat 0 in v0/v4/results.json','Verified saved evidence','Mock rules, development set; no recovered historical checkout'),
      ('E2','Current tests and Original100','artifacts/remediation_20261101/Status_Summary.json','main_tests; fixtures_passed; original100_final/summary.json','Verified saved outputs','Not rerun; source/provenance qualification remains open'),
      ('E3','BOW100 and 100 case trace links','artifacts/remediation_20261101/bow100_release/summary.json','cases_executed, passed, trace_coverage; sibling results/traces','Verified local result','100 case bundles, not universal answer-quality validation'),
      ('E4','RAGAS and 12 public judge grades','artifacts/local_completion/semantic_expanded_final.json','rows[*].ragas; rows[*].judge; quality_review_flags','Verified; means recomputed','11 exact-input results retained; one corrected binding remeasured; two low faithfulness flags'),
      ('E5','Completed banking judge and prompt','artifacts/remediation_20261101/report/LLM_Judge_Analysis.xlsx','00 Summary, 01 Public Policy 12, 02 Calibration 12, 03 Judge Prompt; companion JSONs','Verified; JSON copies match canonical outputs','One model; not calibrated human agreement or compliance certification'),
      ('E6','Chat human feedback receipt','artifacts/human_feedback_20261101_batch02/Review_Summary.json','22 observations: 14 PASS, 6 FAIL, 2 PARTIAL_PASS','Received and recorded','Overlaps later review; no complete original browser state'),
      ('E7','Excel review and no-disclosure clarification','artifacts/human_review_received/817cb87ce51af0d4/Clarified_Review_Analysis.json','combined_marks; review_target; user_statement_case_access; Received_Human_Review.xlsx','Received and clarified','Live app, different saved judge answers; no agreement calculation'),
      ('E8','Implemented architecture and boundaries','resolveguard/workflow.py','Conversation/workflow nodes; web.py, bow_knowledge.py, customer_review.py, reply_generation.py','Code reviewed','Public path is direct Python; not every service is a model agent'),
      ('E9','Active synthetic BOW dataset','data/bow/active.json','Versioned snapshot referenced by active.json; bow_data.py validation','Verified source snapshot','Fictional policies, dates and test-only approval'),
      ('E10','16 source-contract contradictions','artifacts/remediation_20261101/Proposed_Reference_Corrections.json','10 get_transaction, 6 get_case_status; 16 human_decision=PENDING','Verified counts','Suggested denial semantics are proposals, not approved labels'),
      ('E11','Handout comparison and calibration limits','artifacts/remediation_20261101/calibration_status.json','human_model_pairs=0; agreement=null; feedback receipt overlay','Verified; handout read locally','Handout needs prompt edit / hosted traces; banking adaptation is separate'),
      ('E12','Submission workbook and saved analysis','ResolveGuard_AI_Final_Evaluation_Submission.xlsx','15 evaluation tabs + receipt; artifacts/week3_agent_evaluation_submission/Evidence_Analysis.ipynb','Existing artifacts verified','Notebook analyzes saved evidence; not a new live experiment'),
      ('E13','Historical screenshot and demo script','demo/screenshots/welcome_historical.png','demo/screenshots/README.md; demo/demo_script.md','Artifact exists; historical provenance retained','No new screenshot or final recorded demo'),
    ]
    lines=['# ResolveGuard Project Evidence Index','','All references are repository-relative. Verification reads saved artifacts and code; it does not rerun model evaluations.','',
      '| ID | Claim | Supporting file | Evidence location | Verified status | Limitation |','| --- | --- | --- | --- | --- | --- |']
    for entry in entries:lines.append('| '+' | '.join(entry)+' |')
    handout=Path(os.environ.get('RESOLVEGUARD_HANDOUT_PATH', ROOT/'data/references/Customer Support Agent Evaluation Project Handout.docx'))
    lines+=['','## Assignment source','',f'Local handout: `{handout.name}`. SHA-256: `{hashlib.sha256(handout.read_bytes()).hexdigest()}`. Read through Word XML; no notebook/model executed.','',
      'The handout requests one focused classifier-prompt edit and hosted LangSmith inspection. The project supplies an explicitly identified banking mock-rule adaptation. Its executed banking response-quality judge is separate from the optional binary failure-category experiment.','',
      '## RG-020 exact trace references','','Baseline: `6c65c356-1274-4e55-93ce-7d15ea774170`. Improved v4: `36be76f0-b74c-4031-b74e-23c070bdcaa3`. Both are embedded in `actual.trace` in the corresponding `artifacts/mock_iterations_final/v0/results.json` and `v4/results.json` rows.','',
      '## Immutable source evidence','','Original returned human workbook SHA-256: `817cb87ce51af0d4429098b0e6ba09931a6e6482f15ab43939c266630856f628`. Source bank hash and current code hashes remain available in the saved suite summaries. No source data, evaluation labels, or application code is modified by report generation.']
    (OUT/'ResolveGuard_Project_Evidence_Index.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return entries


def main():
    figures();entries=evidence_register()
    source=OUT/'ResolveGuard_Final_Project_Summary_Report.md';text=source.read_text(encoding='utf-8')
    template=ROOT/'submission/project_summary_report/ResolveGuard_Project_Summary_Report_Updated.docx'
    with ZipFile(template) as z:parts={n:z.read(n) for n in z.namelist()}
    old=ET.fromstring(parts['word/document.xml']);sect=old.find('{'+W+'}body/{'+W+'}sectPr')
    doc=ET.Element('{'+W+'}document');body=element(doc,'body');lines=text.splitlines();i=0;images=[]
    while i<len(lines):
        line=lines[i].strip()
        if line=='<!-- PAGEBREAK -->':
            p=element(body,'p');element(element(p,'r'),'br',{'type':'page'})
        elif line.startswith('<!-- FIGURE '):
            key=line.split()[2];images.append(key);picture(body,key,len(images))
        elif line.startswith('|'):
            group=[]
            while i<len(lines) and lines[i].strip().startswith('|'):group.append(lines[i]);i+=1
            table(body,group);continue
        elif line.startswith('# '):paragraph(body,line[2:],'Title')
        elif line.startswith('## '):paragraph(body,line[3:],'Heading1')
        elif line.startswith('### '):paragraph(body,line[4:],'Heading2')
        elif line:paragraph(body,line)
        i+=1
    body.append(sect)
    # WordprocessingML requires run properties before text content.
    for run in doc.iter('{'+W+'}r'):
        props=run.find('{'+W+'}rPr')
        if props is not None:
            run.remove(props)
            run.insert(0,props)
    parts['word/document.xml']=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
    relationships=ET.fromstring(parts['word/_rels/document.xml.rels'])
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    for index,key in enumerate(images,1):
        ET.SubElement(relationships,'{'+relns+'}Relationship',{'Id':f'rIdFigure{index}','Type':R+'/image','Target':f'media/{key}.png'})
        parts[f'word/media/{key}.png']=(ASSETS/f'{key}.png').read_bytes()
    parts['word/_rels/document.xml.rels']=ET.tostring(relationships,encoding='utf-8',xml_declaration=True)
    types=ET.fromstring(parts['[Content_Types].xml'])
    ET.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Default',{'Extension':'png','ContentType':'image/png'})
    parts['[Content_Types].xml']=ET.tostring(types,encoding='utf-8',xml_declaration=True)
    delivery=OUT/'delivery'
    delivery.mkdir(exist_ok=True)
    target=delivery/'ResolveGuard_Final_Project_Summary_Report.docx'
    with ZipFile(target,'w',ZIP_DEFLATED) as z:
        for name,data in parts.items():z.writestr(name,data)
    with ZipFile(target) as z:
        assert z.testzip() is None
        for name in z.namelist():
            if name.endswith('.xml'):ET.fromstring(z.read(name))
    # Companion readiness checklist distinguishes delivery, execution, and qualification.
    checks='''# ResolveGuard Submission Readiness Checklist

## Completed evidence tasks

- [x] Historical mock baseline, four focused routing stages, and matched 40-case comparison inspected.
- [x] Numerical results and denominators checked against saved files; no new model calls.
- [x] Current Original100/BOW100 local results and test log inspected; not rerun.
- [x] LLM-as-a-Judge execution and workbook confirmed complete; model and rubric identified.
- [x] RAGAS scores recomputed; low faithfulness flags retained.
- [x] Both human reviews acknowledged without double-counting.
- [x] Source conflicts counted: 10 transaction and six case tool contradictions; decisions pending.
- [x] Seven-page report source, architecture figure, scorecard, failure comparison, and evidence index prepared.
- [x] All nine requested project-link placeholders retained exactly.

## Open qualification and submission items

- [ ] Resolve formal source-contract/provenance approvals; do not substitute live-app PASS marks.
- [ ] Retest two product-context failures and three denial-wording partial passes.
- [ ] Review SEM-003 and SEM-011 faithfulness disagreements.
- [ ] Label exact saved responses before claiming human-judge agreement; second-model comparison not performed.
- [ ] Establish independent holdout and broader live-response evidence before generalizing quality.
- [ ] Record final demo video, publish chosen artifacts, supply verified links, and complete upload.
- [ ] Select a license and verify repository publication.
- [ ] Hosted LangSmith evidence remains unverified/deferred; Replit and real banking deferred separately.

## Document verification

DOCX structural checks passed. See REPORT_VALIDATION.json for the actual Word/PDF render status and final page count; document generation alone is not a render check. Application files, golden data, and saved evaluation outputs are unchanged.

## Changes from the previous report

Reorganized into seven reader-focused pages; defined technical terms in plain language; added one architecture diagram, a small evaluation lifecycle, and a measured scorecard; documented exact RG-020 routes and trace IDs; classified the 16 recorded tool conflicts; kept completed judging separate from pending agreement; added evidence IDs and preserved all specified link placeholders.
'''
    (OUT/'ResolveGuard_Submission_Readiness_Checklist.md').write_text(checks,encoding='utf-8')
    checks={'docx_structure':'PASS','page_breaks':text.count('<!-- PAGEBREAK -->'),'word_count':len(text.split()),'evidence_entries':len(entries),'model_calls':0,'tests_rerun':False,'render_status':'PENDING_WORD_EXPORT'}
    (OUT/'REPORT_VALIDATION.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(checks))


if __name__=='__main__':main()
