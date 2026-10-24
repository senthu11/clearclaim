# ClearClaim Evidence workspace verification

Date: October 24, 2026
Status: full application running on port 8503; dependency block resolved.

## Recovery

Recovered the original billing, data, assets, tests and scripts from:
C:\Senthil\Projects\Medical fraud billing\Week3\Week3\Medical Billing Fraud Detective

No credentials, personal documents, caches, or the other computer's virtual environment were copied. A fresh Python 3.12 environment was installed in this workspace. The original requirements.lock.txt remains available; requirements.windows-py312.lock.txt records the new environment.

## Implemented

- Source PDF/image preview beside editable charges; selectable PDF pages; extracted-text fallback; local rasterization bounded to a reasonable image size.
- Patient and visit metadata grouped under an expander; original validation and human-review checkpoint retained.
- Source bytes and page selection cleared when starting a new bill.
- Calm green/white overview with three clearly labeled synthetic-example metrics, existing queue/search/filter controls and case actions.
- Report begins with grouped questions. Each finding shows its source charges, explanation, references and next question.
- Consistent card, typography, button and caption treatment; workspace columns stack at narrow widths.
- Built-in cloud sample processing is opt-in; no key is needed for local samples.
- Graph error handling preserves prior state if its diagnostic state lookup also fails.

## Verification completed

- Full offline suite: 47 tests passed after the xxhash compatibility fix, including OCR, workflow pause/resume, UI navigation, privacy isolation, chat and Excel export checks. Tests ran outside the sandbox because its UI runner stalled.
- Six tests in tests/test_evidence_workspace.py passed: restored sample totals and overlap handling; PDF/image preview bounds; selected PDF page; form edit return values without source mutation; source cleanup on new bill; report grouping and empty state.
- Restored sample calculates $840 total, $340 illustrative reduction and seven findings. Clean and distinct-service cases have no findings.
- Python compilation passed for app.py, billing, tests and scripts.
- pip check reports no broken requirements.
- Real overview, Evidence workspace and report-question components were rendered with tests/preview_ui.py in the in-app browser. Desktop overview and Evidence workspace were visually inspected; Evidence workspace stacking was inspected at 390px width. Caption contrast was improved following inspection.
- outputs/evidence-workspace.jpg captures the actual rendered workspace component. The harness explicitly labels itself as component QA, not the complete application.

## Dependency resolution and full-app verification

Windows Application Control blocked the xxhash 4.0.2 native wheel. Replacing it with the official PyPI xxhash 3.6.0 Windows/Python 3.12 wheel resolved imports. requirements.txt and requirements.windows-py312.lock.txt now pin 3.6.0. pip check passes. No security policies were changed and no dependency was replaced with a stub.

The preview process was stopped and replaced with app.py at http://127.0.0.1:8503. This port is also saved in .streamlit/config.toml. Browser verification completed Overview -> Open investigation -> Confirm charges and run audit -> report, with $840 billed, $340 illustrative reduction and seven findings. outputs/full-app-running.jpg captures the actual application. Live paid cloud calls were not made.

To run the full suite and application:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    .\run.ps1

Component checks can be repeated independently:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -p test_evidence_workspace.py -v

The preview harness is for layout inspection only; it does not validate graph-backed overview actions, full report downloads, or cloud calls.
