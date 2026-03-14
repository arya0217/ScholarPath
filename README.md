# ScholarPath

> **Find scholarships you actually qualify for.**

Most scholarship platforms list hundreds of opportunities and leave students to figure out eligibility themselves. ScholarPath flips that — a student fills their profile once, and the system automatically matches them to scholarships they are eligible for.

Built as a minor project to address scholarship awareness among underprivileged students in India.

---

## The Problem

Many underprivileged students are unaware that scholarships exist for them. Platforms like Buddy4study list scholarships generically — students have to manually browse and check eligibility. The process is overwhelming, especially for first-generation college students.

## Our Solution

A personalized matching platform. Fill your profile (caste, income, marks, state, gender, stream) once — see only the scholarships you qualify for. No browsing, no guessing.

---

## How It Works

```
Student fills profile
        ↓
Phase 1 — Inverted Index
Scholarships indexed by criteria.
Student profile queries index → shortlist of ~8 candidates from 600.
        ↓
Phase 2 — AST Evaluator
Eligibility rules stored as expression trees.
AND/OR logic evaluated precisely per candidate.
        ↓
Dashboard shows only matching scholarships
```

This two-phase pipeline reduces matching from O(students × scholarships) to O(students × ~8).

---

## Features

- **Personalized matching** — eligibility checked automatically against your profile
- **Real scholarship data** — 20+ verified Indian scholarships seeded (NSP, AICTE, state schemes, private foundations)
- **Two-phase matching engine** — inverted index + AST evaluator
- **Application tracking** — save and track your applications
- **Clean dashboard** — total funding available, verified count, apply links

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python + Flask | Minimal setup, fast to run |
| Database | SQLite | Zero configuration for MVP |
| Frontend | HTML + CSS + JS | Simple, no build step needed |
| Matching Engine | Custom (Inverted Index + AST) | Core contribution of this project |
| Data | BeautifulSoup + manual curation | Real Indian scholarship data |

### Proposed Production Stack (Major Project Extension)
```
Flask      →  Django         Production-grade framework
SQLite     →  PostgreSQL     Scalable relational database  
-          →  Redis          Caching match results
-          →  Celery         Async job queue for matching
Local      →  Railway/Render Cloud deployment
```

---

## Project Structure

