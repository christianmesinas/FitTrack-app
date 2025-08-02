from flask import render_template, redirect, url_for, session
from flask_login import current_user, login_required
from . import bp as main, logger
from ..decorators import get_user_workout_plans, check_onboarding_status, get_workout_data
from ..forms import DeleteWorkoutForm


@main.route('/')
def landing():
    # Toon de landingspagina of redirect naar index voor ingelogde gebruikers.

    logger.debug(f"Landing route, is_authenticated: {current_user.is_authenticated}, session: {session.get('_user_id')}")
    if current_user.is_authenticated:
        logger.debug(f"Gebruiker ingelogd: {current_user.name}")
        return redirect(url_for('main.index'))
    try:
        logger.debug("Probeer landings.html te renderen")
        return render_template('landings.html', is_landing_page=True)
    except Exception as e:
        logger.error(f"Fout bij renderen van landings.html: {str(e)}", exc_info=True)
        raise

@main.route('/index')
@login_required
def index():
    # Toon het dashboard met workout-plannen van de gebruiker.

    logger.debug(f"Index route aangeroepen voor {current_user.name}")
    # Controleer onboarding-status
    onboarding_redirect = check_onboarding_status(current_user)
    if onboarding_redirect:
        logger.debug(f"Redirect naar onboarding-stap: {onboarding_redirect}")
        return redirect(onboarding_redirect)

    # Haal niet-gearchiveerde workout-plannen op
    workout_plans = get_user_workout_plans(current_user.id, archived=False)
    workout_data = get_workout_data(workout_plans)
    delete_form = DeleteWorkoutForm()

    return render_template('index.html', workout_data=workout_data, delete_form=delete_form)
