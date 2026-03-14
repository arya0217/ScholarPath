from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scholarpath.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'scholarpath-secret'
db = SQLAlchemy(app)

# ── MODELS ──────────────────────────────────────────────

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    caste = db.Column(db.String(20))
    income = db.Column(db.Integer)
    marks = db.Column(db.Float)
    state = db.Column(db.String(50))
    gender = db.Column(db.String(10))
    stream = db.Column(db.String(50))
    disability = db.Column(db.Boolean, default=False)
    area = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Scholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    provider = db.Column(db.String(200))
    amount = db.Column(db.Integer)
    deadline = db.Column(db.String(20))
    apply_url = db.Column(db.String(300))
    is_verified = db.Column(db.Boolean, default=False)
    # Eligibility criteria stored as JSON
    allowed_caste = db.Column(db.String(200))       # comma-separated e.g. "SC,ST,OBC"
    max_income = db.Column(db.Integer)               # e.g. 250000
    min_marks = db.Column(db.Float)                  # e.g. 75.0
    allowed_states = db.Column(db.String(500))       # comma-separated
    allowed_gender = db.Column(db.String(10))        # "Male","Female","Any"
    allowed_stream = db.Column(db.String(200))       # comma-separated
    disability_required = db.Column(db.Boolean)      # None=not required, True=required
    allowed_area = db.Column(db.String(10))          # "Rural","Urban","Any"

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'))
    current_status = db.Column(db.String(20), default='SAVED')
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── MATCHING ENGINE ──────────────────────────────────────
# Two-phase matching:
# Phase 1 - Inverted index simulation using SQL indexed queries
# Phase 2 - AST-style rule evaluation per candidate

def build_inverted_index(student):
    """Phase 1: Build candidate set using indexed queries"""
    candidates = Scholarship.query.all()
    shortlist = []
    for s in candidates:
        # Quick pre-filter: check primary criteria first
        if s.allowed_caste and student.caste:
            allowed = [c.strip() for c in s.allowed_caste.split(',')]
            if student.caste not in allowed and 'Any' not in allowed:
                continue
        if s.max_income and student.income:
            if student.income > s.max_income:
                continue
        shortlist.append(s)
    return shortlist

def evaluate_ast(scholarship, student):
    """Phase 2: Precise rule evaluation (AST-style) on shortlisted candidates"""
    results = {}

    # Caste check
    if scholarship.allowed_caste:
        allowed = [c.strip() for c in scholarship.allowed_caste.split(',')]
        results['caste'] = (student.caste in allowed) if 'Any' not in allowed else True
    else:
        results['caste'] = True

    # Income check
    if scholarship.max_income:
        results['income'] = (student.income <= scholarship.max_income) if student.income else False
    else:
        results['income'] = True

    # Marks check
    if scholarship.min_marks:
        results['marks'] = (student.marks >= scholarship.min_marks) if student.marks else False
    else:
        results['marks'] = True

    # State check
    if scholarship.allowed_states:
        allowed = [s.strip() for s in scholarship.allowed_states.split(',')]
        results['state'] = (student.state in allowed) if 'Any' not in allowed else True
    else:
        results['state'] = True

    # Gender check
    if scholarship.allowed_gender and scholarship.allowed_gender != 'Any':
        results['gender'] = (student.gender == scholarship.allowed_gender)
    else:
        results['gender'] = True

    # Stream check
    if scholarship.allowed_stream:
        allowed = [s.strip() for s in scholarship.allowed_stream.split(',')]
        results['stream'] = (student.stream in allowed) if 'Any' not in allowed else True
    else:
        results['stream'] = True

    # Disability check
    if scholarship.disability_required is not None:
        results['disability'] = (student.disability == scholarship.disability_required)
    else:
        results['disability'] = True

    # Area check
    if scholarship.allowed_area and scholarship.allowed_area != 'Any':
        results['area'] = (student.area == scholarship.allowed_area)
    else:
        results['area'] = True

    # AND logic: all conditions must be true
    return all(results.values()), results

