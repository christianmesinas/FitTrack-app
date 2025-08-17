from flask import render_template, redirect, url_for
from . import signup_bp
from flask_login import current_user



@signup_bp.route('/coach')
def signup_coach():
    return render_template('signup_coach.html')