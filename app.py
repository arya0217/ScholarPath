import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from flask_wtf import CSRFProtect
from models import db, Student, Scholarship, SavedScholarship, Application, Admin, StudentDocument
from matching_engine import match_scholarships
from decision_engine import rank_matches, application_readiness, next_actions
from werkzeug.utils import secure_filename
from datetime import datetime
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///scholarpath.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(app.instance_path, 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.instance_path, exist_ok=True)

db.init_app(app)
CSRFProtect(app)

with app.app_context():
    db.create_all()
    # Lightweight migration for existing SQLite MVP databases.
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    scholarship_columns = {c['name'] for c in inspector.get_columns('scholarship')}
    if 'required_documents' not in scholarship_columns:
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE scholarship ADD COLUMN required_documents TEXT DEFAULT ''"))
    # Give legacy seeded scholarships meaningful document requirements after migration.
    legacy_docs = {
        'National Merit Scholarship': 'Marksheet,Income Certificate,Bank Passbook',
        'SC Higher Education Grant': 'Caste Certificate,Income Certificate,Marksheet',
        'Women in STEM Scholarship': 'Marksheet,Bonafide Certificate,Bank Passbook',
        'Rural Student Opportunity Grant': 'Income Certificate,Residence Certificate,Marksheet',
    }
    for scholarship_name, docs in legacy_docs.items():
        legacy = Scholarship.query.filter_by(name=scholarship_name).first()
        if legacy and not legacy.required_documents:
            legacy.required_documents = docs
    db.session.commit()
    if not Admin.query.filter_by(username='admin').first():
        a = Admin(username='admin'); a.set_password(os.environ.get('ADMIN_PASSWORD', 'admin123')); db.session.add(a); db.session.commit()
    if Scholarship.query.count() == 0:
        seed = [
            Scholarship(name='National Merit Scholarship', provider='Government of India', amount=50000, deadline='2026-12-31', verified=True, allowed_caste='Any', max_income=800000, min_marks=75, allowed_states='Any', allowed_gender='Any', allowed_stream='Any', disability_required=None, allowed_area='Any', required_documents='Marksheet,Income Certificate,Bank Passbook', description='Merit support for eligible Indian students.', url='https://scholarships.gov.in/'),
            Scholarship(name='SC Higher Education Grant', provider='Education Department', amount=60000, deadline='2026-11-30', verified=True, allowed_caste='SC', max_income=500000, min_marks=60, allowed_states='Any', allowed_gender='Any', allowed_stream='Any', disability_required=None, allowed_area='Any', required_documents='Caste Certificate,Income Certificate,Marksheet', description='Higher education support for SC students.', url='https://scholarships.gov.in/'),
            Scholarship(name='Women in STEM Scholarship', provider='Future Skills Foundation', amount=75000, deadline='2026-10-31', verified=True, allowed_caste='Any', max_income=700000, min_marks=70, allowed_states='Any', allowed_gender='Female', allowed_stream='Science,Engineering', disability_required=None, allowed_area='Any', required_documents='Marksheet,Bonafide Certificate,Bank Passbook', description='Scholarship for women pursuing STEM degrees.', url='https://scholarships.gov.in/'),
            Scholarship(name='Rural Student Opportunity Grant', provider='Rural Education Trust', amount=40000, deadline='2026-09-30', verified=False, allowed_caste='Any', max_income=400000, min_marks=55, allowed_states='Gujarat,Rajasthan,Madhya Pradesh', allowed_gender='Any', allowed_stream='Any', disability_required=None, allowed_area='Rural', required_documents='Income Certificate,Residence Certificate,Marksheet', description='Support for students from rural communities.', url='https://scholarships.gov.in/'),
        ]
        db.session.add_all(seed); db.session.commit()

def current_student(): return Student.query.get(session.get('student_id')) if session.get('student_id') else None

def student_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not current_student(): return redirect(url_for('home'))
        return f(*a, **kw)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not session.get('admin_id'): return redirect(url_for('home'))
        return f(*a, **kw)
    return w

def explanation_rows(node):
    rows=[]
    def walk(n, group=None):
        t=n.get('type')
        if t=='leaf': rows.append({'label': n['label'], 'passed': n['passed'], 'wildcard': ': Any' in n['label']})
        elif t=='or':
            children=n.get('children',[])
            passed_any=any(c.get('passed') for c in children)
            label=' or '.join(c.get('label','') for c in children)
            rows.append({'label': label, 'passed': passed_any, 'wildcard': False})
        elif t=='and':
            for c in n.get('children',[]): walk(c, group)
        elif t=='not': walk(n.get('child',{}), group)
    walk(node); return rows

@app.context_processor
def inject(): return {'student': current_student()}

