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
            return redirect(url_for('admin.dashboard'))
        else:
            return redirect(url_for('main.index'))

    return render_template('signup_choice.html')