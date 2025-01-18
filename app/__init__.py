from flask import Flask
from flask_session import Session
import os

def create_app():
    app = Flask(__name__)

    # Postavi osnovne postavke
    app.config['SECRET_KEY'] = os.urandom(24).hex()

    # Postavi sesijske postavke
    app.config['SESSION_TYPE'] = 'filesystem'  # Sesije će biti spremljene na datotečnom sustavu
    app.config['SESSION_PERMANENT'] = False  # Sesija će isteći kada se preglednik zatvori
    Session(app)  # Inicijaliziraj Flask-Session

    # Registracija ruta
    from .routes import main
    app.register_blueprint(main)

    return app
