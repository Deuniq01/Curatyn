# Curatyn — MVP (all phases implemented and running)

This is the actual, runnable codebase for all 11 phases of `08-execution-plan.md`, not just the blueprint. It has been built, started, and exercised end to end against a real PostgreSQL + pgvector database and a real Next.js production build in this environment.

## What was actually verified here, and how

There is no path from this sandbox to Google's or Microsoft's OAuth and mail APIs (no network route to `accounts.google.com`, `graph.microsoft.com`, etc., and no real client credentials), so a live Gmail/Outlook send could not be executed in this session. Everything else was:

- **Backend**: a real PostgreSQL 16 instance with the `vector` extension was installed and started, the full schema in `backend/app/models.py` was created against it, the FastAPI app was started with `uvicorn`, and `backend/tests/smoke_test.py` ran the entire golden path as real HTTP requests against the running server: signup, login, CV upload with text extraction and embedding, job description submission and AI extraction, application creation with pgvector-ranked CV matching (correctly picked the frontend-relevant CV over the warehouse CV), manual field edits, cover-letter regeneration that preserves a manually edited subject line (FR-REVIEW-004), a deliberately forced send failure that left every reviewed field untouched, a retry that succeeded, and a duplicate send with the same idempotency key that returned the stored result instead of sending twice. All 26 assertions pass.
- **Frontend**: `npm run build` completes a real TypeScript-checked Next.js production build with zero errors, and the production server was started and each route (`/`, `/apply`, `/cvs`, `/applications`, `/applications/[id]`, `/login`, `/signup`) was confirmed to return HTTP 200.

What is genuinely untested, because it requires infrastructure this sandbox doesn't have: the real Gmail/Microsoft OAuth redirect flow, a real `send_email()`/`create_draft()` call against Gmail or Graph, and OCR on a real JD screenshot. The seams for all three (`app/token_refresh.py`, `app/gmail_provider.py`, `app/microsoft_provider.py`, `app/ocr.py`) are implemented and code-reviewed against each provider's documented API shape, but "implemented correctly" and "verified against the live API" are different claims, and only the first one is true right now.

## Running it yourself

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# generate a real value for CURATYN_TOKEN_ENCRYPTION_KEY:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# paste it into .env

# needs a running Postgres with the vector extension available, e.g.:
#   apt-get install postgresql postgresql-contrib postgresql-16-pgvector
#   service postgresql start
#   createuser -s curatyn (or your own role) and set DATABASE_URL in .env to match

PYTHONPATH=. python3 scripts/init_db.py   # creates the extension + tables
PYTHONPATH=. uvicorn app.main:app --reload
```

Health check: `curl http://127.0.0.1:8000/api/health`

Run the smoke test against it (`AI_BACKEND=mock` and `EMAIL_BACKEND=mock` are the defaults, so no external API keys are needed for this):

```bash
PYTHONPATH=. python3 tests/smoke_test.py
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at the backend above
npm run dev
```

Visit `http://localhost:3000`.

## Switching from mock to real backends

- **AI**: set `AI_BACKEND=gemini` (or `ollama`) in the backend `.env`, and implement the two `NotImplementedError` branches in `app/ai_client.py`. The rest of the codebase (`app/ai_pipeline.py` and everything above it) does not change.
- **Email**: set `EMAIL_BACKEND=live`. `app/routers/send_routes.py` will then require the user to have gone through the real OAuth flow (`app/token_refresh.py` needs real `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` or `MICROSOFT_CLIENT_ID`/`MICROSOFT_CLIENT_SECRET` in `.env`, and `app/routers/auth_routes.py` needs the real `start`/`callback` endpoints added — the dev-only `oauth/dev-connect` stand-in should be deleted at that point).
- **OCR**: implement `app/ocr.py`'s `extract_text_from_image()` — Tesseract for a local option, or a vision-capable model call.

## Where things live

Same layout as the earlier blueprint, now as working code instead of a spec:

- `backend/app/` — FastAPI app, SQLAlchemy models (mirrors `02-database-schema.prisma` from the blueprint), routers for auth/CVs/job descriptions/applications/send, the AI pipeline, the email provider abstraction, idempotency, and token encryption.
- `backend/scripts/init_db.py` — one-shot schema creation for local dev.
- `backend/tests/smoke_test.py` — the end-to-end test described above.
- `frontend/app/` — landing page, signup/login, CV vault, JD paste ("apply"), the Final Review screen, application history.
- `frontend/components/FinalReviewScreen.jsx` — the review screen and send-confirmation modal, Tailwind + Lucide only, wired to the real API in `frontend/lib/api.ts`.

The original planning documents (architecture diagram, full API spec, execution plan, project handoff) from the first pass are still accurate and are not repeated here — see them alongside this package.

## Bugs found and fixed while actually running this (worth knowing about)

These were caught only by running the code, not by reading it, which is exactly why "run all phases at once" was worth doing for real:

1. **Password hashing crashed on this platform's `bcrypt` build** (`passlib`'s bcrypt backend-detection routine hit a known incompatibility with newer `bcrypt` releases). Switched to `pbkdf2_sha256`, which has no native-extension dependency and no such issue.
2. **Lazy-loading `job_description`/`selected_cv` relationship objects outside an awaited context raised `MissingGreenlet`** under the async SQLAlchemy driver. Fixed by eager-loading both relationships with `selectinload` everywhere an application is serialized, instead of `session.refresh(obj, attribute_names=[...])`.
3. **Retrying a failed send was silently rejected.** The original idempotency claim only allowed the `READY_TO_SEND → SENDING` transition; a `SEND_FAILED` application could never be re-claimed for a retry. Fixed `claim_for_sending()` to also accept `SEND_FAILED` as a valid starting state.
4. **The mock JD-extraction heuristic missed company names that lead the sentence** (e.g. "Acme Technologies is hiring...") because it only looked for "at X" / "company: X" patterns. Added a second pattern for "X is hiring/looking/seeking".
5. **The mock email-address extractor captured trailing punctuation** ("careers@acme.com." instead of "careers@acme.com") because the character class included `.`. Fixed by stripping trailing punctuation after the match.

None of these were in the code you'd have read and nodded along to; all five only surfaced once real requests hit a real database and a real HTTP server.
