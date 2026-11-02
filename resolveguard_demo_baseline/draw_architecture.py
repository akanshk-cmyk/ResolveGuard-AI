"""Render the proposed ResolveGuard architecture as editable SVG and PNG."""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 2800, 1900
im = Image.new('RGB', (W, H), 'white')
d = ImageDraw.Draw(im)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">', '<rect width="100%" height="100%" fill="white"/>']
INK, MUTED, BORDER = '#192431', '#596779', '#c8d2dd'
TEAL, BLUE, GOLD, PURPLE = '#087b77', '#2f649b', '#967519', '#7055cf'

def font(size, bold=False, mono=False):
    name = 'consola.ttf' if mono else ('arialbd.ttf' if bold else 'arial.ttf')
    return ImageFont.truetype(str(Path('C:/Windows/Fonts') / name), size)

def rect(x, y, w, h, fill='white', stroke=BORDER, radius=17, width=2):
    d.rounded_rectangle((x, y, x+w, y+h), radius, fill=fill, outline=stroke, width=width)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

def text(x, y, value, size=23, color=MUTED, bold=False, mono=False):
    d.text((x, y), value, font=font(size, bold, mono), fill=color)
    family = 'Consolas,monospace' if mono else 'Arial,sans-serif'
    svg.append(f'<text x="{x}" y="{y+size}" font-family="{family}" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}">{escape(value)}</text>')

def box(x, y, w, h, title, lines, stroke=BORDER, fill='white', title_color=INK, body_size=22):
    rect(x,y,w,h,fill,stroke)
    text(x+24,y+20,title,26,title_color,True)
    for i,line in enumerate(lines):
        text(x+24,y+65+i*31,line,body_size)

def arrow(points, color=TEAL, dashed=False, label=None, label_xy=None):
    for a,b in zip(points,points[1:]):
        if dashed:
            dx,dy=b[0]-a[0],b[1]-a[1]
            length=(dx*dx+dy*dy)**.5
            for k in range(0,int(length),16):
                end=min(k+9,length)
                d.line((a[0]+dx*k/length,a[1]+dy*k/length,a[0]+dx*end/length,a[1]+dy*end/length), fill=color,width=3)
        else:
            d.line((*a,*b),fill=color,width=3)
    a,b=points[-2:]
    dx,dy=b[0]-a[0],b[1]-a[1]
    length=(dx*dx+dy*dy)**.5
    ux,uy=dx/length,dy/length
    tri=[b,(b[0]-16*ux-7*uy,b[1]-16*uy+7*ux),(b[0]-16*ux+7*uy,b[1]-16*uy-7*ux)]
    d.polygon(tri,fill=color)
    coords=' '.join(f'{x},{y}' for x,y in points)
    dash='stroke-dasharray="9 7"' if dashed else ''
    svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3" {dash}/>')
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in tri)}" fill="{color}"/>')
    if label:
        text(*label_xy,label,19,color,mono=True)

rect(1,1,W-2,H-2,'white',BORDER,20)
text(40,24,'ResolveGuard AI | Proposed demo architecture',34,INK,True)
text(42,70,'Fraud/error intake + transaction inquiries | Synthetic data only | GLM-5.3-Flash selected; evaluations not run',22)

# Three horizontal lanes follow the supplied visual template.
rect(20,125,2230,345,'#edf3f8','#edf3f8',20)
text(52,149,'BUILD TIME  /  WHEN FIXTURES OR SYNTHETIC POLICIES CHANGE',22,MUTED,True)
build=[
 (55,'PRD + synthetic sources',['Proposed v0.4 controls','Existing JSON fixtures','100 expected test cases']),
 (485,'prepare_data.py',['Normalize tools + states','Preserve golden labels','Validate IDs + scope']),
 (915,'seed_demo.py',['12 customers / accounts','48 transactions; 8 cases','Sessions + fixed clock']),
 (1345,'prepare_policy.py',['Approved demo text only','Product + date filters','Versioned evidence IDs']),
 (1775,'demo_manifest.json',['Fixture + policy versions','SQLite seed + local lookup','Concrete test bindings'])]
for x,title,lines in build:
    box(x,215,375,195,title,lines,BLUE if x==55 else BORDER,'#eaf2fc' if x==55 else 'white')
for x in [430,860,1290,1720]:arrow([(x,310),(x+55,310)],GOLD)

rect(20,495,2230,840,'#edf5f3','#edf5f3',20)
text(52,518,'QUERY TIME  /  PER CUSTOMER MESSAGE',22,MUTED,True)
box(55,780,220,155,'Customer',['Demo browser','Synthetic identity'])
rect(315,650,680,450,'#edf5f3',TEAL,20)
text(340,672,'REPLIT APP  /  PLANNED HOSTING',21,TEAL,True)
box(340,720,295,265,'Chat UI',['Transaction selector','Report reference','Human-support button','Source evidence','Honest status updates'],body_size=21)
box(665,720,305,265,'api.py / FastAPI',['POST /api/chat','Session binding','Request idempotency','Server-side secrets','Rate limit + validation'],body_size=21)
text(340,1010,'Separate demo controls: customer switch,',20)
text(340,1042,'expired session, API / queue failure injection',20)
arrow([(275,855),(340,855)])
arrow([(635,855),(665,855)])
arrow([(970,855),(1040,855)])
box(340,1150,630,130,'ask.py / local CLI',['Same workflow entry point; reproducible fixture reset'],body_size=21)
arrow([(970,1215),(1008,1215),(1008,1090),(1040,1090)])

