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

Later decisions (D7–D17) are recorded inline, in the phase where they were
made. Most notable: D7 (broken clan/person edit form fixed), D8 (news CRUD
added to the dashboard), D13 (.doc/.avi uploads dropped), D16 (ClanBoma
`history` field preserved), D17 (Django 4.2 → 5.2 LTS).

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

---

## Phase 3 — File upload security

- `apps/core/validators.py` (content-checking, attached to **model fields** so
  forms, inline formsets and the admin are all covered):

  | Validator | Extensions | Content check | Max |
  |---|---|---|---|
  | `validate_image` | jpg jpeg png gif webp | Pillow format allow-list + `verify()` + full decode; ≤ 60 MP | 8 MB |
  | `validate_pdf` | pdf | starts with `%PDF-` | 25 MB |
  | `validate_document` | pdf, docx | PDF header, or a real OOXML zip with **no macros** | 25 MB |
  | `validate_audio` | mp3 wav m4a ogg aac | magic bytes per format | 200 MB |
  | `validate_video` | mp4 webm mov | magic bytes / ISO-BMFF atoms | 500 MB |
  | `validate_media` | union of the above | dispatches by extension, then checks content | per type |

  Files already in storage are not re-validated on every edit.
- D13: Dropped `.doc` (legacy OLE, macro risk) and `.avi` (browsers can't
  play it). Existing stored files are untouched; only new uploads are affected.
  Kept `.docx` (macro-free only) and `.aac` so current workflows keep working.
- `upload_to=UploadTo('<prefix>')` → `<prefix>/<yyyy>/<mm>/<uuid4>.<ext>`.
  The user's filename (which often contained real names) is discarded.
- `SafeFileField` / `SafeImageField` re-encode every new **image** upload in
  memory just before it's written to storage (works the same on S3): EXIF
  orientation applied, **all metadata stripped (EXIF incl. GPS, XMP)**, long
  edge capped at 1600 px (2400 px for certificates so scans stay legible),
  re-encoded JPEG q85 (WebP q85 if the image has real transparency). Animated
  GIFs keep their first frame only. Non-image files are stored byte-for-byte.
- `DATA_UPLOAD_MAX_MEMORY_SIZE` 10 MB, `FILE_UPLOAD_MAX_MEMORY_SIZE` 5 MB
  (larger uploads stream to a temp file), `FILE_UPLOAD_PERMISSIONS` 0640.
- Migrations: clans 0004, cultural 0003, elders 0003, genealogy 0004, news 0003,
  submissions 0003 (field class / upload_to / validators only; no data change).
- **Note:** a 500 MB video through gunicorn on Railway is slow and fragile.
  Prefer YouTube/Vimeo links for long videos (see Deferred: direct-to-bucket uploads).

---

## Phase 4 — Media storage and privacy

**Storage** (`apps/core/storage.py`, `STORAGES` in settings):

| Alias | Local (no bucket) | Production (bucket configured) | Used for |
|---|---|---|---|
| `default` | `MEDIA_ROOT` | S3Storage, prefix `media/`, unsigned URLs on `MEDIA_PUBLIC_BASE_URL` (or signed 6 h URLs if unset) | Person/chief/elder photos, news covers, cultural images & audio, clan/news media |
| `private` | `PRIVATE_MEDIA_ROOT` (outside `MEDIA_ROOT`) | `PrivateS3Storage`, separate bucket, prefix `private/`, signed URLs | `Person.profile_pdf`, `PersonEducation.certificate`, `PersonMedia.file`, `ElderInterview.audio_file`/`video_file`, `Submission.attachment` |

- Private fields use `storage=get_private_storage` (a callable), so migrations
  don't change between environments.
- Every private file's `.url` is `/private-media/<name>` → the
  `core:private_media` gate (`apps/core/private_media.py`). It works out which
  record owns the file, checks the role (superadmin always; genealogy files →
  genealogy/memorial/content admins; interview recordings → elder/cultural/content
  admins, **or anyone once the interview is published**; submission
  attachments → content admins), then streams the file (local) or 302s to a
  **5-minute signed URL** (S3). Responses are `Cache-Control: private, no-store`.
  Anyone else gets a 404, so the gate never confirms a file exists. Path traversal is rejected.
