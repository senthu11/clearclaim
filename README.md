# Medical Billing Fraud Detective

## Public demo deployment

Deploy `streamlit_app.py` from the `main` branch with Python 3.12 on Streamlit Community Cloud. `requirements.txt` supplies Python dependencies; `packages.txt` supplies Linux OCR libraries. No API keys or secrets are required for the complete synthetic review, findings, report and letter workflow. Do not copy local `.env` files into the repository or deployment.

The public entry point enables `CLEARCLAIM_PUBLIC_DEMO=1`. Saved-review creation, listing, opening and deletion are disabled at the storage boundary, so anonymous visitors cannot access a shared saved-review directory. Download exports during the session instead. Use synthetic data only: on a hosted deployment, "local" processing means on the hosting server, not on the visitor's device. Uploaded documents, typed questions and personal details are not sent to an LLM. This educational demo is not a service for real patient data.

The desktop entry point remains `app.py`; its encrypted local saved reviews remain available.

A Python class project with three specialized AI agents, LangGraph orchestration, LangChain integrations, local RAG, and a Streamlit interface. Use synthetic bills only. Every bundled price and billing policy is fictional.

## Restored Evidence workspace (October 24, 2026)

The missing `billing/`, `data/`, `assets/`, `tests/`, and `scripts/` files were recovered from an existing local copy of this project, not regenerated. The app now uses the approved Evidence workspace direction: a source PDF/image preview beside editable charges, a calmer three-card overview, and a report organized around questions and supporting evidence. Source PDFs are rasterized locally one page at a time; no external viewer is used. Starting a new bill clears the source bytes and page selection.

Cloud AI for built-in samples is now **opt-in**. Leave the checkbox off to complete the sample workflow without an API key. Uploaded bills always follow the local path. The original graph, audit rules, synthetic reference corpus, privacy boundary, and export implementations are retained.

**Windows dependency compatibility:** The official `xxhash==3.6.0` wheel is pinned because this computer's Application Control blocks the 4.0.2 build. Version 3.6.0 loads successfully with the installed LangGraph/LangSmith packages; no security controls were changed. See `design-qa.md` for verification results.

## Privacy boundary

The optional **Personal details** form is available on Overview and when starting a bill. Name, age, sex, and bill reference are held in a separate local session dictionary, outside graph state and provider requests. Name/reference may personalize local reports and dispute letters. Age/sex are not used by the audit. **Clear details** removes the saved profile from the active session. No database or internet synchronization is used.

**Download Excel** on Overview exports saved personal details plus the latest completed review, if any. **Download all details (Excel)** in the report exports Summary, Charges, Findings, and References in one workbook. The local export includes age and sex if saved. It is generated in memory, not uploaded or sent to an LLM. Free text is written as literal text, without executable formulas or hyperlinks.

**No uploaded document, personal metadata, typed chat question, or chat history is sent to the cloud LLM or web search.** All uploads are treated as sensitive, including files labeled synthetic. The app does not attempt to classify a document as safe to transmit.

- Uploaded PDFs/images use local text extraction or OCR, local table parsing, local audit rules, and locally composed explanations and letters. Unrecognized layouts require manual entry in the review table.
- Incomplete extraction placeholders and bills with no positive charges are blocked before the audit runs. Correct the charges against the local source preview, then submit again. This checks input completeness; it does not verify document authenticity. Potential duplicate, pricing, and date issues remain available for audit and human review.
- The three cloud-agent demonstration is limited to the app's built-in, unchanged synthetic fixtures. Each provider request is reconstructed from those fixed fixtures and the bundled reference corpus. Even their fictional patient, provider, and account names are excluded.
- Editing any fixture field switches subsequent processing to the local path. An uploaded copy of a sample remains an upload and cannot enable cloud processing.
- Chat is routed locally into fixed billing topics. Only a fixed topic and built-in fixture may reach the LLM. Original wording and conversation history never do.
- Optional Keenable search receives a fixed public topic query for unchanged built-in samples only. It is disabled for uploads. Public results are displayed locally and are not sent to the LLM.
- External LangSmith/LangChain tracing is disabled to prevent graph state export. API credentials are still used to authenticate permitted provider requests.

This boundary is not a claim of HIPAA compliance or verified de-identification. The project remains an educational demo with fictional reference data. Local source previews, downloads, and letters can contain details retained on your computer.

## Run on Windows

The project virtual environment and dependencies have been installed in this workspace.

