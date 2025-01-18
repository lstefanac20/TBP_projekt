from flask import Flask
from flask_session import Session
import os

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.urandom(24).hex()

    app.config['SESSION_TYPE'] = 'filesystem' 
    app.config['SESSION_PERMANENT'] = False  
    Session(app)
    
    # Registracija ruta
    from .routes import main
    app.register_blueprint(main)

    return app
