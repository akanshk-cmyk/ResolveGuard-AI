"""Plain-language customer copy derived from confirmed workflow results."""
from datetime import date

STATUS = {'POSTED': 'posted', 'PENDING': 'pending', 'REVERSED': 'reversed', 'DECLINED': 'declined', 'OPEN': 'open',
          'IN_REVIEW': 'being reviewed', 'WAITING_FOR_CUSTOMER': 'waiting for information from you',
          'RESOLVED': 'marked resolved', 'CLOSED': 'closed','PENDING_REVIEW':'awaiting review'}

# Draft paraphrases of the demo policies; human approval is not recorded.
GUIDANCE = {
    'POL-FEE-001': 'In this demo, a $12 monthly account fee may apply. Whether it can be waived depends on the account terms.',
    'POL-FEE-002': 'Support needs to check your account terms before confirming a fee waiver or refund.',
    'POL-TRAN-001': 'A pending payment is still being processed. A completed payment appears in your transaction history.',
    'POL-TRAN-002': 'If you do not recognise a payment, tell us what happened so we can save your report and request support.',
    'POL-ERR-001': 'We save your report and the time you sent it. The support team determines how it should be handled.',
    'POL-ERR-002': 'A support reference alone does not confirm that a formal error notice has been accepted.',
    'POL-AUTH-001': 'Please sign in to view details of accounts you have permission to access.',
    'POL-AUTH-002': 'If you are helping someone else, your access must cover their account and the action you want to take.',
    'POL-AUTH-003': 'Some actions need an extra identity check. Never share passwords, PINs, card security codes or one-time codes in chat.',
    'POL-FRAUD-001': 'For suspected ongoing card fraud, contact the fraud support team. Saving a report does not block your card.',
    'POL-CASE-001': 'A request may be open, being reviewed, waiting for your information, resolved or closed. Closed does not necessarily mean the issue was resolved.',
    'POL-CASE-002': 'If we cannot confirm a request was saved, retry the same request before starting another one.',
    'POL-PRIV-001': 'Only information needed for your request should be shared.',
    'POL-PRIV-002': 'Sensitive account and sign-in details should only be shared through approved, secure channels.',
    'POL-HAND-001': 'We only confirm delivery when the support team has received your request.',
    'POL-HAND-002': 'Your information can only be shared with a support team that is allowed to access it.',
    'POL-COMP-001': 'A problem checking account details should not prevent your complaint from being saved and passed to support.',
    'POL-SERV-001': 'The assistant can only view account information when your current access allows it.',
    'POL-DEMO-LIMIT': 'This demo uses an example daily debit-card purchase limit of $1,000. This is not a real bank limit.',
    'POL-DEMO-ATM': 'In this demo, an out-of-network ATM withdrawal may have a $3.50 bank fee. The ATM operator may also charge a fee. Check the transaction for the actual amount.',
    'POL-DEMO-OVERDRAFT': 'Overdraft fees and eligibility depend on your account terms and choices. Support can help check these; a refund is not guaranteed.',
}


