"""Practical results first; transparency about partial, unverified coverage."""
import io
from docx import Document
from docx.shared import Inches, Pt

def make_learning_docx(analyses,old_label,new_label,old_hash,new_hash,total_clauses=None,eligible_clauses=None,complete=False):
    doc=Document();sec=doc.sections[0]
    sec.top_margin=Inches(.72);sec.bottom_margin=Inches(.72)
    doc.styles['Normal'].font.size=Pt(9)
    doc.add_heading('Key Changes & Practical Implications',0)
    doc.add_paragraph(f'{old_label} → {new_label}')
    doc.add_paragraph('Developed by ByungGil Ken Ha')
    selected=[v for v in analyses.values() if v.get('classification')=='substantive_candidate']
    selected.sort(key=lambda x:tuple(int(n) for n in x['clause'].split('.')))
    doc.add_heading('Executive Summary',1)
    coverage=f'{len(analyses)} clauses analyzed'
    if eligible_clauses is not None: coverage+=f' of {eligible_clauses} eligible'
    if total_clauses is not None: coverage+=f' ({total_clauses} clause identifiers in the comparison)'
    doc.add_paragraph(coverage+'. '+str(len(selected))+' potential substantive changes identified by local AI.')
    if not complete:
        doc.add_paragraph('PARTIAL ANALYSIS — this document does not cover every potentially important change.')
    doc.add_paragraph('UNVERIFIED AI INTERPRETATIONS — use for learning, not as a compliance determination. Some clauses were excluded because source extraction was incomplete or misaligned.')
    if not selected:
        doc.add_paragraph('No evidence-supported substantive candidates are available from the processed clauses. This does not establish that the standard is unchanged.')
    for a in selected:
        doc.add_heading(f'Clause {a["clause"]}',2)
        for label,key in [('Key Change','key_change'),('Practical Implication','why_it_matters'),('What to Review','organization_review'),('Audit Focus','auditor_questions')]:
            p=doc.add_paragraph();p.add_run(label+': ').bold=True;p.add_run(a.get(key,''))
        p=doc.add_paragraph();p.add_run('Source evidence: ').bold=True;p.add_run('“'+a.get('evidence_quote','')+'”')
        doc.add_paragraph(f'Previous PDF p. {a.get("previous_page")}; Revised PDF p. {a.get("revised_page")}. AI draft, not human-verified.')
    doc.add_heading('Coverage & Limitations',1)
    doc.add_paragraph('Source quotations are checked against extracted text, not against a human-reviewed original. Quote matching does not establish that the interpretation is correct. Excluded, failed, or unprocessed clauses may contain important changes. Consult the complete Excel evidence and original licensed PDFs.')
    doc.add_paragraph('Previous SHA-256: '+old_hash+'\nRevised SHA-256: '+new_hash)
    buf=io.BytesIO();doc.save(buf);return buf.getvalue()
