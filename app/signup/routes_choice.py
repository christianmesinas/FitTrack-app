from flask import render_template, redirect, url_for
from . import signup_bp
from flask_login import current_user

@signup_bp.route('/signup_choice')
def signup_choice():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))  # redirige vers login si pas connecté
    return render_template('signup_choice.html')
