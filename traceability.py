"""Clause-linked traceability records; AI interpretations are never represented as verified."""
from difflib import SequenceMatcher
import re

def _snippet(text, limit=280):
    return ' '.join(str(text or '').split())[:limit]

def trace_rows(rows, analyses, failures=None):
    failures=failures or {}
    out=[]
    for row in rows:
        clause=str(row['Clause'])
        old=str(row.get('Previous text') or '')
        new=str(row.get('Revised text') or '')
        ai=analyses.get(clause,{})
        warning=str(row.get('Extraction warning') or '')
        if warning or not old.strip() or not new.strip():
            state='Source alignment review required'
        elif clause in failures and not ai:
            state='Local AI analysis failed'
        elif not ai:
            state='Not analyzed'
        elif ai.get('classification')=='uncertain':
            state='Interpretation not established'
        else:
            state='AI draft — expert review required'
        out.append({
            'Clause':clause,
            'Previous PDF page':row.get('Previous PDF page'),
            'Revised PDF page':row.get('Revised PDF page'),
            'Previous requirement excerpt':_snippet(old),
            'Revised requirement excerpt':_snippet(new),
            'Comparison status':row.get('Status'),
            'AI change classification':ai.get('classification','Not assessed'),
            'Key change (unverified)':ai.get('key_change',''),
            'Practical implication (unverified)':ai.get('why_it_matters',''),
            'Organization review (unverified)':ai.get('organization_review',''),
            'Audit focus (unverified)':ai.get('auditor_questions',''),
            'Revised evidence quote':ai.get('evidence_quote',''),
            'Evidence gate':ai.get('quality_gate',''),
            'Verification state':state,
            'Source warning':warning,
            'Failure detail':failures.get(clause,''),
        })
    return out
