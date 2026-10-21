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
- `GOOGLE_ACCESS_TOKEN`: a short-lived OAuth bearer token authorized for `https://www.googleapis.com/auth/documents`. Enable the Google Docs API in your Google Cloud project and obtain the token using Google's OAuth consent flow. Uses docs.googleapis.com. The app does not implement account sign-in or token refresh; restart with a refreshed token when it expires. Do not paste tokens into chat. OAuth sign-in and managed user accounts are future production work.

No external API is needed for local extraction and Word export. Scanned images/PDFs need OCR first. Legacy .ppt files must be converted to .pptx. Embedded images, equations, layout, and slide diagrams are not reproduced by text extraction. Large recordings must be split before upload. The sample CC1.docx was used only as a format reference and extraction check; its contents are not bundled into the app.

## Privacy and limitations
Notes persist in browser localStorage, not a server database. Shared browser profiles can access them. Export before clearing browser data. Uploaded files are processed in memory; AI actions transmit selected content to OpenAI, Google export sends the notebook to Google. No automatic sync, collaboration, authentication, OCR, or cloud deployment is included. Treat the extracted source as educational material, not instructions to execute.

## Validation
```sh
python -m unittest discover -s tests -v
node --check static/app.js
```
Tests exercise HTTP document extraction including tables, slide extraction, all four exported sections, and app serving. External API calls require configured accounts and have not been integration-tested. Manual browser interaction and PDF layout fidelity have not been verified.
