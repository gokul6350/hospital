from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .models import db

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = '1234567890abcdef1234567890abcdef'  # Add this line for flash messages

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from .routes import main
    app.register_blueprint(main)

    return app