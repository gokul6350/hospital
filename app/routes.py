from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from .models import db, Patient, Appointment, Doctor, OPRecord, Inpatient, Staff, DischargedPatient, DoctorNotes
from datetime import datetime, date, timedelta
from sqlalchemy import inspect, text
import csv
import json
from sqlalchemy.orm import aliased
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import tkinter as tk
from tkinter import messagebox
from datetime import datetime, timezone
import threading
import time
import os
import google.generativeai as genai

def format_datetime(dt_str):
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

# Add this function to handle the popup
def show_reminder_popup(patient_name, note_text, room_number):
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    message = f"Reminder for patient: {patient_name}\nRoom: {room_number}\nNote: {note_text}"
    messagebox.showinfo("Doctor Reminder", message)
    root.destroy()

# Add this function to check reminders periodically
def check_reminders(app):
    with app.app_context():
        while True:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Create a new session for this check
                session = db.create_scoped_session()
                
                try:
                    # Query for due reminders
                    due_reminders = session.query(
                        DoctorNotes, 
                        Inpatient
                    ).join(
                        Inpatient,
                        DoctorNotes.patient_id == Inpatient.id
                    ).filter(
                        DoctorNotes.reminder_time.isnot(None),
                        DoctorNotes.reminder_time <= current_time
                    ).all()

                    for note, inpatient in due_reminders:
                        try:
                            note_data = json.loads(note.note_text)[0]
                            # Show popup for each due reminder
                            show_reminder_popup(
                                inpatient.patient_name,
                                note_data.get('text', ''),
                                inpatient.room_number
                            )
                            # Clear the reminder time after showing
                            note.reminder_time = None
                            session.commit()
                        except Exception as e:
                            session.rollback()
                            print(f"Error processing reminder: {str(e)}")
                            continue

                except Exception as e:
                    session.rollback()
                    print(f"Error in reminder check: {str(e)}")
                
                finally:
                    # Always close the session
                    session.close()

            except Exception as e:
                print(f"Critical error in reminder checker: {str(e)}")
            
            # Wait for 1 minute before checking again
            time.sleep(60)

# Make sure to pass the app instance to the thread
def start_reminder_checker(app):
    reminder_thread = threading.Thread(target=check_reminders, args=(app,), daemon=True)
    reminder_thread.start()

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # Get total counts
    patients_count = db.session.query(Patient).count()
    op_records_count = db.session.query(OPRecord).count()
    inpatients_count = db.session.query(Inpatient).count()
    appointments_count = db.session.query(Appointment).count()
    doctors_count = db.session.query(Doctor).count()
    staff_count = db.session.query(Staff).count()
    discharged_count = db.session.query(DischargedPatient).count()

    # Calculate revenue (assuming 10000 is the target)
    revenue = 4800  # Example static value
    max_revenue = 10000
    revenue_percentage = min((revenue/max_revenue) * 100, 100)

    # Get monthly data for charts
    current_year = datetime.now().year
    monthly_ops = db.session.query(
        db.func.strftime('%m', OPRecord.visit_date).label('month'),
        db.func.count(OPRecord.id).label('count')
    ).filter(
        db.func.strftime('%Y', OPRecord.visit_date) == str(current_year)
    ).group_by('month').all()

    monthly_ips = db.session.query(
        db.func.strftime('%m', Inpatient.admission_date).label('month'),
        db.func.count(Inpatient.id).label('count')
    ).filter(
        db.func.strftime('%Y', Inpatient.admission_date) == str(current_year)
    ).group_by('month').all()

    # Format data for charts
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    ops_data = [0] * 12
    ips_data = [0] * 12

    for month, count in monthly_ops:
        ops_data[int(month)-1] = count

    for month, count in monthly_ips:
        ips_data[int(month)-1] = count

    return render_template('new_dashboard.html',
                         patients_count=patients_count,
                         op_records_count=op_records_count,
                         inpatients_count=inpatients_count,
                         appointments_count=appointments_count,
                         doctors_count=doctors_count,
                         staff_count=staff_count,
                         discharged_count=discharged_count,
                         revenue=revenue,
                         revenue_percentage=revenue_percentage,
                         months=months,
                         ops_data=ops_data,
                         ips_data=ips_data)



