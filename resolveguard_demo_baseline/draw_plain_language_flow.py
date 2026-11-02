"""Create a plain-language, end-to-end ResolveGuard design diagram."""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W,H = 2800,2850
im = Image.new('RGB',(W,H),'white')
d = ImageDraw.Draw(im)
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">','<rect width="100%" height="100%" fill="white"/>']
INK,MUTED,BORDER='#192431','#566579','#cad4df'
TEAL,BLUE,GOLD,PURPLE='#087b77','#2f649b','#97701a','#7055bf'
overflow=[]

def font(size,bold=False):
    return ImageFont.truetype(str(Path('C:/Windows/Fonts')/('arialbd.ttf' if bold else 'arial.ttf')),size)

def rect(x,y,w,h,fill='white',stroke=BORDER,width=2):
    d.rounded_rectangle((x,y,x+w,y+h),18,fill=fill,outline=stroke,width=width)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

def text(x,y,value,size=23,color=MUTED,bold=False):
    d.text((x,y),value,font=font(size,bold),fill=color)
    svg.append(f'<text x="{x}" y="{y+size}" font-family="Arial,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{escape(value)}</text>')

def box(x,y,w,h,title,lines,stroke=BORDER,fill='white',body=23,title_size=27):
    rect(x,y,w,h,fill,stroke)
    text(x+22,y+18,title,title_size,INK,True)
    for i,line in enumerate(lines):text(x+22,y+63+33*i,line,body)
    for line,size,bold in [(title,title_size,True)]+[(v,body,False) for v in lines]:
        if d.textbbox((0,0),line,font=font(size,bold))[2]>w-42:overflow.append(line)
    if lines and 63+33*(len(lines)-1)+body>h-12:overflow.append('height: '+title)

def arrow(points,color=TEAL,dashed=False):
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];n=(dx*dx+dy*dy)**.5
        if not dashed:d.line((*a,*b),fill=color,width=3)
        else:
            for k in range(0,int(n),16):
                z=min(k+9,n);d.line((a[0]+dx*k/n,a[1]+dy*k/n,a[0]+dx*z/n,a[1]+dy*z/n),fill=color,width=3)
    a,b=points[-2:];dx,dy=b[0]-a[0],b[1]-a[1];n=(dx*dx+dy*dy)**.5;ux,uy=dx/n,dy/n
    tri=[b,(b[0]-16*ux-7*uy,b[1]-16*uy+7*ux),(b[0]-16*ux+7*uy,b[1]-16*uy-7*ux)]
    d.polygon(tri,fill=color)
    dash='stroke-dasharray="9 7"' if dashed else ''
    svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{color}" stroke-width="3" {dash}/>')
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in tri)}" fill="{color}"/>')

rect(1,1,W-2,H-2)
text(40,24,'ResolveGuard | Follow the data from source to answer',36,INK,True)
text(42,78,'Proposed learning/demo design. All customers, transactions, policies and human-support queues are synthetic.',24)

rect(20,140,2220,395,'#edf3f8','#edf3f8')
text(48,162,'A. PREPARE THE KNOWLEDGE  /  ONCE, THEN AGAIN WHEN DOCUMENTS CHANGE',24,BLUE,True)
xs=[55,495,935,1375,1815]
build=[
('1  Collect policy text',['Invented servicing policies','PDF / text / JSON inputs','PRD defines app behavior']),
('2  Clean and approve',['Remove repeated footers','Keep headings and tables','Exclude invalid / old text']),
('3  Split into passages',['One topic per passage','Keep rules + exceptions','Add source + version IDs']),
('4  Make it searchable',['Store passages locally','Search words + headings','No model training here']),
('5  Keep records separate',['Transactions stay structured','Reports saved in database','Never chunk private records'])]
for x,(title,lines) in zip(xs,build):box(x,230,390,200,title,lines,BLUE,body=22,title_size=25)
for x in [445,885,1325]:arrow([(x,330),(x+50,330)],GOLD)
text(1390,459,'Policy lookup ready',22,BLUE,True)
text(1830,459,'Authorized API reads ready',22,BLUE,True)
text(55,485,'Two evidence sources: document passages explain rules; authorized records establish exact amounts, dates and action states.',22)

