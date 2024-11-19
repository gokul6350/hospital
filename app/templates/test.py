from datetime import datetime
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import sqlite3

def format_datetime(dt_str):
    """Convert ISO datetime string to human readable format"""
    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    return dt.strftime("%B %d, %Y at %I:%M %p")  # Example: November 25, 2023 at 01:20 PM

def get_reminders():
    try:
        # Connect to your SQLite database
        conn = sqlite3.connect('instance/hospital.db')
        cursor = conn.cursor()
        
        current_time = datetime.utcnow()
        
        # Query to get reminders from doctor_notes
        query = """
        SELECT 
            d.id,
            d.note_text,
            d.reminder_time,
            i.patient_name,
            i.room_number
        FROM doctor_notes d
        JOIN inpatient2 i ON d.patient_id = i.id
        WHERE d.reminder_time IS NOT NULL
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        reminders = []
        for row in rows:
            try:
                note_id, note_text, reminder_time, patient_name, room_number = row
                
                # Parse the JSON note_text
                note_data = json.loads(note_text)[0]
                
                # Convert reminder_time string to datetime if it's not None
                if reminder_time:
                    reminder_time = datetime.fromisoformat(reminder_time.replace('Z', '+00:00'))
                    
                    # Only include future reminders
                    if reminder_time >= current_time:
                        is_upcoming = (reminder_time - current_time).total_seconds() <= 86400  # 24 hours
                        
                        reminders.append({
                            'id': note_id,
                            'patient_name': patient_name,
                            'note_text': note_data.get('text', ''),
                            'reminder_time': format_datetime(reminder_time.isoformat()),  # Format the datetime
                            'is_upcoming': is_upcoming,
                            'room_number': room_number
                        })
                
            except (json.JSONDecodeError, IndexError, KeyError, ValueError) as e:
                print(f"Error processing note {note_id}: {str(e)}")
                continue
        
        # Sort reminders by time
        reminders.sort(key=lambda x: datetime.strptime(x['reminder_time'], "%B %d, %Y at %I:%M %p"))
        
        return {
            'count': len(reminders),
            'reminders': reminders
        }
        
    except Exception as e:
        print(f"Database error: {str(e)}")
        return {'count': 0, 'reminders': []}
        
    finally:
        cursor.close()
        conn.close()

# Test the function
if __name__ == "__main__":
    result = get_reminders()
    print("\nTotal Reminders:", result['count'])
    print("\nReminders:")
    for reminder in result['reminders']:
        print("\n-------------------")
        print(f"Patient: {reminder['patient_name']}")
        print(f"Room: {reminder['room_number']}")
        print(f"Note: {reminder['note_text']}")
        print(f"Due: {reminder['reminder_time']}")  # Will now show like "November 25, 2023 at 01:20 PM"
        print(f"Upcoming: {'Yes' if reminder['is_upcoming'] else 'No'}")