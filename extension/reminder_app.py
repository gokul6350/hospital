import tkinter as tk
from tkinter import ttk
import requests
from datetime import datetime, timedelta
import threading
import time
from tkinter import messagebox
from flask import Flask, jsonify, request
import winsound
import os

# Create Flask app for debug server
debug_app = Flask(__name__)
debug_reminders = []  # Store debug reminders in memory

@debug_app.route('/connetreminders', methods=['GET', 'POST'])
def handle_reminders():
    if request.method == 'POST':
        reminder = request.json
        debug_reminders.append(reminder)
        print(f"[DEBUG] Added new reminder: {reminder}")
        return jsonify({"status": "success"})
    else:
        print(f"[DEBUG] Returning {len(debug_reminders)} debug reminders")
        return jsonify({"reminders": debug_reminders})

def run_debug_server():
    print("[DEBUG] Starting debug server on port 8000...")
    debug_app.run(port=8000)

class ReminderPopup:
    def __init__(self, parent, title, description):
        self.top = tk.Toplevel(parent)
        self.top.title("Reminder Due!")
        self.top.geometry("300x200")
        self.top.lift()  # Bring window to front
        self.top.focus_force()  # Force focus
        
        # Make window stay on top
        self.top.attributes('-topmost', True)
        
        # Center the window
        self.center_window()
        
        # Sound playing flag
        self.playing_sound = True
        
        # Start sound in separate thread
        self.sound_thread = threading.Thread(target=self.play_sound_loop)
        self.sound_thread.daemon = True
        self.sound_thread.start()
        
        # Create widgets
        ttk.Label(self.top, text="Reminder Due!", font=('Helvetica', 12, 'bold')).pack(pady=10)
        ttk.Label(self.top, text=f"Title: {title}").pack(pady=5)
        ttk.Label(self.top, text=f"Description: {description}", wraplength=250).pack(pady=5)
        
        # OK button
        ttk.Button(self.top, text="OK", command=self.on_ok).pack(pady=20)
        
        # Handle window close button
        self.top.protocol("WM_DELETE_WINDOW", self.on_ok)
    
    def center_window(self):
        """Center the popup window on the screen"""
        self.top.update_idletasks()
        width = self.top.winfo_width()
        height = self.top.winfo_height()
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f'{width}x{height}+{x}+{y}')
    
    def play_sound_loop(self):
        """Play sound in a loop until window is closed"""
        sound_file = os.path.join(os.path.dirname(__file__), "tone.wav")
        while self.playing_sound:
            try:
                # Use SND_ASYNC to play sound asynchronously
                winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
                # Wait a bit before checking if we should continue
                for _ in range(10):  # Check every 0.1 seconds
                    if not self.playing_sound:
                        # Stop the current sound
                        winsound.PlaySound(None, winsound.SND_PURGE)
                        return
                    time.sleep(0.1)
            except:
                break
    
    def on_ok(self):
        """Handle OK button click"""
        self.playing_sound = False
        # Stop any currently playing sound
        winsound.PlaySound(None, winsound.SND_PURGE)
        self.top.destroy()

class ReminderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Reminder App")
        self.root.geometry("600x400")
        
        # Refresh interval (in seconds)
        self.refresh_interval = 60
        self.refresh_var = tk.StringVar(value=str(self.refresh_interval))
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Add current time display at the top
        self.time_frame = ttk.Frame(self.main_frame)
        self.time_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.current_time_label = ttk.Label(self.time_frame, text="Current Time: ")
        self.current_time_label.grid(row=0, column=0, padx=5)
        
        self.time_display = ttk.Label(self.time_frame, text="")
        self.time_display.grid(row=0, column=1, padx=5)
        
        # Settings frame
        self.settings_frame = ttk.LabelFrame(self.main_frame, text="Settings", padding="5")
        self.settings_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Refresh interval setting
        ttk.Label(self.settings_frame, text="Refresh Interval (seconds):").grid(row=0, column=0, padx=5)
        self.refresh_entry = ttk.Entry(self.settings_frame, textvariable=self.refresh_var, width=10)
        self.refresh_entry.grid(row=0, column=1, padx=5)
        
        # Refresh button
        self.refresh_btn = ttk.Button(self.settings_frame, text="Refresh Now", command=self.refresh_reminders)
        self.refresh_btn.grid(row=0, column=2, padx=5)
        
        # Add debug mode toggle in settings frame
        self.debug_mode = tk.BooleanVar(value=False)
        self.debug_toggle = ttk.Checkbutton(
            self.settings_frame, 
            text="Debug Mode (Port 8000)", 
            variable=self.debug_mode,
            command=self.refresh_reminders
        )
        self.debug_toggle.grid(row=0, column=3, padx=5)
        
        # Start debug server when debug mode is enabled
        self.debug_server_thread = None
        self.debug_mode.trace_add('write', self.handle_debug_mode_change)
        
        # Reminders display
        self.reminder_frame = ttk.LabelFrame(self.main_frame, text="Upcoming Reminders", padding="5")
        self.reminder_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # Reminder text widget
        self.reminder_text = tk.Text(self.reminder_frame, wrap=tk.WORD, height=15)
        self.reminder_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        self.scrollbar = ttk.Scrollbar(self.reminder_frame, orient=tk.VERTICAL, command=self.reminder_text.yview)
        self.scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.reminder_text['yscrollcommand'] = self.scrollbar.set
        
        # Start the refresh thread
        self.running = True
        self.refresh_thread = threading.Thread(target=self.auto_refresh)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
        
        # Initial refresh
        self.refresh_reminders()
        
        # Add debug reminder form
        self.debug_frame = ttk.LabelFrame(self.main_frame, text="Debug: Add Test Reminder", padding="5")
        self.debug_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Minutes offset entry
        ttk.Label(self.debug_frame, text="Minutes from now:").grid(row=0, column=0, padx=5)
        self.minutes_var = tk.StringVar(value="1")
        self.minutes_entry = ttk.Entry(self.debug_frame, textvariable=self.minutes_var, width=10)
        self.minutes_entry.grid(row=0, column=1, padx=5)
        
        # Title entry
        ttk.Label(self.debug_frame, text="Title:").grid(row=0, column=2, padx=5)
        self.debug_title_var = tk.StringVar(value="Test Reminder")
        self.title_entry = ttk.Entry(self.debug_frame, textvariable=self.debug_title_var, width=20)
        self.title_entry.grid(row=0, column=3, padx=5)
        
        # Add button
        self.add_btn = ttk.Button(self.debug_frame, text="Add Test Reminder", command=self.add_test_reminder)
        self.add_btn.grid(row=0, column=4, padx=5)
        
    def handle_debug_mode_change(self, *args):
        if self.debug_mode.get():
            print("[DEBUG] Debug mode enabled - starting debug server")
            self.debug_server_thread = threading.Thread(target=run_debug_server)
            self.debug_server_thread.daemon = True
            self.debug_server_thread.start()
        else:
            print("[DEBUG] Debug mode disabled")
    
    def get_server_url(self):
        """Get the appropriate server URL based on debug mode"""
        return 'http://127.0.0.1:8000/connetreminders' if self.debug_mode.get() else 'http://127.0.0.1:5000/connetreminders'
    
    def fetch_reminders(self):
        """Fetch reminders from HTTP endpoint"""
        try:
            # Get reminders from production server
            prod_reminders = {"reminders": []}
            debug_reminders = {"reminders": []}
            
            # Always try production server
            try:
                response = requests.get('http://127.0.0.1:5000/connetreminders', timeout=5)
                prod_reminders = response.json()
            except requests.exceptions.RequestException:
                prod_reminders = {"reminders": []}
            
            # If debug mode is on, also get debug reminders and combine them
            if self.debug_mode.get():
                try:
                    response = requests.get('http://127.0.0.1:8000/connetreminders', timeout=5)
                    debug_reminders = response.json()
                    
                    # Combine both sets of reminders
                    return {
                        "status": "success",
                        "reminders": prod_reminders.get("reminders", []) + debug_reminders.get("reminders", [])
                    }
                except requests.exceptions.RequestException:
                    pass  # If debug server fails, just use production reminders
            
            # Return production reminders if debug mode is off or debug server failed
            return prod_reminders
                
        except Exception as e:
            return {
                "status": "error",
                "reminders": [],
                "message": str(e)
            }
    
    def refresh_reminders(self):
        """Refresh the reminders display"""
        current_time = datetime.now()
        self.time_display.config(text=current_time.strftime('%d %b %Y %I:%M %p'))
        
        reminders = self.fetch_reminders()
        
        self.reminder_text.delete(1.0, tk.END)
        
        if reminders["status"] == "error":
            self.reminder_text.insert(tk.END, f"Error: {reminders['message']}\n")
            return
            
        for reminder in reminders["reminders"]:
            reminder_time = datetime.fromisoformat(reminder["datetime"])
            time_left = reminder_time - current_time
            
            # Get absolute seconds and calculate days/hours/minutes
            total_seconds = abs(time_left.total_seconds())
            days = int(total_seconds // (24 * 3600))
            hours = int((total_seconds % (24 * 3600)) // 3600)
            minutes = int((total_seconds % 3600) // 60)
            
            # Show popup if reminder is due (within the last minute)
            if 0 <= total_seconds <= 60 and time_left.total_seconds() >= 0:
                ReminderPopup(
                    self.root,
                    reminder['title'],
                    reminder['description']
                )
            
            if time_left.total_seconds() < 0:
                time_left_str = f"Overdue by {days} days and {hours} hrs {minutes} min"
            else:
                time_left_str = f"{days} days and {hours} hrs {minutes} min"
            
            display_text = (
                f"Title: {reminder['title']}\n"
                f"Description: {reminder['description']}\n"
                f"Time: {reminder_time.strftime('%d %b %Y %I:%M %p')}\n"
                f"Time Left: {time_left_str}\n"
                f"Priority: {reminder['priority']}\n"
                f"{'-'*50}\n"
            )
            self.reminder_text.insert(tk.END, display_text)
    
    def auto_refresh(self):
        """Auto refresh thread"""
        while self.running:
            try:
                # Get the interval value safely
                interval = int(self.refresh_var.get())
            except:
                interval = self.refresh_interval  # Use default if there's an error
            
            time.sleep(interval)
            # Use after() to schedule the refresh on the main thread
            self.root.after(0, self.refresh_reminders)
    
    def on_closing(self):
        """Clean up before closing"""
        self.running = False
        self.root.destroy()
    
    def add_test_reminder(self):
        """Add a test reminder X minutes from now"""
        try:
            minutes = int(self.minutes_var.get())
            future_time = datetime.now() + timedelta(minutes=minutes)
            
            test_reminder = {
                "title": self.debug_title_var.get(),
                "description": "Debug reminder for testing",
                "datetime": future_time.isoformat(),
                "priority": "medium"
            }
            
            print(f"[DEBUG] Attempting to add test reminder: {test_reminder}")
            
            try:
                response = requests.post(
                    'http://127.0.0.1:8000/connetreminders',
                    json=test_reminder,
                    headers={'Content-Type': 'application/json'},
                    timeout=5
                )
                
                if response.status_code == 200:
                    print("[DEBUG] Successfully added reminder to debug server")
                    messagebox.showinfo("Success", f"Test reminder added to debug server for {future_time.strftime('%d %b %Y %I:%M %p')}")
                    self.refresh_reminders()
                else:
                    print(f"[DEBUG] Server error: {response.status_code}")
                    messagebox.showerror("Error", "Failed to add to debug server")
            except requests.exceptions.ConnectionError:
                print("[DEBUG] Connection error - debug server not running")
                messagebox.showerror("Connection Error", "Cannot connect to debug server (port 8000)")
            except Exception as e:
                print(f"[DEBUG] Error: {str(e)}")
                messagebox.showerror("Error", f"Failed to add reminder: {str(e)}")
                
        except ValueError:
            print("[DEBUG] Invalid minutes value entered")
            messagebox.showerror("Error", "Please enter a valid number of minutes")

if __name__ == "__main__":
    root = tk.Tk()
    app = ReminderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop() 