@app.route('/', methods=['GET','POST'])
def home():
    if request.method=='POST':
        action=request.form.get('action')
        if action=='register':
            name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
            if not name or '@' not in email or len(password)<8: flash('Please enter a valid name, email, and password of at least 8 characters.','error')
            elif Student.query.filter_by(email=email).first(): flash('An account with that email already exists.','error')
            else:
                s=Student(name=name,email=email,password=''); s.set_password(password); db.session.add(s); db.session.commit(); session['student_id']=s.id; return redirect(url_for('profile'))
        elif action=='login':
            email=request.form.get('email','').strip().lower(); password=request.form.get('password',''); s=Student.query.filter_by(email=email).first()
            if s and s.check_password(password): session.clear(); session['student_id']=s.id; return redirect(url_for('dashboard'))
            a=Admin.query.filter_by(username=email).first()
            if a and a.check_password(password): session.clear(); session['admin_id']=a.id; return redirect(url_for('admin_dashboard'))
            flash('Invalid email or password','error')
    return render_template('login.html')

@app.get('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/profile', methods=['GET','POST'])
@student_required
def profile():
    s=current_student()
    if request.method=='POST':
        s.caste=request.form.get('caste') or None; s.state=request.form.get('state') or None; s.gender=request.form.get('gender') or None; s.stream=request.form.get('stream') or None; s.area=request.form.get('area') or None
        try: s.income=float(request.form.get('income')) if request.form.get('income') else None
        except ValueError: s.income=None
        try: s.marks=float(request.form.get('marks')) if request.form.get('marks') else None
        except ValueError: s.marks=None
        s.disability = request.form.get('disability') == 'yes' if request.form.get('disability') else None
        db.session.commit(); flash('Profile saved.','success'); return redirect(url_for('dashboard'))
    return render_template('profile.html', s=s)

@app.get('/dashboard')
@student_required
def dashboard():
    s=current_student(); scholarships=Scholarship.query.all(); matches=match_scholarships(s,scholarships)
    verified=request.args.get('verified')=='1'; order=request.args.get('order','')
    if verified: matches=[m for m in matches if m[0].verified]
    q=request.args.get('q','').strip().lower()
    if q: matches=[m for m in matches if q in m[0].name.lower() or q in m[0].provider.lower()]
    ranked=rank_matches(matches, s.documents)
    if order=='asc': ranked=sorted(ranked,key=lambda x:x['scholarship'].amount or 0)
    elif order=='desc': ranked=sorted(ranked,key=lambda x:x['scholarship'].amount or 0, reverse=True)
    saved_ids={x.scholarship_id for x in SavedScholarship.query.filter_by(student_id=s.id)}
    apps={x.scholarship_id:x for x in Application.query.filter_by(student_id=s.id)}
    total=sum(x['scholarship'].amount or 0 for x in ranked)
    top=ranked[:3]
    for item in top:
        item['actions']=next_actions(item, apps.get(item['scholarship'].id))
    return render_template('dashboard.html', ranked=ranked, top=top, saved_ids=saved_ids, apps=apps, total=total, verified=verified, order=order, q=q, explanation_rows=explanation_rows)

@app.route('/documents', methods=['GET','POST'])
@student_required
def documents():
    student=current_student()
    if request.method=='POST':
        document_type=request.form.get('document_type','').strip()
        uploaded=request.files.get('file')
        allowed={'pdf','png','jpg','jpeg'}
        ext=uploaded.filename.rsplit('.',1)[-1].lower() if uploaded and '.' in uploaded.filename else ''
        if not document_type or not uploaded or ext not in allowed:
            flash('Choose a document type and upload a PDF, JPG, or PNG file.','error')
        else:
            filename=f"{student.id}_{uuid.uuid4().hex}_{secure_filename(uploaded.filename)}"
            uploaded.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            db.session.add(StudentDocument(student_id=student.id, document_type=document_type, file_path=filename))
            db.session.commit(); flash('Document added to your vault.','success')
        return redirect(url_for('documents'))
    docs=StudentDocument.query.filter_by(student_id=student.id).order_by(StudentDocument.uploaded_at.desc()).all()
    return render_template('documents.html', documents=docs)

@app.post('/documents/<int:doc_id>/delete')
@student_required
def delete_document(doc_id):
    doc=StudentDocument.query.filter_by(id=doc_id, student_id=current_student().id).first_or_404()
    path=os.path.join(app.config['UPLOAD_FOLDER'], doc.file_path)
    if os.path.exists(path): os.remove(path)
    db.session.delete(doc); db.session.commit(); return redirect(url_for('documents'))

@app.get('/documents/file/<int:doc_id>')
@student_required
def document_file(doc_id):
    doc=StudentDocument.query.filter_by(id=doc_id, student_id=current_student().id).first_or_404()
    return send_from_directory(app.config['UPLOAD_FOLDER'], doc.file_path, as_attachment=False)

