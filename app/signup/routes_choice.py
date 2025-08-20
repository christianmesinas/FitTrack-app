# app/signup/routes_choice.py
from flask import render_template, redirect, url_for, session, flash
from . import signup_bp
from flask_login import current_user, login_required
import logging

logger = logging.getLogger(__name__)


@signup_bp.route('/choice')
@login_required
def signup_choice():
    """Laat nieuwe gebruikers kiezen tussen normaal account of trainer account"""
    logger.debug(f"Signup choice route voor gebruiker: {current_user.email}")

    # Check of gebruiker al een account type heeft
    if hasattr(current_user, 'account_type') and current_user.account_type:
        logger.debug(f"Gebruiker heeft al account type: {current_user.account_type}")

        if current_user.account_type == 'trainer':
            flash('Je bent al geregistreerd als trainer.', 'info')
            return redirect(url_for('admin.dashboard'))
        elif current_user.account_type == 'user':
            # Check of profiel compleet is
            if not current_user.name or not current_user.current_weight or not current_user.fitness_goal:
                flash('Vul je profiel aan om verder te gaan.', 'info')
                return redirect(url_for('signup.signup_particular'))
            else:
                flash('Je bent al geregistreerd als gebruiker.', 'info')
                return redirect(url_for('main.index'))

    # Nieuwe gebruiker - toon keuze scherm
    logger.debug("Toon keuze scherm voor nieuwe gebruiker")
    return render_template('signup_choice.html')