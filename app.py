from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scholarpath.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'scholarpath-secret-2025'
db = SQLAlchemy(app)


# ── MODELS ──────────────────────────────────────────────────────────────────

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

    def profile_complete(self):
        return all([self.caste, self.income, self.marks, self.state, self.gender, self.stream])

    def profile_percent(self):
        fields = [self.caste, self.income, self.marks, self.state, self.gender, self.stream, self.area, self.disability is not None]
        filled = sum(1 for f in fields if f)
        return int((filled / len(fields)) * 100)


class Scholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    provider = db.Column(db.String(200))
    amount = db.Column(db.Integer)
    deadline = db.Column(db.String(20))
    apply_url = db.Column(db.String(300))
    description = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)
    allowed_caste = db.Column(db.String(200))
    max_income = db.Column(db.Integer)
    min_marks = db.Column(db.Float)
    allowed_states = db.Column(db.String(500))
    allowed_gender = db.Column(db.String(10))
    allowed_stream = db.Column(db.String(200))
    disability_required = db.Column(db.Boolean)
    allowed_area = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedScholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'))
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)


class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'))
    status = db.Column(db.String(20), default='Applied')
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)


# ── MATCHING ENGINE ──────────────────────────────────────────────────────────

def build_inverted_index(student):
    candidates = Scholarship.query.all()
    shortlist = []
    for s in candidates:
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
    results = {}
    if scholarship.allowed_caste:
        allowed = [c.strip() for c in scholarship.allowed_caste.split(',')]
        results['caste'] = (student.caste in allowed) if 'Any' not in allowed else True
    else:
        results['caste'] = True
    if scholarship.max_income:
        results['income'] = (student.income <= scholarship.max_income) if student.income else False
    else:
        results['income'] = True
    if scholarship.min_marks:
        results['marks'] = (student.marks >= scholarship.min_marks) if student.marks else False
    else:
        results['marks'] = True
    if scholarship.allowed_states:
        allowed = [s.strip() for s in scholarship.allowed_states.split(',')]
        results['state'] = (student.state in allowed) if 'Any' not in allowed else True
    else:
        results['state'] = True
    if scholarship.allowed_gender and scholarship.allowed_gender != 'Any':
        results['gender'] = (student.gender == scholarship.allowed_gender)
    else:
        results['gender'] = True
    if scholarship.allowed_stream:
        allowed = [s.strip() for s in scholarship.allowed_stream.split(',')]
        results['stream'] = (student.stream in allowed) if 'Any' not in allowed else True
    else:
        results['stream'] = True
    if scholarship.disability_required is not None:
        results['disability'] = (student.disability == scholarship.disability_required)
    else:
        results['disability'] = True
    if scholarship.allowed_area and scholarship.allowed_area != 'Any':
        results['area'] = (student.area == scholarship.allowed_area)
    else:
        results['area'] = True
    return all(results.values())

def match_scholarships(student):
    shortlist = build_inverted_index(student)
    matches = []
    for s in shortlist:
        if evaluate_ast(s, student):
            matches.append(s)
    return matches


# ── SEED DATA ────────────────────────────────────────────────────────────────