rect(1040,575,1170,725,'#edf5f3',TEAL,22,3)
text(1070,593,'workflow.py / explicit Python state machine',27,TEAL,True)
text(1070,634,'LLM proposes; backend authorizes, persists and establishes state',20)

nodes=[
 (1080,690,'1  classify',['Intent + fraud flag','Human flag; typed schema']),
 (1465,690,'2  preserve report',['If flagged: original text','Capture time + dedupe']),
 (1850,690,'3  authorize',['Session + resource scope','Deny restricted access']),
 (1080,895,'4  scoped tools',['Authorized reads only','Applicable demo policy']),
 (1465,895,'5  human routing',['Queue + receiver scope','ACK / unknown / fallback']),
 (1850,895,'6  evidence packet',['Exact amounts + states','No legal-state inference']),
 (1080,1100,'7  explain',['GLM grounded response','Fixed status templates']),
 (1465,1100,'8  output checks',['Facts + field allowlists','No false action success']),
 (1850,1100,'9  respond safely',['Verified result or fallback','Keep captured report'])]
for x,y,title,lines in nodes:box(x,y,320,145,title,lines,TEAL,body_size=20)
for y in [762,967,1172]:
    arrow([(1400,y),(1465,y)])
    arrow([(1785,y),(1850,y)])
arrow([(2170,835),(2190,835),(2190,865),(1060,865),(1060,967),(1080,967)])
arrow([(2170,1040),(2190,1040),(2190,1070),(1060,1070),(1060,1172),(1080,1172)])
arrow([(1960,410),(1960,490),(1200,490),(1200,575)],GOLD,True,'load versioned artifacts',(1400,465))

# Right-hand services mirror the template, but preserve the local retrieval scope.
text(2290,140,'SERVICES & APP DATA',22,MUTED,True)
rect(2280,185,495,355,'#eaf2fc',BLUE,20)
text(2305,205,'Nebius Token Factory',26,BLUE,True)
box(2300,260,455,250,'GLM-5.3-Flash',['zai-org/GLM-5.3-Flash','Structured routing + explanation','Server-side API calls only','Scoped, minimized context','Never the authorization authority'],BLUE,body_size=21)
arrow([(2210,610),(2260,610),(2260,365),(2280,365)],TEAL,False,'classify + explain',(1980,548))

rect(2280,605,495,690,'#eaf2fc',BLUE,20)
text(2305,626,'App-owned synthetic backend',25,BLUE,True)
box(2300,685,455,180,'FixtureBank + local policy',['Ownership / session enforcement','Existing scoped transaction reads','Local approved policy lookup'],BLUE,body_size=21)
box(2300,890,455,260,'SQLite + simulated queues',['Durable reports + request keys','Case commit / unknown states','Delivery ACK + receiver scope','Legal notice defaults to review','Hosting persistence to validate'],BLUE,body_size=21)
text(2305,1180,'Planned extensions; no real bank APIs',20)
text(2305,1215,'No vector database needed initially',20)
arrow([(2210,940),(2280,940)],TEAL)
text(2230,870,'tools',18,TEAL,mono=True)

rect(20,1370,2230,500,'#f1f0f8','#f1f0f8',20)
text(52,1394,'EVALUATE & SHIP  /  DEMO ACCEPTANCE, NOT BANK LAUNCH APPROVAL',22,MUTED,True)
ev=[
 (55,'Source repository',['Code + setup instructions','Versioned synthetic data','Prompt / model versions','No credentials in source']),
 (490,'bind_cases.py',['RG-001 through RG-100','Principal + resource IDs','Expected events + states','84 critical; 16 standard']),
 (925,'run_eval.py',['Same workflow as the UI','Isolated state + fault injection','API checks + full trajectories','Repeat selected journeys']),
 (1360,'review_results.py',['Actual vs expected evidence','Routing + grounding + privacy','Latency, tokens and cost','Human review of semantics']),
 (1795,'demo_gate.py',['100 executed; no missing runs','84 critical: every assertion','Proposed intent: >= 95 / 100','Critical failure blocks release'])]
for x,title,lines in ev:box(x,1480,380,245,title,lines,body_size=21)
for x in [435,870,1305,1740]:arrow([(x,1600),(x+55,1600)],PURPLE,True)
arrow([(1100,1480),(1100,1348),(1260,1348),(1260,1300)],PURPLE,True,'execute real workflow',(1150,1320))
text(55,1760,'Existing: fixture package + 13 passing unit tests. Proposed: application, durable workflows, complete evaluation harness and hosting.',21)
text(55,1800,'No transfers, refunds, credential changes, card freeze or dispute adjudication. No statutory deadline calculations.',21)

rect(2280,1370,495,500,'#eaf2fc',BLUE,20)
text(2305,1394,'LangSmith',27,BLUE,True)
box(2300,1455,455,150,'Tracing',['Sanitize before export','Step spans + session / test IDs'],BLUE,body_size=21)
box(2300,1630,455,205,'Datasets + experiments',['100 expected cases; all Not Run','Code-based critical assertions','Compare prompt / model versions','Judge optional after calibration'],BLUE,body_size=21)
arrow([(2210,1265),(2240,1265),(2240,1530),(2300,1530)],PURPLE,True)
text(1990,1307,'sanitized traces',18,PURPLE,mono=True)
arrow([(2175,1630),(2230,1630),(2230,1735),(2300,1735)],PURPLE,True)

svg.append('</svg>')
(ROOT/'resolveguard_architecture.svg').write_text('\n'.join(svg),encoding='utf-8')
im.save(ROOT/'resolveguard_architecture.png')
print('Created resolveguard_architecture.svg and resolveguard_architecture.png')