def customer_copy(result):
    state = result.get('response_state')
    if state in {'SECURITY_BLOCKED','PUBLIC_SECURITY_INFORMATION'}:
        from .security_routing import BLOCK_MESSAGE, EDUCATION_MESSAGE
        return BLOCK_MESSAGE if state == 'SECURITY_BLOCKED' else EDUCATION_MESSAGE
    if state=='DATA_BLOCKED':return "I cannot use or share another customer's information. Unexpected private information needs review."
    if state=='PRIVACY_INCIDENT':return 'A possible secret in a trace needs privacy review. Please do not repeat the code here. The incident signal is recorded for local review.'
    if state=='SAFE_GUIDANCE' and 'full debit card number' in result.get('response','').lower():return 'Full card numbers are not available in chat. Please use the approved secure banking channel.'
    if state == 'AUTH_REQUIRED':
        return 'Please sign in again to view your account details.'
    if state == 'ACCESS_DENIED':
        return 'I cannot show those details with your current access. Please contact support for help.'
    if state=='STEP_UP_REQUIRED':return 'Please complete additional secure verification before viewing account details.'
    lines = []
    if state=='RECEIPT_SEPARATE':lines.append('Your report, formal notice receipt and support case are separate. A case status does not confirm formal notice receipt.')
    if state=='VERIFIED_NOTICE_STATE':lines.append('Your report is recorded. Its formal notice status still needs review; this is separate from the support-case status.')
    if state=='RECEIVED_CASE_UNKNOWN':lines.append('Your report is saved, but case creation is not confirmed.')
    if state=='HUMAN_REVIEW':lines.append('I have not closed the claim. A person must review this request; the report remains saved.')
    intent = result.get('route', {}).get('primary_intent')
    if intent == 'UNSUPPORTED_REQUEST':
        lines.append('This demo cannot move money, issue refunds, change sign-in details or decide disputes. A support team can help with your next steps.')
    report = result.get('report') or {}
    if report:
        if report.get('status') == 'OK':
            lines.append(f"Your report is saved. Your reference is {report['event_id']}. Saving a report does not block your card, start an investigation or confirm acceptance of a formal error notice.")
        elif report.get('status') == 'CONFLICT':
            lines.append('This request was already used for a different report. Start a new message to report a different issue.')
        else:
            lines.append('I could not confirm that your report was saved. Please retry the same request before sending a new report.')
    case = result.get('case') or {}
    if case.get('status') == 'OK':
        lines.append(f"Your support request is saved and open. Your reference is {case['event_id']}.")
    elif case and not result.get('draft'):
        lines.append('I could not confirm that your support request was saved. Please retry the same request before creating another one.')
    for record in result.get('records', []):
        if record.get('kind') == 'transaction':
            amount = format_money(record['amount_cents'], record.get('currency', 'USD'))
            when = date.fromisoformat(record['posted_on']).strftime('%b %d, %Y')
            merchant = record['merchant'].removeprefix('DEMO ').title()
            status = STATUS.get(record['status'], 'not confirmed')
            lines.append(f"The payment to {merchant} is {amount}. Its status is {status}. The date shown in the record is {when}.")
        else:
            status = STATUS.get(record.get('status'), 'not confirmed')
            lines.append(f"Your support request ({record['case_id']}) is {status}.")
    reads = [t for t in result.get('tools', []) if t['name'] in {'get_transaction', 'get_case_status'}]
    if any(t['status'] == 'DENIED' for t in reads):
        lines.append('I cannot show the account details with your current access. Please sign in again or contact support.')
    elif any(t['status'] == 'UNKNOWN' for t in reads):
        lines.append('I could not check the account details right now. Please try again.')
    if result.get('draft'):
        lines.append('Please review your request below, then choose Send request or Cancel. Nothing has been sent yet.')
    if state == 'CANCELLED':
        lines.append('Your draft is cancelled. No support request was created.')
    if state == 'ACTION_UNAVAILABLE':
        lines.append('I could not complete that step. Please sign in again and review your request. If the draft has expired, start a new one.')
    if state == 'CLARIFICATION_REQUIRED':
        lines.append('Please select the payment you want to ask about, or tell us which support request you mean.')
    if intent in {'POLICY_LOOKUP', 'FEE_INQUIRY'}:
        summaries = policy_sources(result)
        lines.extend(s['summary'] for s in summaries[:2] if s['summary'])
        if not summaries:
            lines.append('I could not find guidance that answers this question. Please check with support.')
    handoff = (result.get('handoff') or {}).get('handoff_status')
    if handoff == 'ACKNOWLEDGED':
        lines.append('The support team has received your request. This does not mean a person has started reviewing it yet.')
    elif handoff == 'UNAVAILABLE':
        lines.append('I could not connect you to the support team right now. Please try again.')
    elif handoff == 'BLOCKED':
        lines.append('I could not share these details with the support team because access could not be confirmed. Please contact support through a secure channel.')
    elif handoff:
        lines.append('I could not confirm that your request reached the support team. Please try again.')
    return '\n\n'.join(lines) or 'Tell us a little more about what you need help with. Please do not share passwords, PINs or one-time codes.'


def policy_sources(result):
    if result.get('bank_id')=='BOW':
        from .bow_knowledge import BowKnowledge
        return BowKnowledge().sources(result.get('citations',[]))
    from .retrieval import PolicyIndex
    lookup = {c['chunk_id']: c for c in PolicyIndex().chunks}
    return [{'title': c['title'], 'summary': GUIDANCE.get(c['doc_id'], '') if c['version'] in {'demo-v1', 'demo-extension-v1'} else 'Please check this guidance with support.',
             'reference': c['chunk_id'], 'version': c['version'], 'effective_date': c['effective_date'],
             'notice': 'Sample policy; customer wording awaits human review.'}
            for key in dict.fromkeys(result.get('citations', [])) if (c := lookup.get(key)) is not None]


def format_money(cents, currency='USD'):
    """Preserve signed integer cents without floating-point conversion."""
    if type(cents) is not int or currency != 'USD':
        raise ValueError('Only integer USD cents are supported')
    return f"{'-' if cents < 0 else ''}${abs(cents)//100:,}.{abs(cents)%100:02d} USD"


def customer_cards(result):
    cards=[]
    for record in result.get('records', []):
        if record.get('kind') == 'transaction':
            cards.append({'kind':'transaction', 'reference':record['transaction_id'],
                          'title':record['merchant'].removeprefix('DEMO ').title(),
                          'amount':format_money(record['amount_cents'],record['currency']),
                          'status':STATUS[record['status']].capitalize(), 'date':record['posted_on'],
                          'date_label':'Date in record' if record['status']=='PENDING' else 'Posting date',
                          'note':'Signed amount from the BOW source record.' if result.get('bank_id')=='BOW' else 'Sample payment. Debit/credit direction is not supplied.',
                          **({'account_display':record['account_display']} if record.get('account_display') else {})})
        else:
            cards.append({'kind':'case','reference':record['case_id'],'title':'Support request',
                          'status':STATUS[record['status']].capitalize(),'date':record['created_at'],
                          'date_label':'Created','note':'Closed does not necessarily mean resolved.' if record['status']=='CLOSED' else ''})
    case=result.get('case') or {}
    if case.get('status')=='OK':
        cards.append({'kind':'case','reference':case['event_id'],'title':'Support request created',
                      'status':'Open','date':case['committed_at'],'date_label':'Created',
                      'note':'A saved support request does not confirm a refund or investigation.'})
    return cards
