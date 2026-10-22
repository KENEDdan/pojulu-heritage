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