```powershell
.\run.ps1
```

If PowerShell blocks script execution, use the Python command directly:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open http://127.0.0.1:8503. This project's Streamlit configuration defaults to port 8503.

For a fresh checkout, Python 3.11 or newer is recommended:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If using `uv` behind a corporate certificate proxy:

```powershell
uv --system-certs --cache-dir .uv-cache venv .venv
uv --system-certs --cache-dir .uv-cache pip install --python .venv/Scripts/python.exe -r requirements.txt
```

`requirements.lock.txt` is the historical Windows/Python 3.11 environment snapshot and contains the blocked xxhash version. Use `requirements.windows-py312.lock.txt` to reproduce this Python 3.12 environment, or `requirements.txt` for a fresh compatible installation; both pin xxhash 3.6.0.

## Keys and configuration

Your existing keys are in `.local-config/.env`. A root `.env` file is also supported. Both locations are excluded by the `.gitignore` file. `.env.example` is a safe, blank configuration template.

```dotenv
NEBIUS_API_KEY=your_nebius_inference_key
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1
NEBIUS_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
KEENABLE_API_KEY=your_optional_keenable_key
```

`KEENABLE` is accepted as an alias for the existing key entry. No LangChain or LangGraph API key is required. LangSmith is not required or enabled by this app. Local RAG requires no embedding service or downloaded embedding model.

Use **Refresh keys and list models** in the sidebar after editing credentials. Choose a chat model available to your Nebius account. The default Qwen model was available and successfully exercised during setup; model availability can change. Model changes apply to new bills. Never paste secrets into chat, source code, or uploaded documents.

## Try the demo

The **ClearClaim Overview** uses the approved calm visual style: top navigation, three summary cards for the clearly labeled Issues-to-find example, an investigation queue, and a selected-bill detail panel. Queue figures are calculated from the three bundled scenarios. Use search and status filters, then choose **Open investigation**. **Mark as reviewed** records a local demo-session status without clearing findings. **Analyze a bill** opens a fresh investigation; **Choose a file** opens the upload path. **Providers** opens the fictional reference library; **Reports** opens the current session's completed report or an empty state.

Start from **Overview → Analyze a bill**, then:

1. Select **Use a synthetic sample**, **Issues to find**, and **Digital PDF**.
2. Leave **Use cloud AI for this fixed synthetic sample** off for a local review, or opt in after configuring a key. Click **Extract bill charges**. The bundled fixture remains authoritative. Uploaded documents use local parsing instead.
3. Compare the source preview beside the editable charge table. Switch PDF pages or view extracted text as needed. Expand **Patient & visit details** to correct metadata, then confirm.
4. The Auditor runs deterministic checks, retrieves cited evidence, and explains ambiguous cases.
5. The Advocate creates a plain-language explanation and a dispute-letter draft. Download the report, charges, and letter.
6. Ask chat “Why was the glucose charge flagged?” or “How did you avoid double-counting savings?” Inspect the retrieved citations.
7. Repeat with **Clean comparison**, **Distinct services**, or an **Image (PNG)** sample.

The issues sample contains six lines totaling **$840.00**. The expected illustrative reduction is **$340.00**, across seven findings. This is $100 on the original office visit, $200 on its possible duplicate, and $40 on the glucose line. The glucose price and bundle findings overlap and count only once. Date and visit-setting mismatches have no assumed dollar reduction.

The clean and distinct-service samples should produce no rule findings. Sample PDF and PNG files can be downloaded directly from the app.

## Agents and RAG

```text
PDF / image
    ↓
Extractor agent — local text / OCR; fixed synthetic rows only may use Nebius
    ↓
Human review — LangGraph interrupt and editable charge table
    ↓
Auditor agent — Python rules + exact code lookups + RAG + Nebius review
    ↓
Advocate agent — Nebius explanation + precise dispute-letter composition
    ↓
Report / downloads / bill-grounded chat
```

Each agent has a separate role, prompt, and graph node. LangGraph shares typed state and an in-memory checkpointer, with a unique thread for each bill. The agents collaborate sequentially rather than running concurrently. The full cloud demonstration uses only unchanged built-in synthetic fixtures. Uploaded or edited bills use local processing in the same graph, without external LLM calls.

