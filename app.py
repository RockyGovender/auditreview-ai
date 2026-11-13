"""AuditReview Local — human-in-the-loop working paper review pilot."""
import io, os, re, json, hashlib
from datetime import datetime
import pandas as pd
import streamlit as st
from openpyxl import load_workbook

st.set_page_config(page_title='AuditReview AI — Private Pilot', page_icon='🔎', layout='wide')
# Shared-password gate is suitable for a synthetic-data demo only; not enterprise authentication.
password = st.secrets.get('APP_PASSWORD', '')
if not password:
    st.error('Deployment not configured: set APP_PASSWORD in Streamlit app secrets.')
    st.stop()
if not st.session_state.get('authenticated', False):
    st.title('AuditReview AI — Private Pilot')
    attempt = st.text_input('Pilot access password', type='password')
    if st.button('Unlock'):
        import hmac
        if hmac.compare_digest(attempt, password):
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.error('Incorrect password')
    st.stop()
st.title('AuditReview AI — Private Pilot')
st.caption('Hosted first-pass working-paper review • Synthetic data only • No automatic audit sign-off')
if st.button('Lock session'):
    st.session_state.clear()
    st.rerun()


SECTION_RULES = {
 'Inventory': ['valuation','cost','overhead','conversion','nrv','sample','population','conclusion'],
 'Revenue': ['occurrence','cut-off','completeness','sample','revenue','conclusion'],
 'Receivables': ['existence','recoverability','ageing','subsequent','sample','conclusion'],
 'General': ['risk','assertion','sample','evidence','exception','conclusion']
}

def extract_xlsx(name, data, max_rows=1800, max_cols=45):
    wb=load_workbook(io.BytesIO(data),read_only=True,data_only=False,keep_links=False)
    out=[]
    for ws in wb.worksheets:
        rows=[]
        for row in ws.iter_rows(min_row=1,max_row=min(ws.max_row or 1,max_rows),max_col=min(ws.max_column or 1,max_cols)):
            cells=[]
            for c in row:
                if c.value is not None:
                    val=str(c.value).replace('\n',' ')[:250]
                    cells.append(f'{c.coordinate}={val}')
            if cells: rows.append(' | '.join(cells)[:1200])
        out.append({'file':name,'sheet':ws.title,'rows':rows,'truncated':(ws.max_row or 0)>max_rows or (ws.max_column or 0)>max_cols})
    return out

def extract_pdf(name, data, max_pages=60):
    import fitz
    doc=fitz.open(stream=data,filetype='pdf')
    out=[]
    for i in range(min(len(doc),max_pages)):
        txt=doc[i].get_text()[:16000]
        out.append({'file':name,'sheet':f'page {i+1}','rows':[txt] if txt.strip() else ['[No extractable text — scanned page; not assessed]'],'truncated':len(doc)>max_pages})
    return out

def deterministic_review(docs, section):
    findings=[]
    alltext='\n'.join(' '.join(d['rows']) for d in docs).lower()
    rules=[('Objective and conclusion','objective','conclusion'),('Sampling documentation','sample','population'),('Risk linkage','risk','assertion')]
    for label,a,b in rules:
        if a not in alltext or b not in alltext:
            findings.append({'Priority':'Clarification','Category':label,'Reference':'Uploaded documents (scope-wide)','Observation':f'Could not identify both {a!r} and {b!r} in extracted text. This is not proof they are absent.','Proposed review note':f'Please identify where the {label.lower()} is documented and cross-referenced.','Status':'Unverified — manual assessment needed'})
    for d in docs:
        if d['truncated']:
            findings.append({'Priority':'Limitation','Category':'Extraction','Reference':f"{d['file']} / {d['sheet']}",'Observation':'Worksheet/page extraction limit reached; remaining content was not reviewed.','Proposed review note':'Expand extraction limits or inspect the original file.','Status':'Not assessed'})
        for line in d['rows']:
            if re.search(r'(?i)\b(#REF!|#DIV/0!|#VALUE!|#N/A)\b',line):
                findings.append({'Priority':'Investigate','Category':'Formula error','Reference':f"{d['file']} / {d['sheet']} / {line[:65]}",'Observation':'Possible spreadsheet error token detected in extracted values or formulas.','Proposed review note':'Investigate the referenced cell and confirm the impact on the audit calculation.','Status':'Requires verification'})
    return findings