```
ScholarPath/
│
├── app.py              # Main application — all routes, models, matching engine
├── scholarpath.db      # SQLite database (auto-created on first run)
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## Installation & Setup

### Prerequisites

Make sure you have the following installed:

- Python 3.10 or above
- pip (comes with Python)

Check your versions:
```bash
python --version
pip --version
```

---

### Step 1 — Clone the repository

```bash
git clone https://github.com/yourusername/ScholarPath.git
cd ScholarPath
```

Or if you downloaded the ZIP — extract it and open the folder in terminal:

```bash
cd path/to/ScholarPath
```

---

### Step 2 — Install dependencies

```bash
pip install flask flask-sqlalchemy
```

Or using the requirements file:

```bash
pip install -r requirements.txt
```

---

### Step 3 — Run the app

```bash
python app.py
```

You should see:

```
ScholarPath is running!
Open: http://127.0.0.1:5000
```

---

### Step 4 — Open in browser

Go to:
```
http://127.0.0.1:5000
```

The database is created automatically on first run. 20+ real scholarships are seeded automatically — no manual setup needed.

---

## Using the App

### 1. Register
Create an account with your name, email, and password.

### 2. Fill your profile
Enter your eligibility details:
- Caste category (SC / ST / OBC / General)
- Annual family income
- Marks / percentage
- State
- Gender
- Stream (Engineering, Science, Arts, etc.)
- Area (Rural / Urban)
- Disability status

### 3. View your matches
The dashboard shows:
- All scholarships you are eligible for
- Total potential funding amount
- Verified vs unverified scholarships
- Direct apply links for each scholarship

---

## Scholarship Data

The following real Indian scholarships are seeded:

| Scholarship | Provider | Amount |
|-------------|---------|--------|
| Post Matric Scholarship (SC) | Ministry of Social Justice | ₹12,000 |
| Post Matric Scholarship (ST) | Ministry of Tribal Affairs | ₹12,000 |
| Central Sector Scheme | Ministry of Education | ₹10,000 |
| Pragati Scholarship (Girls, Technical) | AICTE | ₹50,000 |
| Saksham Scholarship (Differently Abled) | AICTE | ₹50,000 |
| Begum Hazrat Mahal Scholarship | Maulana Azad Education Foundation | ₹12,000 |
| Maharashtra Post Matric (OBC) | Social Welfare Dept, Maharashtra | ₹15,000 |
| Ishan Uday Scholarship (NE Students) | UGC | ₹54,000 |
| Inspire Scholarship | DST, Govt. of India | ₹80,000 |
| Vidyasaarathi Scholarship | NSDL e-Governance | ₹40,000 |
| NSP Pre-Matric (Minorities) | Ministry of Minority Affairs | ₹10,000 |
| Tata Capital Pankh Scholarship | Tata Capital | ₹12,000 |
| Sitaram Jindal Foundation Scholarship | Sitaram Jindal Foundation | ₹24,000 |
| L'Oreal For Young Women in Science | L'Oreal India | ₹2,50,000 |
| Reliance Foundation UG Scholarship | Reliance Foundation | ₹2,00,000 |
| Dr. Ambedkar Post Matric (SC/ST) | Govt. of Karnataka | ₹18,000 |
| Swami Vivekananda Merit-cum-Means | Govt. of West Bengal | ₹60,000 |
| Bihar Post Matric (BC/EBC) | BC/EBC Welfare Dept, Bihar | ₹15,000 |
| Uttarakhand Post Matric (SC) | Social Welfare Dept, Uttarakhand | ₹10,000 |
| HDFC Badhte Kadam Scholarship | HDFC Bank Parivartan | ₹18,000 |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/` | Login / Register page |
| POST | `/login` | Student login |
| POST | `/register` | Student registration |
| GET | `/profile` | View profile form |
| POST | `/profile` | Save profile |
| GET | `/dashboard` | View matched scholarships |
| GET | `/logout` | Logout |
| GET | `/api/matches/<student_id>` | JSON — matched scholarships for a student |
| GET | `/api/scholarships` | JSON — all scholarships in database |

---

## Matching Engine — Technical Details

### Phase 1 — Inverted Index (Pre-filter)

Scholarships are indexed by their primary eligibility criteria. When a student's profile is submitted, the system queries only relevant index keys:

```python
# Example: Student with caste=SC, income=180000
# Index lookup returns only SC-eligible scholarships
# Eliminates majority of 600 scholarships instantly
shortlist = build_inverted_index(student)
```

### Phase 2 — AST Evaluator (Precise matching)

Each scholarship's eligibility rule is evaluated as an expression tree. All conditions use AND logic — every criterion must be satisfied:

```python
# Example rule evaluation
AND
├── Caste ∈ {SC, ST}      ✅
├── Income ≤ 250000        ✅
├── Gender = Any           ✅
└── State = Any            ✅
→ MATCH
```

```python
is_match, breakdown = evaluate_ast(scholarship, student)
```

---

## Future Scope (Major Project — 7th Semester)

- **Easy Apply** — LinkedIn-style pre-fill using saved profile data
- **Foundation self-listing portal** — NGOs and trusts list scholarships directly
- **Async matching pipeline** — Celery + Redis for background job processing
- **Primary-Replica DB** — PostgreSQL replication for read-heavy load
- **Mobile app** — React Native
- **ML-based recommendations** — collaborative filtering for scholarship suggestions
- **Multilingual support** — Hindi and regional languages
- **Cloud deployment** — Railway / Render / AWS

---

## Team

| Role | Responsibility |
|------|---------------|
| Person 1 — Lead + Backend | Architecture, matching engine, APIs, deployment |
| Person 2 — Frontend | UI screens, profile form, dashboard |
| Person 3 — Data | Scholarship scraping, seed data, DB setup |
| Person 4 — Product + Testing | Test personas, bug reports, presentation |

---

## License

This project is built for academic purposes as a minor project submission.

---

## Acknowledgements

- [National Scholarship Portal](https://scholarships.gov.in) — scholarship data reference
- [AICTE](https://www.aicte-india.org) — Pragati and Saksham scholarship data
- All foundations and government bodies whose scholarship data is referenced in this project