- If `MEDIA_PUBLIC_BASE_URL` is set (public bucket), settings refuse to start
  unless the private bucket is a *different* bucket.
- Run `py manage.py move_private_media` once after deploying to move
  existing private-field files out of public storage (idempotent; `--dry-run`).

**Privacy of living people**

- `Person.show_contact_publicly` (default False): phone/email/address only
  appear on the public person page when ticked (and never for deceased
  people). Staff dashboards always show them. No other public page renders them.
- `Person.is_private` (default False): hides a **living** person from every
  public page, list, search, family tree, relatives list and counts (404 on
  their URLs). Deceased people are unaffected.
- Every public model now has a `.public()` queryset (Clan, Family, Person,
  MemorialRecord, Achievement, Marriage, CulturalRecord, ElderInterview,
  NewsPost) and **every public view uses it**. This fixes the Phase 0 leaks:
  memorials of unverified people, achievement/marriage detail by pk,
  unverified relatives on person pages and in family trees, and marriages
  naming hidden people (a marriage is public only if both linked spouses are).
  Links to unverified clans/families on person pages are suppressed.
- **Unguessable public media:** public files have random 128-bit names, so
  an unpublished record's photo can't be found by guessing. Sensitive files are
  in private storage behind the gate.
- Migrations: elders 0004, genealogy 0005 (new fields default False; existing
  people stay as they were), submissions 0004.

---

## Phase 5 — Public surface

- **Submissions are no longer public.** `apps/submissions/{views,forms,urls}.py` and
  `templates/submissions/` were deleted and `/submit/` now 404s. The model and the
  dashboard review screens (content_admin) stay for historical submissions.
- **Rate limits** (django-ratelimit, keyed on the proxy-aware client IP, HTTP 429 with a
  PHF page): search 30/min, family tree 30/min, home page 120/min, private-media gate
  120/min. Every list view's `q` is trimmed and capped at 100 characters. Search needs
  at least 2 characters.
  D14: the counters live in the default cache, which is **Redis when `REDIS_URL` is set**
  and per-process LocMem otherwise. Without Redis each gunicorn worker counts on its own,
  so the effective limit is multiplied by the worker count. Adding Railway's Redis plugin
  is recommended.
- **CSP (django-csp 4.0), report-only.** `default-src 'self'`; scripts from self and
  jsdelivr; styles from self, jsdelivr and Google Fonts; fonts from self, gstatic and
  jsdelivr; images/media from self, `data:` and the media bucket hosts; frames only
  `www.youtube-nocookie.com` and `player.vimeo.com`; `object-src 'none'`;
  `frame-ancestors 'none'`; `base-uri`/`form-action` self. `CSP_ENFORCE=True` switches
  to enforcing, and `CSP_REPORT_URI` collects reports.

  **Before enforcing**, these must move into static files (or get nonces):
  - Inline `<script>` blocks: `clans/detail.html`, `dashboard/base_dashboard.html`.
  - Inline event handlers (`onclick=` etc.): `base.html`, `achievements/list.html`,
    `clans/detail.html`, `core/search_results.html`, `genealogy/family_detail.html`,
    `marriages/list.html`, `dashboard/base_dashboard.html`, `dashboard/accounts.html`,
    `dashboard/family_accounts.html`, `dashboard/will_reveal_confirm.html`.
  - `<style>` blocks: `dashboard/base_dashboard.html`, `dashboard/login.html`,
    `lockout.html`, `wills/base_family.html`, `wills/login.html`.
  - About 260 `style="…"` attributes across 47 templates. Either move them to
    `pojulu.css` or add `'unsafe-inline'` to `style-src` only, which is a much smaller
    risk than inline scripts.
  The error pages already use a static stylesheet.
- **Video links**: `video_url` fields (CulturalRecord, ElderInterview, NewsPost,
  PersonMedia, ClanMedia) only accept YouTube/Vimeo URLs (watch, youtu.be, shorts,
  embed, vimeo.com/ID, player.vimeo.com). Templates never put the raw URL in an
  iframe: `|embed_url` rebuilds `https://www.youtube-nocookie.com/embed/<id>` or
  `https://player.vimeo.com/video/<id>` from a strictly validated ID. Old invalid
  URLs simply aren't embedded. Migrations: clans 0005, cultural 0004, elders 0005,
  genealogy 0006, news 0004.
