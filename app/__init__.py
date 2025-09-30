import json
import logging
import os

from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_session import Session
from authlib.integrations.flask_client import OAuth

import app
from config import Config
from flask_moment import Moment
from flask_wtf import CSRFProtect

# Initialiseer extensies globaal
db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
oauth = OAuth()
csrf = CSRFProtect()
moment = Moment()

# Stel logging in
logger = logging.getLogger(__name__)


# Definieer de user_loader voor Flask-Login
@login.user_loader
def load_user(user_id):
    from app.models import User  # Import hier om circulaire imports te vermijden
    try:
        user = db.session.get(User, int(user_id))
        if not user:
            session.clear()  # Forceer nieuwe login als gebruiker niet bestaat
            logger.debug("Geen gebruiker gevonden voor id, sessie gecleared")
        else:
            logger.debug(f"Gebruiker geladen: {user.name}")
        return user
    except Exception as e:
        logger.error(f"Fout bij laden van gebruiker met id {user_id}: {str(e)}")
        return None


def create_app(config_class=Config):
    """Applicatie factory voor het maken van de Flask app"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configureer sessie-opslag op bestandssysteem (optioneel)
    app.config['SESSION_TYPE'] = 'filesystem'  # Persistente sessies
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'  # Map voor sessiebestanden

    # Initialiseer Flask-Session voor server-side sessiebeheer
    Session(app)

    # Registreer de from_json filter
    def from_json_filter(data):
        return json.loads(data) if data else []

    app.jinja_env.filters['from_json'] = from_json_filter

    # Maak upload-mappen aan voor exercises, videos en profiles
    upload_directories = [
        os.path.abspath(os.path.join('app', 'static', 'img', 'exercises')),
        os.path.abspath(os.path.join('app', 'static', 'videos', 'exercises')),
        os.path.abspath(os.path.join('app', 'static', 'uploads', 'profiles')),  # NIEUW - voor profielfoto's
        os.path.abspath(os.path.join('app', 'static', 'uploads', 'exercises'))  # NIEUW - voor custom exercises
    ]

    for directory in upload_directories:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Upload directory aangemaakt/gecontroleerd: {directory}")

    # Initialiseer extensies met de app
    db.init_app(app)  # Database-ORM
    migrate.init_app(app, db)  # Database-migraties
    moment.init_app(app)  # Tijdformattering
    login.init_app(app)  # Gebruikersauthenticatie
    oauth.init_app(app)  # OAuth voor Auth0
    csrf.init_app(app)  # Activeer CSRF-bescherming

    # Stel login-view in voor Flask-Login
    login.login_view = 'auth.login'  # Verwijs naar de login-route in de auth blueprint

    # Configureer OAuth voor Auth0
    auth0_domain = app.config['AUTH0_DOMAIN']
    oauth.register(
        name='auth0',
        client_id=app.config['AUTH0_CLIENT_ID'],
        client_secret=app.config['AUTH0_CLIENT_SECRET'],
        server_metadata_url=f'https://{auth0_domain}/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid profile email',  # Vraag toegang tot profiel en e-mail
        },
    )

    # Registreer blueprints
    from app.calendar import bp as calendar_bp
    app.register_blueprint(calendar_bp, url_prefix='/calendar')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)  # Geen prefix, voor algemene routes

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.workouts import bp as workouts_bp
    app.register_blueprint(workouts_bp, url_prefix='/workouts')

    from app.sessions import bp as sessions_bp
    app.register_blueprint(sessions_bp, url_prefix='/sessions')

    from app.profile import bp as profile_bp
    app.register_blueprint(profile_bp, url_prefix='/profile')

    from app.signup import signup_bp
    app.register_blueprint(signup_bp, url_prefix='/signup')

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)  # Geen prefix, voor error handling

    from app.admin import admin
    app.register_blueprint(admin)

    # Importeer modellen om database-tabellen te registreren
    from app import models

    logger.info("FitTrack applicatie succesvol geïnitialiseerd")

    return app