rect(20,565,2220,455,'#fff7e9','#fff7e9')
text(48,587,'B. WHAT DOES CHUNKING MEAN?  /  TURN A DOCUMENT INTO SMALL, USEFUL ANSWER CARDS',23,GOLD,True)
box(55,650,1045,295,'Proposed starting rules for splitting documents',[
 'Split at a heading, topic or numbered procedure first.',
 'Aim for 300-500 tokens per passage (tokens are small text pieces).',
 'Keep short sections whole; split long sections at sentence boundaries.',
 'For long prose splits, repeat about 50 tokens to preserve context.',
 'Keep a rule with its exception; repeat table headings if tables must split.',
 'Do not combine different products, versions or jurisdictions.'
],GOLD,body=23)
box(1135,650,1070,295,'Example: one policy becomes traceable answer cards',[
 'Document: DEMO transaction guidance, version 1, U.S. debit checking.',
 'Card 1: what pending and posted mean. Card 2: report an unknown debit.',
 'Each card keeps: source ID, heading/page, version, product and dates.',
 'Search first filters applicable cards, then ranks relevant passages.',
 'Use up to 3-5 useful passages; missing/conflicting evidence means fallback.',
 'These chunk sizes and retrieval settings must be tested, not assumed best.'
],GOLD,body=22)
text(55,969,'Initial RAG uses local word search. Optional later: embeddings turn passages into numeric signatures for meaning-based search.',22)

rect(20,1050,2220,1185,'#edf5f3','#edf5f3')
text(48,1071,'C. ANSWER THE CUSTOMER  /  LANGGRAPH DIRECTS THE STEPS AND REMEMBERS THEIR RESULTS',23,TEAL,True)
box(55,1145,410,175,'Customer uses Replit app',[
 '"I do not recognize this debit."','Message + selected transaction','Session identifies demo customer'
],TEAL,body=21,title_size=25)
box(515,1145,440,175,'1  AI understands the request',[
 'GLM returns a typed decision','Fraud? Human requested?','A request is not permission'
],TEAL,body=22,title_size=25)
box(1005,1145,535,175,'2  Save a potential error report',[
 'Original words + timestamp + reference','Capture can happen before verified access','Retry safely; do not create duplicates'
],TEAL,body=22,title_size=25)
box(1590,1145,615,175,'3  Backend checks permission',[
 'Is the session valid? Is this the right customer?','Denied: no restricted record enters AI context','Report stays captured; offer a safe next step'
],TEAL,body=23,title_size=25)
for a,b in [(465,515),(955,1005),(1540,1590)]:arrow([(a,1232),(b,1232)])

text(70,1380,'4A  POLICY RAG: find guidance for this question',23,BLUE,True)
text(1145,1380,'4B  RECORDS + ACTIONS: fetch facts and verified outcomes',23,TEAL,True)
box(55,1425,1050,265,'Retrieve -> add context -> generate (RAG)',[
 'Filter cards by product, jurisdiction, approval and effective date.',
 'Search the question against eligible text; rank useful passages.',
 'Keep source IDs with the selected passages and check for conflicts.',
 'Example evidence: POL-TRAN-002, section "Unrecognized transaction".',
 'The model receives these passages, not the whole document library.'
],BLUE,fill='#f7fbff',body=23)
box(1140,1425,1065,265,'Authorized tools read records and save action events',[
 'Transaction API -> TXN-001-01, $45.99, posted, DEMO GROCERY.',
 'Intake database -> report captured, reference DEMO-REPORT-001.',
 'Human queue -> acknowledged, pending, unknown or unavailable.',
 'Backend rechecks permission whenever a restricted tool executes.',
 'Capture, legal receipt, investigation and handoff remain separate states.'
],TEAL,body=22)
arrow([(1890,1320),(1890,1350),(580,1350),(580,1425)])
arrow([(1890,1350),(1690,1350),(1690,1425)])

