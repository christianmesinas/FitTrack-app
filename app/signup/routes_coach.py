# app/signup/routes_coach.py
from flask import render_template, redirect, url_for, flash, request
from . import signup_bp
from flask_login import current_user, login_required
from app import db
import logging

logger = logging.getLogger(__name__)


@signup_bp.route('/coach', methods=['GET', 'POST'])
@login_required
def signup_coach():
    """Registratie proces voor trainers/coaches"""

    if request.method == 'POST':
        # Haal form data op
        company_name = request.form.get('company_name')
        specialization = request.form.get('specialization')
        experience_years = request.form.get('experience_years')
        certification = request.form.get('certification')

        # Update gebruiker als trainer
        current_user.account_type = 'trainer'
        current_user.name = request.form.get('name', current_user.email.split('@')[0])

        # Voeg trainer-specifieke velden toe (je moet deze toevoegen aan je User model)
        # current_user.company_name = company_name
        # current_user.specialization = specialization
        # current_user.experience_years = experience_years
        # current_user.certification = certification

        db.session.commit()

        flash('Welkom als trainer bij FitTrack+! Je account is succesvol aangemaakt.', 'success')
        logger.debug(f"Trainer account aangemaakt voor: {current_user.email}")

        # Redirect naar admin dashboard
        return redirect(url_for('admin.dashboard'))

    return render_template('signup_coach.html')
