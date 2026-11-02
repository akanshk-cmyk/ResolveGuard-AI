"""Conservative payment-error assertions shared by routing and safety fallback."""
import re


def asserted_payment_error(message: str) -> bool:
    text=' '.join(message.lower().split())
    if re.search(r'\b(without my permission|transfer i never made|never shopped there|do not remember buying|no idea how|second payment was not mine|atm.*error.*account was debited|transaction.*(?:is a mistake|shown is a mistake)|report reached the bank|lost their debit card)\b',text):
        if not re.search(r'\b(what if|how do|how can|what does)\b',text):return True
    if re.search(r'\bmerchant debited\s*\$[\d.]+.*\breceipt says\s*\$[\d.]+',text):
        amounts=re.findall(r'\$([\d.]+)',text)
        return len(amounts)>=2 and amounts[0]!=amounts[1]
    subject=r'\b(?:charges?|charged|payments?|transactions?|debits?|amount)\b'
    issue=r'(?:(?<!not )incorrect(?:ly)?|(?<!not )wrong(?:ly)?|not (?:right|correct)|isn\'t (?:right|correct)|(?:applied|charged|debited) (?:in error|by mistake))\b'
    # Definitions and hypothetical procedures are not reports of actual activity.
    if re.search(r'\b(?:what (?:is|does)|meaning of|definition of|how (?:do|can).*(?:report|handle)|what.*\bif)\b',text):
        if not re.search(r'\b(?:my|our|this|that|selected)\s+(?:charge|payment|transaction|debit|amount)\b.*'+issue,text):
            return False
    if re.search(subject+r'(?:\s+[a-z]+){0,5}\s+'+issue,text):
        return True
    return bool(re.search(r'\b(?:my|our|this|that|selected)\s+'+issue+r'\s+'+subject,text))
