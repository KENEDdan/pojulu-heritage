# PHF Hardening Log

Branch: `hardening`. Each phase is one commit. Nothing here has been pushed or
run against the Railway production database.

## Decisions (running log)

| # | Decision | Why |
|---|----------|-----|
| D1 | Uncommitted WIP on `main` (wills app, upload validators, 6 migrations, Docker files) was committed as a "Baseline" commit before Phase 0 | Keeps each phase diff reviewable (owner approved) |
| D2 | The `wills` / family-accounts app is in scope | Highest-sensitivity data in the project (owner approved) |
| D3 | Local venv is Python 3.12 (only interpreter installed); Dockerfile stays on 3.11 for now, CI tests both | Brief says 3.11, Railway commits mention 3.12/3.13 |
| D4 | Local Postgres container is `pojulu_heritage_db` (docker-compose), port 5435 | Brief called it `pojulu_db` |
| D5 | Dashboard home quick Approve/Reject buttons (posting to a non-existent `approve_submission` view) were removed; the row keeps the "Full review" link to `dashboard:submission_review` | A one-click approve has no reviewer notes and the submission flow is now internal-only |
| D6 | `scratch_*.py` is gitignored | `scratch_seed_demo.py` creates demo users with a fixed password |

---

## Phase 0 — Audit (baseline)

**Baseline checks:** `check` 0 issues; `makemigrations --check` clean; `check --deploy`
with prod-like env vars: 0 warnings (HSTS / SSL redirect / secure cookies were
already set when `DEBUG=False`). No tests existed.

**Secrets:** git history contains
`SECRET_KEY = config('SECRET_KEY', default='django-insecure-pojulu-heritage-foundation-change-in-production')`.
If Railway ever ran without `SECRET_KEY` set, sessions/CSRF/password-reset
tokens were signed with a public key. **Rotate `SECRET_KEY` in Railway.** No real
DB passwords or tokens found in history (placeholders only). `.env` was never tracked.

**Broken / dead links fixed in Phase 0:**
- `templates/dashboard/home.html` referenced `dashboard:approve_submission` (does
  not exist) → superadmin home raised `NoReverseMatch` whenever a submission was pending.
- Public links to `submissions:form` removed from search results, elders list,
  family detail ("Add Member").
- No template links to `/admin/`.

**Public surface findings (fixed in later phases):**

| Where | Problem | Fixed in |
|---|---|---|
| Memorial list/detail/search | No visibility filter — memorials of unverified persons public | Phase 4 |
| Achievement detail, Marriage detail | No `is_verified` filter — reachable by pk guessing | Phase 4 |
| `person_detail.html` | father/mother/spouses/children/siblings not filtered by `is_verified` | Phase 4 |
| Marriage list | Shows linked unverified Person records | Phase 4 |
| cultural/elders/news detail | `<iframe src="{{ video_url }}">` accepts any http(s) URL | Phase 5 |
| Media in production | Not served at all with `DEBUG=False`, and Railway disk is ephemeral | Phase 4 |
| Submissions review | Any staff role could review submissions | Phase 2 |
| Login lockout | Hand-rolled, trusts spoofable `X-Forwarded-For` first hop | Phase 2 |
| `CreateAdminForm` | Never ran password validators | Phase 2 |
| Uploads | Extension-only checks, user filenames kept, no EXIF stripping | Phase 3 |
| Clan/Family counts | Per-row queries in lists | Phase 7 |

Contact fields (`phone`, `email_contact`, `address`) were not rendered in any
public template at baseline.
