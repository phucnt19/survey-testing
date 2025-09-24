
# Flask Survey (Postgres)

Production-friendly version using PostgreSQL on Render.

## Features
- Multi-page respondent flow with CSRF + step gating
- Admin login via env (`ADMIN_USER`, `ADMIN_PASS`)
- PostgreSQL storage via SQLAlchemy (`DATABASE_URL`)
- Admin dashboard with aggregates + last 10
- Admin-only CSV export (`/admin/export`)

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
export ADMIN_USER=admin
export ADMIN_PASS=supersecret
export SECRET_KEY="random-string"

python app.py  # http://localhost:8000
```

## Deploy on Render

1. Create a **PostgreSQL** instance on Render → copy the `External Database URL`.
2. Create a **Web Service** from this repo.
3. Set environment variables:
   - `DATABASE_URL` = (from step 1)
   - `ADMIN_USER`, `ADMIN_PASS`
   - `SECRET_KEY` = a long random string
4. Build: `pip install -r requirements.txt`
5. Start: `python app.py`

Tables will auto-create on first boot.