`billing/knowledge.py` turns synthetic policies and prices into LangChain Documents. A local `HashingVectorizer` embeds text into lexical vectors, and LangChain `InMemoryVectorStore` retrieves similar documents. Exact procedure-code and policy-ID lookups supplement vector retrieval so prices and rule citations refer to the correct records. This is lexical vector RAG, not a trained semantic embedding model. For cloud demonstrations, retrieval is reconstructed from the fixed fixture and topic; no uploaded content enters the external context. Source IDs appear alongside the findings and in the report.

The rule engine owns calculations. LLM prose does not change the finding list or dollar totals. Confidence labels describe a rule match requiring review; they are not statistically calibrated scores. The dispute letter combines confirmed facts and findings into a template so it preserves precise amounts and clearly labels fictional evidence.

### Optional web context

Keenable is available only for unchanged built-in examples when **Web context for chat** is switched on. The LangChain `KeenableSearch` tool receives a hardcoded public topic query selected locally. It never receives the typed question, conversation, uploaded content, or account metadata. Public results appear separately as `WEB-*` links and are not forwarded to the LLM. Search is disabled for uploads, changed fixtures, and unrecognized topics.

### OCR

Digital PDFs use PyMuPDF. Images and scanned PDF pages use Tesseract if it is already installed; otherwise the bundled RapidOCR CPU engine works locally with packaged model files. No separate system installation is needed for the tested PNG workflow.

To select a Tesseract installation, optionally set:

