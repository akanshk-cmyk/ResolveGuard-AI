"""Build a readable local review pack from the active, validated BOW import."""
import csv
import html
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolveguard.bow_data import load_dataset,ROOT
from tools.shared.report_rendering import render_table


def table(rows):
    return render_table(rows)


if __name__=='__main__':
    data,manifest=load_dataset();output=ROOT.parents[1]/'artifacts/bow_review';output.mkdir(parents=True,exist_ok=True)
    body=['<h1>Bank of Whatever: imported data review</h1><p>All records, policies and rates are fictional demo material. Synthetic approval and KYC labels are not real institution approval or identity proof.</p>',
          '<p>Source: '+html.escape(manifest['source_file'])+'</p><p><a href="source.xlsx">Exact source workbook</a> | <a href="manifest.json">Source fingerprint and row lineage</a></p>',
          '<p>100 evaluation scenarios remain NOT_RUN. The seeded intake event is reference data; it was not submitted as a new live report.</p>',
          '<p>Excel serial timestamps are normalised to UTC for the demo. Original workbook bytes and all archived sheets are preserved in the source copy; archive rows are not activated as BOW records.</p>',
          '<nav>'+''.join('<a href="#'+name+'">'+html.escape(name.replace('_',' ').title())+'</a> | ' for name in data)+'</nav>',
          '<h2>Imported record counts</h2>'+table([{'worksheet_data':name,'records':len(rows)} for name,rows in data.items()])]
    for name,rows in data.items():
        (output/(name+'.json')).write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        with (output/(name+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
            writer.writerows({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in row.items()} for row in rows)
        body+=['<section id="'+name+'"><h2>'+html.escape(name.replace('_',' ').title())+'</h2><p><a href="'+name+'.json">JSON</a> | <a href="'+name+'.csv">Spreadsheet-friendly CSV</a></p>'+table(rows)+'</section>']
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    shutil.copy2(ROOT/manifest['source_sha256']/'source.xlsx',output/'source.xlsx')
    (output/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BOW data review</title><style>body{font:15px system-ui;line-height:1.6;margin:32px;color:#243d36}h1,h2{color:#17685e}.scroll{overflow:auto}table{border-collapse:collapse;min-width:100%;font-size:13px}th,td{border:1px solid #dce3de;padding:9px;text-align:left;vertical-align:top;min-width:100px;max-width:600px;white-space:pre-wrap}th{background:#eef5f0}a{color:#075eaa}section{margin-top:32px}</style>'+''.join(body)+'</html>',encoding='utf-8')
    archive=shutil.make_archive(str(output.parent/'BOW_review_pack'),'zip',output)
    print(json.dumps({'review_page':str(output/'index.html'),'zip':archive,'counts':manifest['counts']},indent=2))