@app.get('/scholarship/<int:sid>')
@student_required
def detail(sid):
    scholarship=Scholarship.query.get_or_404(sid); student=current_student(); passed, explanation=__import__('matching_engine').evaluate_ast(scholarship,student)
    rows=explanation_rows(explanation); saved=SavedScholarship.query.filter_by(student_id=student.id,scholarship_id=scholarship.id).first(); appn=Application.query.filter_by(student_id=student.id,scholarship_id=scholarship.id).first()
    ranked=rank_matches([(scholarship, explanation)], student.documents)[0]
    ranked['actions']=next_actions(ranked, appn)
    return render_template('detail.html', scholarship=scholarship, rows=rows, passed=passed, saved=bool(saved), application=appn, decision=ranked)

@app.post('/save/<int:sid>')
@student_required
def save(sid):
    s=current_student(); obj=SavedScholarship.query.filter_by(student_id=s.id,scholarship_id=sid).first()
    if obj: db.session.delete(obj)
    else: db.session.add(SavedScholarship(student_id=s.id,scholarship_id=sid))
    db.session.commit(); return redirect(request.referrer or url_for('dashboard'))

@app.post('/apply/<int:sid>')
@student_required
def apply(sid):
    s=current_student(); obj=Application.query.filter_by(student_id=s.id,scholarship_id=sid).first()
    if not obj: db.session.add(Application(student_id=s.id,scholarship_id=sid,status='Applied')); db.session.commit()
    return redirect(url_for('detail',sid=sid))

@app.post('/application/<int:aid>/status')
@student_required
def application_status(aid):
    obj=Application.query.get_or_404(aid); obj.status=request.form.get('status','Applied'); db.session.commit(); return redirect(url_for('detail',sid=obj.scholarship_id))

@app.get('/api/decision/<int:student_id>')
def api_decision(student_id):
    s=Student.query.get_or_404(student_id)
    ranked=rank_matches(match_scholarships(s, Scholarship.query.all()), s.documents)
    return jsonify([{
        'id': x['scholarship'].id, 'name': x['scholarship'].name, 'priority_score': x['score'],
        'readiness_percent': x['readiness']['percent'], 'missing_documents': x['readiness']['missing'],
        'deadline_days': x['deadline_days'], 'criteria_score': x['criteria_score']
    } for x in ranked])

@app.get('/api/scholarships')
def api_scholarships(): return jsonify([{'id':s.id,'name':s.name,'provider':s.provider,'amount':s.amount,'verified':s.verified} for s in Scholarship.query.all()])

@app.get('/api/matches/<int:student_id>')
def api_matches(student_id):
    s=Student.query.get_or_404(student_id); return jsonify([{'id':x.id,'name':x.name,'amount':x.amount,'explanation':e} for x,e in match_scholarships(s,Scholarship.query.all())])

@app.route('/admin')
@admin_required
def admin_dashboard(): return render_template('admin_dashboard.html', scholarships=Scholarship.query.order_by(Scholarship.id.desc()).all(), students=Student.query.order_by(Student.id.desc()).limit(5).all(), application_count=Application.query.count())

@app.route('/admin/scholarship/add', methods=['GET','POST'])
@app.route('/admin/scholarship/edit/<int:sid>', methods=['GET','POST'])
@admin_required
def admin_scholarship(sid=None):
    s=Scholarship.query.get_or_404(sid) if sid else Scholarship()
    if request.method=='POST':
        for f in ['name','provider','deadline','url','description','allowed_caste','allowed_states','allowed_gender','allowed_stream','allowed_area','required_documents']:
            setattr(s,f,request.form.get(f,'').strip())
        for f in ['amount','max_income','min_marks']:
            try: setattr(s,f,float(request.form.get(f))) if request.form.get(f) else setattr(s,f,None)
            except ValueError: setattr(s,f,None)
        s.verified=request.form.get('verified')=='on'
        s.disability_required=None if request.form.get('disability_required') in ('','any') else request.form.get('disability_required')=='yes'
        db.session.add(s); db.session.commit(); return redirect(url_for('admin_dashboard'))
    return render_template('admin_scholarship_form.html', s=s)

@app.post('/admin/scholarship/<int:sid>/delete')
@admin_required
def admin_delete(sid):
    s=Scholarship.query.get_or_404(sid); db.session.delete(s); db.session.commit(); return redirect(url_for('admin_dashboard'))

@app.post('/admin/scholarship/<int:sid>/verify')
@admin_required
def admin_verify(sid):
    s=Scholarship.query.get_or_404(sid); s.verified=not s.verified; db.session.commit(); return redirect(url_for('admin_dashboard'))

if __name__=='__main__': app.run(debug=True)
