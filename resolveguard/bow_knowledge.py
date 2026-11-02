"""Source-linked BOW retrieval. Never falls back to archived bank policies."""
from datetime import date
import re
from .bow_data import load_dataset
from .presentation import format_money


class BowKnowledge:
    conversation_version='strict-product-v7-topic-scope'
    def __init__(self,data=None):
        if data is None:self.data,self.manifest=load_dataset()
        else:
            from .bow_data import validate_dataset
            self.data=validate_dataset(data);self.manifest={'source_file':'isolated test fixture','source_sha256':'0'*64,'counts':{k:len(v) for k,v in data.items()}}
        self.products=self.data['products'];self.chunks=self.data['chunks']
        self.product_map={p['product_id']:p for p in self.products}
        self.policy_map={p['doc_id']:p for p in self.data['policies']}
        self.chunk_map={c['chunk_id']:c for c in self.chunks}
        self.version='bow-'+self.manifest['source_sha256'][:16]

    def catalog(self):
        return {'bank_id':'BOW','bank_name':'Bank of Whatever','products':[
                    {**p,'name':p['product_name'],'category':p['product_type'].upper()} for p in self.products],
                'coverage':self.manifest['counts'],'notice':'Fictional synthetic test terms, not real banking offers or institution approval.',
                'source':self.manifest['source_file'],'source_sha256':self.manifest['source_sha256'],
                'active_chunks':len(self.chunks),'workbook_imported':True,
                'evaluation_status':'Imported workbook statuses are preserved; separate versioned local execution reports exist. Human qualification remains pending.',
                'evaluation_report':'artifacts/local_completion/bow100_final_checked/summary.json'}

    def applicable(self,scope,product_id):
        product=self.product_map.get(product_id)
        return product is not None and (scope in {'ALL',product_id}
            or scope=='ALL_SAVINGS' and product['product_type']=='savings'
            or scope=='CHECKING_DEBIT' and product['product_type'] in {'checking','debit_card'})

    def retrieve(self,bank_id,product_id,as_of,access_level='PUBLIC',allow_demo=False,query='',limit=5):
        if bank_id!='BOW' or product_id not in self.product_map or access_level!='PUBLIC' or not allow_demo:return []
        today=date.fromisoformat(as_of);tokens=set(re.findall(r'[a-z0-9]+',query.lower()))
        eligible=[]
        for c in self.chunks:
            parent=self.policy_map[c['doc_id']]
            if c['bank_id']!='BOW' or parent['bank_id']!='BOW':continue
            if c['access_level']!='PUBLIC' or parent['access_level']!='PUBLIC':continue
            if c['approval_status']!='SYNTHETIC_APPROVED_FOR_TEST_ONLY' or parent['approval_status']!=c['approval_status']:continue
            if not self.applicable(c['product_id'],product_id):continue
            if date.fromisoformat(c['effective_date'])>today or c['expires_on'] and today>=date.fromisoformat(c['expires_on']):continue
            score=(10 if c['product_id']==product_id else 0)+len(tokens.intersection(re.findall(r'[a-z0-9]+',c['chunk_text'].lower())))
            eligible.append((score,c))
        eligible.sort(key=lambda pair:(-pair[0],pair[1]['chunk_id']))
        return [dict(c,retrieval_score=float(score+1)) for score,c in eligible[:limit]]

    def product_summary(self,p):
        if p['product_type']=='checking':
            return f"{p['product_name']}: sample monthly fee {format_money(p['monthly_fee_cents_or_annual_card_fee_cents'])}. Fee/waiver terms: {p['waiver_or_fee_terms']}. Rewards: {p['reward_structure']}."
        if p['product_type']=='savings':
            return f"{p['product_name']}: illustrative variable APY {p['illustrative_apy_percent']}%. {p['reward_structure']}. Terms: {p['waiver_or_fee_terms']}."
        return f"{p['product_name']}: {p['waiver_or_fee_terms']}. Rewards: {p['reward_structure']}. Eligibility: {p['eligibility']}."+(' Public information only; credit-card servicing is outside the MVP.' if p['product_type']=='credit_card' else '')

    def catalog_source(self,product_id,linked_sources):
        import hashlib,json
        p=self.product_map[product_id]
        expires=[s['expires_on'] for s in linked_sources if s.get('expires_on')]
        return {'title':p['product_name']+' product catalog','summary':self.product_summary(p),
            'reference':'BOW-CATALOG:'+product_id+':'+self.version,'version':self.version,'bank_id':'BOW','product_id':product_id,
            'effective_date':p['effective_date'],'expires_on':min(expires) if expires else None,
            'access_level':'PUBLIC','approval_status':'SYNTHETIC_APPROVED_FOR_TEST_ONLY',
            'content_hash':hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest(),'record':dict(p),
            'notice':'Fictional BOW product record from BOW Products; linked current policy required.'}

    def sources(self,ids):
        sources=[]
        for ident in dict.fromkeys(ids):
            c=self.chunk_map.get(ident)
            if not c:continue
            p=self.product_map.get(c['product_id']);parent=self.policy_map[c['doc_id']]
            sources.append({'title':p['product_name'] if p else parent['topic'].replace('_',' ').capitalize(),
                'summary':c['chunk_text'],'reference':c['chunk_id'],
                'version':self.version,'effective_date':c['effective_date'],'expires_on':c['expires_on'],
                'notice':'Fictional BOW test policy. Source: '+self.manifest['source_file']+' / BOW Products, BOW Policies and BOW RAG Chunks.',
                'bank_id':'BOW','product_id':c['product_id'],'parent_policy_id':c['doc_id'],'content_hash':c['sha256_text'],
                'access_level':c['access_level'],'approval_status':c['approval_status']})
        return sources

    @staticmethod
    def question_topic(message):
        text=message.lower()
        if 'waiv' in text:return 'WAIVER'
        if any(w in text for w in ('interest','apy','rate')):return 'APY'
        if any(w in text for w in ('fee','maintenance','service charge')):return 'FEE'
        if any(w in text for w in ('reward','cashback','point','mile')):return 'REWARDS'
        if any(w in text for w in ('eligib','qualif','relationship')):return 'ELIGIBILITY'
        if any(w in text for w in ('feature','product','tell me about','details','information','offer')):return 'FEATURES'
        return 'UNKNOWN'

    @staticmethod
    def question_category(message,topic):
        text=message.lower()
        if 'saving' in text:return 'savings'
        if 'checking' in text:return 'checking'
        if 'credit' in text or 'yolo' in text:return 'credit_card'
        if 'debit' in text:return 'debit_card'
        if topic=='APY':return 'savings'
        return None

    def named_products(self,message,category=None):
        normal=lambda value:' '.join(re.findall(r'[a-z0-9]+',value.lower()))
        text=normal(message);matches=[]
        for p in self.products:
            if category and p['product_type']!=category:continue
            aliases=[normal(p['product_name']),normal(p['product_name'].removeprefix('Whatever ')),normal(p['tier'])]
            hits=[alias for alias in aliases if alias and re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text)]
            if hits:matches.append((max(len(alias) for alias in hits),p))
        if not matches:return []
        longest=max(length for length,p in matches)
        return [p for length,p in matches if length==longest]

    def answer(self,message,product_id,as_of):
        text=message.lower();source_ids=[]
        def result(response,**extra):
            return {'response':response,'response_state':'CLARIFICATION_REQUIRED' if extra.get('choose_product') else 'PUBLIC_GUIDANCE','data_scope':'PUBLIC','auth_required':False,
                    'bank_id':'BOW','cards':[],'source_details':self.sources(source_ids),'execution_mode':'MOCK','presentation_version':'bow-conversation-v2',
                    'execution_evidence':{'data_scope':'PUBLIC','private_records_accessed':False,'personal_eligibility_checked':False},**extra}
        if any(bank in text for bank in ('chase','capital one','capitalone')):
            from .comparisons import is_comparison
            named=self.named_products(message)
            if len(named)==1 and not is_comparison(message):
                eligible=self.retrieve('BOW',named[0]['product_id'],as_of,allow_demo=True,query=message)
                source_ids.extend(c['chunk_id'] for c in eligible if c['product_id']==named[0]['product_id'])
            return result('This guide contains only fictional Bank of Whatever terms. No policy from another bank will be substituted or mixed into a BOW answer.',
                          selected_product_id=named[0]['product_id'] if len(named)==1 else None)
        from .comparisons import is_comparison,is_status_comparison,compare_payment_statuses,compare_products
        if is_status_comparison(message):return compare_payment_statuses(self,message,as_of)
        if is_comparison(message):return compare_products(self,message,as_of)
        if product_id and product_id not in self.product_map:return result('Please select a product from the BOW catalog. That product is not available here.')
        general_topics=[('authentication',('sign in','authentication','verification','verify')),
                        ('data_privacy',('privacy','password','pin','cvv','otp')),
                        ('human_handoff',('human support','handoff','support transfer')),
                        ('fraud_error_intake',('report an error','report fraud','error reporting','fraud policy')),
                        ('case_state',('case policy','case submission'))]
        topic=next((topic for topic,terms in general_topics if any(term in text for term in terms)),None)
        if topic:
            valid=self.retrieve('BOW',product_id or self.products[0]['product_id'],as_of,allow_demo=True,query=message,limit=61)
            selected=[c for c in valid if c['topic']==topic]
            if not selected:return result('No current eligible BOW support policy is available for that topic.')
            source_ids.extend(c['chunk_id'] for c in selected)
            friendly={'authentication':'Public product guidance needs no sign-in. Private account details need a trusted sign-in and a separate permission check. Extra verification is required only when the demo risk rule asks for it. Chat text cannot verify your identity.',
                      'data_privacy':'Public product information is available to guests. Private accounts, payments and cases require sign-in and permission. Never share passwords, PINs, card security codes or one-time codes in chat.',
                      'human_handoff':'You can request support. A requested, pending, confirmed or unavailable connection must be described accurately; no response time is invented.',
                      'fraud_error_intake':'A possible unauthorised-payment report can be saved before account verification. Saving it does not confirm a formal notice, an investigation or a dispute decision.',
                      'case_state':'A support request is created only after the reporting system confirms it and returns a reference. An uncertain submission must be checked before another is created.'}
            return result('Fictional BOW support guidance. '+friendly[topic])
        question_topic=self.question_topic(message)
        category=self.question_category(message,question_topic)
        named=self.named_products(message,category)
        if question_topic=='UNKNOWN':
            normal=' '.join(re.findall(r'[a-z0-9]+',message.lower()))
            aliases=[] if len(named)!=1 else [' '.join(re.findall(r'[a-z0-9]+',value.lower())) for value in
                (named[0]['product_name'],named[0]['product_name'].removeprefix('Whatever '),named[0]['tier'])]
            if normal in aliases:question_topic='FEATURES'
            else:return result('I can help with BOW fees, fee waivers, savings APYs, rewards or product eligibility. What would you like to know?')
        # An explicit product in chat overrides a stale sidebar selection.
        selected=named if named else [self.product_map[product_id]] if product_id else []
        if category and selected and any(p['product_type']!=category for p in selected):selected=[]
        if len(selected)>1:selected=[]
        if not selected:
            choice_category=category or ('checking' if question_topic in {'FEE','WAIVER'} else None)
            choices=[{'product_id':p['product_id'],'name':p['product_name']} for p in self.products if not choice_category or p['product_type']==choice_category]
            label={'savings':'savings account','checking':'checking account','debit_card':'debit card','credit_card':'credit card'}.get(choice_category,'product')
            return result(f'Which {label} would you like to know about? Choose one below, or type its name.',choose_product=True,
                          product_choices=choices,selected_product_id=None,question_topic=question_topic,question_category=choice_category,
                          clarification_question=message)
        p=selected[0]
        matches=self.retrieve('BOW',p['product_id'],as_of,allow_demo=True,query=message)
        exact=[c for c in matches if c['product_id']==p['product_id']]
        if not exact:return result(f"No current, eligible BOW policy snapshot is available for {p['product_name']} on {as_of}. I cannot confirm a fee or APY from stale or missing evidence.")
        relevant={'FEE':('fee','waiv'),'WAIVER':('fee','waiv'),'APY':('apy','balance','variable'),
                  'REWARDS':('reward','cashback','point','eligible debit')}.get(question_topic)
        evidence=[c for c in exact if not relevant or any(word in c['chunk_text'].lower() for word in relevant)]
        source_ids.extend(c['chunk_id'] for c in evidence or exact)
        feature=next((word for word in ('atm','overdraft','wire','replacement','foreign','late','transfer','returned item') if word in text),None)
        incompatible_period=('annual' in text and p['product_type'] in {'checking','savings'} or
                             'monthly' in text and p['product_type'] in {'debit_card','credit_card'})
        if question_topic in {'FEE','WAIVER'} and (feature or incompatible_period):
            if feature=='atm' and 'atm' in p['waiver_or_fee_terms'].lower():
                return result(f"For {p['product_name']}, the supplied terms say out-of-network ATM charges may apply. No charge amount or ATM-fee waiver rule is specified, so I cannot confirm either.",selected_product_id=p['product_id'])
            source_ids.clear()
            return result(f"The supplied terms do not specify the requested fee or waiver for {p['product_name']}. I need a current policy for that particular charge before I can give an amount or conditions.",selected_product_id=p['product_id'])
        money_text=lambda value:re.sub(r'\$(\d+)',lambda match:'$'+format(int(match[1]),','),value.replace('\u2265','of at least').replace(' OR ',' or '))
        if question_topic=='FEE':
            fee=format_money(p['monthly_fee_cents_or_annual_card_fee_cents'])
            period='annual card fee' if p['product_type'] in {'debit_card','credit_card'} else 'monthly maintenance fee'
            explanation=f"{p['product_name']} has a {period} of {fee}."
            if p['product_type']=='checking':
                explanation+=' Fee and waiver conditions: '+money_text(p['waiver_or_fee_terms'])+'.'
        elif question_topic=='WAIVER':
            explanation=f"For {p['product_name']}, the fee and waiver rules are:\n\n"+money_text(p['waiver_or_fee_terms'])+'.'
            if re.search(r'\b(i|my|me)\b',text):
                explanation+='\n\nWhether you qualify depends on the account deposits or balances in these rules. This public-policy answer does not check your personal eligibility.'
                support=self.retrieve('BOW',p['product_id'],as_of,allow_demo=True,query='privacy account information passwords',limit=61)
                privacy={c['chunk_id']:c for c in support if c['topic']=='data_privacy'}
                if 'POL-BOW-PRIVACY-C02' in privacy:
                    source_ids.append('POL-BOW-PRIVACY-C02')
                    explanation+=' Personal account information requires secure sign-in and permission.'
                if 'POL-BOW-PRIVACY-C03' in privacy:
                    source_ids.append('POL-BOW-PRIVACY-C03')
                    explanation+=' Never share your PIN, CVV, password or one-time code in chat.'
        elif question_topic=='APY':
            tiers=re.search(r'below \$(\d+);\s*(\d+\.\d+)% on \$(\d+)\+',p['reward_structure'])
            if tiers:
                explanation=(f"{p['product_name']} has these illustrative variable APYs:\n\n"
                    f"- {p['illustrative_apy_percent']}% on balances below ${int(tiers[1]):,}.\n"
                    f"- {tiers[2]}% on balances of ${int(tiers[3]):,} or more.")
            else:explanation=f"{p['product_name']} has an illustrative variable APY of {p['illustrative_apy_percent']}%."
            if 'relationship' in p['waiver_or_fee_terms'].lower():explanation+=' An eligible Premier Checking relationship is required.'
        elif question_topic=='REWARDS':explanation=f"Rewards for {p['product_name']}: "+money_text(p['reward_structure'])+'.'
        elif question_topic=='ELIGIBILITY':
            explanation=f"Eligibility for {p['product_name']}: "+(money_text(p['waiver_or_fee_terms']) if 'relationship' in p['waiver_or_fee_terms'].lower() else p['eligibility'])+'.'
        elif question_topic=='FEATURES':explanation=self.product_summary(p)
        else:return result('I can help with BOW fees, fee waivers, savings APYs, rewards or product eligibility. What would you like to know?')
        effective=date.fromisoformat(exact[0]['effective_date'])
        output=result(explanation+f"\n\nDemo terms, effective {effective.strftime('%B')} {effective.day}, {effective.year}.",
                      selected_product_id=p['product_id'],question_topic=question_topic)
        if question_topic in {'FEE','APY','REWARDS','FEATURES'}:
            output['source_details'].insert(0,self.catalog_source(p['product_id'],output['source_details']))
        return output

    def converse(self,message,product_id,as_of,context=None):
        """Resolve product-only replies against a saved public question."""
        context=dict(context or {})
        pending=context.get('pending_question')
        allowed=context.get('pending_choices',[])
        reply=' '.join(re.findall(r'[a-z0-9]+',message.lower()))
        categories={'checking':'checking','checking account':'checking','checking accounts':'checking',
                    'saving account':'savings','savings':'savings','savings account':'savings','savings accounts':'savings',
                    'debit card':'debit_card','credit card':'credit_card'}
        category_reply=categories.get(reply)
        from .comparisons import is_comparison,product_subjects,compare_products
        if context.get('comparison_pending') and not is_comparison(message):
            selections=product_subjects(self,message,context.get('pending_category'))
            ordinals={'1':0,'first':0,'first one':0,'2':1,'second':1,'second one':1,'3':2,'third':2,'third one':2}
            if reply in ordinals and ordinals[reply]<len(allowed):selections=[allowed[ordinals[reply]]]
            aliases=[]
            for pid in selections:
                product=self.product_map[pid]
                aliases.extend(' '.join(re.findall(r'[a-z0-9]+',value.lower())) for value in (
                    product['product_name'],product['product_name'].removeprefix('Whatever '),product['tier'],pid))
            if category_reply or reply in ordinals or reply in aliases:
                combined=list(dict.fromkeys(context.get('comparison_product_ids',[])+selections))
                output=compare_products(self,pending,as_of,combined,category_reply or context.get('pending_category'))
                return self._comparison_context(output,pending)
        named=self.named_products(message,context.get('pending_category') if pending else None)
        selection_only=(self.question_topic(message)=='UNKNOWN' and bool(named))
        if pending and reply in {'1','first','first one','2','second','second one','3','third','third one'}:
            index={'1':0,'first':0,'first one':0,'2':1,'second':1,'second one':1,'3':2,'third':2,'third one':2}[reply]
            if index<len(allowed):product_id=allowed[index];selection_only=True
        if category_reply:
            label=category_reply.replace('_',' ')
            if pending:
                question=re.sub(r'\b(checking|savings|saving|debit card|credit card)\b',label,pending,flags=re.I)
                question=f'For {label} accounts: '+question
            else:question=f'What product features are available for {label} accounts?'
            chosen=None
        elif pending and selection_only:
            if len(named)==1:product_id=named[0]['product_id']
            if product_id not in allowed:
                return self.answer(pending,None,as_of),context
            question=pending
            chosen=product_id
        else:
            question=message
            topic=self.question_topic(message)
            explicit_followup=bool(re.search(r'^(and\b|what about\b)|\b(its|that product|this product|same account|same card)\b',message,re.I))
            fee_followup=topic in {'FEE','WAIVER'} and context.get('last_topic') in {'FEE','WAIVER'}
            chosen=context.get('product_id') if context.get('product_confirmed') and (explicit_followup or fee_followup) else None
        output=self.answer(question,chosen,as_of)
        if output.get('comparison_plan'):return self._comparison_context(output,question)
        if output.get('choose_product'):
            context={'pending_question':question,'pending_category':output.get('question_category'),
                     'pending_choices':[p['product_id'] for p in output.get('product_choices',[])]}
        elif output.get('selected_product_id'):
            context={'product_id':output['selected_product_id'],'product_confirmed':True,
                     'last_topic':output.get('question_topic',self.question_topic(question))}
        else:context={}
        output['answered_question']=question
        return output,context

    @staticmethod
    def _comparison_context(output,question):
        context={}
        if output.get('choose_product'):
            context={'comparison_pending':True,'comparison_product_ids':output['comparison_plan']['product_ids'],
                     'pending_question':question,'pending_category':output.get('question_category'),
                     'pending_choices':[p['product_id'] for p in output.get('product_choices',[])]}
        output['answered_question']=question
        return output,context


