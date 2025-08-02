from flask import render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_required, current_user, login_user, logout_user
from markupsafe import escape
import logging

from . import bp as auth
from app.forms import NameForm, CurrentWeightForm, GoalWeightForm
from app.models import User
from app import db
from ..decorators import check_onboarding_status

logger = logging.getLogger(__name__)


@auth.route('/login')
def login():
    """Start het inlogproces via Auth0."""
    logger.debug("Login route aangeroepen")

    if current_user.is_authenticated:
        logger.debug(f"Gebruiker al ingelogd: {current_user.name} — uitloggen voor login")
        logout_user()
        session.clear()

    try:
        from app import oauth  # Lazy import om import-tijd te verminderen
        redirect_response = oauth.auth0.authorize_redirect(
            redirect_uri=url_for('auth.callback', _external=True)
        )
        logger.debug(f"Auth0 login redirect URL: {redirect_response.location}")
        return redirect_response
    except Exception as e:
        logger.error(f"Auth0 login fout: {str(e)}")
        flash('Fout bij inloggen. Probeer opnieuw.')
        return redirect(url_for('main.landing'))


@auth.route('/signup')
def signup():
    """Start het aanmeldproces via Auth0."""
    logger.debug("Signup route aangeroepen")

    if current_user.is_authenticated:
        logger.debug(f"Gebruiker al ingelogd: {current_user.name} — uitloggen voor signup")
        logout_user()
        session.clear()

    try:
        from app import oauth  # Lazy import
        redirect_response = oauth.auth0.authorize_redirect(
            redirect_uri=url_for('auth.callback', _external=True),
            screen_hint='signup'
        )
        logger.debug(f"Auth0 signup redirect URL: {redirect_response.location}")
        return redirect_response
    except Exception as e:
        logger.error(f"Auth0 signup fout: {str(e)}")
        flash('Fout bij aanmelden. Probeer opnieuw.')
        return redirect(url_for('main.landing'))


@auth.route('/callback')
def callback():
    """Verwerk Auth0-callback na login of signup."""
    try:
        from app import oauth

        # Haal toegangstoken op
        token = oauth.auth0.authorize_access_token()
        if not token:
            logger.error("Geen toegangstoken ontvangen van Auth0.")
            flash('Authenticatie mislukt.')
            return redirect(url_for('main.landing'))

        # Haal gebruikersinfo op
        userinfo = oauth.auth0.get(f"https://{current_app.config['AUTH0_DOMAIN']}/userinfo").json()

        # Zoek of maak gebruiker
        user = User.query.filter_by(email=userinfo['email']).first()
        if not user:
            user = User(
                email=userinfo['email'],
                auth0_id=userinfo['sub'],
            )
            db.session.add(user)
            db.session.commit()

        login_user(user)
        logger.debug(f"User ingelogd: id={user.get_id()}, name={user.name}")

        # Markeer als bestaande gebruiker
        session['new_user'] = False

        # Controleer onboarding-status
        onboarding_redirect = check_onboarding_status(user)
        if onboarding_redirect:
            return redirect(onboarding_redirect)

        return redirect(url_for('main.index'))

    except Exception as e:
        logger.error(f"Callback fout: {e}")
        flash('Authenticatie mislukt. Probeer opnieuw.')
        return redirect(url_for('main.landing'))


@auth.route('/logout')
@login_required
def logout():
    """Log de gebruiker uit en redirect naar Auth0 logout."""
    logger.debug(f"Logout route, user: {current_user.name}")
    logout_user()
    session.clear()
    return redirect('https://' + current_app.config['AUTH0_DOMAIN'] +
                    '/v2/logout?client_id=' + current_app.config['AUTH0_CLIENT_ID'] +
                    '&returnTo=' + url_for('main.landing', _external=True))


@auth.route('/onboarding/name', methods=['GET', 'POST'])
@login_required
def onboarding_name():
    """Verwerk de naam-invoerstap van onboarding."""
    user = current_user
    form = NameForm()

    if form.validate_on_submit():
        # Update de naam van de gebruiker in de database
        user.name = escape(form.name.data)
        db.session.commit()
        logger.debug(f"Onboarding naam voltooid voor {user.name}")

        # Redirect naar de volgende onboarding stap
        return redirect(url_for('auth.onboarding_current_weight'))

    return render_template('onboarding_name.html', form=form, user=user)


@auth.route('/onboarding/current_weight', methods=['GET', 'POST'])
@login_required
def onboarding_current_weight():
    """Verwerk de huidige gewicht-invoerstap van onboarding."""
    form = CurrentWeightForm()

    if form.validate_on_submit():
        current_user.current_weight = form.current_weight.data
        db.session.commit()
        logger.debug(
            f"Onboarding huidig gewicht voltooid voor {current_user.name}, huidig gewicht: {current_user.current_weight}")
        return redirect(url_for('auth.onboarding_goal_weight'))

    return render_template('onboarding_current_weight.html', form=form)


@auth.route('/onboarding/goal_weight', methods=['GET', 'POST'])
@login_required
def onboarding_goal_weight():
    """Verwerk de doelgewicht-invoerstap van onboarding."""
    form = GoalWeightForm()

    if form.validate_on_submit():
        current_user.fitness_goal = form.fitness_goal.data
        db.session.commit()
        logger.debug(f"Onboarding doelgewicht voltooid voor {current_user.name}, doel: {current_user.fitness_goal}")

        # Controleer of er meer onboarding-stappen zijn
        onboarding_redirect = check_onboarding_status(current_user)
        if onboarding_redirect:
            return redirect(onboarding_redirect)

        flash('Welkom bij FitTrack! Je profiel is compleet.', 'success')
        return redirect(url_for('main.index'))

    return render_template(
        'onboarding_goal_weight.html',
        form=form,
        user=current_user
    )