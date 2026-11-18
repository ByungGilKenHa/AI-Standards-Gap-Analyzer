"""Opt-in local Ollama analysis; untrusted educational draft with evidence gates."""
import json
import re
from urllib.request import Request, urlopen
from quality_gate import evaluate

FIELDS = ('previous_summary','revised_summary','key_change','why_it_matters','organization_review','auditor_questions','classification','confidence','evidence_quote')
CLASSES = {'substantive_candidate','editorial','relocation_or_structure','uncertain'}

def candidates(rows, limit=None):
    """Exclude empty/misaligned clauses; prioritize content words, not raw edit count."""
    keywords = re.compile(r'climate|risk|opportunit|shall|determin|evaluat|document|communicat|monitor|review|responsib|customer|supplier|change|quality|objective|competenc|process', re.I)
    good=[]
    for r in rows:
        a,b = str(r.get('Previous text') or ''),str(r.get('Revised text') or '')
        if r.get('Status') != 'Modified' or r.get('Extraction warning') or min(len(a),len(b))<70:
            continue
        if re.sub(r'\s+',' ',a).strip()==re.sub(r'\s+',' ',b).strip():
            continue
        from difflib import SequenceMatcher
        score=SequenceMatcher(None,a,b,autojunk=False).ratio()
        rank = (2 if keywords.search(a+' '+b) else 0) + (1 if len(a)>140 and len(b)>140 else 0) + min(0.9,1-score)
        good.append((rank,r))
    return [r for _,r in (sorted(good,key=lambda p:-p[0])[:limit] if limit else sorted(good,key=lambda p:-p[0]))]

def analyze_clause(row, model='qwen3:1.7b', timeout=240):
    a,b = str(row['Previous text']),str(row['Revised text'])
    if row.get('Extraction warning') or min(len(a),len(b))<70:
        raise ValueError('Clause extraction is incomplete or flagged; AI interpretation blocked.')
    # Limit context and explicitly reject long/truncated clauses rather than silently analyzing fragments.
    if len(a)>6500 or len(b)>6500:
        raise ValueError('Clause too long for safe small-model analysis; needs manual subdivision.')
    prompt = '''You are preparing an UNVERIFIED educational ISO edition comparison, NOT a legal or compliance determination.
Use ONLY the two provided clause passages. Do not rely on prior knowledge of ISO standards.
Do not invent new obligations. Distinguish rewording, rearrangement and possible substantive changes.
Return ONLY one JSON object with exactly these string fields:
previous_summary, revised_summary, key_change, why_it_matters, organization_review, auditor_questions, classification, confidence, evidence_quote.
classification MUST be one of substantive_candidate, editorial, relocation_or_structure, uncertain.
confidence MUST be low, medium, or high (confidence in text-based explanation, not correctness of standard).
evidence_quote MUST be a SHORT verbatim contiguous excerpt from the REVISED passage (max 130 characters).
If unable to infer meaning, choose uncertain and explicitly say why. Keep each explanatory field under 350 characters.
Do not repeat generic advice to compare the PDFs. Use concrete language grounded in the text.
CLAUSE: '''+str(row['Clause'])+'\nPREVIOUS:\n'+a+'\nREVISED:\n'+b
    payload=json.dumps({'model':model,'prompt':prompt,'stream':False,'format':'json','options':{'temperature':0,'num_predict':950}}).encode()
    req=Request('http://127.0.0.1:11434/api/generate',data=payload,headers={'Content-Type':'application/json'},method='POST')
    with urlopen(req,timeout=timeout) as resp: result=json.load(resp)
    raw=result.get('response','')
    try: parsed=json.loads(raw)
    except (ValueError,TypeError) as e: raise ValueError('Local AI returned invalid JSON') from e
    if not isinstance(parsed,dict) or any(not isinstance(parsed.get(k),str) or not parsed[k].strip() for k in FIELDS):
        raise ValueError('Incomplete local AI response')
    if parsed['classification'] not in CLASSES or parsed['confidence'] not in {'low','medium','high'}:
        raise ValueError('Invalid AI classification')
    quote=parsed['evidence_quote'].strip()
    if len(quote)>130 or quote not in b:
        raise ValueError('AI evidence quote not found verbatim in revised clause; rejected')
    for k in FIELDS:
        parsed[k]=parsed[k].strip()[:500]
    parsed['clause']=str(row['Clause'])
    parsed['previous_page']=row.get('Previous PDF page')
    parsed['revised_page']=row.get('Revised PDF page')
    passed, reason = evaluate(row, parsed)
    parsed['quality_gate'] = reason
    if not passed:
        parsed['classification'] = 'uncertain'
        parsed['key_change'] = 'Potential change not confirmed by available text evidence.'
        parsed['why_it_matters'] = 'No reliable practical implication can be established from the extracted comparison.'
        parsed['organization_review'] = 'Verify the clause against the original source before making changes.'
        parsed['auditor_questions'] = 'No new audit obligation can be concluded from this draft.'
    parsed['review_status']='AI draft — human verification required'
    return parsed
