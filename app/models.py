from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string

db = SQLAlchemy()

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    alternate_mobile = db.Column(db.String(20))
    email = db.Column(db.String(120))
    sex = db.Column(db.String(10))  # Changed nullable to match the database
    age = db.Column(db.Integer)
    marital_status = db.Column(db.String(20))
    occupation = db.Column(db.String(100))
    blood_group = db.Column(db.String(5))
    emergency_contact_person = db.Column(db.String(100))
    emergency_contact_number = db.Column(db.String(20))
    emergency_contact_relation = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Changed from registered_on to created_at
    address = db.Column(db.Text)  # Add this line

    def __repr__(self):
        return f'<Patient {self.firstname} {self.lastname}>'

    def to_dict(self):
        return {
            'id': self.id,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'mobile': self.mobile,
            'alternate_mobile': self.alternate_mobile,
            'email': self.email,
            'sex': self.sex,
            'age': self.age,
            'marital_status': self.marital_status,
            'occupation': self.occupation,
            'blood_group': self.blood_group,
            'emergency_contact_person': self.emergency_contact_person,
            'emergency_contact_number': self.emergency_contact_number,
            'emergency_contact_relation': self.emergency_contact_relation,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'address': self.address,
        }

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.Time, nullable=False)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doctor = db.relationship('Doctor', backref='appointments')

    def __repr__(self):
        return f'<Appointment {self.id}: {self.patient_name} on {self.appointment_date}>'

class Doctor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'sex': self.sex,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class OPRecord(db.Model):
    __tablename__ = 'op_record'

    id = db.Column(db.Integer, primary_key=True)
    op_id = db.Column(db.String(20), nullable=False, unique=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    visit_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False)

    doctor = db.relationship('Doctor', backref='op_records')
    patient = db.relationship('Patient', backref='op_records')

    @staticmethod
    def generate_op_id():
        # Generate a random 4-character alphanumeric string
        random_string = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        # Use a shorter timestamp format (YYMMDD)
        timestamp = datetime.utcnow().strftime('%y%m%d')
        return f"OP{timestamp}{random_string}"

    def to_dict(self):
        return {
            'id': self.id,
            'op_id': self.op_id,
            'patient_id': self.patient_id,
            'patient_name': f"{self.patient.firstname} {self.patient.lastname}",
            'phone': self.patient.mobile,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.name if self.doctor else None,
            'visit_date': self.visit_date.strftime('%Y-%m-%d'),
            'reason': self.reason,
            'status': self.status
        }

class Inpatient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    admission_date = db.Column(db.Date, nullable=False)
    diagnosis = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    doctor = db.relationship('Doctor', backref='inpatients')

    def to_dict(self):
        return {
            'id': self.id,
            'patient_name': self.patient_name,
            'room_number': self.room_number,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.name if self.doctor else None,
            'admission_date': self.admission_date.strftime('%Y-%m-%d'),
            'diagnosis': self.diagnosis
        }

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    sex = db.Column(db.String(10), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Staff {self.name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'sex': self.sex,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class DischargedPatient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctor.id'), nullable=False)
    admission_date = db.Column(db.Date, nullable=False)
    discharge_date = db.Column(db.Date, nullable=False)
    diagnosis = db.Column(db.Text)
    doctor = db.relationship('Doctor', backref='discharged_patients')

    def to_dict(self):
        return {
            'id': self.id,
            'patient_name': self.patient_name,
            'room_number': self.room_number,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.name if self.doctor else None,
            'admission_date': self.admission_date.strftime('%Y-%m-%d'),
            'discharge_date': self.discharge_date.strftime('%Y-%m-%d'),
            'diagnosis': self.diagnosis
        }
