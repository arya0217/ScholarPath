from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    caste = db.Column(db.String(40))
    income = db.Column(db.Float)
    marks = db.Column(db.Float)
    state = db.Column(db.String(80))
    gender = db.Column(db.String(40))
    stream = db.Column(db.String(80))
    disability = db.Column(db.Boolean)
    area = db.Column(db.String(80))

    documents = db.relationship('StudentDocument', backref='student', cascade='all, delete-orphan')

    saved = db.relationship('SavedScholarship', backref='student', cascade='all, delete-orphan')
    applications = db.relationship('Application', backref='student', cascade='all, delete-orphan')

    def set_password(self, value):
        self.password = generate_password_hash(value)

    def check_password(self, value):
        return check_password_hash(self.password, value)

    def profile_percent(self):
        fields = [self.caste, self.income, self.marks, self.state, self.gender, self.stream, self.disability is not None, self.area]
        return round(sum(bool(v) for v in fields) / len(fields) * 100)

class Scholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    provider = db.Column(db.String(160), nullable=False)
    amount = db.Column(db.Float, default=0)
    deadline = db.Column(db.String(40))
    url = db.Column(db.String(500))
    description = db.Column(db.Text)
    verified = db.Column(db.Boolean, default=False)
    allowed_caste = db.Column(db.String(200), default='Any')
    max_income = db.Column(db.Float)
    min_marks = db.Column(db.Float)
    allowed_states = db.Column(db.String(300), default='Any')
    allowed_gender = db.Column(db.String(80), default='Any')
    allowed_stream = db.Column(db.String(200), default='Any')
    disability_required = db.Column(db.Boolean)
    allowed_area = db.Column(db.String(120), default='Any')
    required_documents = db.Column(db.Text, default='')

class StudentDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    document_type = db.Column(db.String(160), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedScholarship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'), nullable=False)
    scholarship = db.relationship('Scholarship')
    __table_args__ = (db.UniqueConstraint('student_id', 'scholarship_id', name='uq_saved'),)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarship.id'), nullable=False)
    status = db.Column(db.String(40), default='Applied')
    scholarship = db.relationship('Scholarship')
    __table_args__ = (db.UniqueConstraint('student_id', 'scholarship_id', name='uq_application'),)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    def set_password(self, value): self.password = generate_password_hash(value)
    def check_password(self, value): return check_password_hash(self.password, value)