class BowPolicyIndex:
    """Adapt source chunks to the existing graph contract after exact scope filters."""
    def __init__(self,product_id):self.product_id=product_id;self.knowledge=BowKnowledge()
    def retrieve(self,query,product='DEBIT_CHECKING',jurisdiction='US',as_of='2026-10-30',k=4):
        if jurisdiction!='US':return {'status':'NOT_FOUND','chunks':[]}
        chunks=self.knowledge.retrieve('BOW',self.product_id,as_of,allow_demo=True,query=query,limit=min(k,5))
        def category(scope):
            if scope=='ALL':return 'ALL'
            if scope=='ALL_SAVINGS':return 'SAVINGS'
            if scope=='CHECKING_DEBIT':return 'DEBIT_CHECKING'
            return self.knowledge.product_map[scope]['product_type'].upper()
        mapped=[{'doc_id':c['doc_id'],'title':self.knowledge.product_map.get(c['product_id'],{}).get('product_name',c['topic']),
                 'version':self.knowledge.version,'product':category(c['product_id']),'jurisdiction':'US','effective_date':c['effective_date'],
                 'expires_at':c['expires_on'],'approval_status':c['approval_status'],'chunk_id':c['chunk_id'],
                 'section':c['topic'],'text':c['chunk_text'],'token_count_approx':len(c['chunk_text'].split()),
                 'oversize_preserved':False,'score':c['retrieval_score'],'bank_id':'BOW','product_id':c['product_id'],
                 'content_hash':c['sha256_text']} for c in chunks]
        return {'status':'OK' if mapped else 'NOT_FOUND','chunks':mapped}