def seed_data():
    if Scholarship.query.count() > 0:
        return
    scholarships = [
        Scholarship(name="Post Matric Scholarship for SC Students", provider="Ministry of Social Justice, Govt. of India", amount=12000, deadline="31-Oct-2025", apply_url="https://scholarships.gov.in", description="Financial assistance for SC students pursuing post-matric education.", is_verified=True, allowed_caste="SC", max_income=250000, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Post Matric Scholarship for ST Students", provider="Ministry of Tribal Affairs, Govt. of India", amount=12000, deadline="31-Oct-2025", apply_url="https://scholarships.gov.in", description="Financial assistance for ST students pursuing post-matric education.", is_verified=True, allowed_caste="ST", max_income=250000, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Central Sector Scheme for College Students", provider="Ministry of Education, Govt. of India", amount=10000, deadline="31-Dec-2025", apply_url="https://scholarships.gov.in", description="Merit based scholarship for top students in class 12.", is_verified=True, allowed_caste="Any", max_income=800000, min_marks=80.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Pragati Scholarship for Girl Students (Technical)", provider="AICTE", amount=50000, deadline="30-Nov-2025", apply_url="https://www.aicte-india.org", description="Scholarship for girl students pursuing technical education.", is_verified=True, allowed_caste="Any", max_income=800000, allowed_states="Any", allowed_gender="Female", allowed_stream="Engineering", allowed_area="Any"),
        Scholarship(name="Saksham Scholarship for Differently Abled", provider="AICTE", amount=50000, deadline="30-Nov-2025", apply_url="https://www.aicte-india.org", description="For differently abled students in technical programs.", is_verified=True, allowed_caste="Any", max_income=800000, allowed_states="Any", allowed_gender="Any", allowed_stream="Engineering", disability_required=True, allowed_area="Any"),
        Scholarship(name="Begum Hazrat Mahal National Scholarship", provider="Maulana Azad Education Foundation", amount=12000, deadline="30-Sep-2025", apply_url="https://maef.net.in", description="For meritorious girl students from minority communities.", is_verified=True, allowed_caste="Any", max_income=200000, min_marks=50.0, allowed_states="Any", allowed_gender="Female", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Maharashtra Post Matric Scholarship (OBC)", provider="Social Welfare Dept, Maharashtra", amount=15000, deadline="31-Dec-2025", apply_url="https://mahadbt.maharashtra.gov.in", description="For OBC students from Maharashtra.", is_verified=True, allowed_caste="OBC", max_income=300000, allowed_states="Maharashtra", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Ishan Uday Scholarship for NE Students", provider="UGC", amount=54000, deadline="31-Dec-2025", apply_url="https://scholarships.gov.in", description="For students from North Eastern states pursuing higher education.", is_verified=True, allowed_caste="Any", max_income=450000, allowed_states="Assam,Meghalaya,Manipur,Mizoram,Nagaland,Tripura,Arunachal Pradesh,Sikkim", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Inspire Scholarship for Higher Education", provider="DST, Govt. of India", amount=80000, deadline="30-Nov-2025", apply_url="https://online-inspire.gov.in", description="For top science students to pursue natural and basic sciences.", is_verified=True, allowed_caste="Any", min_marks=75.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Science", allowed_area="Any"),
        Scholarship(name="Vidyasaarathi Scholarship", provider="NSDL e-Governance", amount=40000, deadline="28-Feb-2026", apply_url="https://www.vidyasaarathi.co.in", description="For SC/ST/OBC students with good academic record.", is_verified=True, allowed_caste="SC,ST,OBC", max_income=250000, min_marks=60.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="NSP Pre-Matric Scholarship for Minorities", provider="Ministry of Minority Affairs", amount=10000, deadline="31-Oct-2025", apply_url="https://scholarships.gov.in", description="For minority students in rural areas.", is_verified=True, allowed_caste="Any", max_income=100000, min_marks=50.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Rural"),
        Scholarship(name="Tata Capital Pankh Scholarship", provider="Tata Capital", amount=12000, deadline="31-Aug-2025", apply_url="https://www.tatacapital.com", description="For underprivileged students with academic excellence.", is_verified=True, allowed_caste="Any", max_income=250000, min_marks=60.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Sitaram Jindal Foundation Scholarship", provider="Sitaram Jindal Foundation", amount=24000, deadline="30-Jun-2025", apply_url="https://sitaramjindalfoundation.org", description="Merit cum means scholarship for deserving students.", is_verified=False, allowed_caste="Any", max_income=150000, min_marks=60.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="L'Oreal India For Young Women in Science", provider="L'Oreal India", amount=250000, deadline="31-Mar-2026", apply_url="https://www.loreal.com/en/india", description="For outstanding female science students.", is_verified=True, allowed_caste="Any", min_marks=85.0, allowed_states="Any", allowed_gender="Female", allowed_stream="Science", allowed_area="Any"),
        Scholarship(name="Reliance Foundation Undergraduate Scholarship", provider="Reliance Foundation", amount=200000, deadline="28-Feb-2026", apply_url="https://reliancefoundation.org", description="For meritorious students from low income families.", is_verified=True, allowed_caste="Any", max_income=250000, min_marks=60.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Dr. Ambedkar Post Matric Scholarship (SC/ST)", provider="Govt. of Karnataka", amount=18000, deadline="31-Dec-2025", apply_url="https://sw.kar.nic.in", description="For SC/ST students from Karnataka.", is_verified=True, allowed_caste="SC,ST", max_income=250000, allowed_states="Karnataka", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Swami Vivekananda Merit-cum-Means Scholarship", provider="Govt. of West Bengal", amount=60000, deadline="31-Oct-2025", apply_url="https://svmcm.wbhed.gov.in", description="For meritorious students from West Bengal.", is_verified=True, allowed_caste="Any", max_income=250000, min_marks=75.0, allowed_states="West Bengal", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Bihar Post Matric Scholarship (BC/EBC)", provider="BC/EBC Welfare Dept, Bihar", amount=15000, deadline="31-Jan-2026", apply_url="https://pmsonline.bih.nic.in", description="For BC/EBC students from Bihar.", is_verified=True, allowed_caste="OBC", max_income=150000, allowed_states="Bihar", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="Uttarakhand Post Matric Scholarship (SC)", provider="Social Welfare Dept, Uttarakhand", amount=10000, deadline="30-Nov-2025", apply_url="https://scholarship.uk.gov.in", description="For SC students from Uttarakhand.", is_verified=True, allowed_caste="SC", max_income=200000, allowed_states="Uttarakhand", allowed_gender="Any", allowed_stream="Any", allowed_area="Any"),
        Scholarship(name="HDFC Badhte Kadam Scholarship", provider="HDFC Bank Parivartan", amount=18000, deadline="31-Aug-2025", apply_url="https://hdfcbank.com", description="For students from rural areas with financial need.", is_verified=True, allowed_caste="Any", max_income=250000, min_marks=55.0, allowed_states="Any", allowed_gender="Any", allowed_stream="Any", allowed_area="Rural"),
    ]
    for s in scholarships:
        db.session.add(s)

    if Admin.query.count() == 0:
        db.session.add(Admin(username="admin", password="admin123"))

    db.session.commit()
    print(f"Seeded {len(scholarships)} scholarships and 1 admin.")


# ── HELPERS ──────────────────────────────────────────────────────────────────

def current_student():
    sid = session.get('student_id')
    return Student.query.get(sid) if sid else None

def current_admin():
    aid = session.get('admin_id')
    return Admin.query.get(aid) if aid else None


# ── STUDENT ROUTES ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if current_student():
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    student = Student.query.filter_by(email=email, password=password).first()
    if not student:
        return render_template('login.html', error="Invalid email or password.")
    session['student_id'] = student.id
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    if Student.query.filter_by(email=email).first():
        return render_template('login.html', error="Email already registered.", tab='register')
    student = Student(name=name, email=email, password=password)
    db.session.add(student)
    db.session.commit()
    session['student_id'] = student.id
    return redirect(url_for('profile'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    student = current_student()
    if not student:
        return redirect(url_for('index'))
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
        flash('Profile saved successfully.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('profile.html', student=student)

@app.route('/dashboard')
def dashboard():
    student = current_student()
    if not student:
        return redirect(url_for('index'))

    search = request.args.get('search', '').lower()
    filter_verified = request.args.get('verified', '')
    filter_amount = request.args.get('amount', '')
    tab = request.args.get('tab', 'matches')

    matches = match_scholarships(student) if student.profile_complete() else []

    # Apply search and filters
    if search:
        matches = [m for m in matches if search in m.name.lower() or search in (m.provider or '').lower()]
    if filter_verified == '1':
        matches = [m for m in matches if m.is_verified]
    if filter_amount == 'asc':
        matches = sorted(matches, key=lambda x: x.amount or 0)
    elif filter_amount == 'desc':
        matches = sorted(matches, key=lambda x: x.amount or 0, reverse=True)

    saved_ids = {s.scholarship_id for s in SavedScholarship.query.filter_by(student_id=student.id).all()}
    saved_scholarships = [Scholarship.query.get(sid) for sid in saved_ids]
    applications = Application.query.filter_by(student_id=student.id).all()
    app_map = {a.scholarship_id: a for a in applications}

    total_amount = sum(m.amount for m in matches if m.amount)
    verified_count = sum(1 for m in matches if m.is_verified)

    return render_template('dashboard.html',
        student=student,
        matches=matches,
        saved_ids=saved_ids,
        saved_scholarships=saved_scholarships,
        app_map=app_map,
        total_amount=total_amount,
        verified_count=verified_count,
        tab=tab,
        search=search,
        filter_verified=filter_verified,
        filter_amount=filter_amount,
    )

@app.route('/scholarship/<int:sid>')
def scholarship_detail(sid):
    student = current_student()
    if not student:
        return redirect(url_for('index'))
    s = Scholarship.query.get_or_404(sid)
    is_saved = SavedScholarship.query.filter_by(student_id=student.id, scholarship_id=sid).first() is not None
    application = Application.query.filter_by(student_id=student.id, scholarship_id=sid).first()
    return render_template('detail.html', student=student, scholarship=s, is_saved=is_saved, application=application)

@app.route('/save/<int:sid>', methods=['POST'])
def save_scholarship(sid):
    student = current_student()
    if not student:
        return redirect(url_for('index'))
    existing = SavedScholarship.query.filter_by(student_id=student.id, scholarship_id=sid).first()
    if existing:
        db.session.delete(existing)
    else:
        db.session.add(SavedScholarship(student_id=student.id, scholarship_id=sid))
    db.session.commit()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/apply/<int:sid>', methods=['POST'])
def apply_scholarship(sid):
    student = current_student()
    if not student:
        return redirect(url_for('index'))
    existing = Application.query.filter_by(student_id=student.id, scholarship_id=sid).first()
    if not existing:
        db.session.add(Application(student_id=student.id, scholarship_id=sid, status='Applied'))
        db.session.commit()
    return redirect(url_for('scholarship_detail', sid=sid))

@app.route('/update-status/<int:aid>', methods=['POST'])
def update_status(aid):
    student = current_student()
    if not student:
        return redirect(url_for('index'))
    application = Application.query.get_or_404(aid)
    if application.student_id != student.id:
        return redirect(url_for('dashboard'))
    application.status = request.form.get('status', 'Applied')
    application.updated_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('scholarship_detail', sid=application.scholarship_id))


# ── ADMIN ROUTES ──────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username, password=password).first()
        if not admin:
            return render_template('admin_login.html', error="Invalid credentials.")
        session['admin_id'] = admin.id
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_dashboard():
    if not current_admin():
        return redirect(url_for('admin_login'))
    total_scholarships = Scholarship.query.count()
    total_students = Student.query.count()
    total_applications = Application.query.count()
    total_verified = Scholarship.query.filter_by(is_verified=True).count()
    scholarships = Scholarship.query.order_by(Scholarship.created_at.desc()).all()
    recent_students = Student.query.order_by(Student.created_at.desc()).limit(5).all()
    return render_template('admin_dashboard.html',
        total_scholarships=total_scholarships,
        total_students=total_students,
        total_applications=total_applications,
        total_verified=total_verified,
        scholarships=scholarships,
        recent_students=recent_students,
    )

@app.route('/admin/scholarship/add', methods=['GET', 'POST'])
def admin_add_scholarship():
    if not current_admin():
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        s = Scholarship(
            name=request.form.get('name'),
            provider=request.form.get('provider'),
            amount=int(request.form.get('amount') or 0) or None,
            deadline=request.form.get('deadline'),
            apply_url=request.form.get('apply_url'),
            description=request.form.get('description'),
            is_verified=bool(request.form.get('is_verified')),
            allowed_caste=request.form.get('allowed_caste') or None,
            max_income=int(request.form.get('max_income') or 0) or None,
            min_marks=float(request.form.get('min_marks') or 0) or None,
            allowed_states=request.form.get('allowed_states') or None,
            allowed_gender=request.form.get('allowed_gender') or None,
            allowed_stream=request.form.get('allowed_stream') or None,
            allowed_area=request.form.get('allowed_area') or None,
        )
        db.session.add(s)
        db.session.commit()
        flash('Scholarship added successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_scholarship_form.html', scholarship=None)

@app.route('/admin/scholarship/edit/<int:sid>', methods=['GET', 'POST'])
def admin_edit_scholarship(sid):
    if not current_admin():
        return redirect(url_for('admin_login'))
    s = Scholarship.query.get_or_404(sid)
    if request.method == 'POST':
        s.name = request.form.get('name')
        s.provider = request.form.get('provider')
        s.amount = int(request.form.get('amount') or 0) or None
        s.deadline = request.form.get('deadline')
        s.apply_url = request.form.get('apply_url')
        s.description = request.form.get('description')
        s.is_verified = bool(request.form.get('is_verified'))
        s.allowed_caste = request.form.get('allowed_caste') or None
        s.max_income = int(request.form.get('max_income') or 0) or None
        s.min_marks = float(request.form.get('min_marks') or 0) or None
        s.allowed_states = request.form.get('allowed_states') or None
        s.allowed_gender = request.form.get('allowed_gender') or None
        s.allowed_stream = request.form.get('allowed_stream') or None
        s.allowed_area = request.form.get('allowed_area') or None
        db.session.commit()
        flash('Scholarship updated successfully.', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_scholarship_form.html', scholarship=s)

@app.route('/admin/scholarship/delete/<int:sid>', methods=['POST'])
def admin_delete_scholarship(sid):
    if not current_admin():
        return redirect(url_for('admin_login'))
    s = Scholarship.query.get_or_404(sid)
    SavedScholarship.query.filter_by(scholarship_id=sid).delete()
    Application.query.filter_by(scholarship_id=sid).delete()
    db.session.delete(s)
    db.session.commit()
    flash('Scholarship deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/scholarship/toggle-verify/<int:sid>', methods=['POST'])
def admin_toggle_verify(sid):
    if not current_admin():
        return redirect(url_for('admin_login'))
    s = Scholarship.query.get_or_404(sid)
    s.is_verified = not s.is_verified
    db.session.commit()
    return redirect(url_for('admin_dashboard'))


# ── API ───────────────────────────────────────────────────────────────────────

@app.route('/api/matches/<int:student_id>')
def api_matches(student_id):
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'error': 'Student not found'}), 404
    matches = match_scholarships(student)
    return jsonify({'student_id': student_id, 'count': len(matches),
                    'matches': [{'id': m.id, 'name': m.name, 'amount': m.amount} for m in matches]})

@app.route('/api/scholarships')
def api_scholarships():
    scholarships = Scholarship.query.all()
    return jsonify([{'id': s.id, 'name': s.name, 'provider': s.provider, 'amount': s.amount} for s in scholarships])


# ── INIT ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    print("\n ScholarPath is running!")
    print(" Student: http://127.0.0.1:5000")
    print(" Admin:   http://127.0.0.1:5000/admin/login")
    print(" Admin credentials: admin / admin123\n")
    app.run(debug=True)
