
# Flask Survey (Admin & Secure Export)

What you get:
- Multi-page respondent flow with CSRF + step gating.
- **Admin login** (`/admin/login`) using env `ADMIN_USER`, `ADMIN_PASS`.
- **Admin dashboard** (`/admin`) with key stats + last 10 responses.
- **Admin-only export** (`/admin/export`) — respondents cannot download data.
- Public UI hides any export link.

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_USER=admin
export ADMIN_PASS=supersecret
export SECRET_KEY='random-string'
python app.py  # http://localhost:8000
```

Windows (CMD):
```
set ADMIN_USER=admin
set ADMIN_PASS=supersecret
set SECRET_KEY=random-string
python app.py
```

## Deploy (Render)
- Build: `pip install -r requirements.txt`
- Start: `python app.py`
- Set env: `ADMIN_USER`, `ADMIN_PASS`, `SECRET_KEY`

## Notes
- Consider HTTPS and stronger auth (e.g., session expiry, password hashing) for production.
- For big samples, switch CSV to a database (Postgres) and paginate the dashboard.
