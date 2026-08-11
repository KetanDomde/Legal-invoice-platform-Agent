# Legal Invoice Tracking — Capstone: Daily Log

This is the running source-of-truth for the daily leadership status report. Ketan (or whoever ran that day's sync-up) should add one dated entry per working day — a few lines is enough. The daily-report automation reads the entry matching today's date; if none exists, it falls back to the planned milestone for that day from `Execution_Plan.docx` and labels the report as plan-based rather than actual-progress-based.

Entry format:
```
## YYYY-MM-DD — Day N
Decisions/progress: ...
Plan for tomorrow: ...
Risks/blockers: ...
Status: On Track / At Risk / Off Track
```

---

## 2026-08-06 — Day 0 (Kickoff)
Decisions/progress: Finalized the full documentation set (BRD, PRD, Architecture Document, ERD, Execution Plan). Locked the tech stack — LangGraph, Groq API (free tier), FastAPI + SQLite, Streamlit (Phase 2) — all free-tier/open-source. Divided responsibilities by architecture module: Ketan (orchestration/LangGraph + integration + docs), Rajat (data layer), Bhushan (invoice ingestion + AI extraction), Trinkesh (validation, review workflow, login/RBAC). Added login + role-based access (Admin/Editor/Viewer, real JWT + bcrypt) as a formal requirement. Agreed working process: thin end-to-end slice first, live demo every day, no slide-only updates.
Plan for tomorrow: Team reviews BRD/PRD/Architecture together; repo/env/dependency setup; Rajat drafts SQLite schema + seed data; Bhushan confirms Groq API access; Trinkesh drafts user/roles table + password-hashing utility; Ketan scaffolds the LangGraph project structure.
Risks/blockers: None yet. Tracked risks (Groq rate limits, tight 7-day timeline, RBAC scope) have agreed mitigations in the Execution Plan.
Status: On Track

## 2026-08-07 — Day 1+2 (combined)
Decisions/progress: Team reviewed the Architecture Document together. Repo created and shared with the team on GitHub (KetanDomde/Legal-invoice-platform-Agent), with the backend/frontend/docs folder structure in place. Ketan built and tested the LangGraph thin slice — ingest_invoice → extract_with_groq → validate → router → auto_approve/human_review — using stub functions for Rajat/Bhushan/Trinkesh's not-yet-built modules so nobody is blocked; both routing branches verified working. Code committed and pushed to main. Sent each teammate their specific Day 1+2 assignment (Rajat: schema+seed+budget function; Bhushan: Groq extraction+PDF parsing; Trinkesh: password hashing+JWT login+RBAC dependency), each mapped to the exact stub they're replacing in the agent file.
Plan for tomorrow: Rajat/Bhushan/Trinkesh land their real modules in place of the stubs; team resolves the open raw-sqlite-vs-ORM/Alembic decision before the data layer goes further; aim for the Day 2 demo checkpoint (log in as seeded Admin, get a JWT, run one sample invoice through the pipeline end-to-end with real — not stubbed — data).
Risks/blockers: None blocking yet. One open decision flagged: repo has an `alembic` folder implying ORM migrations, but ERD.docx assumed raw sqlite3 (migration-light) — needs a team call before Rajat builds the schema, to avoid rework.
Status: On Track

## 2026-08-10 — Day 3 (Ketan on leave)
Decisions/progress: Ketan on leave today. The graph-wiring half of his Day 3 task (conditional router + auto_approve/human_review/update_budget nodes) was already completed on Day 1+2, so it didn't block anyone. Team proceeds independently on their own Day 3 items: Bhushan (confidence scoring on extraction, tested against 3–5 sample invoices incl. one OCR/scanned PDF), Rajat (budget-ledger updates on approval + threshold alerts, duplicate-invoice detection), Trinkesh (human-review queue, approve/reject/clarify actions with audit logging, require_role dependency on review-queue endpoints). To avoid merge conflicts while Ketan is out, each works on their own branch (rajat/budget-ledger, bhushan/confidence-scoring, trinkesh/review-queue) instead of committing to main.
Plan for tomorrow: Ketan back — merges all three branches into main, finishes his own leftover Day 3 item (multi-firm/multi-matter seed data, one Editor + one Viewer test account), runs the proper Day 3 demo checkpoint (auto-approve path, human-review path, a fired budget alert, a Viewer token denied on approve), then moves straight into Day 4 scope (FastAPI endpoints, auth enforcement across all endpoints, reporting queries) same day if time allows.
Risks/blockers: Second schedule compression in a row (after Day 1+2) — losing part of Day 3 to leave shrinks the buffer further. Day 5 (Streamlit) is the milestone to watch if Day 4 doesn't fully close out tomorrow. Branch-based workflow adopted today specifically to avoid losing additional time to merge conflicts.
Status: At Risk (schedule buffer shrinking, not blocked)

## 2026-08-11 — Day 4
Decisions/progress: Ketan back from leave and picked up his Day 4 task — wrapping the LangGraph workflow behind FastAPI endpoints. While integrating, discovered Trinkesh had already landed real auth code (SQLAlchemy-based JWT + bcrypt login) directly in the repo — which resolves the open raw-sqlite-vs-ORM decision in favor of SQLAlchemy. Trinkesh's auth code depended on a data-layer and config module that didn't exist yet, so Ketan built the missing pieces (SQLAlchemy models for all 9 ERD entities, database session setup, settings/config) to make it actually runnable, then built the FastAPI app itself: /auth/login, /invoices/submit, /invoices/{id}/status, /invoices/review-queue, /invoices/{id}/approve, /invoices/{id}/reject, /reports/summary. Ran the full Day 4 demo checkpoint end-to-end against a live server: login → submit → status → review-queue → approve → report, plus a 401 (no token) and a 403 (Viewer token denied on approve) — all passed. Also resolved a passlib/bcrypt version conflict (pinned bcrypt==4.0.1) that would have blocked every teammate's local setup. Files delivered directly to Ketan's machine via the device bridge after regular downloads failed to open on his end.
Plan for tomorrow: Rajat picks up the real budget/ledger/reporting queries against the new SQLAlchemy models (currently reference implementations); Bhushan strengthens extraction robustness + duplicate-detection signal; Trinkesh applies require_role([...]) across every endpoint per the PRD permission table and adds Admin-only user-management endpoints; move into Day 5 (Streamlit, incl. login page) once Day 4 auth enforcement is fully applied.
Risks/blockers: Third schedule compression risk in a row — Day 3's leftover items plus all of Day 4 landed on the same day. Day 5 (Streamlit) is now the milestone most likely to feel the squeeze; worth a team check-in on whether Day 6 (testing/polish) needs to absorb some slack. One cleanup item outstanding: a stale duplicate workflow file (with spaces in its filename) needs manual deletion from the repo.
Status: On Track (caught back up to schedule; buffer still thin)