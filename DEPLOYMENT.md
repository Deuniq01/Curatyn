# Deploying Curatyn to Production

This is the click-by-click runbook to take Curatyn live on **Vercel (frontend) + Render (backend) + Supabase (Postgres + file storage)**, with real Gemini AI and real Gmail sending.

Work top to bottom. Each phase produces values you paste into a later phase, so don't skip ahead. Where a step says **📋 copy**, save the value somewhere temporary — you'll need it soon.

---

## Two things to know before you start

1. **Gmail sending is gated by Google.** `gmail.send` is a Google *restricted scope*. Until your app passes Google's OAuth verification + a CASA security assessment (a multi-week, sometimes paid process), your app stays in **"Testing" mode**. That is fully functional but limited:
   - Only **test users you add by hand** (up to 100) can connect Gmail.
   - They see an **"Google hasn't verified this app"** warning (they click *Advanced → Go to Curatyn*).
   - Their Gmail connection **expires every 7 days** and must be reconnected.

   This is Google policy — no code changes it. It's fine for launch, you, and a small pilot group. See [Scaling past the test-user limit](#scaling-past-the-test-user-limit) at the end for the verification path. **Gemini AI has no such gate.**

2. **Free tiers sleep.** Render's free web service spins down after ~15 min idle; the first request afterward takes ~50s to wake. Fine for a pilot; upgrade to a paid instance ($7/mo) when you want it always-on.

---

## Phase 0 — Push the cleaned repo

Your first commit accidentally included secrets (the `.gitignore` was misspelled). That's now handled: the keys are rotated, `backend/.env` and `backend/.venv/` are un-tracked, and the Supabase database password is reset. The old values are still in git history but are no longer live, so nothing needs rotating again.

1. **Make the GitHub repo private** (recommended). On GitHub: **Settings → General → Danger Zone → Change repository visibility → Private**.

2. Push `main`. Nothing in the current working tree contains a live secret.

---

## Phase 1 — Supabase (database + file storage)

You already created the project. Now configure it.

### 1a. Enable pgvector
Supabase supports it; you just enable the extension. **Database → Extensions**, search `vector`, toggle it on. (The init script in step 1d also runs `CREATE EXTENSION IF NOT EXISTS vector` as a safety net, so this is belt-and-suspenders.)

### 1b. Create a private storage bucket
**Storage → New bucket**:
- Name: `cvs`
- **Public bucket: OFF** (must stay private — CVs are personal documents)
- Create.

### 1c. Collect your connection values
You need three things. All are in **Project Settings**.

**Database connection string** — **Project Settings → Database → Connection string → "Session pooler"** (the "Transaction pooler" also works; the code disables the prepared-statement cache either way). It looks like:
```
postgresql://postgres.abcdxyz:[YOUR-PASSWORD]@aws-0-xx.pooler.supabase.com:5432/postgres
```
Build your `DATABASE_URL` from it:
- Replace `[YOUR-PASSWORD]` with your new database password.
- Change the scheme `postgresql://` → **`postgresql+asyncpg://`**

📋 The final value (this is `DATABASE_URL`):
```
postgresql+asyncpg://postgres.abcdxyz:YOUR_NEW_PASSWORD@aws-0-xx.pooler.supabase.com:5432/postgres
```
> Use the **pooler** host (`...pooler.supabase.com`), not the direct `db.<ref>.supabase.co` host — the direct host is IPv6-only and Render can't reach it. The app strips SSL/pgbouncer quirks automatically, so no `?sslmode=...` is needed.

**Project URL** — **Project Settings → API → Project URL**, e.g. `https://abcdxyz.supabase.co`. 📋 this is `SUPABASE_URL`.

**Service role key** — **Project Settings → API → Project API keys → `service_role`** (click *Reveal*). 📋 this is `SUPABASE_SERVICE_KEY`.
> ⚠️ The `service_role` key bypasses all row-level security. It lives **only** on the backend (Render). Never put it in the frontend or commit it.

### 1d. Create the database schema
Run the init script once from your machine, pointed at Supabase. In a terminal:

```bash
cd backend
```

Set the one variable and run the script (bash, on your Windows machine):

```bash
DATABASE_URL="postgresql+asyncpg://postgres.abcdxyz:YOUR_NEW_PASSWORD@aws-0-xx.pooler.supabase.com:5432/postgres" PYTHONPATH=. python scripts/init_db.py
```

