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
2. Upload lecture audio/video up to 1.5 GB (1,500,000,000 bytes), or a TXT transcript. With AI configured, match lecture discussion to concepts as side notes. Review the match before studying. Transcripts include segment-start timestamps, not word-level timestamps or speaker separation.
3. Import reference chapters separately and enter their related concept/chapter. These remain in the Book references section.
4. Generate a 100-item identification/enumeration quiz or 100-item multiple-choice exam with answer explanations immediately after each item. AI output is editable and should be checked for count, accuracy, and coverage. If sources cannot support 100 distinct items, the model is instructed to report the limitation. Generated content is never represented as validated assessment material.
5. Export Word without credentials, or create a Google document with four named tabs: Class notes, Book references, Quiz review, Exam review. Word uses page breaks rather than Google document tabs. Google may retain an initial blank tab.

## Optional connections
Set variables in the server process before starting; never put credentials in source or browser code.

- `OPENAI_API_KEY`: required for recording transcription, lecture matching, and review generation. Uses api.openai.com. `OPENAI_MODEL` defaults to gpt-4.1-mini. Recording transcription uses whisper-1. Provider usage may incur charges. Browser prompts confirm each AI send.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: web OAuth client credentials, kept only in Render environment variables. Set the authorized origin to `https://margin-t56k.onrender.com` and redirect URI to `https://margin-t56k.onrender.com/auth/google/callback`. If deploying elsewhere, set `APP_URL` to that exact HTTPS origin and update Google's client settings. Enable Drive and Docs APIs. Add your account as an External/Testing test user. Click Connect Google Drive in Margin and consent. No Picker key is needed: the built-in Drive file browser supports search and pagination. Import Google Docs/Slides or supported uploaded files; export creates a new document in My Drive. Folder selection is not included yet.
- OAuth requests read-only Drive access for imports and per-app file access for creating documents. Tokens stay server-side in expiring in-memory sessions; secure HTTP-only cookies identify each browser session. Tokens refresh while the session is active, but server restarts/deploys clear sessions. Reconnect when needed. Disconnect removes the local session; revoke access in your Google account to revoke Google's grant. External Testing grants may expire after seven days. The old shared GOOGLE_ACCESS_TOKEN setting is no longer used.

No external API is needed for local extraction and Word export. Scanned images/PDFs need OCR first. Legacy .ppt files must be converted to .pptx. Embedded images, equations, layout, and slide diagrams are not reproduced by text extraction. Lecture recordings are automatically converted to mono audio and split into 10-minute segments. The sample CC1.docx was used only as a format reference and extraction check; its contents are not bundled into the app.

## Privacy and limitations
Notes persist in browser localStorage, not a server database. Shared browser profiles can access them. Export before clearing browser data. Documents are processed in memory; lecture files temporarily use server disk and are deleted after processing, cancellation, or upload expiry; AI actions transmit selected content to OpenAI, Google export sends the notebook to Google. No automatic sync, collaboration, general account management, or OCR is included. Google OAuth secures each user’s Drive connection; it does not restrict access to local extraction. On public deployments, AI endpoints also require a connected Google session. Treat the extracted source as educational material, not instructions to execute.

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

## Large lecture recordings
- Use the Lecture recording category when importing videos from Drive. Class materials and books retain their small-document limits (24 MB via Drive, 28 MB local).
- Up to 1.5 decimal GB per video/audio file; maximum 12-hour duration. Local transfers use 4 MiB requests; Drive downloads stream directly to temporary disk in 1 MiB reads. Video is never base64-encoded into the browser. Audio conversion is serialized to one lecture job at a time, uses one decoding thread, and creates mono 64 kbps MP3 segments of ten minutes each. FFmpeg is found on PATH or provided by the pinned imageio-ffmpeg package.
- Configure OPENAI_API_KEY in Render before beginning. Public deployments also require an authenticated Google session. Audio transcription is billed by the provider based on duration. Google file access alone does not provide transcription.
- Temporary free disk must cover the input size plus 512 MiB. A full 1.5 GB recording therefore needs about 2.04 GB free at job creation. If the service lacks space, the app rejects it with an explicit message; raising the app limit does not increase Render resources.
- Keep the browser tab open while uploading. It polls processing progress and can cancel. Page reload can resume polling a processing job in the same tab; interrupted local uploads must be cancelled and restarted. Uploads inactive for 30 minutes are removed. Background jobs, credentials, and partial transcripts are not durable across Render restarts/deploys; free-plan idle shutdown can interrupt a job when the tab is closed. One instance/process is required for these in-memory job sessions. Persistent storage and a separate durable worker are needed for guaranteed long-running processing.
- After a provider failure, completed transcript segments are retained in memory and offered to the browser, avoiding silent loss of partial results. Completed jobs expire after six hours. Cancelled/failed jobs remove temporary files. No automatic paid transcription retries occur.
- Validation covers the exact size boundary without allocating a 1.5 GB fixture, disk-space rejection, chunk offsets/overruns, job ownership, bounded Drive streaming, cancellation, partial failure, and real FFmpeg conversion on a short generated audio sample with a mocked transcription provider. A real 1.5 GB Render transfer and paid transcription have not been tested.

## Subject notebooks and categorized imports
The subject buttons select independent notebooks for Clinical Microscopy, Clinical Bacteriology, Clinical Chemistry, and Clinical Hematology 1. Use **Add notebook** for another subject. Materials, lecture transcripts, reference notes, quizzes, and exams are saved separately in each notebook. Word/Google export uses the selected notebook. **Clear this notebook** affects only the selected subject.

Each source card has its own **Upload from device** and **Import from Google Drive** controls. The card sets the import category automatically; the Drive dialog confirms the destination subject and category. Unsupported file types are disabled in the picker. An import, transcript, or generated review stays assigned to the notebook where it began, even if another subject is selected while processing.

On first load after upgrading, notes from the old single-notebook format are preserved in **Existing notebook** alongside the four new subjects; the old browser storage key is retained as a backup. Notebooks remain local to this browser/device, not automatically synced through Google. Export important notes before clearing browser storage.

Notebook storage tests: `node tests/notebooks.test.cjs`. Browser regression checks: `node tests/browser.cjs` (requires Playwright and Chromium installed; optionally set `CHROMIUM_PATH`). The browser checks use mocked provider responses and cover category routing, notebook isolation and reload, legacy migration, background-import destinations, and mobile layout.
