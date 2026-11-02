"""Public policy conversation state, replay boundaries and retrieval traces."""
import hashlib
import json
from fastapi import HTTPException
from .web_contracts import PublicContext


def public_bow_turn(binding, turn, backend, knowledge, *, store, review):
    review_binding=binding
    if turn.bank_id!='BOW':binding=binding+':LEGACY_DEMO'
    digest=hashlib.sha256(turn.model_dump_json().encode()).hexdigest();as_of=backend.now[:10]
    version=knowledge.version+':'+knowledge.conversation_version
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        cached=db.execute('SELECT * FROM web_public_turns WHERE binding=? AND request_key=?',(binding,turn.request_key)).fetchone()
        if cached:
            if cached['payload_hash']!=digest:raise HTTPException(409,'This request was already used for another message. Please send a new question.')
            if cached['as_of']!=as_of or cached['source_version']!=version:
                raise HTTPException(409,'Please send the question again so I can check the current source.')
            return json.loads(cached['result'])
        previous=db.execute('SELECT payload FROM web_public_context WHERE binding=?',(binding,)).fetchone()
        state=PublicContext.model_validate_json(previous['payload']).model_dump(exclude_none=True) if previous else {}
        from .telemetry import Trace
        trace=Trace({'bank_id':turn.bank_id,'workflow':'public-policy','source_version':version})
        tools=[]
        if hasattr(knowledge,'retrieve'):
            original=knowledge.retrieve
            def traced_retrieve(*args,**kwargs):
                with trace.span('search_public_policy','tool') as span:
                    chunks=original(*args,**kwargs)
                    span['outputs']={'source_refs':[c['chunk_id'] for c in chunks],'source_version':knowledge.version}
                    tools.append({'name':'search_public_policy','status':'OK' if chunks else 'NOT_FOUND'})
                    return chunks
            knowledge.retrieve=traced_retrieve
        with trace.span('public.converse') as span:
            result,state=knowledge.converse(turn.message,turn.product_id,as_of,state)
            span['outputs']={'response_state':result.get('response_state'),'selected_product_id':result.get('selected_product_id')}
        if result.get('question_topic')=='APY' and result.get('source_details'):
            with trace.span('verify_current_rate','tool') as span:
                current=all(s.get('effective_date','9999')<=as_of and (not s.get('expires_on') or as_of<s['expires_on']) for s in result['source_details'])
                span['outputs']={'current':current,'as_of':as_of}
                tools.append({'name':'verify_current_rate','status':'OK' if current else 'DENIED'})
        state=PublicContext.model_validate(state)
        db.execute('INSERT INTO web_public_context VALUES(?,?) ON CONFLICT(binding) DO UPDATE SET payload=excluded.payload',(binding,state.model_dump_json()))
        db.execute('INSERT INTO web_public_turns VALUES(?,?,?,?,?,?)',(binding,turn.request_key,digest,as_of,version,json.dumps(result)))
    review.capture_workflow(review_binding,turn.request_key,{'trace':trace.export(),'tools':tools,'bank_id':turn.bank_id,'response_state':result.get('response_state')})
    return result
