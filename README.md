# AuditReview AI — hosted private demonstration

A Streamlit web app that can be deployed without installing software on the user's work laptop. **Synthetic files only**. This is a proof of concept, not a production-ready audit platform.

## Deploy using Streamlit Community Cloud

1. Create a **private GitHub repository** and upload `app.py`, `requirements.txt`, and `.streamlit/config.toml` (preserve the directory).
2. Sign in to https://share.streamlit.io/ and choose **Create app**, selecting the repository and `app.py` as entry point. Check whether your hosting plan supports private repositories and the access controls you need.
3. Before launch, set the app's **Secrets** in the Streamlit deployment settings:

   ```toml
   APP_PASSWORD = "replace-with-a-long-random-pilot-password"
   OPENAI_API_KEY = "your-provider-api-key"
   ```

   Never put secrets in GitHub, files sent by email, or the browser UI. You can omit `OPENAI_API_KEY` to use rules-only mode.
4. Deploy and open the provided `*.streamlit.app` URL in Chrome or Edge. Enter your pilot password.
5. Upload **synthetic** Excel/PDF documents, choose Inventory and the review mode, run, and export CSV findings.

## What it can and cannot do

- Reads Excel cells and formulas and extracts PDF text; identifies basic documentation gaps.
- Optional AI-assisted review produces proposed findings with evidence references, but **does not validate all arithmetic, cross-workbook links, cached formula values, or audit sufficiency**.
- Spreadsheet extraction is capped (1,800 rows × 45 columns per sheet), PDFs at 60 pages, and AI prompt input is truncated; check the extraction limitations shown in the app.
- No direct CaseWare integration, no automated sign-off, no enterprise identity management, no secure multi-tenant isolation, no audit trail, and no production data-retention or incident-response controls.
- The shared password is a **pilot access gate, not enterprise-grade authentication**. Hosted environments and third-party providers may process uploaded content; do not assume confidential client data is safe to upload.
- All findings require manager verification against originals.

## Production requirements before any real audit data

Written firm authorisation; POPIA/privacy and contractual review; approved hosting and model provider; SSO/MFA and role-based access; secure encrypted storage and documented retention/deletion; data processing agreements; logging/audit trails; access monitoring and incident response; full extraction coverage; validated technical review and calculation engine; human review and CaseWare sign-off.

## Running without AI

The app can run without `OPENAI_API_KEY` in rules-only mode. AI mode is unavailable until a server-side key is configured. API usage can incur fees separate from ChatGPT subscriptions.
