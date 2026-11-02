"""Improve readability of generated case evidence without changing its data."""
import shutil
from tools.build_week3_submission import ROOT,OUT

old='.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}'
new=('.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}'
     '.pair>div{min-width:0}.pair p{overflow-wrap:anywhere}.pair pre{max-height:360px;overflow:auto}')
for path in (ROOT/'tools/build_week3_submission.py',OUT/'index.html',OUT/'report.html'):
    path.write_text(path.read_text(encoding='utf-8').replace(old,new),encoding='utf-8')
path=OUT/'index.html'
text=path.read_text(encoding='utf-8')
intro=('<header id="project-overview"><h1>ResolveGuard AI · Week 3 Agent Evaluation</h1>'
       '<p><strong>Mock-agent experiment:</strong> 40 identical cases, three repeats per version. '
       'Human reference review pending.</p><p><strong>Journey:</strong> 80% → 97.5% · '
       '<strong>Intent:</strong> 85% → 100% · <strong>Fraud recall:</strong> 80% → 100%. '
       'These are not GLM quality gains.</p></header>')
if 'id="project-overview"' not in text:
    path.write_text(text.replace('<section class="interactive">',intro+'<section class="interactive">',1),encoding='utf-8')
shutil.copyfile(ROOT/'tools/build_week3_submission.py',OUT/'supporting_code/tools/build_week3_submission.py')
print('Report layout and supporting-code snapshot updated; scores unchanged.')
