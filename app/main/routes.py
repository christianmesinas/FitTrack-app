from flask import render_template, redirect, url_for, session
from flask_login import current_user, login_required
from . import bp as main, logger
from ..decorators import get_user_workout_plans, check_onboarding_status, get_workout_data
from ..forms import DeleteWorkoutForm


@main.route('/')
def landing():
    """Toon de landingspagina of redirect naar juiste dashboard voor ingelogde gebruikers."""

    logger.debug(
        f"Landing route, is_authenticated: {current_user.is_authenticated}, session: {session.get('_user_id')}")

    if current_user.is_authenticated:
        logger.debug(f"Gebruiker ingelogd: {current_user.name}")

        # Check account type en redirect naar juiste dashboard
        if hasattr(current_user, 'account_type'):
            if current_user.account_type == 'trainer':
                logger.debug("Redirect naar admin dashboard voor trainer")
                return redirect(url_for('admin.dashboard'))
            elif current_user.account_type == 'user':
                # Check of profiel compleet is
                if not current_user.name or not current_user.current_weight or not current_user.fitness_goal:
                    logger.debug("Profiel niet compleet - redirect naar signup particular")
                    return redirect(url_for('signup.signup_particular'))
                logger.debug("Redirect naar user index")
                return redirect(url_for('main.index'))
        else:
            # Geen account type - nieuwe gebruiker
            logger.debug("Geen account type - redirect naar signup choice")
            return redirect(url_for('signup.signup_choice'))

    try:
        logger.debug("Probeer landings.html te renderen")
        return render_template('landings.html', is_landing_page=True)
    except Exception as e:
        logger.error(f"Fout bij renderen van landings.html: {str(e)}", exc_info=True)
        raise


@main.route('/index')
@login_required
def index():
    """Toon het dashboard met workout-plannen van de gebruiker."""

    logger.debug(f"Index route aangeroepen voor {current_user.name}")

    # Check of gebruiker een trainer is (zou niet hier moeten komen)
    if hasattr(current_user, 'account_type') and current_user.account_type == 'trainer':
        logger.debug("Trainer probeert user index te bereiken - redirect naar admin")
        return redirect(url_for('admin.dashboard'))

    # Check of profiel compleet is
    if not current_user.name or not current_user.current_weight or not current_user.fitness_goal:
        logger.debug("Profiel niet compleet - redirect naar signup particular")
        return redirect(url_for('signup.signup_particular'))

    # Haal niet-gearchiveerde workout-plannen op
    workout_plans = get_user_workout_plans(current_user.id, archived=False)
    workout_data = get_workout_data(workout_plans)
    delete_form = DeleteWorkoutForm()

    return render_template('index.html',
                           workout_data=workout_data,
                           delete_form=delete_form)