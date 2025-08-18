# app/signup/routes_particular.py
from flask import render_template, redirect, url_for, flash, request
from . import signup_bp
from flask_login import current_user, login_required
from app import db
import logging

logger = logging.getLogger(__name__)


@signup_bp.route('/particular', methods=['GET', 'POST'])
@login_required
def signup_particular():
    """Registratie proces voor normale gebruikers"""

    if request.method == 'POST':
        # Update gebruiker als normale gebruiker
        current_user.account_type = 'user'
        current_user.name = request.form.get('name', current_user.email.split('@')[0])

        # Haal fitness goals op
        fitness_goal = request.form.get('fitness_goal')
        current_weight = request.form.get('current_weight')
        target_weight = request.form.get('target_weight')

        if current_weight:
            current_user.current_weight = float(current_weight)
        if target_weight:
            current_user.fitness_goal = float(target_weight)

        db.session.commit()

        flash('Welkom bij FitTrack+! Je account is succesvol aangemaakt.', 'success')
        logger.debug(f"Gebruiker account aangemaakt voor: {current_user.email}")

        # Redirect naar onboarding of main index
        if not current_user.name or not current_user.current_weight:
            return redirect(url_for('auth.onboarding_name'))
        else:
            return redirect(url_for('main.index'))

    return render_template('signup_particular.html')