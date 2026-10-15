# Matrimony Platform

Foundation for a professional matrimonial platform: public website, member portal, admin panel,
telemarketing/CRM interface and a central REST API shared with future Android and iOS apps.

| Layer | Stack |
|-------|-------|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, ESLint, Zod, React Hook Form |
| Backend | Python 3.11+, Django 5.2 LTS, Django REST Framework, SimpleJWT, drf-spectacular |
| Database | MySQL 8.x (8.4 LTS recommended) |

Design documents: [architecture](docs/architecture.md) · [database design](docs/database-design.md) ·
[API specification](docs/api-specification.md)

> **Status:** project foundation only. Health checks, the custom user model with roles, JWT
> endpoints and a placeholder website are in place. Business modules (profiles, search,
> memberships, payments, CRM, …) are not implemented yet.

---

## 1. Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11, 3.12 or 3.13 (Django 5.2 supports 3.10–3.13) | `python --version` |
| Node.js | 20.9+ (tested with 24.10) | `node -v` |
| npm | 10+ (tested with 11.6) | `npm -v` |
| MySQL Server | 8.0.11+ (8.4 LTS recommended) **or** Docker Desktop | `mysql --version` / `docker --version` |
| Git | any recent version | `git --version` |

On Linux/macOS, `mysqlclient` compiles from source and needs the MySQL client headers and
`pkg-config` (see [Common errors](#14-common-installation-errors-and-fixes)). On Windows a prebuilt
wheel is installed automatically.

## 2. Project directory structure

```
matrimony-platform/
├── backend/                     Django REST API
│   ├── config/                  project config (settings/, urls, api_v1 routes, env loading)
│   │   └── settings/            base · development · production · test
│   ├── apps/
│   │   ├── core/                health checks, shared base models, error handling
│   │   ├── accounts/            custom User model, roles, permissions, JWT endpoints
│   │   ├── profiles/  memberships/  payments/  interactions/  notifications/
│   │   └── enquiries/  crm/  website_content/  audit/      (registered, not yet implemented)
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
├── frontend/                    Next.js website and future portals
│   ├── app/                     routes: (public) group, status page, error/404, robots, sitemap
│   ├── components/              layout (header, footer) and ui primitives
│   ├── features/                feature modules (system-status so far)
│   ├── lib/                     config validation, API client, utilities
│   ├── types/                   shared API types
│   └── .env.example
├── docs/                        architecture, database design, API specification
├── docker/mysql/init/           first-run MySQL init script (test DB privileges)
├── docker-compose.yml           local MySQL server
├── .gitignore
└── README.md
```

## 3. Frontend installation

```bash
cd frontend
npm install
```

## 4. Backend virtual environment

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows (Git Bash): `source .venv/Scripts/activate`

Linux / macOS:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

All backend commands below assume the virtual environment is active and you are in `backend/`.

## 5. Python dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 6. MySQL database creation  ⚠️ manual step

You need a MySQL server and a dedicated database user. Choose **one** option.
Pick your own strong password; it goes only into `backend/.env`.

### Option A — Docker (recommended if you have Docker Desktop)

1. Create `backend/.env` (step 7) and set `DB_NAME`, `DB_USER`, `DB_PASSWORD` and
   `MYSQL_ROOT_PASSWORD`.
2. From the project root:

   ```bash
   docker compose --env-file backend/.env up -d mysql
   docker compose --env-file backend/.env ps     # wait for "healthy"
   ```

The container creates the database and user from those variables, and grants the user access to
the `test_<DB_NAME>` database used by the test runner. Data persists in the `mysql_data` volume.
`docker compose down` keeps data; **`docker compose down -v` deletes it permanently.**

### Option B — Existing / locally installed MySQL Server

Install MySQL Server 8.4 LTS (Windows: MySQL Installer from dev.mysql.com; macOS: `brew install mysql`;
Ubuntu: `sudo apt install mysql-server`). Then, as an administrative user:

```bash
mysql -u root -p
```

```sql
CREATE DATABASE IF NOT EXISTS matrimony_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'matrimony_user'@'localhost' IDENTIFIED BY 'choose-a-strong-password';
GRANT ALL PRIVILEGES ON matrimony_db.* TO 'matrimony_user'@'localhost';

-- Allows `manage.py test` to create and drop its separate test database:
GRANT ALL PRIVILEGES ON test_matrimony_db.* TO 'matrimony_user'@'localhost';
FLUSH PRIVILEGES;
```

`CREATE DATABASE IF NOT EXISTS` never touches an existing database. If you already have a database
you want to use, skip creation and only create/grant the user.

## 7. Environment variables  ⚠️ manual step

### Backend

```bash
cd backend
cp .env.example .env          # PowerShell: Copy-Item .env.example .env
```

Edit `backend/.env`:

| Variable | Required | Notes |
|----------|----------|-------|
| `DJANGO_SECRET_KEY` | yes | Generate: `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD` | yes | Must match step 6 |
| `DB_HOST`, `DB_PORT` | no | Default `127.0.0.1`, `3306` |
| `MYSQL_ROOT_PASSWORD` | Docker only | Root password for the MySQL container |
| `DJANGO_ALLOWED_HOSTS` | production | Comma-separated host names |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | production | Exact frontend origins, `https://` in production |
| others | no | Documented inline in `.env.example` |

The app refuses to start if a required variable is missing and names the variable.

> A `backend/.env` was already created during setup with a freshly generated secret key.
> `DB_PASSWORD` and `MYSQL_ROOT_PASSWORD` are intentionally **blank**: fill them in.

### Frontend

```bash
cd frontend
cp .env.example .env.local    # PowerShell: Copy-Item .env.example .env.local
```

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | Required. Embedded in the browser bundle at build time |
| `NEXT_PUBLIC_SITE_URL` | `http://localhost:3000` | Canonical URL for metadata and sitemap |
| `NEXT_PUBLIC_SITE_NAME` | `Maasil Matrimony` | Display name |
| `API_INTERNAL_BASE_URL` | unset | Optional server-only API URL |

Never put secrets in `NEXT_PUBLIC_*` variables.

## 8. Django migrations

```bash
cd backend
python manage.py migrate
```

When you change models later:

```bash
python manage.py makemigrations
python manage.py migrate
```

The custom user model (`accounts.User`) is part of the initial migration. Do not switch
`AUTH_USER_MODEL` after migrating a database.

## 9. Create a superuser

```bash
python manage.py createsuperuser
```

You will be asked for an email and password. The account gets role `super_admin`. No default or
hardcoded admin account exists.

## 10. Start the backend

```bash
cd backend
python manage.py runserver
```

## 11. Start the frontend

```bash
cd frontend
npm run dev
```

Production build check: `npm run build && npm run start`.

## 12. Local URLs

| URL | What |
|-----|------|
| http://localhost:3000 | Website (home page) |
| http://localhost:3000/status | Live frontend → API connectivity check |
| http://127.0.0.1:8000/api/v1/health/ | API liveness check |
| http://127.0.0.1:8000/api/v1/health/ready/ | API readiness check (includes database) |
| http://127.0.0.1:8000/api/v1/docs/ | Swagger UI (development) |
| http://127.0.0.1:8000/api/v1/schema/ | OpenAPI schema |
| http://127.0.0.1:8000/admin/ | Django admin (sign in with the superuser) |

## 13. Running tests and checks

### Backend

Against MySQL (default; needs step 6 including the `test_` grant). Django creates and destroys a
separate `test_<DB_NAME>` database and never touches your development data:

```bash
cd backend
python manage.py test --settings=config.settings.test
```

Without a MySQL server (quick local check on a throwaway in-memory SQLite database):

```bash
# bash
TEST_DATABASE=sqlite python manage.py test --settings=config.settings.test
# PowerShell
$env:TEST_DATABASE="sqlite"; python manage.py test --settings=config.settings.test; Remove-Item Env:TEST_DATABASE
```

Other checks:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run    # fails if a migration is missing
```

Production configuration check (with production env vars set):

```bash
python manage.py check --deploy --settings=config.settings.production
```

### Frontend

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

## 14. Common installation errors and fixes

| Error | Fix |
|-------|-----|
| `ImproperlyConfigured: Environment variable DB_PASSWORD is required` (or another name) | Create/complete `backend/.env` (step 7). |
| `django.db.utils.OperationalError: (2003, "Can't connect to MySQL server on '127.0.0.1' (10061)")` | MySQL is not running or listens on another port. Start the service (Windows: `services.msc` → MySQL84; Docker: `docker compose --env-file backend/.env up -d mysql`) and check `DB_PORT`. |
| `(1045, "Access denied for user 'matrimony_user'@'localhost'")` | Wrong password or user/host mismatch. Re-run the `CREATE USER`/`GRANT` statements; if connecting via `127.0.0.1` still fails, also create the user for `'127.0.0.1'`. |
| `(1049, "Unknown database 'matrimony_db'")` | Create the database (step 6) or fix `DB_NAME`. |
| `Got an error creating the test database: (1044, "Access denied …")` | Grant the user privileges on `test_<DB_NAME>.*` (step 6). |
| `pip install mysqlclient` fails with `pkg-config` / `mysql_config not found` (Linux/macOS) | Ubuntu/Debian: `sudo apt install python3-dev default-libmysqlclient-dev build-essential pkg-config`. macOS: `brew install mysql pkg-config`. |
| `pip install mysqlclient` tries to compile on Windows | Your Python version has no wheel: use 64-bit Python 3.11–3.13. |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use `.venv\Scripts\activate.bat` from cmd. |
| `Invalid frontend configuration … NEXT_PUBLIC_API_BASE_URL` | Create `frontend/.env.local` (step 7) and restart `npm run dev`. |
| Browser console: `blocked by CORS policy` | Add the exact frontend origin (scheme + host + port) to `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` in `backend/.env`, then restart Django. |
| Changed `NEXT_PUBLIC_*` but nothing changed | These are inlined at build time: restart `npm run dev`, or rebuild for production. |
| `Error: listen EADDRINUSE :::3000` / `port 8000 is already in use` | Stop the other process or use `npm run dev -- -p 3001` / `python manage.py runserver 8001` (and update the env URLs/origins). |
| `/status` page shows "Unavailable" | Start the backend and check `NEXT_PUBLIC_API_BASE_URL`. |
| `npm audit` reports high-severity `braces` issues | Comes from ESLint tooling (dev-only, not shipped). Do **not** run `npm audit fix --force`; it downgrades Next.js. Update `eslint-config-next` when a fixed release ships. |

## 15. Preparing the project for Git

The repository is **not** initialised yet.

```bash
cd matrimony-platform
git init
git status
```

Before the first commit, confirm none of these appear in `git status`:
`backend/.env`, `frontend/.env.local`, `backend/.venv/`, `frontend/node_modules/`, `frontend/.next/`,
`backend/media/`, `__pycache__/`. They are excluded by `.gitignore`; `.env.example` files are
intentionally committed.

```bash
git add .
git commit -m "Initial project foundation"
git branch -M main
git remote add origin <your-repository-url>
git push -u origin main
```

`frontend/AGENTS.md` is generated by Next.js for AI coding tools and can be committed.

## Dependency versions

**Backend** (`backend/requirements.txt`, pinned)

| Package | Version |
|---------|---------|
| Django | 5.2.18 (LTS, supported until April 2028) |
| djangorestframework | 3.18.3 |
| djangorestframework-simplejwt | 5.5.1 |
| django-cors-headers | 4.9.0 |
| django-environ | 0.14.0 |
| drf-spectacular | 0.30.0 |
| mysqlclient | 2.3.0 |
| gunicorn (Linux production only) | 26.2.0 |

**Frontend** (`frontend/package.json`; exact versions locked in `package-lock.json`)

| Package | Version |
|---------|---------|
| next | 16.4.0 |
| react / react-dom | 19.3.0 |
| typescript | 5.9.3 |
| tailwindcss | 4.3.3 |
| eslint / eslint-config-next | 9.39.5 / 16.4.0 |
| zod | 4.6.7 |
| react-hook-form | 7.90.0 |
| @hookform/resolvers | 5.9.1 |

## Manual configuration summary

| Step | Who | Why |
|------|-----|-----|
| Install MySQL or Docker | You | Neither is installed on this machine yet |
| Create database + user, set `DB_PASSWORD` | You | Credentials must not be invented or committed |
| `python manage.py migrate` | You | Needs a running MySQL |
| `python manage.py createsuperuser` | You | No default admin account exists |
| Production env vars (hosts, origins, secrets, HTTPS) | You | Environment-specific |
| SMS/OTP provider, payment gateway credentials | Later | Not integrated yet |