box(55,1800,655,215,'5  Assemble an evidence packet',[
 'Only necessary authorized facts + policy cards','Add confirmed report / queue outcomes','Keep the original request and source IDs','Do not include another customer\'s data'
],TEAL,body=23,title_size=26)
box(800,1800,655,215,'6  One AI agent explains the result',[
 'GLM writes a short, grounded explanation','Cite the policy used; quote exact record facts','Use fixed wording for important action states','Do not invent missing facts or legal deadlines'
],TEAL,body=22,title_size=26)
box(1545,1800,660,215,'7  Backend checks before sending',[
 'Amounts, dates and states match evidence?','Any unauthorized fields or false success?','Pass -> send. Fail -> safe template / human path.','Never discard an already captured report'
],TEAL,body=22,title_size=26)
arrow([(580,1690),(580,1735),(380,1735),(380,1800)])
arrow([(1690,1690),(1690,1735),(380,1735)],TEAL)
arrow([(710,1905),(800,1905)])
arrow([(1455,1905),(1545,1905)])
box(55,2080,2150,115,'8  Customer sees the verified outcome',[
 '"Your report was captured as DEMO-REPORT-001. The fraud-team connection is currently unavailable."  No claim of a card block or investigation.'
],TEAL,fill='#e2f1ed',body=23,title_size=26)
arrow([(1875,2015),(1875,2080)])

rect(20,2270,2220,535,'#f1eff8','#f1eff8')
text(48,2293,'D. WATCH, TEST AND IMPROVE  /  LANGSMITH HELPS THE TEAM UNDERSTAND WHAT HAPPENED',23,PURPLE,True)
bottom=[
 (55,'Record a safe trace',['Log steps and allow/deny decisions','Keep evidence IDs + action states','Measure time, tokens and cost','Mask sensitive content before export']),
 (790,'Test the same application',['Run 100 scenarios with isolated data','Check all 84 critical cases fully','Test fraud misses, leakage and retries','Repeat selected multi-turn journeys']),
 (1525,'Review before demo release',['Compare expected vs actual results','Human checks meaning and clarity','Critical failures block acceptance','Version fixes and rerun affected tests'])]
for x,title,lines in bottom:box(x,2380,680,245,title,lines,PURPLE,body=24,title_size=26)
arrow([(735,2500),(790,2500)],PURPLE,True)
arrow([(1470,2500),(1525,2500)],PURPLE,True)
text(55,2670,'LangSmith observes and evaluates. It does not authorize banking actions or decide whether a legal notice was received.',23)
text(55,2715,'Existing: synthetic tools and expected cases. Proposed: LangGraph application, chunking pipeline, durable writes, integrations and full evaluations.',22)
text(55,2758,'No live banking data, automatic refunds, transfers, credential changes, dispute decisions or card freezes in this demo.',22)

# Plain-language role cards at the right make the division of responsibility explicit.
text(2280,145,'WHO DOES WHAT?',25,INK,True)
roles=[
 (210,'Replit = the front door',[
 'Hosts the planned app and chat UI.','Customer enters a question here.','Displays answers and report status.','API keys stay on the server.'
 ],BLUE),
 (600,'LangGraph = the coordinator',[
 'Runs the steps in a defined order.','Branches on intent and permission.','Carries results between steps.','Tracks retries and safe fallback.','Checks still live in backend code.'
 ],TEAL),
 (1040,'Agent = the interpreter',[
 'One conversational AI agent.','GLM-5.3-Flash on Nebius.','Understands and explains.','Uses only allowed evidence.','Not a team of independent agents.'
 ],TEAL),
 (1480,'Backend = the authority',[
 'Checks identity and access.','Reads exact transaction records.','Saves reports durably.','Confirms real simulated outcomes.','RAG is not the transaction ledger.'
 ],GOLD),
 (1920,'LangSmith = the reviewer',[
 'Records sanitized workflow traces.','Helps inspect failures and costs.','Compares evaluation runs.','Supports human feedback.','Safety assertions run in code.'
 ],PURPLE),
 (2360,'RAG = look up, then explain',[
 'R: retrieve useful policy cards.','A: add them to the model context.','G: generate a grounded answer.','The model is not being retrained.','No vectors required for word search.'
 ],BLUE)]
for y,title,lines,c in roles:box(2280,y,495,330,title,lines,c,fill='#f8fafc',body=22,title_size=25)

# Carry each prepared data source into its runtime lookup without crossing text.
arrow([(1570,430),(1570,550),(35,550),(35,1560),(55,1560)],GOLD,True)
arrow([(2010,430),(2010,550),(2225,550),(2225,1560),(2205,1560)],GOLD,True)

svg.append('</svg>')
if overflow:raise ValueError('Text exceeds its box: '+repr(overflow))
(ROOT/'resolveguard_data_flow.svg').write_text('\n'.join(svg),encoding='utf-8')
im.save(ROOT/'resolveguard_data_flow.png')
print('Rendered plain-language data flow; all text fits its boxes.')