def match_scholarships(student):
    """Full two-phase pipeline"""
    shortlist = build_inverted_index(student)
    matches = []
    for scholarship in shortlist:
        is_match, breakdown = evaluate_ast(scholarship, student)
        if is_match:
            matches.append({
                'id': scholarship.id,
                'name': scholarship.name,
                'provider': scholarship.provider,
                'amount': scholarship.amount,
                'deadline': scholarship.deadline,
                'apply_url': scholarship.apply_url,
                'is_verified': scholarship.is_verified,
            })
    return matches


# ── SEED DATA ────────────────────────────────────────────

def seed_scholarships():
    if Scholarship.query.count() > 0:
        return
    scholarships = [
        Scholarship(name="Post Matric Scholarship for SC Students",
            provider="Ministry of Social Justice, Govt. of India",
            amount=12000, deadline="31-Oct-2025",
            apply_url="https://scholarships.gov.in",
            is_verified=True,
            allowed_caste="SC", max_income=250000,
            min_marks=None, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Post Matric Scholarship for ST Students",
            provider="Ministry of Tribal Affairs, Govt. of India",
            amount=12000, deadline="31-Oct-2025",
            apply_url="https://scholarships.gov.in",
            is_verified=True,
            allowed_caste="ST", max_income=250000,
            min_marks=None, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Central Sector Scheme for College Students",
            provider="Ministry of Education, Govt. of India",
            amount=10000, deadline="31-Dec-2025",
            apply_url="https://scholarships.gov.in",
            is_verified=True,
            allowed_caste="Any", max_income=800000,
            min_marks=80.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Pragati Scholarship for Girl Students (Technical)",
            provider="AICTE",
            amount=50000, deadline="30-Nov-2025",
            apply_url="https://www.aicte-india.org",
            is_verified=True,
            allowed_caste="Any", max_income=800000,
            min_marks=None, allowed_states="Any",
            allowed_gender="Female", allowed_stream="Engineering",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Saksham Scholarship for Differently Abled",
            provider="AICTE",
            amount=50000, deadline="30-Nov-2025",
            apply_url="https://www.aicte-india.org",
            is_verified=True,
            allowed_caste="Any", max_income=800000,
            min_marks=None, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Engineering",
            disability_required=True, allowed_area="Any"),

        Scholarship(name="Begum Hazrat Mahal National Scholarship",
            provider="Maulana Azad Education Foundation",
            amount=12000, deadline="30-Sep-2025",
            apply_url="https://maef.net.in",
            is_verified=True,
            allowed_caste="Any", max_income=200000,
            min_marks=50.0, allowed_states="Any",
            allowed_gender="Female", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Maharashtra Post Matric Scholarship (OBC)",
            provider="Social Welfare Dept, Maharashtra",
            amount=15000, deadline="31-Dec-2025",
            apply_url="https://mahadbt.maharashtra.gov.in",
            is_verified=True,
            allowed_caste="OBC", max_income=300000,
            min_marks=None, allowed_states="Maharashtra",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Ishan Uday Scholarship for NE Students",
            provider="UGC",
            amount=54000, deadline="31-Dec-2025",
            apply_url="https://scholarships.gov.in",
            is_verified=True,
            allowed_caste="Any", max_income=450000,
            min_marks=None,
            allowed_states="Assam,Meghalaya,Manipur,Mizoram,Nagaland,Tripura,Arunachal Pradesh,Sikkim",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Inspire Scholarship for Higher Education",
            provider="DST, Govt. of India",
            amount=80000, deadline="30-Nov-2025",
            apply_url="https://online-inspire.gov.in",
            is_verified=True,
            allowed_caste="Any", max_income=None,
            min_marks=75.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Science",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Vidyasaarathi Scholarship",
            provider="NSDL e-Governance",
            amount=40000, deadline="28-Feb-2026",
            apply_url="https://www.vidyasaarathi.co.in",
            is_verified=True,
            allowed_caste="SC,ST,OBC", max_income=250000,
            min_marks=60.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="NSP Pre-Matric Scholarship for Minorities",
            provider="Ministry of Minority Affairs",
            amount=10000, deadline="31-Oct-2025",
            apply_url="https://scholarships.gov.in",
            is_verified=True,
            allowed_caste="Any", max_income=100000,
            min_marks=50.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Rural"),

        Scholarship(name="Tata Capital Pankh Scholarship",
            provider="Tata Capital",
            amount=12000, deadline="31-Aug-2025",
            apply_url="https://www.tatacapital.com",
            is_verified=True,
            allowed_caste="Any", max_income=250000,
            min_marks=60.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Sitaram Jindal Foundation Scholarship",
            provider="Sitaram Jindal Foundation",
            amount=24000, deadline="30-Jun-2025",
            apply_url="https://sitaramjindalfoundation.org",
            is_verified=False,
            allowed_caste="Any", max_income=150000,
            min_marks=60.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="L'Oreal India For Young Women in Science",
            provider="L'Oreal India",
            amount=250000, deadline="31-Mar-2026",
            apply_url="https://www.loreal.com/en/india",
            is_verified=True,
            allowed_caste="Any", max_income=None,
            min_marks=85.0, allowed_states="Any",
            allowed_gender="Female", allowed_stream="Science",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Reliance Foundation Undergraduate Scholarship",
            provider="Reliance Foundation",
            amount=200000, deadline="28-Feb-2026",
            apply_url="https://reliancefoundation.org",
            is_verified=True,
            allowed_caste="Any", max_income=250000,
            min_marks=60.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Dr. Ambedkar Post Matric Scholarship (SC/ST)",
            provider="Govt. of Karnataka",
            amount=18000, deadline="31-Dec-2025",
            apply_url="https://sw.kar.nic.in",
            is_verified=True,
            allowed_caste="SC,ST", max_income=250000,
            min_marks=None, allowed_states="Karnataka",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Swami Vivekananda Merit-cum-Means Scholarship",
            provider="Govt. of West Bengal",
            amount=60000, deadline="31-Oct-2025",
            apply_url="https://svmcm.wbhed.gov.in",
            is_verified=True,
            allowed_caste="Any", max_income=250000,
            min_marks=75.0, allowed_states="West Bengal",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Bihar Post Matric Scholarship (BC/EBC)",
            provider="BC/EBC Welfare Dept, Bihar",
            amount=15000, deadline="31-Jan-2026",
            apply_url="https://pmsonline.bih.nic.in",
            is_verified=True,
            allowed_caste="OBC", max_income=150000,
            min_marks=None, allowed_states="Bihar",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="Uttarakhand Post Matric Scholarship (SC)",
            provider="Social Welfare Dept, Uttarakhand",
            amount=10000, deadline="30-Nov-2025",
            apply_url="https://scholarship.uk.gov.in",
            is_verified=True,
            allowed_caste="SC", max_income=200000,
            min_marks=None, allowed_states="Uttarakhand",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Any"),

        Scholarship(name="HDFC Badhte Kadam Scholarship",
            provider="HDFC Bank Parivartan",
            amount=18000, deadline="31-Aug-2025",
            apply_url="https://hdfcbank.com",
            is_verified=True,
            allowed_caste="Any", max_income=250000,
            min_marks=55.0, allowed_states="Any",
            allowed_gender="Any", allowed_stream="Any",
            disability_required=None, allowed_area="Rural"),
    ]
    for s in scholarships:
        db.session.add(s)
    db.session.commit()
    print(f"Seeded {len(scholarships)} scholarships.")


# ── HTML TEMPLATES ───────────────────────────────────────

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ScholarPath — Login</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f8f7f4; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .card { background: white; border-radius: 16px; padding: 40px; width: 100%; max-width: 400px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); border: 0.5px solid #e5e3dc; }
  .logo { font-size: 22px; font-weight: 700; color: #1a1a18; margin-bottom: 6px; }
  .logo span { color: #d97706; }
  .tagline { font-size: 13px; color: #9a9890; margin-bottom: 32px; }
  .tabs { display: flex; gap: 0; margin-bottom: 28px; border-bottom: 1px solid #e5e3dc; }
  .tab { padding: 10px 20px; font-size: 14px; font-weight: 500; color: #9a9890; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; background: none; border-top: none; border-left: none; border-right: none; font-family: system-ui, sans-serif; }
  .tab.active { color: #1a1a18; border-bottom-color: #1a1a18; }
  .form-group { margin-bottom: 16px; }
  label { display: block; font-size: 13px; font-weight: 500; color: #5a5a56; margin-bottom: 6px; }
  input { width: 100%; padding: 10px 14px; border: 0.5px solid #d5d3cc; border-radius: 8px; font-size: 14px; font-family: system-ui, sans-serif; outline: none; transition: border-color .15s; background: #fafaf8; }
  input:focus { border-color: #d97706; background: white; }
  .btn { width: 100%; padding: 12px; background: #1a1a18; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: system-ui, sans-serif; transition: opacity .15s; margin-top: 8px; }
  .btn:hover { opacity: 0.85; }
  .error { background: #fef2f2; color: #991b1b; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 16px; border: 0.5px solid #fecaca; }
  .form-section { display: none; }
  .form-section.active { display: block; }
</style>
</head>
<body>
<div class="card">
  <div class="logo">Scholar<span>Path</span></div>
  <div class="tagline">Find scholarships you actually qualify for</div>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <div class="tabs">
    <button class="tab active" onclick="switchTab('login', this)">Login</button>
    <button class="tab" onclick="switchTab('register', this)">Register</button>
  </div>
  <div id="login" class="form-section active">
    <form method="POST" action="/login">
      <div class="form-group"><label>Email</label><input type="email" name="email" placeholder="you@email.com" required></div>
      <div class="form-group"><label>Password</label><input type="password" name="password" placeholder="••••••••" required></div>
      <button class="btn" type="submit">Login</button>
    </form>
  </div>
  <div id="register" class="form-section">
    <form method="POST" action="/register">
      <div class="form-group"><label>Full Name</label><input type="text" name="name" placeholder="Your name" required></div>
      <div class="form-group"><label>Email</label><input type="email" name="email" placeholder="you@email.com" required></div>
      <div class="form-group"><label>Password</label><input type="password" name="password" placeholder="••••••••" required></div>
      <button class="btn" type="submit">Create Account</button>
    </form>
  </div>
</div>
<script>
  function switchTab(id, btn) {
    document.querySelectorAll('.form-section').forEach(f => f.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    btn.classList.add('active');
  }
  {% if tab == 'register' %}switchTab('register', document.querySelectorAll('.tab')[1]);{% endif %}
</script>
</body>
</html>
"""

PROFILE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ScholarPath — Your Profile</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f8f7f4; min-height: 100vh; }
  nav { background: white; border-bottom: 0.5px solid #e5e3dc; padding: 14px 32px; display: flex; justify-content: space-between; align-items: center; }
  .logo { font-size: 18px; font-weight: 700; color: #1a1a18; } .logo span { color: #d97706; }
  .nav-right { display: flex; align-items: center; gap: 16px; }
  .nav-name { font-size: 13px; color: #5a5a56; }
  .nav-link { font-size: 13px; color: #d97706; text-decoration: none; font-weight: 500; }
  .container { max-width: 680px; margin: 40px auto; padding: 0 24px; }
  h1 { font-size: 22px; font-weight: 700; color: #1a1a18; margin-bottom: 6px; }
  .subtitle { font-size: 14px; color: #9a9890; margin-bottom: 32px; }
  .card { background: white; border-radius: 16px; padding: 28px; border: 0.5px solid #e5e3dc; }
  .section-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: #9a9890; margin-bottom: 16px; margin-top: 24px; }
  .section-label:first-child { margin-top: 0; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .form-group { margin-bottom: 0; }
  label { display: block; font-size: 13px; font-weight: 500; color: #5a5a56; margin-bottom: 6px; }
  input, select { width: 100%; padding: 10px 14px; border: 0.5px solid #d5d3cc; border-radius: 8px; font-size: 14px; font-family: system-ui, sans-serif; outline: none; background: #fafaf8; transition: border-color .15s; }
  input:focus, select:focus { border-color: #d97706; background: white; }
  .btn { padding: 12px 28px; background: #1a1a18; color: white; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; font-family: system-ui, sans-serif; transition: opacity .15s; margin-top: 24px; }
  .btn:hover { opacity: 0.85; }
  .success { background: #f0fdf4; color: #166534; padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 16px; border: 0.5px solid #bbf7d0; }
</style>
</head>
<body>
<nav>
  <div class="logo">Scholar<span>Path</span></div>
  <div class="nav-right">
    <span class="nav-name">{{ student.name }}</span>
    <a href="/dashboard" class="nav-link">Dashboard</a>
    <a href="/logout" class="nav-link">Logout</a>
  </div>
</nav>
<div class="container">
  <h1>Your Profile</h1>
  <div class="subtitle">Fill in your details to see scholarships you qualify for</div>
  {% if saved %}<div class="success">Profile saved! <a href="/dashboard" style="color:#166534;font-weight:600">View your matches →</a></div>{% endif %}
  <div class="card">
    <form method="POST" action="/profile">
      <div class="section-label">Academic Details</div>
      <div class="grid2">
        <div class="form-group">
          <label>Marks / Percentage (%)</label>
          <input type="number" name="marks" step="0.1" min="0" max="100" placeholder="e.g. 78.5" value="{{ student.marks or '' }}">
        </div>
        <div class="form-group">
          <label>Stream</label>
          <select name="stream">
            <option value="">Select stream</option>
            {% for s in ['Engineering','Medical','Science','Commerce','Arts','Law','Management','Any'] %}
            <option value="{{ s }}" {% if student.stream == s %}selected{% endif %}>{{ s }}</option>
            {% endfor %}
          </select>
        </div>
      </div>
      <div class="section-label">Personal Details</div>
      <div class="grid2">
        <div class="form-group">
          <label>Caste Category</label>
          <select name="caste">
            <option value="">Select category</option>
            {% for c in ['SC','ST','OBC','General'] %}
            <option value="{{ c }}" {% if student.caste == c %}selected{% endif %}>{{ c }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="form-group">
          <label>Gender</label>
          <select name="gender">
            <option value="">Select gender</option>
            {% for g in ['Male','Female','Other'] %}
            <option value="{{ g }}" {% if student.gender == g %}selected{% endif %}>{{ g }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="form-group">
          <label>Annual Family Income (₹)</label>
          <input type="number" name="income" placeholder="e.g. 180000" value="{{ student.income or '' }}">
        </div>
        <div class="form-group">
          <label>Area</label>
          <select name="area">
            <option value="">Select area</option>
            {% for a in ['Rural','Urban'] %}
            <option value="{{ a }}" {% if student.area == a %}selected{% endif %}>{{ a }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="form-group">
          <label>State</label>
          <select name="state">
            <option value="">Select state</option>
            {% for s in ['Andhra Pradesh','Arunachal Pradesh','Assam','Bihar','Chhattisgarh','Goa','Gujarat','Haryana','Himachal Pradesh','Jharkhand','Karnataka','Kerala','Madhya Pradesh','Maharashtra','Manipur','Meghalaya','Mizoram','Nagaland','Odisha','Punjab','Rajasthan','Sikkim','Tamil Nadu','Telangana','Tripura','Uttar Pradesh','Uttarakhand','West Bengal','Delhi'] %}
            <option value="{{ s }}" {% if student.state == s %}selected{% endif %}>{{ s }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="form-group">
          <label>Disability</label>
          <select name="disability">
            <option value="0" {% if not student.disability %}selected{% endif %}>No</option>
            <option value="1" {% if student.disability %}selected{% endif %}>Yes</option>
          </select>
        </div>
      </div>
      <button class="btn" type="submit">Save Profile & Find Matches</button>
    </form>
  </div>
</div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ScholarPath — Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f8f7f4; min-height: 100vh; }
  nav { background: white; border-bottom: 0.5px solid #e5e3dc; padding: 14px 32px; display: flex; justify-content: space-between; align-items: center; }
  .logo { font-size: 18px; font-weight: 700; color: #1a1a18; } .logo span { color: #d97706; }
  .nav-right { display: flex; align-items: center; gap: 16px; }
  .nav-name { font-size: 13px; color: #5a5a56; }
  .nav-link { font-size: 13px; color: #d97706; text-decoration: none; font-weight: 500; }
  .container { max-width: 900px; margin: 40px auto; padding: 0 24px 80px; }
  .header { margin-bottom: 32px; }
  h1 { font-size: 22px; font-weight: 700; color: #1a1a18; margin-bottom: 4px; }
  .subtitle { font-size: 14px; color: #9a9890; }
  .stats { display: flex; gap: 12px; margin-bottom: 32px; }
  .stat { background: white; border: 0.5px solid #e5e3dc; border-radius: 12px; padding: 16px 20px; flex: 1; }
  .stat-val { font-size: 28px; font-weight: 700; color: #1a1a18; }
  .stat-label { font-size: 12px; color: #9a9890; margin-top: 2px; }
  .incomplete { background: #fffbeb; border: 0.5px solid #fde68a; border-radius: 12px; padding: 16px 20px; margin-bottom: 24px; }
  .incomplete p { font-size: 14px; color: #92400e; }
  .incomplete a { color: #d97706; font-weight: 600; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
  .scholarship-card { background: white; border: 0.5px solid #e5e3dc; border-radius: 16px; padding: 20px; transition: box-shadow .15s; }
  .scholarship-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
  .card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }
  .card-name { font-size: 14px; font-weight: 600; color: #1a1a18; line-height: 1.4; flex: 1; }
  .verified { font-size: 10px; font-weight: 600; background: #f0fdf4; color: #166534; padding: 2px 8px; border-radius: 8px; margin-left: 8px; white-space: nowrap; border: 0.5px solid #bbf7d0; }
  .provider { font-size: 12px; color: #9a9890; margin-bottom: 12px; }
  .amount { font-size: 22px; font-weight: 700; color: #1a1a18; margin-bottom: 4px; }
  .deadline { font-size: 12px; color: #9a9890; margin-bottom: 16px; }
  .apply-btn { display: block; text-align: center; padding: 9px; background: #1a1a18; color: white; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 600; transition: opacity .15s; }
  .apply-btn:hover { opacity: 0.85; }
  .empty { text-align: center; padding: 60px 20px; color: #9a9890; }
  .empty h2 { font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #5a5a56; }
  .empty p { font-size: 14px; margin-bottom: 20px; }
  .empty a { color: #d97706; font-weight: 600; text-decoration: none; }
</style>
</head>
<body>
<nav>
  <div class="logo">Scholar<span>Path</span></div>
  <div class="nav-right">
    <span class="nav-name">{{ student.name }}</span>
    <a href="/profile" class="nav-link">Edit Profile</a>
    <a href="/logout" class="nav-link">Logout</a>
  </div>
</nav>
<div class="container">
  <div class="header">
    <h1>Your Matched Scholarships</h1>
    <div class="subtitle">Showing scholarships you are eligible for based on your profile</div>
  </div>

  {% if not profile_complete %}
  <div class="incomplete">
    <p>Your profile is incomplete. <a href="/profile">Complete your profile</a> to see all matching scholarships.</p>
  </div>
  {% endif %}

  <div class="stats">
    <div class="stat">
      <div class="stat-val">{{ matches|length }}</div>
      <div class="stat-label">Scholarships matched</div>
    </div>
    <div class="stat">
      <div class="stat-val">₹{{ "{:,}".format(total_amount) }}</div>
      <div class="stat-label">Total potential funding</div>
    </div>
    <div class="stat">
      <div class="stat-val">{{ verified_count }}</div>
      <div class="stat-label">Verified scholarships</div>
    </div>
  </div>

  {% if matches %}
  <div class="grid">
    {% for s in matches %}
    <div class="scholarship-card">
      <div class="card-header">
        <div class="card-name">{{ s.name }}</div>
        {% if s.is_verified %}<span class="verified">✓ Verified</span>{% endif %}
      </div>
      <div class="provider">{{ s.provider }}</div>
      <div class="amount">₹{{ "{:,}".format(s.amount) }}</div>
      <div class="deadline">Deadline: {{ s.deadline }}</div>
      <a href="{{ s.apply_url }}" target="_blank" class="apply-btn">Apply Now →</a>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="empty">
    <h2>No matches yet</h2>
    <p>Complete your profile to find scholarships you qualify for.</p>
    <a href="/profile">Complete Profile →</a>
  </div>
  {% endif %}
</div>
</body>
</html>
"""


# ── ROUTES ───────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(LOGIN_HTML)

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    student = Student.query.filter_by(email=email, password=password).first()
    if not student:
        return render_template_string(LOGIN_HTML, error="Invalid email or password.")
    from flask import session
    session['student_id'] = student.id
    return dashboard()

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    if Student.query.filter_by(email=email).first():
        return render_template_string(LOGIN_HTML, error="Email already registered.", tab='register')
    student = Student(name=name, email=email, password=password)
    db.session.add(student)
    db.session.commit()
    from flask import session
    session['student_id'] = student.id
    return render_template_string(PROFILE_HTML, student=student, saved=False)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    from flask import session
    student_id = session.get('student_id')
    if not student_id:
        return render_template_string(LOGIN_HTML, error="Please login first.")
    student = Student.query.get(student_id)
    if request.method == 'POST':
        student.marks = float(request.form.get('marks') or 0) or None
        student.stream = request.form.get('stream') or None
        student.caste = request.form.get('caste') or None
        student.gender = request.form.get('gender') or None
        student.income = int(request.form.get('income') or 0) or None
        student.area = request.form.get('area') or None
        student.state = request.form.get('state') or None
        student.disability = bool(int(request.form.get('disability', 0)))
        db.session.commit()
        return render_template_string(PROFILE_HTML, student=student, saved=True)
    return render_template_string(PROFILE_HTML, student=student, saved=False)

@app.route('/dashboard')
def dashboard():
    from flask import session
    student_id = session.get('student_id')
    if not student_id:
        return render_template_string(LOGIN_HTML, error="Please login first.")
    student = Student.query.get(student_id)
    profile_complete = all([student.caste, student.income, student.marks, student.state, student.gender])
    matches = match_scholarships(student) if profile_complete else []
    total_amount = sum(m['amount'] for m in matches if m['amount'])
    verified_count = sum(1 for m in matches if m['is_verified'])
    return render_template_string(DASHBOARD_HTML,
        student=student,
        matches=matches,
        profile_complete=profile_complete,
        total_amount=total_amount,
        verified_count=verified_count)

@app.route('/logout')
def logout():
    from flask import session
    session.clear()
    return render_template_string(LOGIN_HTML)

# ── API ENDPOINTS (for documentation) ───────────────────

@app.route('/api/matches/<int:student_id>')
def api_matches(student_id):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    matches = match_scholarships(student)
    return jsonify({'student_id': student_id, 'matches': matches, 'count': len(matches)})

@app.route('/api/scholarships')
def api_scholarships():
    scholarships = Scholarship.query.all()
    return jsonify([{
        'id': s.id, 'name': s.name, 'provider': s.provider,
        'amount': s.amount, 'deadline': s.deadline
    } for s in scholarships])


# ── INIT ─────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_scholarships()
    print("\n ScholarPath is running!")
    print(" Open: http://127.0.0.1:5000\n")
    app.run(debug=True)