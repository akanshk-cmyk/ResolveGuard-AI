"""Export the validated active workbook for review, including lineage and chunks."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolveguard.bow_knowledge import BowKnowledge
from resolveguard.bow_data import load_dataset


if __name__=='__main__':
    output=Path(__file__).resolve().parents[1]/'artifacts/bow_staging'
    output.mkdir(parents=True,exist_ok=True)
    knowledge=BowKnowledge()
    data,manifest=load_dataset();chunks=knowledge.chunks
    for name,rows in data.items():
        (output/(name+'.json')).write_text(json.dumps(rows,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    for filename,value in [('catalog.json',knowledge.catalog()),('rag_chunks.json',chunks),('manifest.json',manifest)]:
        (output/filename).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'products':len(knowledge.products),'chunks':len(chunks),'source':manifest['source_file'],'output':str(output)},indent=2))
