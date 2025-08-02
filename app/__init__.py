import logging
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_session import Session
from authlib.integrations.flask_client import OAuth
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
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configureer sessie-opslag op bestandssysteem (optioneel)
    app.config['SESSION_TYPE'] = 'filesystem'  # Persistente sessies
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'  # Map voor sessiebestanden

    # Initialiseer Flask-Session voor server-side sessiebeheer
    Session(app)

    # Initialiseer extensies met de app
    db.init_app(app)        # Database-ORM
    migrate.init_app(app, db)  # Database-migraties
    moment.init_app(app)  # Tijdformattering
    login.init_app(app)     # Gebruikersauthenticatie
    oauth.init_app(app)  # OAuth voor Auth0

    # Stel login-view in voor Flask-Login
    login.login_view = 'auth.login'  # Verwijs naar de login-route in de auth blueprint

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

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)  # Geen prefix, voor error handling

    # Importeer modellen om database-tabellen te registreren
    from app import models

    csrf.init_app(app)  # Activeer CSRF-bescherming


    return app