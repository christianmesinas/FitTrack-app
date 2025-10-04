import os
from dotenv import load_dotenv, find_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

class Config:
    SECRET_KEY = os.getenv('APP_SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(basedir, 'app.db')).replace(
        'postgres://', 'postgresql://')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True

    AUTH0_DOMAIN = os.getenv('AUTH0_DOMAIN')
    AUTH0_CLIENT_ID = os.getenv('AUTH0_CLIENT_ID')
    AUTH0_CLIENT_SECRET = os.getenv('AUTH0_CLIENT_SECRET')
    AUTH0_CALLBACK_URL = os.getenv('AUTH0_CALLBACK_URL')

    DEBUG = True

    UPLOAD_FOLDER = os.path.abspath(os.path.join('app', 'static', 'img', 'exercises'))
    VIDEO_UPLOAD_FOLDER = os.path.abspath(os.path.join('app', 'static', 'videos', 'exercises'))
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'mp4', 'webm'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024