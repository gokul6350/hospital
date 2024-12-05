from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .models import db
import threading
import tkinter as tk
from extension.reminder_app import ReminderApp

def start_reminder_app():
    root = tk.Tk()
    app = ReminderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = '1234567890abcdef1234567890abcdef'

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from .routes import main
    app.register_blueprint(main)

    # Start reminder app in a separate thread
    reminder_thread = threading.Thread(target=start_reminder_app, daemon=True)
    reminder_thread.start()

    return app