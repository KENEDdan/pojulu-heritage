# 🌿 Pojulu Heritage Foundation — Django Web Platform

**Preserving Our Roots, Empowering Our Future.**

A full-stack Django web application for the Pojulu Heritage Foundation — a digital archive preserving the history, genealogy, culture, and legacy of the Pojulu people of Central Equatoria State, South Sudan.

---

## ✨ What's Inside

| Module | Description |
|---|---|
| **Clans** | Clan histories, chiefs/elders, territorial history, cultural practices |
| **Families & Genealogy** | Family trees, person profiles, parent-child relationships |
| **Memorial** | In Memoriam records honouring those who have passed |
| **Achievements** | Notable achievements across leadership, education, culture, sport |
| **Marriages** | Marriage and lineage registry, inter-clan connections |
| **Cultural Archive** | Songs, proverbs, ceremonies, stories, folklore, oral literature |
| **Elder Interviews** | Audio/video/transcript oral history archive |
| **Community Submissions** | Moderated submission workflow for community contributions |
| **Search** | Full-text search across all records |

---

## 🛠️ Tech Stack

- **Django 4.2** — Backend framework
- **PostgreSQL** — Primary database
- **Bootstrap 5** — Responsive UI framework
- **Whitenoise** — Static file serving
- **Pillow** — Image handling
- **django-crispy-forms** — Form rendering
- **python-decouple** — Environment variable management
- **Cormorant Garamond + DM Sans** — Typography

---

## 🚀 Setup (Windows — PowerShell)

### 1. Clone or extract the project

```powershell
cd C:\Users\User\projects
# Extract pojulu_heritage folder here
cd pojulu_heritage
```

### 2. Create and activate virtual environment

```powershell
py -3.11 -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create the `.env` file

Create a file named `.env` in the project root (same folder as `manage.py`):

```ini
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=pojulu_heritage
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
```

### 5. Create the PostgreSQL database

```sql
-- In psql or pgAdmin:
CREATE DATABASE pojulu_heritage;
```

### 6. Run migrations

```powershell
py manage.py migrate
```

### 7. Create a superuser (admin account)

```powershell
py manage.py createsuperuser
```

### 8. Load sample data (optional)

```powershell
py manage.py loaddata initial_data.json
```

### 9. Run the development server

```powershell
py manage.py runserver
```

Visit: **http://127.0.0.1:8000**
Admin: **http://127.0.0.1:8000/admin**

---

## 📁 Project Structure

```
pojulu_heritage/
├── manage.py
├── requirements.txt
├── .env                    ← Create this (not in version control)
├── pojulu_heritage/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── core/               ← Home, Search, About, Site Stats
│   ├── clans/              ← Clan histories and chiefs
│   ├── genealogy/          ← Persons and family trees
│   ├── memorial/           ← In Memoriam records
│   ├── achievements/       ← Achievement records
│   ├── marriages/          ← Marriage and lineage registry
│   ├── cultural/           ← Songs, proverbs, ceremonies
│   ├── elders/             ← Elder oral history interviews
│   └── submissions/        ← Community submission workflow
├── templates/              ← All HTML templates
│   ├── base.html           ← Master layout
│   ├── core/
│   ├── clans/
│   ├── genealogy/
│   ├── memorial/
│   ├── achievements/
│   ├── marriages/
│   ├── cultural/
│   ├── elders/
│   ├── submissions/
│   └── partials/           ← Reusable template fragments
├── static/
│   ├── css/pojulu.css      ← Complete design system
│   └── js/pojulu.js        ← Animations and interactions
└── media/                  ← User-uploaded files (photos, audio, docs)
```

---

## ⚙️ Admin Panel

The Django admin is fully configured for all models. Log in at `/admin/` with your superuser credentials.

**Key admin features:**
- Verify/feature clans, persons, and records before they appear publicly
- Review and approve community submissions (with status workflow)
- Manage elder interviews (mark as published when ready)
- Inline editing of clan chiefs and historical events

**Approval workflow for submissions:**
1. Community member submits via `/submit/`
2. Record appears in Admin → Community Submissions with status `Pending`
3. Reviewer changes status to `Approved` → record goes live
4. Optionally mark `Needs More Info` and contact submitter

---

## 🌐 Key URLs

| URL | Page |
|---|---|
| `/` | Home (hero, stats, featured clans) |
| `/clans/` | Clan directory |
| `/clans/<slug>/` | Clan detail page |
| `/families/` | Family records |
| `/families/family/<slug>/` | Family detail |
| `/families/person/<slug>/` | Person profile |
| `/families/person/<slug>/tree/` | Family tree view |
| `/memorial/` | In Memoriam |
| `/achievements/` | Achievement records |
| `/marriages/` | Marriage registry |
| `/culture/` | Cultural archive |
| `/elders/` | Elder interviews |
| `/submit/` | Community submission form |
| `/search/?q=...` | Search all records |
| `/about/` | About the Foundation |
| `/admin/` | Admin panel |

---

## 🚢 Deployment (Railway.app)

```powershell
# Install Railway CLI, then:
railway login
railway init
railway add postgresql
railway up
```

Set these environment variables in Railway dashboard:
```
SECRET_KEY=<generate a strong key>
DEBUG=False
ALLOWED_HOSTS=<your-railway-domain>.railway.app
DB_NAME=railway
DB_USER=postgres
DB_PASSWORD=<railway provides this>
DB_HOST=<railway postgres host>
DB_PORT=5432
```

---

## 🎨 Design System

Colors are defined as CSS variables in `static/css/pojulu.css`:

| Variable | Value | Usage |
|---|---|---|
| `--g900` | `#1B5E20` | Navigation, dark backgrounds |
| `--g700` | `#2E7D32` | Primary green, card headers |
| `--g500` | `#43A047` | Accents, badges |
| `--g100` | `#E8F5E9` | Light backgrounds |
| `--white` | `#FFFFFF` | Page background |

Typography: **Cormorant Garamond** (display/headings) + **DM Sans** (body text)

---

## 📞 Contact

**Pojulu Heritage Foundation**
Email: pojuluheritage@gmail.com
Website: www.pojuluheritage.org
Location: Juba, Central Equatoria, South Sudan

---

*"Together, let us build the house where Pojulu memory lives forever."*
