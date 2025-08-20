# app/signup/routes_particular.py
from flask import render_template, redirect, url_for, flash, request
from . import signup_bp
from flask_login import current_user, login_required
from app import db
from app.models import WeightLog
import logging

logger = logging.getLogger(__name__)


@signup_bp.route('/particular', methods=['GET', 'POST'])
@login_required
def signup_particular():
    """Registratie proces voor normale gebruikers"""

    # Check of gebruiker al een account type heeft
    if hasattr(current_user, 'account_type') and current_user.account_type:
        if current_user.account_type == 'trainer':
            flash('Je bent geregistreerd als trainer.', 'info')
            return redirect(url_for('admin.dashboard'))
        elif current_user.account_type == 'user':
            # Check of profiel compleet is
            if not current_user.name or not current_user.current_weight or not current_user.fitness_goal:
                # Laat gebruiker profiel aanvullen
                pass
            else:
                flash('Je profiel is al compleet.', 'info')
                return redirect(url_for('main.index'))

    if request.method == 'POST':
        # Haal form data op
        name = request.form.get('name')
        fitness_goal = request.form.get('fitness_goal')
        current_weight = request.form.get('current_weight')
        target_weight = request.form.get('target_weight')

        # Validatie
        if not name:
            flash('Vul je naam in.', 'error')
            return render_template('signup_particular.html')

        # Update gebruiker als normale gebruiker
        current_user.account_type = 'user'
        current_user.name = name

        # Verwerk fitness goal
        if fitness_goal:
            # Sla het type doel op (voor latere features)
            # Dit kunnen we later uitbreiden met een apart veld
            pass

        # Verwerk gewichten
        if current_weight:
            try:
                weight_value = float(current_weight)
                current_user.current_weight = weight_value

                # Voeg eerste gewichtsmeting toe
                weight_log = WeightLog(
                    user_id=current_user.id,
                    weight=weight_value,
                    notes="Startgewicht bij registratie"
                )
                db.session.add(weight_log)
                logger.debug(f"Toegevoegd startgewicht: {weight_value} kg")
            except ValueError:
                flash('Voer een geldig gewicht in.', 'error')
                return render_template('signup_particular.html')

        if target_weight:
            try:
                target_value = float(target_weight)
                current_user.fitness_goal = target_value
                logger.debug(f"Doelgewicht ingesteld: {target_value} kg")
            except ValueError:
                flash('Voer een geldig doelgewicht in.', 'error')
                return render_template('signup_particular.html')

        try:
            db.session.commit()
            flash('Welkom bij FitTrack+! Je account is succesvol aangemaakt.', 'success')
            logger.info(f"Gebruiker account aangemaakt voor: {current_user.email}")

            # Direct naar main index (skip oude onboarding)
            return redirect(url_for('main.index'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Fout bij aanmaken gebruiker account: {str(e)}")
            flash('Er is een fout opgetreden. Probeer het opnieuw.', 'error')
            return render_template('signup_particular.html')

    # Voor GET request - vul eventueel bestaande data in
    return render_template('signup_particular.html',
                           current_user=current_user)