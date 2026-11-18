"""Deterministic positional text differences. No AI and no normative inference."""
import difflib
import re
from collections import defaultdict


def normalize(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def changes(previous, revised):
    """Case-sensitive word-level differences. Equal blocks are never changes."""
    left, right = normalize(previous).split(), normalize(revised).split()
    matcher = difflib.SequenceMatcher(None, left, right, autojunk=False)
    output = []
    for operation, a, b, c, d in matcher.get_opcodes():
        if operation == 'equal':
            continue
        before, after = ' '.join(left[a:b]), ' '.join(right[c:d])
        if before == after:
            continue
        # This is positional, not proof of a net addition/deletion or a requirement change.
        kind = {'replace': 'Replaced', 'insert': 'Inserted at position', 'delete': 'Deleted at position'}[operation]
        output.append({'Evidence ID': f'E{len(output)+1:04d}', 'Change type': kind,
                       'Previous excerpt': before, 'Revised excerpt': after,
                       'Previous token range': f'{a}:{b}', 'Revised token range': f'{c}:{d}',
                       'Explanation': {'Replaced': 'Different wording at the aligned position.',
                                       'Inserted at position': 'Text appears at this position only in the revised extraction; check for relocation.',
                                       'Deleted at position': 'Text appears at this position only in the previous extraction; check for relocation.'}[kind]})
    return output


def grouped_changes(edits):
    """Summarize identical before/after pairs while retaining each evidence ID."""
    groups = defaultdict(list)
    for item in edits:
        key = (item['Change type'], item['Previous excerpt'], item['Revised excerpt'])
        groups[key].append(item['Evidence ID'])
    return [{'Change type': key[0], 'Previous excerpt': key[1], 'Revised excerpt': key[2],
             'Occurrences': len(ids), 'Evidence IDs': ', '.join(ids)} for key, ids in groups.items()]


def compare_clauses(rows):
    evidence, summary = [], []
    for row in rows:
        number = row['Clause']
        edits = changes(row['Previous text'], row['Revised text']) if row['Status'] == 'Modified' else []
        if row['Status'] in ('Potentially added / renumbered', 'Potentially removed / renumbered'):
            # Do not misrepresent a whole unmatched clause as a confirmed insertion/deletion.
            description = 'Unmatched clause number; possible addition, removal, or relocation.'
        elif edits:
            description = f'{len(edits)} positional text difference(s); meaning not assessed.'
        else:
            description = 'No positional text differences detected.'
        summary.append({'Clause': number, 'Status': row['Status'], 'Previous title': row['Previous title'],
                        'Revised title': row['Revised title'], 'Previous PDF page': row['Previous PDF page'],
                        'Revised PDF page': row['Revised PDF page'], 'Difference count': len(edits),
                        'Plain-language summary': description,
                        'Extraction warning': row.get('Extraction warning', '')})
        for item in edits:
            evidence.append({'Clause': number, 'Previous PDF page': row['Previous PDF page'],
                             'Revised PDF page': row['Revised PDF page'], **item})
    return summary, evidence
