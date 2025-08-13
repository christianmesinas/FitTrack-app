from flask import url_for, jsonify, request
import re
from flask_login import current_user
from functools import wraps
from app.models import WorkoutPlan, WorkoutPlanExercise


def check_onboarding_status(user):
    #    Controleer de onboarding-status van een gebruiker.
    if not user.name:
        return url_for('auth.onboarding_name')
    elif not user.current_weight:
        return url_for('auth.onboarding_current_weight')
    elif not user.fitness_goal:
        return url_for('auth.onboarding_goal_weight')
    return None  # Onboarding is klaar

def fix_image_path(path):
    """Normaliseer bestandspaden voor afbeeldingen met regex."""
    if not path:
        return 'img/exercises/default.jpg'

    # Strip ongewenste tekens
    path = path.strip().strip('"').strip("'")

    # Verwijder alleen app/static/ of static/ voorvoegsels
    if path.startswith('app/static/'):
        path = path.replace('app/static/', '')
    elif path.startswith('static/'):
        path = path.replace('static/', '')

    # Getallen als folders (bijv. 123/123_filename.jpg -> 123_filename.jpg)
    path = re.sub(r'(\d+)/(\d+_[^/]+)', r'\1_\2', path)

    # Twee tekstfolders (bijv. folder1/folder2/123.jpg -> folder1_folder2/123.jpg)
    path = re.sub(r'([^/]+)/([^/]+)/(\d+\.(?:jpg|jpeg|png|gif))', r'\1_\2/\3', path)

    # Verwijder haakjes
    path = re.sub(r'\(([^)]+)\)', r'\1', path)

    # Als het pad leeg is of ongeldig, gebruik standaardafbeelding
    return path if path and path.startswith('img/exercises/') else 'img/exercises/default.jpg'

def clean_instruction_text(text):
    #Reinig instructietekst door speciale tekens te vervangen.
    return text.replace('\ufffd', '¾')


def owns_workout_plan(f):
    #    Decorator om eigendom van een workout-plan te controleren.
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Probeer plan_id uit URL-parameters of JSON te halen
        plan_id = kwargs.get('plan_id') or request.get_json(silent=True, force=True).get('plan_id')
        if not plan_id:
            return jsonify({'success': False, 'message': 'Plan ID is required'}), 400

        try:
            # Converteer plan_id naar integer
            plan_id = int(plan_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid Plan ID'}), 400

        # Haal workout-plan op
        workout_plan = WorkoutPlan.query.get_or_404(plan_id)
        if workout_plan.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized access to workout plan'}), 403

        # Voer de oorspronkelijke functie uit
        return f(*args, **kwargs)

    return decorated_function

def get_user_workout_plans(user_id, archived=False):
    #    Haal workout-plannen op voor een specifieke gebruiker.
    # Basisquery voor gebruikersplannen
    query = WorkoutPlan.query.filter_by(user_id=user_id)
    # Filter op archived-status indien opgegeven
    if archived is not None:
        query = query.filter_by(is_archived=archived)
        # Sorteer op aanmaaktijd (descending)

    return query.order_by(WorkoutPlan.created_at.desc()).all()


def get_workout_data(plans):
    #    Bereid workout-data voor met gekoppelde oefeningen.
    workout_data = []
    for plan in plans:
        # Haal oefeningen op, gesorteerd op volgorde
        exercises = plan.exercises.order_by(WorkoutPlanExercise.order).all()
        # Voeg plan en oefeningen toe als dictionary
        workout_data.append({
            'plan': plan,
            'exercises': [entry.exercise for entry in exercises]
        })
    return workout_data

