"""Automatic evidence-linked matrix; descriptions are textual, not semantic judgments."""
import io
from collections import defaultdict
from docx import Document
from docx.shared import Inches, Pt
from diff_engine import grouped_changes


def short_excerpt(value, limit=160):
    value = ' '.join(str(value or '').split())
    return value if len(value) <= limit else value[:limit].rsplit(' ', 1)[0] + '…'


def auto_matrix(rows, evidence, reviews=None, reference=None):
    by_clause = defaultdict(list)
    for edit in evidence:
        by_clause[str(edit['Clause'])].append(edit)
    output = []
    for row in rows:
        number = str(row['Clause'])
        edits = by_clause[number]
        kinds = sorted(set(e['Change type'] for e in edits))
        status = row['Status']
        if edits:
            details = '; '.join(f"{g['Change type']}: {short_excerpt(g['Previous excerpt'], 65) or '[none]'} → {short_excerpt(g['Revised excerpt'], 65) or '[none]'} (x{g['Occurrences']})" for g in grouped_changes(edits)[:4])
            change = f'{len(edits)} positional differences ({", ".join(kinds)}). Examples: {details}'
        elif status == 'Unchanged':
            change = 'No positional word-level difference detected in extracted matched text.'
        else:
            change = 'Unmatched clause identifier: possible addition, removal, or relocation; not confirmed.'
        old_title = row.get('Previous title', '') or 'Heading not detected'
        new_title = row.get('Revised title', '') or 'Heading not detected'
        old_summary = ('Not found under this clause identifier; verify renumbering.' if not row.get('Previous text') else f'Extracted heading: {short_excerpt(old_title, 100)}. Source: previous PDF p. {row.get("Previous PDF page")}.')
        new_summary = ('Not found under this clause identifier; verify renumbering.' if not row.get('Revised text') else f'Extracted heading: {short_excerpt(new_title, 100)}. Source: revised PDF p. {row.get("Revised PDF page")}.')
        focus = 'Compare both original PDF pages, verify extraction and clause alignment; determine any meaning or audit impact manually.' if status != 'Unchanged' or row.get('Extraction warning') else 'Confirm source extraction if this clause is material to the review.'
        note = (reviews or {}).get(number, {})
        source = (reference or {}).get(number, {})
        # The source matrix is a user-provided educational interpretation, not verified by this program.
        # Prefer user notes, then attributed source interpretation, then deterministic text-only fallback.
        def field(name, fallback):
            return note.get(name) or source.get(name) or fallback
        provenance = ('Human reviewer notes' if any(note.get(f) for f in ('Previous edition summary', 'Revised edition summary', 'Structural / text change', 'Audit / learning focus'))
                      else 'User-provided reference matrix (unverified)' if source else 'Automatic text evidence only')
        output.append({'Clause': number, 'Comparison status': status,
            'Previous edition summary': field('Previous edition summary', old_summary),
            'Revised edition summary': field('Revised edition summary', new_summary),
            'Structural / text change': field('Structural / text change', change),
            'Audit / learning focus': field('Audit / learning focus', focus),
            'Review status': note.get('Review status', 'Not Reviewed'),
            'Previous PDF page': row.get('Previous PDF page', ''),
            'Revised PDF page': row.get('Revised PDF page', ''),
            'Extraction warning': row.get('Extraction warning', ''),
            'Evidence IDs': ', '.join(e['Evidence ID'] for e in edits),
            'Reviewer notes': note.get('Reviewer notes', ''), 'Interpretation source': provenance, 'Observed text evidence': change})
    return output


def make_automatic_docx(rows, evidence, reviews, previous_label, revised_label, previous_hash, revised_hash, reference=None):
    matrix = auto_matrix(rows, evidence, reviews, reference)
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(.65)
    section.bottom_margin = Inches(.65)
    section.left_margin = Inches(.65)
    section.right_margin = Inches(.65)
    doc.styles['Normal'].font.size = Pt(9)
    doc.add_heading('Automatic Clause-by-Clause Change Matrix', 0)
    doc.add_paragraph(f'{previous_label} → {revised_label}')
    doc.add_paragraph('Developed by ByungGil Ken Ha')
    doc.add_paragraph('EDUCATIONAL WORKING DRAFT — interpretations, when present, come from user-provided reference material or reviewer notes. They are not verified by the software. Text evidence is separately identified. No compliance determination.')
    doc.add_paragraph(f'Previous SHA-256: {previous_hash}\nRevised SHA-256: {revised_hash}')
    doc.add_paragraph(f'{len(matrix)} clause identifiers; {sum(1 for x in matrix if x["Review status"] == "Reviewed")} reviewed by user.')
    doc.add_heading('Change matrix', level=1)
    for entry in matrix:
        doc.add_heading(f'Clause {entry["Clause"]} — {entry["Comparison status"]}', level=2)
        doc.add_paragraph(f'Previous PDF p. {entry["Previous PDF page"]} | Revised PDF p. {entry["Revised PDF page"]} | Review: {entry["Review status"]}')
        table = doc.add_table(rows=0, cols=2)
        table.style = 'Light Shading Accent 1'
        for key in ('Previous edition summary', 'Revised edition summary', 'Structural / text change', 'Audit / learning focus'):
            cells = table.add_row().cells
            cells[0].text, cells[1].text = key, str(entry[key])
        doc.add_paragraph('Interpretation source: ' + entry['Interpretation source'])
        doc.add_paragraph('Observed text evidence: ' + entry['Observed text evidence'])
        if entry['Extraction warning']:
            doc.add_paragraph('Extraction / alignment warning: ' + str(entry['Extraction warning']))
        if entry['Evidence IDs']:
            doc.add_paragraph('Evidence IDs: ' + entry['Evidence IDs'])
        if entry['Reviewer notes']:
            doc.add_paragraph('Reviewer notes: ' + entry['Reviewer notes'])
    doc.add_heading('Limitations', level=1)
    doc.add_paragraph('Text extracted from PDFs may be inaccurate. Positional insertions and deletions may be relocations. Edition authenticity and normative effect are not verified. User-supplied comments are not independently validated. Reference material and user-entered notes are unverified interpretations; reference matching by clause number is provisional. AI learning is separate and excluded from this report.')
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
