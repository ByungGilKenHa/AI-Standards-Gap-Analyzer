"""Conservative PDF clause extraction with explicit extraction diagnostics."""
import re
from dataclasses import dataclass
from collections import Counter
from difflib import SequenceMatcher
import fitz

CLAUSE = re.compile(r'^(?P<num>(?:[1-9]|10)(?:\.\d+){0,4})(?:[ \t]+(?P<title>\S.*))?$')
STOP = re.compile(r'^Annex\s+[A-Z]\b', re.I)
NOISE = re.compile(r'^(?:ISO \d{4,6}(?::|\b)|© ISO|All rights reserved|INTERNATIONAL STANDARD|Reference number)', re.I)

@dataclass
class Clause:
    number: str
    title: str
    text: str
    page: int
    warnings: tuple = ()


def _page_noise(doc):
    """Detect recurrent page-margin lines and visibly licensed footer strings.

    Never discard content solely because of language or company name.
    """
    counts = Counter()
    for page in doc:
        h = page.rect.height
        seen = set()
        for text, y in _lines(page):
            if y < h * .11 or y > h * .87:
                seen.add(re.sub(r'\d+', '#', text.casefold()))
        counts.update(seen)
    return {text for text, count in counts.items() if count >= max(3, round(len(doc) * .2))}


def _is_noise(text, y, page_height, repeated):
    normalized = re.sub(r'\d+', '#', text.casefold())
    in_margin = y < page_height * .11 or y > page_height * .87
    return bool(NOISE.match(text) or (in_margin and normalized in repeated))


def _lines(page):
    lines = []
    for block in page.get_text('dict', sort=True)['blocks']:
        for line in block.get('lines', []):
            spans = line.get('spans', [])
            if not spans:
                continue
            raw = re.sub(r'\s+', ' ', ''.join(s['text'] for s in spans).replace('\u00a0', ' ')).strip()
            if raw:
                lines.append((raw, round(line['bbox'][1], 1)))
    return sorted(lines, key=lambda x: x[1])


def extract_clauses(pdf_bytes):
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        if not doc.page_count:
            raise ValueError('PDF has no pages.')
        starts = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if re.search(r'(?m)^\s*1\s+Scope\s*$', text) and ('2 Normative references' in text or i >= 3):
                starts.append(i)
        if not starts:
            raise ValueError('Clause 1 Scope was not located. Check scanned PDFs, edition layout, or text extraction.')
        # Prefer the last plausible Scope start before body; TOC commonly appears first.
        start = starts[-1] if len(starts) <= 2 else starts[1]
        repeated = _page_noise(doc)
        clauses, active = {}, None
        for page_idx in range(start, len(doc)):
            lines = _lines(doc[page_idx])
            j = 0
            while j < len(lines):
                line, y = lines[j]
                if STOP.match(line):
                    return clauses
                if _is_noise(line, y, doc[page_idx].rect.height, repeated):
                    j += 1
                    continue
                match = CLAUSE.fullmatch(line)
                if match:
                    number, title = match.group('num'), match.group('title') or ''
                    if not title and j + 1 < len(lines) and 0 < lines[j + 1][1] - y < 35:
                        candidate = lines[j + 1][0]
                        if len(candidate) < 110 and not CLAUSE.fullmatch(candidate) and not NOISE.match(candidate):
                            title = candidate
                            j += 1
                    if title and len(title) < 130:
                        if number not in clauses:
                            clauses[number] = Clause(number, title, '', page_idx + 1)
                        active = number
                        j += 1
                        continue
                if active and not re.fullmatch(r'[ivxlcdm]+|\d+', line, re.I):
                    # Licensed PDFs sometimes embed a single-line, dated watermark inside
                    # the body region. Flag rather than silently deleting ambiguous text.
                    if re.search(r'\d{4}[-./]\d{2}[-./]\d{2}.*(?:라이센스|라이선스|불법복사|무단배포)', line):
                        item = clauses[active]
                        item.warnings = tuple(dict.fromkeys((*item.warnings, 'Suspected embedded licensing watermark; excluded from comparison; inspect original PDF.')))
                    else:
                        clauses[active].text += ('\n' if clauses[active].text else '') + line
                j += 1
        return clauses


def compare(old, new):
    rows = []
    def order(value):
        return tuple(int(n) for n in value.split('.'))
    for number in sorted(set(old) | set(new), key=order):
        a, b = old.get(number), new.get(number)
        old_text, new_text = (a.text if a else ''), (b.text if b else '')
        similarity = SequenceMatcher(None, old_text.casefold(), new_text.casefold(), autojunk=False).ratio() if a and b else None
        if a and b:
            status = 'Unchanged' if ' '.join(old_text.split()) == ' '.join(new_text.split()) else 'Modified'
        else:
            status = 'Potentially added / renumbered' if b else 'Potentially removed / renumbered'
        rows.append({'Clause': number, 'Previous title': a.title if a else '',
                     'Revised title': b.title if b else '', 'Previous PDF page': a.page if a else None,
                     'Revised PDF page': b.page if b else None, 'Status': status,
                     'Text similarity': round(similarity, 3) if similarity is not None else None,
                     'Previous text': old_text, 'Revised text': new_text,
                     'Extraction warning': '; '.join(dict.fromkeys([*(a.warnings if a else ()), *(b.warnings if b else ()), *(['Empty extracted text; verify PDF'] if not old_text or not new_text else [])]))})
    # Cross-clause candidate matching is advisory, not automatic reassignment.
    missing_old = [r for r in rows if r['Status'] == 'Potentially removed / renumbered']
    missing_new = [r for r in rows if r['Status'] == 'Potentially added / renumbered']
    for r in missing_old:
        candidates = []
        for other in missing_new:
            a, b = r['Previous text'], other['Revised text']
            if a and b:
                score = SequenceMatcher(None, ' '.join(a.split()).casefold(), ' '.join(b.split()).casefold(), autojunk=False).ratio()
                if score >= .75:
                    candidates.append((score, other['Clause']))
        if candidates:
            score, target = max(candidates)
            r['Extraction warning'] += f'; Possible renumbering to {target} (similarity {score:.2f}); verify manually'
            for other in missing_new:
                if other['Clause'] == target:
                    other['Extraction warning'] += f'; Possible renumbering from {r["Clause"]}; verify manually'
    return rows