- `/robots.txt` disallows `/dashboard/`, `/admin/`, `/family/`, `/private-media/`,
  `/healthz` and `/search/`, and points to `/sitemap.xml`. The real `ADMIN_URL_PREFIX` is
  deliberately not listed. The sitemap covers static pages plus public clans, families,
  people (private living people excluded), news and interviews.
- **Error pages** 400/403/403_csrf/404/429/500 in PHF styling. They're standalone (no
  `base.html`, no context-processor data, plain `/static/css/errors.css`), so they render
  with zero DB queries even when the database is down.
- **Social meta**: `base.html` has description, canonical, OpenGraph and Twitter Card
  tags with blocks overridden on news, clan, person and interview pages
  (title/description/image). Person meta only uses name, lifespan and clan, never contact
  details or biography.

---

## Phase 6 — Data integrity, audit trail, soft delete

- **django-simple-history** on Person, Family, Clan, ClanChief, ClanBoma,
  ClanEvent, MemorialRecord, Achievement, Marriage, CulturalRecord,
  ElderInterview, NewsPost, AdminProfile, plus FamilyAccount (D15: the Will
  model, which holds encrypted content, is deliberately *not* tracked).
  `HistoryRequestMiddleware` records the acting user. History stores file
  *names*, not copies (`SIMPLE_HISTORY_FILEFIELD_TO_CHARFIELD`).
  - D16: `ClanBoma` already has a data field called `history` (the boma's
    history text). Its audit manager is named `change_history` instead. A
    first attempt at the migration would have **dropped that column**; this
    was caught before any migration was applied.
  - Existing records have no "created" history entry. Optionally run
    `py manage.py populate_history --auto` once to seed a baseline.
- **Soft delete** (`apps/core/softdelete.py`) for Person, Family, Clan,
  MemorialRecord, ElderInterview and NewsPost: `is_deleted`, `deleted_at`,
  `deleted_by`. The default manager `objects` hides deleted rows (so do related
  managers and form dropdowns), and `all_objects` sees everything. Slug
  generation and uniqueness checks use `all_objects`, so a trashed record never
  causes an IntegrityError. Instead a friendly "this is in the Trash, restore
  it" error appears (Clan name, Memorial-per-person).
  - Dashboard delete views for those six models now move records to the Trash
    (superadmin + POST, logged). The modal says "Move to Trash".
  - Superadmin-only **Trash** page (`/dashboard/trash/`): filter by type,
    Restore (POST), Delete permanently (POST + confirmation modal).
    Permanently deleting a Person who has a family (will) account is
    **blocked**, because the cascade would destroy their will.
  - Permanent deletes remove the stored files after the transaction commits
    (`apps/core/signals.py`). Soft deletes never touch files.
  - Editing a record that points at something now in the Trash (e.g. a child
    whose father was trashed) still works: dropdowns keep the current value.
- Superadmin **Activity Log** (`/dashboard/activity/`): every tracked
  change across all models, newest first, filterable by user and record type,
  paginated. It shows who, when, the action (Created / Updated / Moved to Trash /
  Restored / Deleted permanently) and which fields changed. It covers the latest
  1,000 changes per filter.
