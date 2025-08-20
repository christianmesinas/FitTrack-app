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
        is_new_user = False

        if not user:
            # Nieuwe gebruiker aanmaken
            user = User(
                email=userinfo['email'],
                auth0_id=userinfo['sub'],
            )
            db.session.add(user)
            db.session.commit()
            is_new_user = True
            logger.debug(f"Nieuwe gebruiker aangemaakt: {user.email}")

        login_user(user)
        logger.debug(f"User ingelogd: id={user.get_id()}, email={user.email}")

        # Check of dit een nieuwe gebruiker is of een gebruiker zonder account type
        if is_new_user or not hasattr(user, 'account_type') or user.account_type is None:
            session['new_user'] = True
            logger.debug("Nieuwe gebruiker - redirect naar signup keuze")
            return redirect(url_for('signup.signup_choice'))

        # Bestaande gebruiker met account type
        session['new_user'] = False

        # Check of het een trainer is
        if user.account_type == 'trainer':
            return redirect(url_for('admin.dashboard'))

        # Voor normale gebruikers - check of alle velden zijn ingevuld
        if not user.name or not user.current_weight or not user.fitness_goal:
            # Als niet alle velden zijn ingevuld, stuur naar particulier signup om te voltooien
            flash('Vul je profiel aan om verder te gaan.', 'info')
            return redirect(url_for('signup.signup_particular'))

        # Alles compleet - ga naar hoofdpagina
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


# OUDE ONBOARDING ROUTES - BEHOUDEN MAAR NIET MEER ACTIEF GEBRUIKT
@auth.route('/onboarding/name', methods=['GET', 'POST'])
@login_required
def onboarding_name():
    """LEGACY: Verwerk de naam-invoerstap van onboarding."""
    # Redirect naar nieuwe signup flow
    return redirect(url_for('signup.signup_particular'))


@auth.route('/onboarding/current_weight', methods=['GET', 'POST'])
@login_required
def onboarding_current_weight():
    """LEGACY: Verwerk de huidige gewicht-invoerstap van onboarding."""
    # Redirect naar nieuwe signup flow
    return redirect(url_for('signup.signup_particular'))


@auth.route('/onboarding/goal_weight', methods=['GET', 'POST'])
@login_required
def onboarding_goal_weight():
    """LEGACY: Verwerk de doelgewicht-invoerstap van onboarding."""
    # Redirect naar nieuwe signup flow
    return redirect(url_for('signup.signup_particular'))