# Legal Invoice Tracking — Capstone: Plan Summary

**Team:** Ketan Domde (Lead/Lead Dev), Rajat, Bhushan, Trinkesh
**Duration:** 7 working days | **Budget:** ₹0 (free-tier/open-source only)
**Stack:** LangGraph (orchestration) + Groq API (LLM inference, Llama 3.x free tier) + Streamlit (frontend, Phase 2) + FastAPI + SQLite + PyMuPDF/Tesseract OCR + passlib/bcrypt + python-jose (JWT)

## Module Ownership (by architecture module)
- **Ketan (Lead):** LangGraph state graph, FastAPI integration, docs, demo coordination
- **Rajat:** Data layer — Matter/Budget/Ledger, budget tracking & threshold alerts, reporting queries
- **Bhushan:** Invoice ingestion, OCR fallback, Groq extraction node & prompts, confidence scoring
- **Trinkesh:** Validation & duplicate detection, human-review workflow, audit log, **login/JWT/RBAC**; co-owns Streamlit UI (Day 5)

## Login & RBAC (added 6 Aug 2026, second revision)
- Real, working login — not mocked: bcrypt-hashed passwords (passlib) + signed JWT sessions (python-jose), both free/open-source.
- Exactly three roles: **Admin** (full control incl. user management), **Editor** (create/edit matters/budgets/invoices, act on review queue), **Viewer** (read-only everywhere).
- Orthogonal firm-scoping: a user optionally carries firm_id; if set, that user's access is limited to that firm regardless of role.
- Enforced server-side via a `require_role([...])` FastAPI dependency on every endpoint except `/auth/login` — Streamlit hides buttons per role as a convenience only, not as the actual control.
- USER table: user_id, name, email (unique), password_hash, role (admin/editor/viewer), firm_id (FK, optional).
- Built starting Day 1 (schema + seed Admin) → Day 2 (login endpoint + JWT) → Day 3 (permission dependency + RBAC test account) → Day 4 (enforced on all endpoints) → Day 5 (Streamlit login page).

## 7-Day Milestone Plan
1. Kickoff, env setup, shared LangGraph state schema + USER/role schema agreed
2. Thin slice: login + one invoice end-to-end (ingest→extract→validate)
3. Confidence routing + human-review queue + budget alerts + RBAC checks
4. FastAPI layer + auth enforcement across all endpoints + reporting queries
5. Streamlit frontend (incl. login page) wired to backend
6. Testing, edge cases, RBAC verification, polish
7. Final live demo & handover

## Documents Delivered (5 .docx files, sent to user 6 Aug 2026, revised same day for RBAC)
- BRD.docx — Business Requirements (BR-1..BR-11, BR-11 = Login & Role-Based Access)
- PRD.docx — Product Requirements (FR-1..FR-26: FR-18–22 = Auth & Access Control, FR-23–26 = Streamlit incl. login page; Admin/Editor/Viewer permission table in Section 3)
- Architecture_Document.docx — zero-cost tech stack (now incl. passlib + python-jose), layered architecture diagram (incl. login), LangGraph workflow diagram, new Section 6 "Login & Role-Based Access Control" (roles, login flow, permission enforcement, secrets)
- ERD.docx — 9-entity SQLite schema; USER entity now has email/password_hash/role(admin/editor/viewer)/firm_id, with ERD diagram
- Execution_Plan.docx — RACI matrix (added "Login, JWT & RBAC" row, owner Trinkesh), day-by-day tasks weaving in auth work from Day 1, updated demo checkpoints (401/403 checks), updated risks

## Key Design Decisions
- Human-in-the-loop is non-negotiable: low-confidence or budget-invalid invoices always route to human review, never auto-approved.
- Login/RBAC is real (JWT + bcrypt), not mocked — but intentionally NOT a paid enterprise identity provider, to preserve the zero-cost constraint. Documented as a deliberate scope choice.
- Backend-first: every feature must work via API/CLI before Streamlit is touched (Day 5).
- Permission checks live server-side (FastAPI dependency), never only in the UI — verified explicitly in acceptance criteria and Day 6 testing tasks.

## Preceding Deliverable (also in this project)
A 4-slide "Our Understanding / Current System / Future System / Solution Architecture" deck (Konverge AI branded .pptx) was delivered earlier covering the same use case at a higher level, before the tech-stack constraints (LangGraph/Groq/Streamlit, zero-cost, 7-day team plan, and later RBAC) were specified.

## Daily Leadership Status Report (added 6 Aug 2026)
- A one-page Konverge-branded Word doc goes to leadership: Summary, Decisions/Progress Today, Plan for Tomorrow, Risks & Blockers, Overall Status.
- Day 0 report (covering the kickoff sync-up) was generated and delivered 6 Aug 2026.
- **Generated on demand, not on an automatic schedule** — the user explicitly declined automated daily scheduling. Ketan asks for it in-session each day it's needed.
- **Content source:** `claude/daily-log.md` in this project holds a dated entry per working day (decisions, plan for tomorrow, risks, status) — add a few lines there so the next on-demand report has real content to draw from. If no entry exists for a given day, the report falls back to that day's planned milestone from `Execution_Plan.docx`, labeled as plan-based rather than confirmed progress.
- **Branding:** Konverge AI navy/orange palette + logo (from the `konverge-ai-presentations` skill assets) via the shared `docHelpers.js` doc-generation module.