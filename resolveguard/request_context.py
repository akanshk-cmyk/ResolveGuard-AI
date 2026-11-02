"""Bind customer resource references without treating claimed identity as authority."""
import re
from datetime import date
from decimal import Decimal

VERSION = 'request-context-v1'
TRANSFER_MESSAGE = ("I can't transfer money in this support chat. Use your bank's approved transfer service. "
                    "I can help with payment questions or reporting a problem.")
REPORT_FOLLOWUP = ("To help identify the payment, what merchant name and approximate date appear for the charge? "
                   "You can also sign in securely to select it. Please do not share your full card number, PIN, CVV, password or one-time code.")


def references(message):
    result = {}
    for kind in ('ACC', 'CASE', 'TXN'):
        result[kind] = tuple(dict.fromkeys(value.upper() for value in re.findall(
            rf'\b(?:BOW-)?{kind}-[A-Z0-9]+(?:-[A-Z0-9]+)*\b', message, re.I)))
    return result


def bind_turn(turn):
    """Explicit text replaces old UI context. Principal IDs are never parsed."""
    if turn.action != 'message':
        return turn
    ids = references(turn.message)
    if len(ids['ACC']) > 1 or len(ids['CASE']) > 1:
        raise ValueError('MULTIPLE_RESOURCE_TARGETS')
    updates = {}
    if ids['ACC']:
        updates.update(account_id=ids['ACC'][0], transaction_ids=ids['TXN'])
        if not ids['CASE']:
            updates['case_id'] = None
    if ids['CASE']:
        updates.update(case_id=ids['CASE'][0], transaction_ids=())
    if ids['TXN']:
        updates['transaction_ids'] = ids['TXN']
    return turn.model_copy(update=updates)


def transfer_requested(message):
    text = message.lower().strip()
    return bool(re.search(r'\b(?:transfer|send|move)\b.{0,30}\b(?:funds?|money|balance|dollars?)\b', text)
                and not re.search(r'\b(?:fees?|policy|terms|how does|how do transfers)\b', text))


def charge_inquiry(message):
    return bool(re.search(r'\b(?:charged|why did you charge|why did the bank charge|fee charged|charge on my account)\b', message, re.I))


def match_charges(rows, message, as_of):
    """Filter authorized rows only; calendar months use the trusted server clock."""
    text = message.lower()
    amount = re.search(r'\$\s*([\d,]+(?:\.\d{1,2})?)|\b(\d+(?:\.\d{1,2})?)\s*(?:dollars?|usd)\b', text)
    cents = int(Decimal((amount[1] or amount[2]).replace(',', '')) * 100) if amount else None
    today = date.fromisoformat(as_of[:10])
    start = end = None
    if 'last month' in text:
        end = today.replace(day=1)
        start = date(end.year - 1, 12, 1) if end.month == 1 else end.replace(month=end.month - 1)
    elif 'this month' in text:
        start = today.replace(day=1)
        end = date(start.year + 1, 1, 1) if start.month == 12 else start.replace(month=start.month + 1)
    return [r for r in rows if (cents is None or abs(r['amount_cents']) == cents)
            and (start is None or start <= date.fromisoformat(r['posted_on']) < end)
            and ('fee' not in text or 'fee' in r['merchant'].lower())]