Expected output: `Schema created.` If you get a connection error, re-check the password and that you used the **pooler** host with the `postgresql+asyncpg://` scheme.

---

## Phase 2 — Google Cloud (Gemini AI + Gmail OAuth)

Two separate credentials come from Google: an **API key** for Gemini, and an **OAuth client** for Gmail sending.

### 2a. Gemini API key
Go to **[aistudio.google.com/apikey](https://aistudio.google.com/apikey)** → **Create API key**. 📋 this is `GOOGLE_API_KEY`. That's all Gemini needs — no billing required at free-tier limits.

### 2b. OAuth consent screen
In **[console.cloud.google.com](https://console.cloud.google.com)**, create/select a project, then **APIs & Services → OAuth consent screen**:
- User type: **External** → Create.
- App name: `Curatyn`, your support email, developer email. Save.
- **Scopes → Add or remove scopes → manually add** `https://www.googleapis.com/auth/gmail.send` → Update. Save.
- **Test users → Add users**: add **your own Gmail address** (and any pilot users' addresses). Save.
- Leave publishing status as **Testing**.

Also enable the Gmail API: **APIs & Services → Library** → search **Gmail API** → **Enable**.

### 2c. OAuth client (Web)
**APIs & Services → Credentials → Create credentials → OAuth client ID**:
- Application type: **Web application**
- Name: `Curatyn Web`
- **Authorized redirect URIs**: we don't have the Render URL yet. Add a placeholder now and fix it in Phase 5:
  ```
  https://REPLACE-ME.onrender.com/api/auth/oauth/gmail/callback
  ```
- Create. 📋 copy the **Client ID** (`GOOGLE_CLIENT_ID`) and **Client secret** (`GOOGLE_CLIENT_SECRET`).

---

## Phase 3 — Render (backend)

### 3a. Create the service
Push must be done first (Phase 0). Then in **[dashboard.render.com](https://dashboard.render.com)**:

**Option A — Blueprint (recommended).** **New → Blueprint** → connect your GitHub repo. Render reads `render.yaml` and creates the service, then prompts you for every secret. Fill them in from the values you collected (see the table below).

**Option B — Manual.** **New → Web Service** → connect the repo →
- Root Directory: `backend`
- Runtime: Python 3
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/api/health`
- Add every env var below by hand.

### 3b. Environment variables
Set these in the Render dashboard (**Environment** tab). The non-secret toggles are already baked into `render.yaml` if you used Option A.

| Variable | Value |
|---|---|
| `DATABASE_URL` | your `postgresql+asyncpg://...pooler...` string (Phase 1c) |
| `JWT_SECRET` | the rotated value in your local `backend/.env` |
| `CURATYN_TOKEN_ENCRYPTION_KEY` | the rotated value in your local `backend/.env` |
| `AI_BACKEND` | `gemini` |
| `GOOGLE_API_KEY` | Gemini key (Phase 2a) |
| `GEMINI_MODEL` | `gemini-2.0-flash` |
| `GEMINI_EMBED_MODEL` | `text-embedding-004` |
| `EMAIL_BACKEND` | `live` |
| `GOOGLE_CLIENT_ID` | OAuth client id (Phase 2c) |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret (Phase 2c) |
| `GOOGLE_REDIRECT_URI` | `https://<your-service>.onrender.com/api/auth/oauth/gmail/callback` |
| `STORAGE_BACKEND` | `supabase` |
| `SUPABASE_URL` | Phase 1c |
| `SUPABASE_SERVICE_KEY` | Phase 1c |
| `STORAGE_BUCKET` | `cvs` |
| `FRONTEND_URL` | `https://<your-app>.vercel.app` — placeholder until Phase 4, then update |
| `ALLOWED_ORIGINS` | `https://<your-app>.vercel.app` — same, update in Phase 5 |

> To copy the two rotated secrets: open `backend/.env` locally and copy the `JWT_SECRET=` and `CURATYN_TOKEN_ENCRYPTION_KEY=` values.

### 3c. Deploy and note the URL
Deploy. When it's live, 📋 copy the service URL, e.g. `https://curatyn-backend.onrender.com`.

**Now fix the two placeholders:**
- **Google Cloud** (Phase 2c): edit the OAuth client's Authorized redirect URI to the real value: `https://curatyn-backend.onrender.com/api/auth/oauth/gmail/callback`. It must match `GOOGLE_REDIRECT_URI` **exactly**.
- **Render**: make sure `GOOGLE_REDIRECT_URI` uses this real host.

Test it: open `https://curatyn-backend.onrender.com/api/health` in a browser → should return `{"status":"ok"}` (first hit may take ~50s if the free instance was asleep).

---

## Phase 4 — Vercel (frontend)

In **[vercel.com](https://vercel.com)** → **Add New → Project** → import your GitHub repo:
- **Root Directory: `frontend`** (click Edit, select the folder).
- Framework preset: Next.js (auto-detected).
- **Environment Variables**: add
  | Variable | Value |
  |---|---|
  | `NEXT_PUBLIC_API_BASE` | `https://curatyn-backend.onrender.com` (your Render URL, no trailing slash) |
- Deploy. 📋 copy the resulting URL, e.g. `https://curatyn.vercel.app`.

---

## Phase 5 — Wire the two together

Now that both URLs exist, close the loop:

1. **Render → Environment**: set both to your real Vercel URL, then let it redeploy:
   - `FRONTEND_URL` = `https://curatyn.vercel.app`
   - `ALLOWED_ORIGINS` = `https://curatyn.vercel.app`
   > Vercel also gives every deployment a preview URL. If you want previews to work too, list them comma-separated: `https://curatyn.vercel.app,https://curatyn-git-main-you.vercel.app`.

2. Confirm **Google's redirect URI** and Render's `GOOGLE_REDIRECT_URI` both point at the Render `/api/auth/oauth/gmail/callback` (Phase 3c).

---

## Phase 6 — End-to-end test

On your live Vercel site:

1. **Sign up** with an email + password.
2. Go to **CV Vault** → **Connect Gmail**. You'll be sent to Google.
   - You'll see **"Google hasn't verified this app"** → **Advanced → Go to Curatyn (unsafe)** → allow `gmail.send`. (Expected in Testing mode. Only works for addresses added as test users in Phase 2b.)
   - You return to the CV Vault with **"Connected gmail for sending."**
3. **Upload a CV** (PDF). It should land in your Supabase `cvs` bucket (check **Storage** in Supabase).
4. **Apply to a job** → paste a job description. Real Gemini extracts the fields.
5. **Create the application** → a matching CV is chosen (pgvector), a cover letter is generated.
6. **Send** (or **Save as draft**) → check the recipient inbox / your Gmail "Sent" folder.

If all six pass, you're live. 🎉

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `/api/health` hangs ~50s then works | Free Render instance woke from sleep. Normal. Upgrade to a paid instance for always-on. |
| Login works but every API call fails with a CORS error in the browser console | `ALLOWED_ORIGINS` on Render doesn't exactly match the Vercel origin (scheme + host, no trailing slash). Fix and redeploy. |
| `redirect_uri_mismatch` from Google | The Render `GOOGLE_REDIRECT_URI` and the Authorized redirect URI in Google Cloud aren't byte-for-byte identical. |
| Gmail connect returns `?email_error=no_refresh_token` | Google only returns a refresh token on first consent. In Google Account → Security → Third-party access, remove Curatyn, then reconnect. |
| Gmail connect returns `?email_error=access_denied` | The Google account isn't in your Testing test-user list (Phase 2b), or you declined the consent. |
| DB connection errors on Render startup | Must be the **pooler** host with `postgresql+asyncpg://`. The direct `db.<ref>.supabase.co` host is IPv6-only and unreachable from Render. |
| CV upload fails | Check `SUPABASE_SERVICE_KEY` (the `service_role` key, not `anon`), and that the `cvs` bucket exists. |
| Emails send but AI output looks fake/templated | `AI_BACKEND` isn't `gemini`, or `GOOGLE_API_KEY` is missing/invalid on Render. |

## Redeploying after code changes
- **Backend:** push to `main` → Render auto-deploys (if auto-deploy is on).
- **Frontend:** push to `main` → Vercel auto-deploys.
- **Schema changes:** re-run `scripts/init_db.py` for additive dev changes, or adopt Alembic migrations for anything real.

## Scaling past the test-user limit
To lift the 100-user cap, the unverified warning, and the 7-day token expiry, submit your app for Google verification: **OAuth consent screen → Publish app**, then complete Google's review (a **CASA** security assessment is required for restricted scopes like `gmail.send`). Until then, add pilot users by hand under **Test users**. Everything else about your deployment stays exactly the same.

---

*Config lives in `render.yaml` (backend service + env var names) and `backend/.env.example` (every variable documented). Local dev still runs fully on mock backends with no keys — see the repo README.*