```dotenv
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

OCR may misread scans. The required human review lets users correct extracted data before auditing. For mixed scanned/digital PDFs, pages with very little embedded text use OCR; a page with substantial embedded text and additional raster-only charge regions may require manual correction or uploading the page as an image.

## Project files

| Path | Purpose |
|---|---|
| `app.py` | Streamlit interface, human review, report and chat |
| `billing/workflow.py` | Three agents and LangGraph pause/resume |
| `billing/extraction.py` | PDF text and local OCR ingestion |
| `billing/models.py` | Validated bill and charge schema |
| `billing/audit.py` | Duplicate, pricing, bundling and mismatch rules |
| `billing/knowledge.py` | Local vector RAG and exact references |
| `billing/advocate.py` | Explanation, report export and letter |
| `billing/chat.py` | Bill chat and optional web search |
| `billing/llm.py` | Credentials and Nebius calls through LangChain |
| `billing/privacy.py` | Fixed synthetic request boundary and local topic routing |
| `data/` | Fictional policy and pricing corpus |
| `tests/` | Rule, extraction, OCR, graph and UI checks |

## Validation

Offline tests make no paid model calls:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Optional live verification makes Nebius calls using only the bundled synthetic bill:

```powershell
.\.venv\Scripts\python.exe scripts/check_live.py --chat
```

The live check verifies extraction, the review checkpoint, the expected $840 total and $340 potential reduction, Advocate output, and a cited RAG chat answer. It does not enable Keenable search.

## Demo limits

- Prices, bundling rules, names, and bills are fictional. No real Medicare or insurer data is used.
- Possible duplicate services may be legitimate. The demo cannot prove fraud, reimbursement eligibility, or patient savings.
- Credits, negative adjustments, currency conversion, and real insurer payment adjudication are unsupported.
- Missing dates, unknown codes, or ambiguous metadata require clarification. Unknown codes get no invented reference price.
- Upload limits are 15 MB, 20 PDF pages, 25 megapixels per image, and 300 charge lines. Multi-page TIFF is rejected; use PDF instead.
- Uploads and graph state stay in local process/session memory. Closing or restarting the server loses the run. Only reconstructed built-in fixture content and fixed billing topics can reach Nebius. Uploaded content, personal details, chat wording, and history cannot.
- This local demo has no login, durable database, public deployment, or automated letter sending.
- LLM explanations can be inaccurate; review them against the authoritative charge table, deterministic findings, and source documents.

## GitHub

`.gitignore` is a **file**, containing patterns that exclude `.local-config/`, `.env`, `.venv/`, local caches, and generated uploads/outputs. It does not remove secrets already committed to a repository. This implementation does not publish or push anything to GitHub.


## Evidence workspace improvements (October 2026)

Start locally with `powershell -File scripts/start.ps1`. The launcher checks dependencies before binding to `127.0.0.1:8503`. Python 3.12 Windows installations use `requirements.windows-py312.lock.txt`, including the official xxhash 3.6.0 wheel. The startup screen also explains an xxhash import failure without showing a traceback.

- Compare source text with confirmed charges. Exact description matches are highlighted in PDFs; repeated matches are explicitly candidates, not asserted row identity. Scans and edited descriptions may require manual comparison.
- Missing code/description/date fields are identified. An optional statement charge total blocks confirmation on mismatch unless the user records an explanation. This does not prove all rows were extracted.
- Mixed digital/scanned PDFs trigger local OCR on pages with substantial image coverage. Page separators are retained. Extraction and preview caches belong to the session, not a shared cache of private documents.
- Findings remain immutable. Needs clarification, Explained and Possible error assessments plus notes and timestamped history are separate records. Assessments do not change the audit reduction.
- Payments, credits and explicitly stated EOB responsibility are entered separately. Unknown responsibility stays unknown. EOB code/date matches require uniqueness on both sides; ambiguous pairs stay unresolved. Credits are not negative service charges and do not alter the audit engine.
- Select up to ten statements and review each independently. Do not merge accounts or sum overlapping statement totals. Save each completed review before starting another.
- Report, workbook and JSON exports use one snapshot, including decisions, reconciliation and reference versions. Identifier inclusion is opt-in. This is not general de-identification: free text may still contain personal information.
- Letters support selected findings, tone, editable text, TXT and paginated PDF. Changing selection/tone/identifier inclusion creates a fresh draft. Letter questions intentionally omit monetary claims based on fictional benchmarks.
- Optional AI failures preserve the deterministic audit and local report. Retry the optional summary or chat without re-auditing. Only unchanged built-in fixtures may cross the cloud boundary.
- Optional saved reviews use password-derived Fernet encryption with a fresh salt per file. Original uploads, raw extraction text, model clients and chat are excluded. The passphrase is not written to disk and cannot be recovered. Files reside in `.local-reviews`, excluded from source control.
- Retention is 1, 7, 30 or 90 days. Expired files are removed when Saved reviews is opened; there is no background cleanup daemon. Explicit deletion does not erase backups or guarantee physical media erasure. Session clear and saved-review deletion are separate operations.

The reference version is a demo corpus version, not a medical-policy effective date. All prices and policies remain fictional and have no payer applicability. PDF exports use Arial on Windows or DejaVu Sans on Linux when available; the fallback font supports a more limited character set.

## Release checklist and deployment boundary

Run `python scripts/doctor.py`, `python -m unittest discover -s tests -v`, and `python -m compileall -q app.py billing scripts`. Check the sample upload, charge correction, assessment save, EOB ambiguity, encrypted reopen, clear session, all downloads, narrow viewport and keyboard focus. CI runs these Python checks on Windows/Python 3.12 when this directory is hosted in a GitHub repository; CI has not been run remotely from this local checkout.

This release remains a single-user localhost application. It does not implement public multi-user authentication or tenant isolation. Before public deployment, the required architecture is an authenticated TLS gateway with OIDC, per-user authorization for every review and download, separate user storage/key boundaries, restricted service credentials, scheduled retention enforcement, tested backup deletion, and operational monitoring that excludes bill contents, credentials and chat. Do not expose this Streamlit process or its shared local review directory directly to the internet. Deployment needs an identity provider, hosting/storage decisions, access policy and a separate security review; no public deployment was performed.

Module boundaries: `workflow.py` orchestrates agents; `report_ui.py` renders results; `review.py` owns decisions and snapshots; `review_ui.py` owns reconciliation/history controls; `provenance.py` locates source candidates; `storage.py` handles encrypted persistence; `exports.py` builds selective letters and PDF/report output.


## Additional synthetic test data and presentation

`outputs/clearclaim-synthetic-test-pack.zip` contains 13 digital PDF scenarios and companion JSON expectations, one scan image, a mixed digital/scanned PDF, three invalid bill inputs, and EOB/payment examples. Extract the archive and read START-HERE.txt. Upload PDFs or PNGs through Investigations > Upload a bill. JSON files are programmatic test fixtures, not accepted upload formats.

Regenerate the pack with `python -m scripts.generate_test_pack`. Run its tests with `python -m unittest discover -s tests -p test_synthetic_pack.py -v`. The expected totals and finding categories are explicit fixtures in `billing/test_cases.py`, independent of the auditor calculation.

`outputs/presentation/ClearClaim-project-overview.pptx` covers the project purpose, intended users, workflow diagrams, technology stack, local/cloud boundaries, findings, synthetic testing and deployment scope. It contains editable text and diagrams. The application remains login-free as requested.
