"""User-verified clause notes and a conservative, evidence-linked change matrix."""
import io
from docx import Document
from docx.shared import Inches, Pt, RGBColor

FIELDS = ('Previous edition summary', 'Revised edition summary', 'Structural / text change', 'Audit / learning focus')
STATUS = ('Not Reviewed', 'Reviewed', 'Needs Recheck')


def reviewed_count(rows, reviews):
    return sum(reviews.get(str(row['Clause']), {}).get('Review status') == 'Reviewed' for row in rows)


def ready_for_final(rows, reviews):
    return bool(rows) and reviewed_count(rows, reviews) == len(rows)


def matrix_rows(rows, reviews):
    result = []
    for row in rows:
        clause = str(row['Clause'])
        note = reviews.get(clause, {})
        result.append({
            'Clause': clause,
            'Previous heading (extracted)': row.get('Previous title', ''),
            'Revised heading (extracted)': row.get('Revised title', ''),
            'Comparison status': row.get('Status', ''),
            'Review status': note.get('Review status', 'Not Reviewed'),
            'Previous edition summary': note.get('Previous edition summary', ''),
            'Revised edition summary': note.get('Revised edition summary', ''),
            'Structural / text change': note.get('Structural / text change', ''),
            'Audit / learning focus': note.get('Audit / learning focus', ''),
            'Reviewer notes': note.get('Reviewer notes', ''),
            'Previous PDF page': row.get('Previous PDF page', ''),
            'Revised PDF page': row.get('Revised PDF page', ''),
            'Extraction warning': row.get('Extraction warning', ''),
        })
    return result


def make_docx(rows, reviews, previous_label, revised_label, previous_hash, revised_hash):
    if not ready_for_final(rows, reviews):
        raise ValueError('All clause identifiers must be marked Reviewed before final report export.')
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(.72)
    section.bottom_margin = Inches(.72)
    section.left_margin = Inches(.7)
    section.right_margin = Inches(.7)
    styles = doc.styles
    styles['Normal'].font.name = 'Aptos'
    styles['Normal'].font.size = Pt(9)
    title = doc.add_heading('Clause-by-Clause Change Matrix', 0)
    title.style.font.color.rgb = RGBColor(23, 54, 93)
    doc.add_paragraph(f'{previous_label}  →  {revised_label}')
    doc.add_paragraph('Developed by ByungGil Ken Ha')
    doc.add_paragraph('Human-reviewed working document for gap analysis and learning. Not an official interpretation or compliance determination.')
    doc.add_heading('Source and review record', level=1)
    doc.add_paragraph(f'Previous PDF SHA-256: {previous_hash}\nRevised PDF SHA-256: {revised_hash}\nReviewed clause identifiers: {len(rows)} of {len(rows)}')
    doc.add_paragraph('Notes and summaries below were entered by the reviewer. Clause alignment and extracted headings are provisional; check the original PDFs. Blank cells mean no reviewer text was entered.')
    doc.add_heading('Significant change and learning matrix', level=1)
    for entry in matrix_rows(rows, reviews):
        doc.add_heading(f"Clause {entry['Clause']} — {entry['Revised heading (extracted)'] or entry['Previous heading (extracted)'] or 'Heading not detected'}", level=2)
        doc.add_paragraph(f"Comparison: {entry['Comparison status']}  |  Previous PDF p. {entry['Previous PDF page']}  |  Revised PDF p. {entry['Revised PDF page']}")
        table = doc.add_table(rows=0, cols=2)
        table.style = 'Light Shading Accent 1'
        for key in FIELDS:
            cells = table.add_row().cells
            cells[0].text = key
            cells[1].text = entry[key] or '—'
        if entry['Reviewer notes']:
            doc.add_paragraph('Reviewer notes: ' + entry['Reviewer notes'])
        if entry['Extraction warning']:
            doc.add_paragraph('Extraction warning: ' + entry['Extraction warning'])
    doc.add_heading('Limitations', level=1)
    doc.add_paragraph('This report is based on positional text differences and human-entered notes. It does not establish normative impact, confirm clause relocation, or authenticate editions. The user is responsible for validating interpretations against licensed originals.')
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
