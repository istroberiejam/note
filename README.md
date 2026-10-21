# Margin
A local note-making app for class materials, lecture discussion, chapter references, and exam preparation.

## Run
Use Python 3.12+:

```sh
cd /workspace/note
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

Open the app on port 8000 in a browser on the same machine. It binds to loopback intentionally. `PORT` changes the port. This is a single-user local app, not a public production deployment.

## Workflow
1. Name your notebook and import PDF, PPTX, DOCX, or UTF-8 text. Each PDF page or slide becomes an editable concept with a source location. DOCX tables are read in document order. Original extracted text is preserved; splitting a document into concepts and correcting extraction artifacts is manual.
2. Upload lecture audio/video (under 24 MB) or a TXT transcript. With AI configured, match lecture discussion to concepts as side notes. Review the match before studying. Audio timestamps and speaker separation are not currently included.
3. Import reference chapters separately and enter their related concept/chapter. These remain in the Book references section.
4. Generate a 100-item identification/enumeration quiz or 100-item multiple-choice exam with answer explanations immediately after each item. AI output is editable and should be checked for count, accuracy, and coverage. If sources cannot support 100 distinct items, the model is instructed to report the limitation. Generated content is never represented as validated assessment material.
5. Export Word without credentials, or create a Google document with four named tabs: Class notes, Book references, Quiz review, Exam review. Word uses page breaks rather than Google document tabs. Google may retain an initial blank tab.

## Optional connections
Set variables in the server process before starting; never put credentials in source or browser code.

- `OPENAI_API_KEY`: required for recording transcription, lecture matching, and review generation. Uses api.openai.com. `OPENAI_MODEL` defaults to gpt-4.1-mini. Recording transcription uses whisper-1. Provider usage may incur charges. Browser prompts confirm each AI send.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: web OAuth client credentials, kept only in Render environment variables. Set the authorized origin to `https://margin-t56k.onrender.com` and redirect URI to `https://margin-t56k.onrender.com/auth/google/callback`. If deploying elsewhere, set `APP_URL` to that exact HTTPS origin and update Google's client settings. Enable Drive and Docs APIs. Add your account as an External/Testing test user. Click Connect Google Drive in Margin and consent. No Picker key is needed: the built-in Drive file browser supports search and pagination. Import Google Docs/Slides or supported uploaded files; export creates a new document in My Drive. Folder selection is not included yet.
- OAuth requests read-only Drive access for imports and per-app file access for creating documents. Tokens stay server-side in expiring in-memory sessions; secure HTTP-only cookies identify each browser session. Tokens refresh while the session is active, but server restarts/deploys clear sessions. Reconnect when needed. Disconnect removes the local session; revoke access in your Google account to revoke Google's grant. External Testing grants may expire after seven days. The old shared GOOGLE_ACCESS_TOKEN setting is no longer used.

No external API is needed for local extraction and Word export. Scanned images/PDFs need OCR first. Legacy .ppt files must be converted to .pptx. Embedded images, equations, layout, and slide diagrams are not reproduced by text extraction. Large recordings must be split before upload. The sample CC1.docx was used only as a format reference and extraction check; its contents are not bundled into the app.

## Privacy and limitations
Notes persist in browser localStorage, not a server database. Shared browser profiles can access them. Export before clearing browser data. Uploaded files are processed in memory; AI actions transmit selected content to OpenAI, Google export sends the notebook to Google. No automatic sync, collaboration, general account management, or OCR is included. Google OAuth secures each user’s Drive connection; it does not restrict access to local extraction or shared AI endpoints. Treat the extracted source as educational material, not instructions to execute.

## Validation
```sh
python -m unittest discover -s tests -v
node --check static/app.js
```
Tests exercise HTTP document extraction including tables, slide extraction, all four exported sections, and app serving. External API calls require configured accounts and have not been integration-tested. Manual browser interaction and PDF layout fidelity have not been verified.

## Deploy on Render
Create a Python web service connected to this repository's `main` branch.

- Build command: `pip install -r requirements.txt`
- Start command: `HOST=0.0.0.0 python server.py`
- Health check path: `/api/status`

Render supplies `PORT`. `HOST` defaults to loopback for local use; the deployment command explicitly enables external access. Leave API credentials unset for an initial public demo: extraction and Word export work without them. Add authentication and request/rate limits before enabling paid AI or Google credentials on a public service. This prototype has no user accounts or server-side notebook storage.

Google OAuth and Drive tests use mocked Google responses; a real-account sign-in/import/export check on Render remains required. No Google tokens or credentials were supplied to this workspace.