@main.route('/patients', methods=['GET', 'POST'])
def patients():
    if request.method == 'GET':
        # Get filter parameters from request
        sex = request.args.getlist('sex')
        marital_status = request.args.getlist('marital_status')
        search = request.args.get('search', '')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Start with all patients
        query = Patient.query

        # Apply filters
        if sex:
            query = query.filter(Patient.sex.in_(sex))
        if marital_status:
            query = query.filter(Patient.marital_status.in_(marital_status))
        if search:
            query = query.filter(db.or_(
                Patient.firstname.ilike(f'%{search}%'),
                Patient.lastname.ilike(f'%{search}%'),
                Patient.mobile.ilike(f'%{search}%')
            ))
        if start_date:
            query = query.filter(Patient.created_at >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            query = query.filter(Patient.created_at <= datetime.strptime(end_date, '%Y-%m-%d'))

        # Execute query
        patients = query.all()

        # Fetch all doctors
        doctors = Doctor.query.all()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify([patient.to_dict() for patient in patients])
        else:
            return render_template('patients.html', patients=patients, doctors=doctors)
    elif request.method == 'POST':
        # Add new patient
        new_patient = Patient(
            firstname=request.form['firstname'],
            lastname=request.form['lastname'],
            mobile=request.form['mobile'],
            alternate_mobile=request.form.get('alternate_mobile'),
            email=request.form.get('email'),
            sex=request.form.get('sex'),
            age=int(request.form['age']) if request.form.get('age') else None,
            marital_status=request.form.get('marital_status'),
            occupation=request.form.get('occupation'),
            blood_group=request.form.get('blood_group'),
            emergency_contact_person=request.form.get('emergency_contact_person'),
            emergency_contact_number=request.form.get('emergency_contact_number'),
            emergency_contact_relation=request.form.get('emergency_contact_relation'),
            address=request.form.get('address')
        )
        db.session.add(new_patient)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Patient added successfully'})

@main.route('/patients/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def manage_patient(id):
    if request.method == 'GET':
        patient = Patient.query.get_or_404(id)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify(patient.to_dict())
        else:
            return render_template('patient_details.html', patient=patient)
    elif request.method == 'PUT':
        patient = Patient.query.get_or_404(id)
        try:
            patient.firstname = request.form['firstname']
            patient.lastname = request.form['lastname']
            patient.mobile = request.form['mobile']
            patient.alternate_mobile = request.form.get('alternate_mobile')
            patient.email = request.form.get('email')
            patient.sex = request.form.get('sex')
            patient.age = int(request.form['age']) if request.form.get('age') else None
            patient.marital_status = request.form.get('marital_status')
            patient.occupation = request.form.get('occupation')
            patient.blood_group = request.form.get('blood_group')
            patient.emergency_contact_person = request.form.get('emergency_contact_person')
            patient.emergency_contact_number = request.form.get('emergency_contact_number')
            patient.emergency_contact_relation = request.form.get('emergency_contact_relation')
            patient.address = request.form.get('address')
            db.session.commit()
            return jsonify({'success': True, 'message': 'Patient updated successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400
    elif request.method == 'DELETE':
        patient = Patient.query.get_or_404(id)
        try:
            db.session.delete(patient)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Patient deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400



@main.route('/appointment-management', methods=['GET', 'POST', 'PUT', 'DELETE'])
@main.route('/appointment-management/<int:id>', methods=['PUT', 'DELETE'])
def appointment_management(id=None):
    doctors = Doctor.query.all()  # Fetch all doctors
    if request.method == 'GET':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Create base query
            
            query = db.session.query(Appointment, Doctor.name.label('doctor_name')).join(
                Doctor, Appointment.doctor_id == Doctor.id
            )

            # Apply filters
            search = request.args.get('search', '')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            if search:
                query = query.filter(db.or_(
                    Appointment.patient_name.ilike(f'%{search}%'),
                    Doctor.name.ilike(f'%{search}%')
                ))
            if start_date:
                query = query.filter(Appointment.appointment_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date:
                query = query.filter(Appointment.appointment_date <= datetime.strptime(end_date, '%Y-%m-%d').date())


            appointments = query.all()
            
            
            return jsonify([{
                'id': a.Appointment.id,
                'patient_name': a.Appointment.patient_name,
                'mobile': a.Appointment.mobile,
                'doctor_id': a.Appointment.doctor_id,
                'doctor_name': a.doctor_name,
                'appointment_date': a.Appointment.appointment_date.strftime('%Y-%m-%d'),
                'appointment_time': a.Appointment.appointment_time.strftime('%H:%M'),
                'reason': a.Appointment.reason
            } for a in appointments])
        else:
            return render_template('appointment_management.html', doctors=doctors)
    
    elif request.method == 'POST':
        new_appointment = Appointment(
            patient_name=request.form['patient_name'],
            mobile=request.form['mobile'],
            doctor_id=request.form['doctor'],
            appointment_date=datetime.strptime(request.form['appointment_date'], '%Y-%m-%d').date(),
            appointment_time=datetime.strptime(request.form['appointment_time'], '%H:%M').time(),
            reason=request.form['reason'],
            status=request.form.get('status', 'open')
        )
        db.session.add(new_appointment)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Appointment added successfully'})    
    
    elif request.method == 'PUT':
        appointment_id = request.form.get('id')
        appointment = Appointment.query.get_or_404(appointment_id)
        appointment.patient_name = request.form['patient_name']
        appointment.mobile = request.form['mobile']
        appointment.doctor_id = request.form['doctor']
        appointment.appointment_date = datetime.strptime(request.form['appointment_date'], '%Y-%m-%d').date()
        appointment.appointment_time = datetime.strptime(request.form['appointment_time'], '%H:%M').time()
        appointment.reason = request.form['reason']
        appointment.status = request.form.get('status', appointment.status)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Appointment updated successfully'})    
    
    elif request.method == 'DELETE':
        if id:
            appointment = Appointment.query.get_or_404(id)
            db.session.delete(appointment)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Appointment deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Appointment ID not provided'}), 400








@main.route('/pharmacy')
def pharmacy():
    # The Streamlit app runs on port 8501 by default
    streamlit_url = "http://localhost:8501"
    return render_template('pharmacy.html', streamlit_url=streamlit_url)

@main.route('/insurance')
def insurance():
    return render_template('insurance.html')

@main.route('/discharge')
def discharge():
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        query = DischargedPatient.query

        # Apply filters
        search = request.args.get('search', '')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        if search:
            query = query.filter(DischargedPatient.patient_name.ilike(f'%{search}%'))
        if start_date:
            query = query.filter(DischargedPatient.discharge_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
        if end_date:
            query = query.filter(DischargedPatient.discharge_date <= datetime.strptime(end_date, '%Y-%m-%d').date())

        discharged_patients = query.all()
        return jsonify([patient.to_dict() for patient in discharged_patients])
    else:
        return render_template('discharge.html')

@main.route('/treatment')
def treatment():
    return render_template('treatment.html')

@main.route('/database-editor', methods=['GET', 'POST'])
def database_editor():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    selected_table = request.form.get('table_name') or request.args.get('table_name')
    action = request.form.get('action')
    search_query = request.args.get('search', '')
    
    columns = []
    rows = []
    edit_row = None
    
    if selected_table:
        with db.engine.connect() as connection:
            columns = [column['name'] for column in inspector.get_columns(selected_table)]
            
            if action == 'edit':
                row_id = request.form.get('row_id')
                edit_query = f"SELECT * FROM {selected_table} WHERE id = :id"
                edit_result = connection.execute(text(edit_query), {'id': row_id})
                edit_row = edit_result.fetchone()._asdict()
            
            elif action == 'save':
                row_id = request.form.get('row_id')
                update_values = ", ".join([f"{column} = :{column}" for column in columns if column != 'id'])
                update_query = f"UPDATE {selected_table} SET {update_values} WHERE id = :id"
                update_data = {column: request.form.get(column) for column in columns if column != 'id'}
                update_data['id'] = row_id
                connection.execute(text(update_query), update_data)
                flash('Row updated successfully!', 'success')
            
            elif action == 'delete':
                row_id = request.form.get('row_id')
                delete_query = f"DELETE FROM {selected_table} WHERE id = :id"
                connection.execute(text(delete_query), {'id': row_id})
                flash('Row deleted successfully!', 'success')
            
            query = f"SELECT * FROM {selected_table}"
            if search_query:
                search_conditions = " OR ".join([f"{column} LIKE :search" for column in columns])
                query += f" WHERE {search_conditions}"
            
            result = connection.execute(text(query), {'search': f'%{search_query}%'})
            rows = [row._asdict() for row in result]
    
    return render_template('database_editor.html', 
                           tables=tables, 
                           selected_table=selected_table, 
                           columns=columns, 
                           rows=rows, 
                           search_query=search_query,
                           edit_row=edit_row)

@main.route('/doctors', methods=['GET', 'POST'])
def doctors():
    if request.method == 'POST':
        # Handle adding a new doctor
        new_doctor = Doctor(
            name=request.form['name'],
            phone=request.form['phone'],
            sex=request.form['sex']
        )
        db.session.add(new_doctor)
        db.session.commit()
        flash('Doctor added successfully!', 'success')
        return redirect(url_for('main.doctors'))

    # Fetch all doctors
    doctors = Doctor.query.all()
    return render_template('doctors.html', doctors=doctors)

@main.route('/doctors/<int:id>', methods=['PUT', 'DELETE'])
def doctor(id):
    doctor = Doctor.query.get_or_404(id)
    
    if request.method == 'PUT':
        # Handle updating a doctor
        doctor.name = request.form['name']
        doctor.phone = request.form['phone']
        doctor.sex = request.form['sex']
        db.session.commit()
        return jsonify({'success': True, 'message': 'Doctor updated successfully'})
    
    elif request.method == 'DELETE':
        # Handle deleting a doctor
        db.session.delete(doctor)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Doctor deleted successfully'})

@main.route('/appointment-management/<int:id>', methods=['GET'])
def get_appointment(id):
    appointment = Appointment.query.get_or_404(id)
    doctor = Doctor.query.get(appointment.doctor_id)
    return jsonify({
        'id': appointment.id,
        'patient_name': appointment.patient_name,
        'mobile': appointment.mobile,
        'doctor_id': appointment.doctor_id,
        'doctor_name': doctor.name if doctor else None,
        'appointment_date': appointment.appointment_date.strftime('%Y-%m-%d'),
        'appointment_time': appointment.appointment_time.strftime('%H:%M'),
        'reason': appointment.reason
    })

@main.route('/op-management', methods=['GET', 'POST'])
@main.route('/op-management/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def op_management(id=None):
    doctors = Doctor.query.all()
    patients = Patient.query.all()  # Add this line
    
    if request.method == 'GET':
        if id:
            # Fetch a single OP record by ID
            op_record = OPRecord.query.get_or_404(id)
            return jsonify(op_record.to_dict())
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Handle AJAX request to fetch all OP records
            try:
                query = OPRecord.query.join(Patient).join(Doctor)

                # Apply filters
                status = request.args.getlist('status')
                search = request.args.get('search', '')
                start_date = request.args.get('start_date')
                end_date = request.args.get('end_date')

                if status:
                    query = query.filter(OPRecord.status.in_(status))
                if search:
                    query = query.filter(db.or_(
                        Patient.firstname.ilike(f'%{search}%'),
                        Patient.lastname.ilike(f'%{search}%'),
                        OPRecord.op_id.ilike(f'%{search}%'),
                        Patient.mobile.ilike(f'%{search}%')
                    ))
                if start_date:
                    query = query.filter(OPRecord.visit_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
                if end_date:
                    query = query.filter(OPRecord.visit_date <= datetime.strptime(end_date, '%Y-%m-%d').date())

                op_records = query.all()
                return jsonify([record.to_dict() for record in op_records])
            except Exception as e:
                print(f"Error fetching OP records: {str(e)}")
                return jsonify({'error': 'An error occurred while fetching OP records'}), 500
        else:
            # Render the OP Management page with the list of doctors
            return render_template('op_management.html', doctors=doctors,patients=patients)
    
    elif request.method == 'POST':
        # Add a new OP record
        try:
            patient_id = request.form['patient_id']
            new_op_record = OPRecord(
                op_id=OPRecord.generate_op_id(),
                patient_id=patient_id,
                doctor_id=int(request.form['doctor_id']),
                visit_date=datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date(),
                reason=request.form.get('reason'),
                status=request.form['status']
            )
            db.session.add(new_op_record)
            db.session.commit()
            return jsonify({'success': True, 'message': 'OP record added successfully'})
        except Exception as e:
            db.session.rollback()
            print(f"Error adding OP record: {str(e)}")
            return jsonify({'error': 'An error occurred while adding the OP record'}), 500
    
    elif request.method == 'PUT':
        # Update an existing OP record
        op_record = OPRecord.query.get_or_404(id)
        op_record.patient_id = request.form['patient_id']
        op_record.doctor_id = int(request.form['doctor_id'])
        op_record.visit_date = datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date()
        op_record.reason = request.form.get('reason')
        op_record.status = request.form['status']
        db.session.commit()
        return jsonify({'success': True, 'message': 'OP record updated successfully'})
    
    elif request.method == 'DELETE':
        # Delete an OP record
        op_record = OPRecord.query.get_or_404(id)
        db.session.delete(op_record)
        db.session.commit()
        return jsonify({'success': True, 'message': 'OP record deleted successfully'})

@main.route('/search-patients')
def search_patients():
    query = request.args.get('q', '')
    patients = Patient.query.filter(
        db.or_(
            Patient.firstname.ilike(f'%{query}%'),
            Patient.lastname.ilike(f'%{query}%')
        )
    ).limit(10).all()
    return jsonify([{
        'id': patient.id,
        'firstname': patient.firstname,
        'lastname': patient.lastname
    } for patient in patients])

@main.route('/inpatient-management', methods=['GET', 'POST'])
@main.route('/inpatient-management/<int:id>', methods=['GET', 'PUT', 'DELETE'])
def inpatient_management(id=None):
    doctors = Doctor.query.all()
    
    if request.method == 'GET':
        if id:
            inpatient = Inpatient.query.get_or_404(id)
            # Get the latest doctor note for this patient
            doctor_note = DoctorNotes.query.filter_by(patient_id=id).order_by(DoctorNotes.id.desc()).first()
            return jsonify({
                'id': inpatient.id,
                'patient_name': inpatient.patient_name,
                'room_number': inpatient.room_number,
                'doctor_id': inpatient.doctor_id,
                'doctor_name': inpatient.doctor.name if inpatient.doctor else None,
                'admission_date': inpatient.admission_date.strftime('%Y-%m-%d'),
                'diagnosis': inpatient.diagnosis,
                'doctor_note': doctor_note.note_text if doctor_note else None
            })
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            query = Inpatient.query

            # Apply filters
            search = request.args.get('search', '')
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            if search:
                query = query.filter(db.or_(
                    Inpatient.patient_name.ilike(f'%{search}%'),
                    Inpatient.room_number.ilike(f'%{search}%')
                ))
            if start_date:
                query = query.filter(Inpatient.admission_date >= datetime.strptime(start_date, '%Y-%m-%d').date())
            if end_date:
                query = query.filter(Inpatient.admission_date <= datetime.strptime(end_date, '%Y-%m-%d').date())

            inpatients = query.all()
            result = []
            for inpatient in inpatients:
                data = inpatient.to_dict()
                # Get the latest doctor note for each patient
                doctor_note = DoctorNotes.query.filter_by(patient_id=inpatient.id).order_by(DoctorNotes.id.desc()).first()
                data['doctor_note'] = doctor_note.note_text if doctor_note else None
                result.append(data)
            return jsonify(result)
        else:
            return render_template('inpatient_management.html', doctors=doctors)
    
    elif request.method == 'POST':
        try:
            new_inpatient = Inpatient(
                patient_name=request.form['patient_name'],
                room_number=request.form['room_number'],
                doctor_id=int(request.form['doctor']),
                admission_date=datetime.strptime(request.form['admission_date'], '%Y-%m-%d').date(),
                diagnosis=request.form.get('diagnosis', '')
            )
            db.session.add(new_inpatient)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Inpatient admitted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 400
    
    elif request.method == 'PUT':
        inpatient = Inpatient.query.get_or_404(id)
        inpatient.patient_name = request.form['patient_name']
        inpatient.room_number = request.form['room_number']
        inpatient.doctor_id = int(request.form['doctor'])
        inpatient.admission_date = datetime.strptime(request.form['admission_date'], '%Y-%m-%d').date()
        inpatient.diagnosis = request.form.get('diagnosis')
        db.session.commit()
        return jsonify({'success': True, 'message': 'Inpatient updated successfully'})
    
    elif request.method == 'DELETE':
        inpatient = Inpatient.query.get_or_404(id)
        db.session.delete(inpatient)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Inpatient discharged successfully'})

@main.route('/staff', methods=['GET', 'POST'])
def staff():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # Handle adding a new staff member
            new_staff = Staff(
                name=request.form['name'],
                phone=request.form['phone'],
                sex=request.form['sex'],
                role=request.form['role']
            )
            db.session.add(new_staff)
            db.session.commit()
            flash('Staff member added successfully!', 'success')
        
        elif action == 'edit':
            # Handle editing an existing staff member
            staff_id = request.form['staff_id']
            staff_member = Staff.query.get_or_404(staff_id)
            staff_member.name = request.form['name']
            staff_member.phone = request.form['phone']
            staff_member.sex = request.form['sex']
            staff_member.role = request.form['role']
            db.session.commit()
            flash('Staff member updated successfully!', 'success')
        
        elif action == 'delete':
            # Handle deleting a staff member
            staff_id = request.form['staff_id']
            staff_member = Staff.query.get_or_404(staff_id)
            db.session.delete(staff_member)
            db.session.commit()
            flash('Staff member deleted successfully!', 'success')
        
        return redirect(url_for('main.staff'))

    # GET request: display staff list
    staff_members = Staff.query.all()
    return render_template('staff.html', staff_members=staff_members)

@main.route('/inpatient-management/<int:id>/discharge', methods=['POST'])
def discharge_inpatient(id):
    try:
        inpatient = Inpatient.query.get_or_404(id)
        discharge_date = datetime.strptime(request.json['discharge_date'], '%Y-%m-%d').date()

        # Create discharged patient record
        discharged_patient = DischargedPatient(
            patient_name=inpatient.patient_name,
            room_number=inpatient.room_number,
            doctor_id=inpatient.doctor_id,
            admission_date=inpatient.admission_date,
            discharge_date=discharge_date,
            diagnosis=inpatient.diagnosis
        )

        # Delete doctor notes first (to handle CASCADE properly)
        DoctorNotes.query.filter_by(patient_id=id).delete()
        
        # Add discharged patient and remove from inpatients
        db.session.add(discharged_patient)
        db.session.delete(inpatient)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Patient discharged successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/op-management/<int:id>/status', methods=['PUT'])
def update_op_record_status(id):
    try:
        op_record = OPRecord.query.get_or_404(id)
        data = request.json
        op_record.status = data['status']
        db.session.commit()
        return jsonify({'success': True, 'message': 'Status updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/admit-inpatient/<int:patient_id>', methods=['POST'])
def admit_inpatient(patient_id):
    try:
        patient = Patient.query.get_or_404(patient_id)
        data = request.form
        
        if not data.get('room_number') or not data.get('doctor_id'):
            return jsonify({'success': False, 'message': 'Room number and doctor are required'}), 400

        new_inpatient = Inpatient(
            patient_name=f"{patient.firstname} {patient.lastname}",
            room_number=data['room_number'],
            doctor_id=int(data['doctor_id']),
            admission_date=datetime.now().date(),
            diagnosis=data.get('diagnosis', '')
        )
        db.session.add(new_inpatient)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Patient admitted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/generate-patient-report/<int:patient_id>', methods=['GET'])
def generate_patient_report(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    op_record = OPRecord.query.filter_by(patient_id=patient_id).order_by(OPRecord.visit_date.desc()).first()

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica", 12)

    # Add content to the PDF
    p.drawString(100, 750, f"Patient Name: {patient.firstname} {patient.lastname}")
    p.drawString(100, 730, f"Sex: {patient.sex}")
    p.drawString(100, 710, f"Age: {patient.age or 'Not provided'}")
    
    if op_record:
        p.drawString(100, 690, f"OP ID: {op_record.op_id}")
        p.drawString(100, 670, f"OP Doctor: {op_record.doctor.name}")
        visit_date = op_record.visit_date.strftime('%d %B %Y')
        p.drawString(100, 650, f"OP Visit Date: {visit_date}")
        valid_till = (op_record.visit_date + timedelta(days=15)).strftime('%d %B %Y')
        p.drawString(100, 630, f"Valid Till: {valid_till}")
    else:
        p.drawString(100, 690, "OP ID: Not available")
        p.drawString(100, 670, "OP Doctor: Not available")
        p.drawString(100, 650, "OP Visit Date: Not available")
        p.drawString(100, 630, "Valid Till: Not available")

    # Add a line separator after OP information
    

    p.drawString(100, 610, f"Mobile No.: {patient.mobile}")
    p.drawString(100, 590, f"Address: {patient.address or 'Not provided'}")

    # Add a final line separator
    p.line(100, 580, 500, 580)

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"patient_report_{patient_id}.pdf",
        mimetype='application/pdf'
    )

@main.route('/add-patient-and-op', methods=['POST'])
def add_patient_and_op():
    try:
        # Extract patient data
        patient_data = {
            'firstname': request.form['firstname'],
            'lastname': request.form['lastname'],
            'mobile': request.form['mobile'],
            'alternate_mobile': request.form.get('alternate_mobile'),
            'email': request.form.get('email'),
            'sex': request.form['sex'],
            'age': int(request.form['age']),
            'address': request.form.get('address')
        }
        
        # Create new patient
        new_patient = Patient(**patient_data)
        db.session.add(new_patient)
        db.session.flush()  # This will assign an ID to the new patient
        
        # Extract OP record data
        op_data = {
            'patient_id': new_patient.id,
            'doctor_id': request.form['doctor_id'],
            'visit_date': datetime.strptime(request.form['visit_date'], '%Y-%m-%d').date(),  # Convert string to date object
            'reason': request.form.get('reason'),
            'status': request.form['status']
        }
        
        # Create new OP record
        new_op_record = OPRecord(**op_data)
        new_op_record.op_id = OPRecord.generate_op_id()  # Generate a unique OP ID
        db.session.add(new_op_record)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Patient and OP record added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@main.route('/inpatient-management/<int:patient_id>/update-note', methods=['POST'])
def update_inpatient_note(patient_id):
    try:
        data = request.json
        note_text = data.get('note_text')
        reminder_time = data.get('reminder_time')
        
        # Get the existing note
        note = DoctorNotes.query.filter_by(patient_id=patient_id).first()
        
        if note:
            # Update existing note
            note.note_text = note_text
            if reminder_time:
                note.reminder_time = datetime.fromisoformat(reminder_time)
            else:
                note.reminder_time = None
        else:
            # Create new note
            note = DoctorNotes(
                patient_id=patient_id,
                note_text=note_text,
                reminder_time=datetime.fromisoformat(reminder_time) if reminder_time else None
            )
            db.session.add(note)
        
        db.session.commit()
        
        # Parse the notes to return them with IDs
        notes = []
        try:
            parsed_notes = json.loads(note_text)
            for note_data in parsed_notes:
                notes.append({
                    'text': note_data.get('text', ''),
                    'datetime': note_data.get('datetime', ''),
                    'reminder_time': note_data.get('reminder_time'),
                    'note_id': note_data.get('note_id')
                })
        except json.JSONDecodeError:
            pass
        
        return jsonify({
            'success': True,
            'notes': notes,
            'message': 'Notes updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating notes: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@main.route('/get-reminders')
def get_reminders():
    print("\n[DEBUG] /get-reminders route accessed")
    try:
        current_time = datetime.utcnow()
        print(f"[DEBUG] Current time: {current_time}")
        
        # Query for notes with non-null reminder_time
        notes = db.session.query(
            DoctorNotes,
            Inpatient
        ).join(
            Inpatient,
            DoctorNotes.patient_id == Inpatient.id
        ).filter(
            DoctorNotes.reminder_time.isnot(None),
            DoctorNotes.reminder_time >= current_time
        ).all()
        
        print(f"[DEBUG] Found {len(notes)} notes with reminders")
        
        reminder_data = []
        for note, inpatient in notes:
            try:
                print(f"\n[DEBUG] Processing note ID: {note.id}")
                note_data = json.loads(note.note_text)[0]
                reminder_time = note.reminder_time
                
                is_upcoming = (reminder_time - current_time).total_seconds() <= 86400
                
                reminder_info = {
                    'id': note.id,
                    'patient_name': inpatient.patient_name,
                    'note_text': note_data.get('text', ''),
                    'reminder_time': format_datetime(reminder_time.isoformat()),
                    'is_upcoming': is_upcoming,
                    'room_number': inpatient.room_number
                }
                
                print(f"[DEBUG] Processed reminder: {reminder_info}")
                reminder_data.append(reminder_info)
                
            except Exception as e:
                print(f"[ERROR] Error processing note {note.id}: {str(e)}")
                continue
        
        response_data = {
            'count': len(reminder_data),
            'reminders': reminder_data
        }
        print(f"\n[DEBUG] Sending response: {json.dumps(response_data, indent=2)}")
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"[ERROR] Error in get_reminders: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@main.route('/inpatient-management/<int:id>/notes', methods=['GET'])
def get_patient_notes(id):
    try:
        # Get all notes for this patient
        notes = DoctorNotes.query.filter_by(patient_id=id).order_by(DoctorNotes.id).all()
        
        all_notes = []
        for note in notes:
            try:
                note_data = json.loads(note.note_text)[0]  # Get the note data
                note_data['note_id'] = note.id
                note_data['reminder_time'] = note.reminder_time.isoformat() if note.reminder_time else None
                all_notes.append(note_data)
            except (json.JSONDecodeError, IndexError):
                continue
                
        return jsonify({
            'success': True,
            'notes': all_notes
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@main.route('/test-reminder')
def test_reminder():
    print("[DEBUG] Test reminder route accessed")
    return jsonify({"message": "Test successful"})

@main.route('/update-reminder/<int:note_id>/snooze', methods=['POST'])
def snooze_reminder(note_id):
    try:
        note = DoctorNotes.query.get_or_404(note_id)
        # Add 15 minutes to the current reminder time
        note.reminder_time = note.reminder_time + timedelta(minutes=15)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main.route('/update-reminder/<int:note_id>/delete', methods=['POST'])
def delete_reminder(note_id):
    try:
        note = DoctorNotes.query.get_or_404(note_id)
        # Set reminder_time to None instead of deleting the note
        note.reminder_time = None
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
    

@main.route('/connetreminders')
def connectreminders():
    try:
        current_time = datetime.utcnow()
        
        # Query for notes with non-null reminder_time
        notes = db.session.query(
            DoctorNotes,
            Inpatient
        ).join(
            Inpatient,
            DoctorNotes.patient_id == Inpatient.id
        ).filter(
            DoctorNotes.reminder_time.isnot(None),
            DoctorNotes.reminder_time >= current_time
        ).order_by(DoctorNotes.reminder_time).all()
        
        reminders = []
        for note, inpatient in notes:
            try:
                note_data = json.loads(note.note_text)[0]
                reminder_time = note.reminder_time
                
                # Calculate priority based on time difference
                time_diff = (reminder_time - current_time).total_seconds()
                if time_diff <= 3600:  # Within 1 hour
                    priority = "high"
                elif time_diff <= 86400:  # Within 24 hours
                    priority = "medium"
                else:
                    priority = "low"
                
                reminder_info = {
                    "id": str(note.id),
                    "title": f"Patient: {inpatient.patient_name}",
                    "description": note_data.get('text', ''),
                    "datetime": reminder_time.isoformat(),
                    "priority": priority
                }
                
                reminders.append(reminder_info)
                
            except Exception as e:
                print(f"[ERROR] Error processing note {note.id}: {str(e)}")
                continue
        
        return jsonify({
            "status": "success",
            "reminders": reminders
        })
        
    except Exception as e:
        print(f"[ERROR] Error in get_reminders: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500  

@main.route('/delete-doctor-note', methods=['POST'])
def delete_doctor_note():
    try:
        data = request.json
        note_id = data.get('note_id')
        patient_id = data.get('patient_id')
        
        if patient_id:
            # Delete all notes for a patient
            DoctorNotes.query.filter_by(patient_id=patient_id).delete()
            message = 'All notes deleted for patient'
        elif note_id:
            # Delete specific note
            note = DoctorNotes.query.get_or_404(note_id)
            db.session.delete(note)
            message = 'Note deleted successfully'
        else:
            return jsonify({
                'success': False,
                'message': 'Either note_id or patient_id is required'
            }), 400
            
        db.session.commit()
        return jsonify({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting note: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@main.route('/chat')
def chat():
    # Get database schema info for the chat interface
    tables_info = {
        'Patient': {
            'count': db.session.query(Patient).count(),
            'columns': [column.name for column in Patient.__table__.columns]
        },
        'Doctor': {
            'count': db.session.query(Doctor).count(),
            'columns': [column.name for column in Doctor.__table__.columns]
        },
        'Appointment': {
            'count': db.session.query(Appointment).count(),
            'columns': [column.name for column in Appointment.__table__.columns]
        },
        'OPRecord': {
            'count': db.session.query(OPRecord).count(),
            'columns': [column.name for column in OPRecord.__table__.columns]
        },
        'Inpatient': {
            'count': db.session.query(Inpatient).count(),
            'columns': [column.name for column in Inpatient.__table__.columns]
        },
        'Staff': {
            'count': db.session.query(Staff).count(),
            'columns': [column.name for column in Staff.__table__.columns]
        }
    }
    
    return render_template('chat.html', tables_info=tables_info)

@main.route('/chat/query', methods=['POST'])
def chat_query():
    try:
        question = request.json.get('question')
        
        # Initialize Gemini (you'll need to move the Gemini setup to a proper config)
        genai.configure(api_key="AIzaSyBoUqeC-oQDQQWMe5-Vcmd17RoGw8qqZVM")
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.1,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
        )

        # Generate and execute SQL query
        # (You'll need to implement proper SQL safety checks)
        sql_query = model.generate_content(f"Convert to SQL: {question}").text
        result = db.session.execute(text(sql_query))
        data = [dict(row) for row in result]

        # Format response
        response = model.generate_content(f"Question: {question}\nData: {data}").text

        return jsonify({
            'sql_query': sql_query,
            'data': data[:4],  # First 4 rows
            'response': response
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/appointment-management/<int:id>/status', methods=['PUT'])
def update_appointment_status(id):
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Invalid content type, expected JSON'}), 400
    
    try:
        appointment = Appointment.query.get_or_404(id)
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'success': False, 'message': 'Status field is required'}), 400
            
        appointment.status = data['status']
        db.session.commit()
        return jsonify({'success': True, 'message': 'Status updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400




























