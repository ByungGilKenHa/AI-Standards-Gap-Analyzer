"""User-supplied educational matrix, not a validated normative authority."""
import io
import re
from docx import Document


def load_reference(docx_bytes):
    doc = Document(io.BytesIO(docx_bytes))
    result = {}
    for table in doc.tables:
        if len(table.columns) < 5:
            continue
        for row in table.rows[1:]:
            cells = [" ".join(c.text.split()) for c in row.cells]
            m = re.match(r"^((?:[1-9]|10)(?:\.\d+){0,4})(?:\s|$)", cells[0])
            if not m:
                continue
            number = m.group(1)
            if number in result:
                continue
            result[number] = {
                "Previous edition summary": cells[1],
                "Revised edition summary": cells[2],
                "Structural / text change": cells[3],
                "Audit / learning focus": cells[4],
                "Reference clause": cells[0],
            }
    return result
