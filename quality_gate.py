"""Conservative checks for local-AI educational interpretations.
A verbatim quote alone cannot validate the model's claim about a *change*.
"""
import re
from difflib import SequenceMatcher

EDITORIAL = re.compile(r'^(?:international standard|this international standard|document|this document|shall|the|a|an|and|or|of|to|for|in|on|is|are|be|was|were|that|which|;|,|\.)$', re.I)

def normalized(text):
    return ' '.join(str(text or '').split()).casefold()

def change_fragments(previous, revised):
    a = re.findall(r'\w+|[^\w\s]', previous, re.UNICODE)
    b = re.findall(r'\w+|[^\w\s]', revised, re.UNICODE)
    fragments=[]
    for tag,i,j,k,l in SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if tag != 'equal':
            fragments.append((' '.join(a[i:j]), ' '.join(b[k:l])))
    return fragments

def evaluate(row, analysis):
    """Returns (accepted, reason); uncertainty is safer than a false claim."""
    old, new = str(row.get('Previous text') or ''), str(row.get('Revised text') or '')
    quote = str(analysis.get('evidence_quote') or '').strip()
    if not quote or quote not in new:
        return False, 'Evidence quote not found in revised clause'
    if analysis.get('classification') != 'substantive_candidate':
        return True, 'Non-substantive classification'
    if normalized(quote) in normalized(old):
        return False, 'Quoted evidence already exists in previous clause; not evidence of a new requirement'
    fragments = change_fragments(old,new)
    meaningful = [newpart for _,newpart in fragments if len(newpart)>12 and not EDITORIAL.fullmatch(newpart.strip())]
    if not meaningful:
        return False, 'No meaningful revised wording identified'
    qwords = set(re.findall(r'\w+', normalized(quote)))
    if not any(len(qwords & set(re.findall(r'\w+', normalized(part)))) >= min(3, len(qwords)) for part in meaningful):
        return False, 'Evidence quote does not overlap meaningful changed wording'
    if re.search(r'\b(note|notes)\b', new[max(0,new.find(quote)-100):new.find(quote)], re.I):
        if re.search(r'\b(new requirement|must|shall|requires|mandatory)\b', ' '.join(str(analysis.get(k,'')) for k in ('key_change','why_it_matters','organization_review')), re.I):
            return False, 'Possible NOTE described as mandatory requirement'
    return True, 'Evidence overlaps changed wording; semantic correctness not verified'
