from flask import Blueprint

signup_bp = Blueprint('signup', __name__, template_folder='templates')

from . import routes_choice, routes_coach, routes_particular
