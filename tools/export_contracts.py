"""Export application JSON schemas for review without invoking any provider."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from resolveguard.contracts import Request, Route, Faults, Explanation, RESULT_ADAPTERS, PAYLOAD_MODELS


def main():
    path=ROOT/'artifacts/pydantic_contracts.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    schemas={cls.__name__:cls.model_json_schema() for cls in (Request,Route,Faults,Explanation)}
    schemas.update({name+'_result':adapter.json_schema() for name,adapter in RESULT_ADAPTERS.items()})
    schemas.update({name+'_payload':cls.model_json_schema() for name,cls in PAYLOAD_MODELS.items()})
    path.write_text(json.dumps({'version':'pydantic-boundaries-v1',
        'note':'Shape validation is not authorization or proof of committed effects. JSON array-to-tuple normalization is explicit; other value coercion is disabled.',
        'schemas':schemas},indent=2)+'\n',encoding='utf-8')
    print('Exported '+str(len(schemas))+' contract schemas to '+str(path.relative_to(ROOT)))


if __name__=='__main__':main()