- **Genealogy integrity**:
  - `Person.clean()` gives field-level form errors for: death year before birth
    year (free-text years like "approx. 1940s" are parsed), death date before
    birth date, being one's own father/mother, the same person as both
    parents, and any **father/mother loop** (a parent who is already the
    person's descendant, which also covers "parent and child of the same
    person"). The ancestor walk is bounded (200 generations), visits each person
    once, and includes trashed records.
  - DB `CHECK` constraints as a backstop: not own father, not own mother,
    parents distinct, `death_date >= birth_date`. Migration genealogy 0007
    first clears self-parent and same-person-both-parents links (unambiguous
    garbage). If any death date precedes a birth date, **the migration stops and
    lists the person IDs to fix** rather than guessing.
- **Family tree**: ancestors/descendants were already batched per generation
  with visited sets. Aunts/uncles, cousins and nieces/nephews are now one query
  per tier instead of one per relative, and every tier excludes people already
  shown. A test creates a real A↔B loop in the database and the tree still
  renders within a bounded number of queries.
- A shared pagination partial (keeps all filters, URL-encoded) is used by the
  Trash and Activity Log and by every public list.

---

## Phase 7 — Performance

- **Indexes** (migrations elders 0007, genealogy 0008, news 0006):
  `Person(last_name, first_name)`, `Person(is_verified, is_deleted)`,
  `NewsPost(is_published, -published_at)`, `ElderInterview(is_published, -interview_date)`.
  Already indexed and left alone: every ForeignKey (`Person.clan/family/father/mother`,
  `Marriage.husband/wife`) gets an index from Django automatically, and
  `Clan.slug`/`Family.slug` are `unique` (which implies an index).
- **N+1 removed**: `Clan.objects.with_counts()` / `Family.objects.with_counts()`
  annotate the public person/family/member counts in one query, and
  `Clan.person_count` / `family_count` / `Family.member_count` use the
  annotation when present (templates unchanged). Clan list, home, clan detail,
  family list and the dashboards use it. Added `select_related` /
  `prefetch_related` where templates follow relations (e.g. the home page's
  `clan.bomas.exists` was one query per featured clan). Cultural/achievement
  dashboard type counts are now one GROUP BY instead of one query per type.
  Tests with `CaptureQueriesContext` assert that every public list, search,
  clan detail and 7 dashboards use **no more queries with 8 rows than with 2**.
- **Pagination**: 25 per page everywhere (`RECORDS_PER_PAGE`), using one shared
  `partials/pagination.html` that keeps all active filters (URL-encoded) and
  supports two tables on one page (`page_param`). Dashboard tables previously
  showed only the newest 25–50 rows with no way to reach older ones.
- **Dashboard search/filters** (name, clan, published/draft) on the persons,
  families, clans, interviews and news tables (`dashboard/_filters.html`).
  The memorial, cultural and achievement tables are paginated.
- **Caching**: the home page stats and news blocks are cached for 60 s
  (`home:stats`, `home:news`) in the default cache: LocMem in dev, Redis when
  `REDIS_URL` is set.

---

## Phase 8 — Observability and backups

- **Sentry** (`sentry-sdk` + DjangoIntegration) only when `SENTRY_DSN` is set:
  `send_default_pii=False`, `max_request_body_size='never'` (no form bodies,
  so no passwords, will passphrases or personal data), `traces_sample_rate`
  0.1 (env `SENTRY_TRACES_SAMPLE_RATE`), `environment` from
  `SENTRY_ENVIRONMENT`, release = Railway's `RAILWAY_GIT_COMMIT_SHA`.
- **Logging**: one-line JSON to stdout in production (`apps/core/logging.py`),
  plain text in dev. The `phf.security` logger records failed logins
  (username + proxy-aware IP, never the password), lockouts (axes), permission
  denials, refused dashboard logins, staff account creation / role changes /
  (de)activation, Trash moves, restores and permanent deletes, and sessions ended
  because an account was deactivated. `django.security` (CSRF failures,
  disallowed hosts) and `django.request` (4xx/5xx) are kept at WARNING.
- **`/healthz`**: `SELECT 1` against the DB → `{"status":"ok","database":"ok"}`
  or HTTP 503 `{"status":"error","database":"unavailable"}`. No versions, hosts
  or error text. Exempt from the HTTPS redirect for Railway's probe.
- **Backups** (`scripts/backup_db.py`): `pg_dump --format=custom --compress=9`
  from `DATABASE_URL` (password passed only via `PGPASSWORD`), validates the
  `PGDMP` header, uploads to `s3://$BACKUP_BUCKET_NAME/db-backups/yyyy/mm/dd/`,
  checks the uploaded size, then deletes backups older than 30 days while always
  keeping the 7 newest. Exits non-zero on any failure. **Tested locally**: dump
  from the compose Postgres 16, restored into a scratch DB, table and row counts
  identical (`scripts/restore_db.md`).
  - The Dockerfile now installs `postgresql-client-17` from the PGDG apt repo.
    Debian's default client is older than Railway's Postgres, and pg_dump refuses
    to dump a newer server.
- **`py manage.py check_media_integrity [--fail]`**: lists every record
  (including the Trash) whose file is missing from storage. `--fail` exits 1, for
  cron or alerts.

### Scheduling the backup on Railway (cron service)

1. In the Railway project: **New → GitHub Repo → this repo** (a second
   service built from the same Dockerfile). Name it `phf-backup`.
2. Settings → **Cron Schedule**: `0 1 * * *` (01:00 UTC = 03:00 Juba time).
3. Settings → **Custom Start Command**: `python scripts/backup_db.py`
   (no web server; the container exits when the backup finishes).
4. Remove the health check and pre-deploy command for this service (the
   `railway.toml` values apply to the web service; override them in the
   service settings).
5. Variables: `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `SECRET_KEY`
   (any value; Django isn't started), and `AWS_ACCESS_KEY_ID`,
   `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`,
   `BACKUP_BUCKET_NAME` (a **private** bucket; a dedicated `phf-backups` bucket is ideal).
6. Trigger one run manually and confirm a `.dump` object appears. Then do
   a test restore following `scripts/restore_db.md`. A backup that has never been
   restored is not a backup.

---

## Phase 9 — Two-factor authentication for superadmins

### Design note (written before implementation)

- **Scope**: superusers only. They can create accounts, reveal wills, purge
  records and read every private file, so they are the account that most needs
  protecting. Role-scoped staff are unaffected.
- **Library**: `django-otp` with the TOTP plugin (authenticator apps such as
  Google Authenticator, Authy, 1Password) and the static plugin for one-time
  **recovery codes**. `OTPMiddleware` gives `request.user.is_verified()`.
- **Flow** (inside the existing `/dashboard/login/`, no Django admin):
  1. The password step runs through axes as before.
  2. If the superuser has a confirmed authenticator, they are **not** logged
     in yet. Only their user id and a timestamp go into the session ("2FA
     pending", valid 5 minutes), and they are sent to `/dashboard/login/verify/`.
  3. A valid 6-digit TOTP code or an unused recovery code completes the login
     (`login()` + `otp_login()`; the session key rotates). Five wrong codes end
     the pending state, so the password must be entered again (and that counts
     towards the axes lockout). django-otp also throttles TOTP attempts and
     rejects a code that was already used.
- **Enrolment**: `/dashboard/2fa/` shows a QR code (inline SVG, no external
  service, CSP-safe) and the base32 secret. The device is only confirmed once a
  correct code has been entered. Ten single-use recovery codes are then shown
  **once**, and can be regenerated later (POST, requires a verified session).
- **Enforcement**: `REQUIRE_SUPERADMIN_2FA=True` makes every superadmin page
  redirect to enrolment until the superuser has an authenticator, and requires a
  verified session afterwards. With the flag off, 2FA is optional, but once a
  superuser enrols, the second step is always required for them.
- **Lost device**: use a recovery code, or have someone with shell access
  run `py manage.py reset_2fa <username>` (removes that user's devices; logged).

### Implementation

Implemented as designed (`apps/dashboard/twofactor.py`): django-otp 1.7
(TOTP + static), routes `/dashboard/login/verify/`, `/dashboard/2fa/`,
`/dashboard/2fa/recovery-codes/` (POST) and `/dashboard/2fa/disable/` (POST, needs a
current code, refused when 2FA is required), sidebar link "Two-Factor Auth",
`py manage.py reset_2fa <username>`. The enrolment check also applies to the
private-media gate and to the (optional) Django admin. Tests cover: password alone
doesn't log in, valid code logs in, wrong codes capped at 5, a code can't be
replayed, recovery codes are single-use, the pending step expires, stale
unverified sessions are rejected, enrolment and the require flag, and staff roles
being unaffected.

**Rollout:** deploy with `REQUIRE_SUPERADMIN_2FA=False`. Each superadmin opens
*Two-Factor Auth* in the dashboard, enrols and saves their recovery codes. Then
set `REQUIRE_SUPERADMIN_2FA=True`.

---

## Phase 10 — Dependencies and CI

- **D17: Django 4.2 → 5.2 LTS (5.2.18).** Django 4.2 left security support in
  April 2026, and `pip-audit` reported 8 Django vulnerabilities fixed only in
  5.2.x/6.0.x. 5.2 LTS is supported until April 2028. The whole suite passed
  unchanged apart from test plumbing: `manage.py shell --no-imports` in
  subprocess tests, and two Django 6.0 deprecations cleaned up early
  (`CheckConstraint(condition=…)` and `FORMS_URLFIELD_ASSUME_HTTPS = True`).
  Plugins moved to their 5.2-compatible releases (crispy-forms 2.7,
  crispy-bootstrap5 2026.9, django-filter 26.2, django-mptt 0.20). **Exercise the
  dashboard forms manually once before deploying** (see the QA checklist).
- Also fixed by upgrading: Pillow 11.2.1 → 13.0.0 (41 advisories) and
  sqlparse 0.5.5 → 0.6.0 (5 advisories). After the upgrade, `pip-audit` reports
  **no known vulnerabilities** in `requirements.txt` or `requirements-dev.txt`
  (2026-10-22).
- `requirements.txt` pins **every** runtime package, transitive ones included
  (resolved in a clean venv). `requirements-dev.txt` adds pytest,
  pytest-django and pip-audit. Removed: `django-extensions` (not in
  `INSTALLED_APPS`, unused).
- `.github/workflows/ci.yml`: Postgres 16 service, Python 3.11 (same as the
  Dockerfile), then `makemigrations --check`, `migrate`, the full pytest suite,
  `check --deploy --fail-level WARNING` with production-like variables (**fails on
  any deploy warning**), `collectstatic` in production mode, and `pip-audit`.
- `.gitattributes` forces LF for `*.sh`, `Dockerfile`, `Procfile`, `*.toml`
  and `*.yml`, so a Windows checkout can't break the container entrypoint.
- The Docker image was built locally (PGDG `postgresql-client-17`, baked
  `collectstatic`).


---

## Phase 11 — Tests

The pytest-django suite (`tests/`, run with `py -m pytest`) has **320 tests**.
They're written alongside each phase and cover:

| Requirement | Where |
|---|---|
| Anonymous users redirected from every `/dashboard/` URL (GET and POST, all routes discovered from the URLconf) | `test_auth.py` |
| Role matrix: each role reaches only its sections; superadmin-only pages; only superadmin deletes / manages accounts; deactivated staff blocked mid-session | `test_auth.py` |
| Lockout after 5 failures (per username+IP; spoofed X-Forwarded-For can't dodge it; family login too) | `test_auth.py` |
| Uploads: renamed .exe/.php rejected, oversized and corrupt files rejected, valid files accepted, EXIF GPS stripped, random filenames | `test_uploads.py` |
| Contact details never public without consent; unpublished/private records 404; private media gate | `test_privacy.py` |
| Soft delete hides publicly, appears in Trash, restores; history rows carry the acting user | `test_integrity.py` |
| Parent/child cycle prevention (+ DB constraints, tree survives a corrupt loop) | `test_integrity.py` |
| Every dashboard page renders with data and empty | `test_dashboard_pages.py` |
| No template links to `/admin/`; every `{% url %}` resolves | `test_settings_and_templates.py` |
| `check --deploy` emits zero warnings with production env vars | `test_settings_and_templates.py` (and CI) |
| Rate limits, CSP, video embeds, robots/sitemap, error pages, social meta | `test_public_surface.py` |
| No N+1 queries, pagination, filters, caching, indexes | `test_performance.py` |
| Logging, Sentry config, backups, media integrity | `test_observability.py` |
| Superadmin 2FA | `test_twofactor.py` |
| Wills: encryption at rest, relatives-only viewing, deactivation, reveal | `test_wills.py` |

---

## Environment variables

| Variable | Purpose | Production value |
|---|---|---|
| `SECRET_KEY` | Django signing key. Required when `DEBUG=False` | **new random value (rotate!)** |
| `DEBUG` | Dev mode. Default `False` | `False` |
| `ALLOWED_HOSTS` | Comma-separated host names | your domain(s) |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated origins with scheme; wildcards OK | `https://your-domain,https://*.up.railway.app` |
| `RAILWAY_PUBLIC_DOMAIN` | Injected by Railway; auto-added to hosts/origins | (automatic) |
| `DATABASE_URL` | Postgres URL. Railway provides it | `${{Postgres.DATABASE_URL}}` |
| `DB_NAME` `DB_USER` `DB_PASSWORD` `DB_HOST` `DB_PORT` | Local fallback when `DATABASE_URL` is unset | (unset) |
| `ENABLE_DJANGO_ADMIN` | Mount the Django admin (superusers only) | `False` |
| `ADMIN_URL_PREFIX` | Admin path if enabled | an unguessable value |
| `SECURE_SSL_REDIRECT` `SECURE_HSTS_SECONDS` `SECURE_HSTS_PRELOAD` | HTTPS / HSTS tuning (prod only) | defaults |
| `TRUSTED_PROXY_COUNT` | Proxies appending to X-Forwarded-For | `1` (default in prod) |
| `AXES_ENABLED` | Brute-force lockout | `True` |
| `REQUIRE_SUPERADMIN_2FA` | Force superuser 2FA enrolment | `True` once enrolled |
| `AWS_STORAGE_BUCKET_NAME` | Public media bucket; enables S3 storage | e.g. `phf-media` |
| `AWS_PRIVATE_STORAGE_BUCKET_NAME` | Private media bucket | e.g. `phf-private` |
| `AWS_ACCESS_KEY_ID` `AWS_SECRET_ACCESS_KEY` | Bucket credentials | R2/B2 API token |
| `AWS_S3_ENDPOINT_URL` | S3 endpoint | `https://<acct>.r2.cloudflarestorage.com` |
| `AWS_S3_REGION_NAME` | Region | `auto` (R2) |
| `MEDIA_PUBLIC_BASE_URL` | Public URL of the public bucket (optional) | `https://media.your-domain` |
| `PRIVATE_MEDIA_URL_EXPIRE` | Signed-URL lifetime (s) for private files | `300` |
| `PRIVATE_MEDIA_ROOT` | Local private media dir (dev only) | (unset) |
| `REDIS_URL` | Shared cache for rate limits + home cache | `${{Redis.REDIS_URL}}` |
| `RATELIMIT_ENABLE` | Per-IP rate limits | `True` |
| `CSP_ENFORCE` / `CSP_REPORT_URI` | CSP mode / violation report endpoint | `False` / optional |
| `LOG_LEVEL` | `phf.*` logger level | `INFO` |
| `SENTRY_DSN` `SENTRY_ENVIRONMENT` `SENTRY_TRACES_SAMPLE_RATE` | Error monitoring | DSN / `production` / `0.1` |
| `RAILWAY_GIT_COMMIT_SHA` | Injected by Railway; Sentry release | (automatic) |
| `EMAIL_BACKEND` `DEFAULT_FROM_EMAIL` | Outgoing mail (not used yet) | defaults |
| `WEB_CONCURRENCY` `GUNICORN_THREADS` `GUNICORN_TIMEOUT` | Gunicorn sizing | `2` / `4` / `120` |
| `BACKUP_BUCKET_NAME` `BACKUP_PREFIX` `BACKUP_RETENTION_DAYS` `BACKUP_KEEP_MIN` | Backup cron service | private bucket / defaults |
| `PG_DUMP` | pg_dump command override (local testing) | (unset) |
| `RUN_MIGRATIONS` | Entrypoint runs migrate (docker-compose only) | (unset on Railway) |

---

## Railway deployment checklist

1. **Rotate `SECRET_KEY`** (a default was committed in git history). Generate one with
   `py -c "import secrets; print(secrets.token_urlsafe(64))"`. Rotating logs everyone out once.
2. **Builder**: `railway.toml` switches the service to the Dockerfile, with
   `preDeployCommand = migrate` and health check `/healthz`. Confirm in
   Service → Settings that no older Nixpacks start command overrides it.
3. **Variables** (web service): `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`,
   `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, bucket variables, `REDIS_URL`,
   `SENTRY_DSN`, `ENABLE_DJANGO_ADMIN=False`, `REQUIRE_SUPERADMIN_2FA=False` (for now).
4. **Buckets** (Cloudflare R2 recommended):
   - `phf-media`: public photos. Optional public access via a custom domain, then set `MEDIA_PUBLIC_BASE_URL`.
   - `phf-private`: **no public access**. Private media + database backups.
   - An API token limited to these buckets (Object Read & Write).
5. **Redis**: add Railway's Redis plugin and set `REDIS_URL=${{Redis.REDIS_URL}}`.
6. **Before the first deploy of this branch**, check production data won't fail
   the new constraint (genealogy 0007 stops and lists IDs if a death date precedes a birth date):
   `select id from genealogy_person where death_date < birth_date;`
   This deploy applies **34 project migrations** (7 from the baseline WIP + 27 from
   hardening) plus the axes and django-otp tables. All are additive except the
   self-parent cleanup described in Phase 6. **Take a backup first.**
7. Deploy. Then, from a Railway shell:
   `python manage.py move_private_media`, `python manage.py check_media_integrity`,
   optionally `python manage.py populate_history --auto`.
8. Media uploaded before this deploy probably lived on Railway's ephemeral disk
   and is already gone. `check_media_integrity` lists what to re-upload.
9. Every superadmin: Dashboard → **Two-Factor Auth** → enrol, save recovery codes.
   Then set `REQUIRE_SUPERADMIN_2FA=True`.
10. **Backup cron service**: see Phase 8. Trigger one run, then do a test restore.
11. **Domain**: add the custom domain in Railway, update `ALLOWED_HOSTS` /
    `CSRF_TRUSTED_ORIGINS`. HSTS (1 year, includeSubDomains, preload flag) is
    sent automatically. Only submit to hstspreload.org if every subdomain is HTTPS.
12. Watch Sentry and the `phf.security` logs for a few days. Collect CSP
    reports before switching `CSP_ENFORCE=True`.

---

## Manual QA checklist

- [ ] Public: home, about, every list (search, filters, pagination page 2), every detail page, family tree (change generations), search with 1 character and with a normal term.
- [ ] Unpublished clan/person/news URL → 404 page in PHF style. Unknown URL → 404.
- [ ] Person with "show contact publicly" ticked shows phone/email/address. Unticked shows nothing. A private living person is invisible everywhere.
- [ ] Elder interview with audio: plays publicly once published, not before.
- [ ] YouTube watch URL pasted into a news post plays as an embed. A non-YouTube URL is refused by the form.
- [ ] Dashboard login: wrong password shows an error. 5 wrong attempts → lockout page. Logout works.
- [ ] Each role account: sees and edits only its sections. Delete buttons are superadmin-only.
- [ ] Add and edit a clan and a person **with media uploads** (Django 5.2 form check). Photo EXIF is stripped (download and inspect).
- [ ] Upload a renamed .exe as a photo → friendly error.
- [ ] Person father/mother loop or death-before-birth → field errors.
- [ ] Delete → record in Trash → Restore → back. Delete permanently → gone (and blocked for a person with a will account).
- [ ] Activity Log shows the above with your name. Filters work.
- [ ] Superadmin 2FA: enrol, sign out, sign in with code. Sign in with a recovery code.
- [ ] Profile PDF link from the dashboard opens (signed URL on S3). The same link logged out → 404.
- [ ] Family (will) account: first login forces password change; write a will; superadmin reveals; a relative reads it with the passphrase; a non-relative can't.
- [ ] `/robots.txt`, `/sitemap.xml`, `/healthz`.
- [ ] Response headers on any page: HSTS, `X-Frame-Options: DENY`, `Content-Security-Policy-Report-Only`.

---

## Skipped / deferred, and why

| Item | Why / what to do |
|---|---|
| **CSP enforcing mode** | Inline scripts, ~260 `style=` attributes and inline handlers would break. Inventory in Phase 5. Collect reports first. |
| ClanBoma, PersonEducation, PersonCareer, Announcement, SiteStats editing in the dashboard | Only editable via the Django admin (D9). Add inline formsets to the clan/person forms, or temporarily enable the admin behind a secret prefix. |
| Direct-to-bucket (presigned) uploads for large audio/video | Uploads up to 500 MB still go through gunicorn. Prefer YouTube/Vimeo for long videos. |
| Deleting the previous file when an upload is *replaced* | Old files are kept (history may reference them). Only permanent deletes remove files. |
| Media files from before this deploy | Likely lost to Railway's ephemeral disk. Re-upload using `check_media_integrity`. |
| Initial history rows | Run `populate_history --auto` if a baseline "created" entry is wanted. |
| Rate limits without Redis | Per gunicorn worker. Add Railway Redis. |
| `FORMS_URLFIELD_ASSUME_HTTPS` | Transitional setting (one deprecation warning). Delete it when moving to Django 6.x (before April 2028, when 5.2 LTS ends). |
| Email-based password reset | No mail provider configured. Superadmin resets staff/family passwords in the dashboard. |
| Antivirus scanning of uploads | Content-type verification + re-encoding of images is done, but there's no AV engine (ClamAV would need its own service). |
| Local tests run on Python 3.12 | Only interpreter installed here. CI and the Docker image use 3.11. |
