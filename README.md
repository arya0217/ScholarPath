# ScholarPath

Scholarship matching MVP based on the supplied Master Design & Development Guide.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

Student accounts are created from the Register tab. The seeded admin login is:
- username: `admin`
- password: `admin123`

Set `ADMIN_PASSWORD` before first run if you want a different seeded admin password. Set `SECRET_KEY` in production.

## Included

- Session auth with hashed passwords and CSRF protection
- Student profile + completion progress
- Inverted-index + AST scholarship matching
- Explainability on dashboard/detail pages
- Save / apply / application status
- Admin dashboard and scholarship CRUD/verification
- SQLite by default; `DATABASE_URL` can point to PostgreSQL
- JSON scholarship/matching endpoints

The async Celery/Redis pipeline from the guide is intentionally not required for the MVP's default run; it can be layered on after the synchronous path is validated.

## Major Project Feature — Smart Application Assistant

The major-project layer extends the existing eligibility matcher with a decision workflow:

- Priority score using eligibility strength, scholarship amount, deadline urgency, and document readiness
- Student document vault with PDF/JPG/PNG uploads
- Scholarship-specific required-document definitions
- Application readiness percentage and missing-document detection
- Personalized application roadmap
- Decision API at `/api/decision/<student_id>`

The existing matching engine remains the eligibility foundation; this feature operates on top of its eligible scholarship set.
