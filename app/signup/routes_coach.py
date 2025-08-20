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

    # Check of gebruiker al een account type heeft
    if hasattr(current_user, 'account_type') and current_user.account_type:
        if current_user.account_type == 'trainer':
            flash('Je bent al geregistreerd als trainer.', 'info')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Je hebt al een gebruikersaccount.', 'info')
            return redirect(url_for('main.index'))

    if request.method == 'POST':
        # Haal form data op
        name = request.form.get('name')
        company_name = request.form.get('company_name')
        specialization = request.form.get('specialization')
        experience_years = request.form.get('experience_years')
        certification = request.form.get('certification')

        # Validatie
        if not name or not specialization or not experience_years:
            flash('Vul alle verplichte velden in.', 'error')
            return render_template('signup_coach.html')

        # Update gebruiker als trainer
        current_user.account_type = 'trainer'
        current_user.name = name

        # Voeg trainer-specifieke velden toe
        current_user.company_name = company_name
        current_user.specialization = specialization
        current_user.experience_years = experience_years
        current_user.certification = certification

        try:
            db.session.commit()
            flash('Welkom als trainer bij FitTrack+! Je account is succesvol aangemaakt.', 'success')
            logger.info(f"Trainer account aangemaakt voor: {current_user.email}")

            # Redirect naar admin dashboard
            return redirect(url_for('admin.dashboard'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Fout bij aanmaken trainer account: {str(e)}")
            flash('Er is een fout opgetreden. Probeer het opnieuw.', 'error')
            return render_template('signup_coach.html')

    return render_template('signup_coach.html')