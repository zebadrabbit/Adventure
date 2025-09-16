from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace-this-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mud.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
socketio = SocketIO(app)

from app.routes import auth, main
app.register_blueprint(auth.bp)
app.register_blueprint(main.bp)

# Import websocket handlers

# Import websocket handlers
from app.websockets import game, lobby

def create_app():
    return app
