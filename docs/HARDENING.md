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

---

## Phase 1 — Core settings

- `SECRET_KEY` from env; `ImproperlyConfigured` if missing while `DEBUG=False`
  (dev falls back to an obviously-insecure local key). `DEBUG` defaults to False.
- `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` are comma-separated env vars
  (wildcards such as `https://*.up.railway.app` work). Railway's injected
  `RAILWAY_PUBLIC_DOMAIN` is trusted automatically; `healthcheck.railway.app`
  is always allowed so the deploy health check works.
- When `DEBUG=False`: SSL redirect (with `/healthz` exempt — Railway's probe is
  plain HTTP), proxy SSL header, HSTS 1 year + subdomains (+ preload, env
  switchable), secure session/CSRF cookies, nosniff, `Referrer-Policy:
  same-origin`, `X-Frame-Options: DENY`.
- Static: Django 4.2 `STORAGES`; `CompressedManifestStaticFilesStorage` only in
  production, plain storage + WhiteNoise finders in dev.
- Database: `dj_database_url` from `DATABASE_URL`, `conn_max_age=600`,
  `conn_health_checks=True`; local fallback to the compose Postgres on 5435.
- Django admin only mounted when `ENABLE_DJANGO_ADMIN=True`, at
  `ADMIN_URL_PREFIX`; superuser-only. `createsuperuser` is unaffected (the app
  stays installed; only the URL is conditional).
- `/healthz` added early (needed by `railway.toml`).
- Deploy files: `Procfile` (release=migrate, gunicorn gthread workers),
  `railway.toml` (Dockerfile builder, `preDeployCommand` migrate, health check),
  Dockerfile now bakes `collectstatic` into the image and honours `$PORT`;
  the entrypoint only migrates when `RUN_MIGRATIONS=1` (set by docker-compose).

**Bugs found and fixed while doing this phase**

- D7: `templates/dashboard/form.html` rendered the media formset *inside the
  delete-confirmation modal's form*. On Add pages media uploads never showed;
  on Edit pages the formset management form was missing from the main POST, so
  **every clan and person edit silently failed to save**. Moved into the main
  form; file-field and formset errors are now displayed. Add views now validate
  the media formset before saving instead of silently dropping it.
- D8: News posts could only be edited in the Django admin, which is now off by
  default. Added News & Events CRUD to the dashboard (content_admin +
  superadmin; delete superadmin-only).
- D9: ClanBoma, PersonEducation, PersonCareer, Announcement and SiteStats are
  still admin-only. Use `ENABLE_DJANGO_ADMIN=True` with a secret
  `ADMIN_URL_PREFIX` temporarily when they need editing (see "Deferred").

---

## Phase 2 — Authentication hardening

- **django-axes 8.3**: `AxesStandaloneBackend` first in
  `AUTHENTICATION_BACKENDS`, `AxesMiddleware` last. 5 failures per
  **username + IP** combination → locked for 1 hour (`AXES_COOLOFF_TIME = 1`),
  counter reset on success, custom `templates/lockout.html` (HTTP 429) in the
  PHF login design. Covers both `/dashboard/login/` and `/family/login/` (both
  call `authenticate(request, ...)`). The old hand-rolled cache counters were
  removed. `password`/`passphrase` are masked in axes logs.
- **Client IP behind Railway** (`apps/core/net.py`): uses the N-th
  X-Forwarded-For entry from the *right* (`TRUSTED_PROXY_COUNT`, default 1 in
  production). The old code took the left-most entry, which the client
  controls, so an attacker could rotate it to dodge the lockout. Values are
  validated as IP addresses. If Railway's proxy topology ever changes, adjust
  `TRUSTED_PROXY_COUNT`.
- **Argon2** primary hasher; PBKDF2/PBKDF2-SHA1/scrypt kept so existing hashes
  still verify (they're upgraded to Argon2 on next login).
- Password validators: min length **12** + similarity/common/numeric.
  `CreateAdminForm` now runs them (it didn't before), including similarity
  to the new user's name/username/email. Existing short passwords keep working
  until changed.
- Sessions: 1 hour sliding idle timeout, HttpOnly, SameSite=Lax (session + CSRF).
- Dashboard and family logout are **POST-only** (405 on GET).
- `ActiveAccountMiddleware` ends the session of a deactivated AdminProfile or
  FamilyAccount on their very next request (any URL), not just at login.
- Role audit results:
  - Delete endpoints and account (de)activation: superadmin-only **and**
    POST-only (`@require_POST`).
  - Submissions list/review: restricted to `content_admin` + superadmin
    (D10 — previously any staff role).
  - D11: A family-account user visiting `/dashboard/login/` got an infinite
    redirect loop (login → home → login…). Non-staff users now get the login
    page / 403, and `get_role_redirect` sends profile-less users to the public site.
  - Wrong-role access → redirect to own dashboard with a message (logged);
    non-staff authenticated users → 403.
- D12: `dashboard/login.html` never displayed the view's `error`, so failed
  logins showed no message. Fixed; the message is identical for unknown
  users, wrong passwords and accounts without dashboard access.
- Security events (role changes, account create/deactivate/reactivate,
  permission denials, refused logins) go to the `phf.security` logger
  (wired to console output in Phase 8).
