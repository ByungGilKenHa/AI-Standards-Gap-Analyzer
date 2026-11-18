"""Free, local, deterministic ISO text difference tool."""
import hashlib
import io
import pandas as pd
import streamlit as st
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from parser import extract_clauses, compare
from diff_engine import compare_clauses, grouped_changes
from review_report import matrix_rows, reviewed_count, STATUS, FIELDS
from auto_report import auto_matrix, make_automatic_docx
from optional_learning import study_clause
from key_report import make_key_changes_docx
from local_analysis import candidates, analyze_clause
from learning_report import make_learning_docx
from reference_matrix import load_reference
from analysis_store import load as load_saved_analysis, save as save_analysis
from traceability import trace_rows

VERSION = '2.0 Traceability & Resume Beta'
AUTHOR = 'ByungGil Ken Ha'


def safe_cell(value):
    if isinstance(value, str):
        value = ILLEGAL_CHARACTERS_RE.sub('', value)
        if value.startswith(('=', '+', '-', '@')):
            value = "'" + value  # Excel formula-injection protection
        return value[:32000]
    return value


def workbook(summary, evidence, rows, old_name, new_name, old_hash, new_hash, reviews=None, reference=None, analyses=None, failures=None):
    buffer = io.BytesIO()
    sheets = {
        'Summary': pd.DataFrame(summary),
        'Text Differences': pd.DataFrame(evidence),
        'Clause Comparison': pd.DataFrame(rows),
        'Review Matrix': pd.DataFrame(matrix_rows(rows, reviews or {})),
        'Automatic Change Matrix': pd.DataFrame(auto_matrix(rows, evidence, reviews or {}, reference or {})),
        'Requirement Traceability Map': pd.DataFrame(trace_rows(rows, analyses or {}, failures or {})),
        'Local AI Analysis': pd.DataFrame(list((analyses or {}).values()), columns=['clause','classification','confidence','previous_summary','revised_summary','key_change','why_it_matters','organization_review','auditor_questions','evidence_quote','previous_page','revised_page','review_status','quality_gate']),
        'Read Me': pd.DataFrame([
            {'Field': 'Product', 'Value': 'AI Standards Gap Analyzer — deterministic text comparison'},
            {'Field': 'Version', 'Value': VERSION}, {'Field': 'Developer', 'Value': AUTHOR},
            {'Field': 'Previous label', 'Value': old_name}, {'Field': 'Revised label', 'Value': new_name},
            {'Field': 'Previous PDF SHA-256', 'Value': old_hash}, {'Field': 'Revised PDF SHA-256', 'Value': new_hash},
            {'Field': 'Limitations', 'Value': 'Deterministic text evidence plus optional UNVERIFIED local AI drafts. AI evidence quote is verified verbatim, but interpretation is NOT verified. Check original PDFs, numbering, amendments and relocation.'},
            {'Field': 'Reference material', 'Value': 'Optional user-supplied DOCX matrix; its educational interpretations are unverified and matched provisionally by clause number.'},
            {'Field': 'Privacy', 'Value': 'Comparison is local. Optional learning sends selected extracted clause text only to local Ollama at 127.0.0.1.'},
            {'Field': 'Review notes', 'Value': 'User-entered notes; not AI-generated or automatically verified. Review state is kept in this browser session only.'},
        ])
    }
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for name, frame in sheets.items():
            frame = frame.copy()
            for column in frame.columns:
                frame[column] = frame[column].map(safe_cell)
            frame.to_excel(writer, sheet_name=name, index=False)
            sheet = writer.sheets[name]
            sheet.freeze_panes = 'A2'
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.fill = PatternFill('solid', fgColor='17365D')
                cell.font = Font(color='FFFFFF', bold=True)
            for idx, column in enumerate(frame.columns, 1):
                max_width = min(48, max(14, len(str(column)) + 3))
                sheet.column_dimensions[get_column_letter(idx)].width = max_width
                for cells in sheet.iter_cols(min_col=idx, max_col=idx, min_row=2):
                    for cell in cells:
                        cell.alignment = Alignment(vertical='top', wrap_text=True)
    return buffer.getvalue()


st.set_page_config(page_title='AI Standards Gap Analyzer', layout='centered')
st.title('AI Standards Gap Analyzer')
st.caption(f'Developed by {AUTHOR}')
st.write('Compare two editions of a standard and generate practical change reports.')
left, right = st.columns(2)
with left:
    old_file = st.file_uploader('Previous Standard PDF', type='pdf', key='previous')
with right:
    new_file = st.file_uploader('Revised Standard PDF', type='pdf', key='revised')
with st.expander('Advanced Settings (optional)'):
    old_name = st.text_input('Previous edition label', 'Previous edition')
    new_name = st.text_input('Revised edition label', 'Revised edition (verify status)')
    ref_file = st.file_uploader('Educational reference matrix (DOCX)', type='docx')
    model = st.text_input('Local AI model (installed in Ollama)', value='qwen3:1.7b')
    st.caption('Local AI drafts are not authoritative. The original PDFs must be checked before compliance decisions.')

if st.button('Compare & Generate Reports', type='primary', use_container_width=True, disabled=not(old_file and new_file)):
    try:
        old_bytes, new_bytes = old_file.getvalue(), new_file.getvalue()
        old, new = extract_clauses(old_bytes), extract_clauses(new_bytes)
        rows = compare(old, new)
        summary, evidence = compare_clauses(rows)
        old_hash, new_hash = hashlib.sha256(old_bytes).hexdigest(), hashlib.sha256(new_bytes).hexdigest()
        st.session_state['results'] = (rows, summary, evidence, old_hash, new_hash)
        st.session_state['source_names'] = (old_file.name, new_file.name)
    except Exception as exc:
        st.session_state.pop('results', None)
        st.error(f'Comparison failed: {exc}')

