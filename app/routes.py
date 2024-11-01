from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from .models import db, Patient, Appointment, Doctor, OPRecord, Inpatient, Staff, DischargedPatient
from datetime import datetime, date, timedelta
from sqlalchemy import inspect, text
import csv
import json
from sqlalchemy.orm import aliased
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO


main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('dashboard.html')



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
            # Use a join to get the doctor's name
            doctor_alias = aliased(Doctor)
            appointments = db.session.query(Appointment, doctor_alias.name.label('doctor_name')).join(
                doctor_alias, Appointment.doctor_id == doctor_alias.id
            ).all()
            
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
            reason=request.form['reason']
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
            return jsonify(inpatient.to_dict())
        
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
            return jsonify([inpatient.to_dict() for inpatient in inpatients])
        else:
            return render_template('inpatient_management.html', doctors=doctors)
    
    elif request.method == 'POST':
        new_inpatient = Inpatient(
            patient_name=request.form['patient_name'],
            room_number=request.form['room_number'],
            doctor_id=int(request.form['doctor']),
            admission_date=datetime.strptime(request.form['admission_date'], '%Y-%m-%d').date(),
            diagnosis=request.form.get('diagnosis')
        )
        db.session.add(new_inpatient)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Inpatient admitted successfully'})
    
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
    inpatient = Inpatient.query.get_or_404(id)
    discharge_date = datetime.strptime(request.json['discharge_date'], '%Y-%m-%d').date()

    discharged_patient = DischargedPatient(
        patient_name=inpatient.patient_name,
        room_number=inpatient.room_number,
        doctor_id=inpatient.doctor_id,
        admission_date=inpatient.admission_date,
        discharge_date=discharge_date,
        diagnosis=inpatient.diagnosis
    )

    db.session.add(discharged_patient)
    db.session.delete(inpatient)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Patient discharged successfully'})

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






















