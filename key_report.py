"""Short, evidence-traceable educational brief. No invented normative interpretations."""
import io
import re
from docx import Document
from docx.shared import Inches, Pt
from auto_report import auto_matrix, short_excerpt

# Do not rank by edit count: punctuation-heavy clauses can have many edits.
EDITORIAL = re.compile(r'^(?:\W|international standard|document|shall|the|a|an|and|or|of|to|is|are|be|this|that|in|for|with|on|at|it|its|[a-z]\))+$', re.I)

def meaningful_evidence(entry):
    text = str(entry.get('Observed text evidence', ''))
    if not text or text.startswith(('No positional', 'Unmatched clause')):
        return False
    snippets = re.findall(r'(?:Replaced|Inserted at position|Deleted at position): (.*?)(?= \(x\d+\)|; (?:Replaced|Inserted at position|Deleted at position):|$)', text)
    return any(len(re.sub(r'\W', '', s)) > 20 and not EDITORIAL.fullmatch(s.strip()) for s in snippets)

def is_interpretation(entry):
    return entry['Interpretation source'] != 'Automatic text evidence only'

def select_key_changes(matrix, max_items=12):
    """Prefer documented educational interpretations; uncertain text-only items never asserted as significant."""
    confirmed = []
    candidates = []
    for entry in matrix:
        if entry['Comparison status'] == 'Unchanged':
            continue
        if (is_interpretation(entry) and entry['Clause'] not in ('1', '2') and not re.search(r'no substantive|editorial only|no significant|unchanged|no material change', str(entry.get('Structural / text change','')), re.I) and any(entry.get(k) for k in ('Structural / text change', 'Audit / learning focus'))):
            confirmed.append(entry)
        elif meaningful_evidence(entry) and entry['Comparison status'] == 'Modified':
            candidates.append(entry)
    # Reference-based interpretations are still unverified, not 'confirmed' normative findings.
    confirmed.sort(key=lambda e: (bool(e['Extraction warning']), len(e['Clause'].split('.')), tuple(int(n) for n in e['Clause'].split('.'))))
    candidates.sort(key=lambda e: (bool(e['Extraction warning']), len(e['Clause'].split('.')), tuple(int(n) for n in e['Clause'].split('.'))))
    return (confirmed + candidates)[:max_items]

def make_key_changes_docx(rows, evidence, reviews, previous_label, revised_label, previous_hash, revised_hash, reference=None, max_items=12):
    matrix = auto_matrix(rows, evidence, reviews, reference)
    chosen = select_key_changes(matrix, max_items)
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(.75); section.bottom_margin = Inches(.7)
    section.left_margin = Inches(.78); section.right_margin = Inches(.78)
    doc.styles['Normal'].font.size = Pt(9)
    doc.add_heading('Key Changes & Learning Guide', 0)
    doc.add_paragraph(f'{previous_label} → {revised_label}')
    doc.add_paragraph('Developed by ByungGil Ken Ha')
    doc.add_paragraph('EDUCATIONAL DRAFT — a concise reading guide, not a verified requirements gap analysis. Source text extraction and edition status require human verification. Reference notes and AI interpretations are not authoritative.')
    doc.add_heading('Executive Summary', 1)
    interpreted = sum(is_interpretation(e) for e in chosen)
    doc.add_paragraph(f'{len(matrix)} clause identifiers compared. {len(chosen)} items selected for focused reading; {interpreted} include user-provided educational descriptions or reviewer notes. Selection is a reading shortlist, NOT a validated ranking of normative significance.')
    if not interpreted:
        doc.add_paragraph('No educational reference matrix or reviewer interpretations were supplied. The items below are provisional text-evidence candidates, not explanations of new requirements. For a substantive learning guide, upload a trusted reference matrix or add reviewed descriptions. Do not treat this shortlist as a confirmed significant-change list.')
    flagged = sum(bool(e['Extraction warning']) for e in matrix)
    doc.add_paragraph(f'{flagged} clause identifiers have extraction/alignment warnings in the full Excel report. Consult Excel for complete evidence, including items omitted here.')
    doc.add_heading('Priority Reading List', 1)
    if not chosen:
        doc.add_paragraph('No suitable key-change candidates were identified. Consult the full Excel evidence report; this does not establish that the standards are equivalent.')
    for i, entry in enumerate(chosen, 1):
        doc.add_heading(f'{i}. Clause {entry["Clause"]}', level=2)
        doc.add_paragraph('Source: ' + ('Reference / reviewer interpretation — unverified' if is_interpretation(entry) else 'Text-evidence candidate — meaning NOT assessed'))
        if is_interpretation(entry):
            table = doc.add_table(rows=0, cols=2); table.style = 'Light Shading Accent 1'
            for label, field in [('Previous edition', 'Previous edition summary'), ('Revised edition', 'Revised edition summary'), ('Key change', 'Structural / text change'), ('Learning / audit focus', 'Audit / learning focus')]:
                c = table.add_row().cells; c[0].text = label; c[1].text = str(entry[field])
        else:
            doc.add_paragraph('Observed change: ' + short_excerpt(entry['Observed text evidence'], 310))
            doc.add_paragraph('Learning task: Compare the complete clause text in both PDFs and decide whether this is editorial, relocated, or potentially substantive. No conclusion is automated.')
        doc.add_paragraph(f'Original PDF pages: previous {entry["Previous PDF page"] or "not located"}; revised {entry["Revised PDF page"] or "not located"}.')
        if entry['Extraction warning']:
            doc.add_paragraph('CHECK ALIGNMENT: ' + short_excerpt(entry['Extraction warning'], 190))
        if entry['Evidence IDs']:
            doc.add_paragraph('Evidence IDs (see Excel): ' + short_excerpt(entry['Evidence IDs'], 180))
    doc.add_heading('How to Use This Guide', 1)
    doc.add_paragraph('Read the selected clauses first, verify every interpretation against licensed source PDFs, and consult the Excel workbook for all clauses, positional changes, and extraction flags. Omission from this guide does not mean an unchanged or non-applicable requirement.')
    doc.add_paragraph('Previous SHA-256: ' + previous_hash + '\nRevised SHA-256: ' + revised_hash)
    out=io.BytesIO();doc.save(out);return out.getvalue()