def ai_review(docs, section, api_key, model):
    from openai import OpenAI
    client=OpenAI(api_key=api_key)
    # Bound prompt size and tell reviewer what is missing. The model cannot access files not represented here.
    payload=json.dumps(docs,ensure_ascii=False)[:110000]
    system='''You are an independent first-pass audit working-paper quality reviewer for a South African audit manager. Apply ISA principles and the applicable financial reporting framework only where established. Use only supplied extracted evidence. Do not invent worksheet/cell references, balances, calculations, evidence, findings, or legal citations. Distinguish confirmed deficiencies, possible issues, and missing information. Never imply audit sign-off. Prioritise material audit risks and avoid generic notes. Respond as valid JSON object with key "findings" array. Each finding: priority (High/Medium/Low/Clarification), category, reference (exact file/sheet/cell or page if visible), observation, proposed_review_note, status (Confirmed documentation gap/Potential issue/Unable to assess), evidence_basis. Maximum 15 findings. If unable to substantiate a finding, omit it or label as unable to assess.'''
    result=client.responses.create(model=model,instructions=system,input=f'Audit section: {section}\nExtracted source data:\n{payload}\nReview with partner-style scepticism. Output JSON only.',max_output_tokens=6500)
    raw=result.output_text.strip()
    raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw)
    parsed=json.loads(raw)
    return [{'Priority':f.get('priority','Clarification'),'Category':f.get('category',''),'Reference':f.get('reference',''),'Observation':f.get('observation',''),'Proposed review note':f.get('proposed_review_note',''),'Status':f.get('status',''),'Evidence basis':f.get('evidence_basis','')} for f in parsed.get('findings',[])]

with st.sidebar:
    st.header('Review settings')
    section=st.selectbox('Audit section',list(SECTION_RULES))
    mode=st.radio('Review mode',['Local rules only (no external transmission)','AI-assisted (sends extracted content to configured provider)'])
    st.error('SYNTHETIC DATA ONLY. This pilot is not approved for confidential client audit files.')
    key=''; model='gpt-4.1-mini'
    if mode.startswith('AI-assisted'):
        key=st.secrets.get('OPENAI_API_KEY', '')
        st.caption('API key is configured server-side by the administrator.')
        model=st.text_input('Model ID',value='gpt-4.1-mini')
        consent=st.checkbox('I confirm these files are synthetic and may be transmitted to the AI provider')
    else: consent=False

uploaded=st.file_uploader('Upload SYNTHETIC working papers and supporting documents',type=['xlsx','pdf'],accept_multiple_files=True)
st.info('Rules-only checks are limited. AI mode transmits extracted content to the configured provider. Do not upload real client information.')
if st.button('Run first-pass review',type='primary',disabled=not uploaded):
    if uploaded and sum(len(f.getvalue()) for f in uploaded) > 35 * 1024 * 1024:
        st.error('Combined file size exceeds the 35 MB pilot limit.')
    elif mode.startswith('AI-assisted') and (not key or not consent):
        st.error('Enter an API key and confirm authorisation before using AI mode.')
    else:
        docs=[]; errors=[]
        with st.spinner('Extracting and reviewing files...'):
            for f in uploaded:
                data=f.getvalue()
                try:
                    docs.extend(extract_xlsx(f.name,data) if f.name.lower().endswith('.xlsx') else extract_pdf(f.name,data))
                except Exception as exc: errors.append(f'{f.name}: {type(exc).__name__}: {exc}')
            findings=deterministic_review(docs,section)
            if mode.startswith('AI-assisted') and docs:
                try: findings+=ai_review(docs,section,key,model)
                except Exception as exc: errors.append(f'AI review failed: {type(exc).__name__}: {exc}')
        st.session_state['review']={'docs':docs,'findings':findings,'errors':errors,'section':section}

if 'review' in st.session_state:
    r=st.session_state['review']
    st.subheader('Review output')
    st.write(f"Documents/sections extracted: **{len(r['docs'])}** · Proposed findings: **{len(r['findings'])}**")
    for e in r['errors']: st.error(e)
    if r['findings']:
        df=pd.DataFrame(r['findings'])
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button('Download review findings (CSV)',df.to_csv(index=False).encode('utf-8-sig'),'review_findings.csv','text/csv')
    else: st.warning('No rules-based findings identified. This does not mean the working paper is satisfactory.')
    with st.expander('Extraction coverage and limitations'):
        for d in r['docs']: st.write(f"{d['file']} / {d['sheet']}: {len(d['rows'])} non-empty extracted rows; truncated={d['truncated']}")
    st.caption('Manager must verify every finding against original files, consider omitted evidence, document resolutions, and complete sign-off in CaseWare.')