if 'results' in st.session_state:
    rows, summary, evidence, old_hash, new_hash = st.session_state['results']
    if st.session_state.get('source_names') != (old_file.name if old_file else None, new_file.name if new_file else None):
        st.warning('PDF files changed. Run comparison again before downloading.')
        st.stop()
    reviews = st.session_state.setdefault(f'review_{old_hash}_{new_hash}', {})
    reference = {}
    if ref_file:
        try:
            reference = load_reference(ref_file.getvalue())
        except Exception as exc:
            st.warning(f'Reference matrix could not be read: {exc}')
    analysis_key = f'analysis_{old_hash}_{new_hash}_{model}'
    failed_key = f'failed_{old_hash}_{new_hash}_{model}'
    if analysis_key not in st.session_state:
        restored, restored_failures = load_saved_analysis(old_hash, new_hash, model)
        st.session_state[analysis_key] = restored
        st.session_state[failed_key] = restored_failures
    analyses = st.session_state[analysis_key]
    eligible = candidates(rows)
    pending = [r for r in eligible if str(r['Clause']) not in analyses]
    failed = st.session_state.setdefault(failed_key, {})
    st.success('PDF comparison complete. Your detailed Excel report is ready.')
    if pending:
        st.info(f'Local analysis: {len(eligible)-len(pending)} of {len(eligible)} completed. Continue to analyze remaining clauses.')
    elif eligible:
        st.success('Local analysis pass completed. Review the Word report before professional use.')
    else:
        st.warning('No clauses were eligible for safe automatic interpretation. Excel evidence is available.')
    if st.button('Resume Word Analysis' if analyses else 'Generate Word Analysis', type='primary', use_container_width=True, disabled=not bool(pending)):
        progress = st.progress(0)
        for i,row in enumerate(pending):
            clause = str(row['Clause'])
            try:
                analyses[clause] = analyze_clause(row, model=model)
                failed.pop(clause, None)
            except Exception as exc:
                failed[clause] = str(exc)
            save_analysis(old_hash,new_hash,model,analyses,failed)
            progress.progress((i+1)/len(pending))
        if failed:
            st.warning(f'Analysis incomplete: {len(failed)} clauses could not be processed. The Word file is a partial draft.')
        else:
            st.success('Local analysis pass finished. The report remains an unverified educational draft.')
    completed = len([r for r in eligible if str(r['Clause']) in analyses])
    if completed < len(eligible):
        st.warning(f'Partial analysis: {completed}/{len(eligible)} analyzed; {len(eligible)-completed} remain. Unprocessed clauses may contain significant changes.')
    a,b=st.columns(2)
    with a:
        st.download_button('Download Excel Report', workbook(summary,evidence,rows,old_name,new_name,old_hash,new_hash,reviews,reference,analyses,failed), file_name='AI_Standards_Gap_Analyzer_Report.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',use_container_width=True)
    with b:
        st.download_button('Download Word Report',make_learning_docx(analyses,old_name,new_name,old_hash,new_hash,total_clauses=len(rows),eligible_clauses=len(eligible),complete=(completed==len(eligible) and bool(eligible))),file_name='AI_Standards_Gap_Analyzer_Practical_Change_Report.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',disabled=not bool(analyses),use_container_width=True)
    with st.expander('Requirement Traceability Map'):
        st.caption('Each clause links source pages and text to provisional AI explanations. This is NOT expert-verified.')
        trace = trace_rows(rows, analyses, failed)
        st.dataframe(pd.DataFrame(trace)[['Clause','Comparison status','AI change classification','Verification state','Key change (unverified)','Previous PDF page','Revised PDF page']], hide_index=True, use_container_width=True)
    with st.expander('Advanced: Comparison evidence and review'):
        st.caption(f'{len(rows)} clause identifiers; {len(evidence)} positional edits; {sum(bool(r["Extraction warning"]) for r in summary)} extraction/alignment flags. These figures are not validated significance counts.')
        if failed:
            st.write('Local analysis errors (first 20):')
            for k,v in list(failed.items())[:20]: st.caption(f'Clause {k}: {v}')
        st.dataframe(pd.DataFrame(summary),hide_index=True,use_container_width=True)
        chosen=st.selectbox('Clause', [str(r['Clause']) for r in rows])
        selected=next(r for r in rows if str(r['Clause'])==chosen)
        a,b=st.columns(2)
        with a: st.text_area('Previous extracted text',selected['Previous text'],height=200)
        with b: st.text_area('Revised extracted text',selected['Revised text'],height=200)
        if selected['Extraction warning']: st.warning(selected['Extraction warning'])
        note=reviews.setdefault(chosen,{})
        note['Review status']=st.selectbox('Review status',STATUS,index=STATUS.index(note.get('Review status','Not Reviewed')),key=f'status_{old_hash}_{new_hash}_{chosen}')
        for field in FIELDS:
            note[field]=st.text_area(field,value=note.get(field,''),key=f'note_{field}_{old_hash}_{new_hash}_{chosen}',height=80)
        note['Reviewer notes']=st.text_area('Reviewer notes',value=note.get('Reviewer notes',''),key=f'misc_{old_hash}_{new_hash}_{chosen}',height=80)
