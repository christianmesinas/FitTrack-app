from flask import render_template, redirect, url_for, session
from flask_login import current_user, login_required
from datetime import datetime, timedelta, timezone
import random
from . import bp as main, logger
from ..decorators import get_user_workout_plans, check_onboarding_status, get_workout_data
from ..forms import DeleteWorkoutForm
from ..models import WorkoutSession, WeightLog, SetLog, Exercise, WorkoutPlanExercise, CalendarEvent
from .. import db


def get_motivational_quote():
    """Krijg een motiverende quote voor de dag"""
    quotes = [
        "Elke workout brengt je dichter bij je doel! 🎯",
        "Vandaag is de dag om sterker te worden! 💪",
        "Jouw enige concurrent is wie je gisteren was! 🏆",
        "Geen excuses, alleen resultaten! 🔥",
        "De pijn van vandaag is de kracht van morgen! ⚡",
        "Focus op vooruitgang, niet op perfectie! 📈",
        "Je lichaam kan het, je moet alleen je geest overtuigen! 🧠",
        "Champions worden niet in de gym gemaakt, ze worden gemaakt van iets diep van binnen! 💖",
    ]
    return random.choice(quotes)


def calculate_workout_stats(user_id):
    """Bereken workout statistieken voor de gebruiker - inclusief kalender events"""
    now = datetime.now()

    # Deze maand
    start_of_month = datetime(now.year, now.month, 1)

    # WorkoutSessions deze maand
    sessions_this_month = WorkoutSession.query.filter(
        WorkoutSession.user_id == user_id,
        WorkoutSession.completed_at >= start_of_month,
        WorkoutSession.is_completed == True
    ).count()

    # CalendarEvents deze maand (voltooide workouts)
    calendar_events_this_month = CalendarEvent.query.filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.start_datetime >= start_of_month,
        CalendarEvent.status == 'completed',
        CalendarEvent.event_type.in_(['workout', 'cardio'])  # Alleen workout/cardio tellen
    ).count()

    workouts_this_month = sessions_this_month + calendar_events_this_month

    # Deze week
    start_of_week = now - timedelta(days=now.weekday())

    sessions_this_week = WorkoutSession.query.filter(
        WorkoutSession.user_id == user_id,
        WorkoutSession.completed_at >= start_of_week,
        WorkoutSession.is_completed == True
    ).count()

    calendar_events_this_week = CalendarEvent.query.filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.start_datetime >= start_of_week,
        CalendarEvent.status == 'completed',
        CalendarEvent.event_type.in_(['workout', 'cardio'])
    ).count()

    workouts_this_week = sessions_this_week + calendar_events_this_week

    # Streak berekenen - combineer beide bronnen
    streak_days = calculate_combined_streak(user_id)

    # Gewicht vooruitgang (blijft hetzelfde)
    latest_weight = WeightLog.query.filter_by(user_id=user_id).order_by(WeightLog.logged_at.desc()).first()
    first_weight = WeightLog.query.filter_by(user_id=user_id).order_by(WeightLog.logged_at).first()

    weight_progress = 0
    if latest_weight and first_weight:
        weight_progress = first_weight.weight - latest_weight.weight

    return {
        'workouts_this_month': workouts_this_month,
        'workouts_this_week': workouts_this_week,
        'streak_days': streak_days,
        'weight_progress': weight_progress
    }


def calculate_combined_streak(user_id):
    """Bereken de workout streak gebaseerd op zowel WorkoutSessions als CalendarEvents"""
    # Haal alle workout datums op van beide bronnen
    workout_dates = set()

    # WorkoutSession datums
    sessions = WorkoutSession.query.filter(
        WorkoutSession.user_id == user_id,
        WorkoutSession.is_completed == True
    ).order_by(WorkoutSession.completed_at.desc()).all()

    for session in sessions:
        workout_dates.add(session.completed_at.date())

    # CalendarEvent datums (voltooide workouts)
    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.status == 'completed',
        CalendarEvent.event_type.in_(['workout', 'cardio'])
    ).order_by(CalendarEvent.start_datetime.desc()).all()

    for event in events:
        workout_dates.add(event.start_datetime.date())

    if not workout_dates:
        return 0

    # Sorteer de datums (nieuwste eerst)
    sorted_dates = sorted(workout_dates, reverse=True)

    # Check streak
    streak = 0
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # Start streak alleen als er vandaag of gisteren getraind is
    if sorted_dates[0] != today and sorted_dates[0] != yesterday:
        return 0

    last_date = sorted_dates[0]
    streak = 1

    for i in range(1, len(sorted_dates)):
        current_date = sorted_dates[i]
        if (last_date - current_date).days == 1:
            streak += 1
            last_date = current_date
        else:
            break

    return streak


def calculate_streak(user_id):
    """Bereken de huidige workout streak - LEGACY functie, gebruik calculate_combined_streak"""
    return calculate_combined_streak(user_id)


def get_last_workout(user_id):
    """Haal de laatste workout op"""
    last_session = WorkoutSession.query.filter(
        WorkoutSession.user_id == user_id,
        WorkoutSession.is_completed == True
    ).order_by(WorkoutSession.completed_at.desc()).first()

    if last_session:
        return {
            'id': last_session.workout_plan_id,
            'name': last_session.workout_plan.name if last_session.workout_plan else "Onbekende workout",
            'date': last_session.completed_at.strftime('%d %B'),
            'duration': last_session.duration_minutes or 30,
            'exercise_count': last_session.total_sets or 0
        }
    return None


def get_week_activity(user_id):
    """Krijg week activiteit voor visualisatie - inclusief kalender events"""
    days = ['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo']
    week_activity = []
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())

    for i, day in enumerate(days):
        day_date = start_of_week + timedelta(days=i)

        # Check WorkoutSessions
        has_session = WorkoutSession.query.filter(
            WorkoutSession.user_id == user_id,
            db.func.date(WorkoutSession.completed_at) == day_date.date(),
            WorkoutSession.is_completed == True
        ).first() is not None

        # Check CalendarEvents
        has_event = CalendarEvent.query.filter(
            CalendarEvent.user_id == user_id,
            db.func.date(CalendarEvent.start_datetime) == day_date.date(),
            CalendarEvent.status == 'completed',
            CalendarEvent.event_type.in_(['workout', 'cardio'])
        ).first() is not None

        week_activity.append({
            'name': day,
            'letter': day[0],
            'completed': has_session or has_event  # True als één van beide bestaat
        })

    return week_activity


def calculate_goal_progress(user):
    """Bereken voortgang naar gewichtsdoel"""
    if not user.fitness_goal or not user.current_weight:
        return 0

    # Haal startgewicht op
    first_weight = WeightLog.query.filter_by(user_id=user.id).order_by(WeightLog.logged_at).first()
    if not first_weight:
        return 0

    start = first_weight.weight
    current = user.current_weight
    goal = user.fitness_goal

    if start == goal:
        return 100

    progress = abs(start - current) / abs(start - goal) * 100
    return min(100, round(progress))


def get_personal_records(user_id):
    """Haal personal records op"""
    # Dit is een vereenvoudigde versie - je zou dit kunnen uitbreiden
    records = []

    # Haal de zwaarste gewichten per oefening
    heaviest = db.session.query(
        Exercise.name,
        db.func.max(SetLog.weight).label('max_weight')
    ).join(
        SetLog, SetLog.exercise_id == Exercise.id
    ).filter(
        SetLog.user_id == user_id,
        SetLog.completed == True
    ).group_by(Exercise.name).order_by(
        db.desc('max_weight')
    ).limit(3).all()

    for exercise_name, weight in heaviest:
        if weight > 0:
            records.append({
                'exercise': exercise_name,
                'value': f'{weight}kg'
            })

    return records


def get_workout_suggestions(user):
    """Genereer workout suggesties gebaseerd op gebruikersdata"""
    suggestions = []

    # Check laatste workout datum
    last_session = WorkoutSession.query.filter_by(
        user_id=user.id,
        is_completed=True
    ).order_by(WorkoutSession.completed_at.desc()).first()

    if not last_session or (datetime.now() - last_session.completed_at).days > 3:
        suggestions.append({
            'title': 'Tijd voor een workout!',
            'description': 'Je hebt al een paar dagen niet getraind',
            'icon': 'fas fa-exclamation-circle',
            'link': url_for('main.index')
        })

    # Suggestie voor cardio als er weinig cardio is
    cardio_count = db.session.query(SetLog).join(
        Exercise, SetLog.exercise_id == Exercise.id
    ).filter(
        SetLog.user_id == user.id,
        Exercise.category == 'CARDIO'
    ).count()

    if cardio_count < 5:
        suggestions.append({
            'title': 'Probeer wat cardio',
            'description': 'Verbeter je conditie met cardio oefeningen',
            'icon': 'fas fa-running',
            'link': url_for('workouts.search_exercise', plan_id=0, category='CARDIO')
        })

    # Als geen suggesties, toon algemene
    if not suggestions:
        suggestions = [
            {
                'title': 'Full Body Workout',
                'description': 'Train je hele lichaam in één sessie',
                'icon': 'fas fa-dumbbell',
                'link': url_for('workouts.add_workout')
            },
            {
                'title': 'HIIT Training',
                'description': 'Verbrand calorieën met interval training',
                'icon': 'fas fa-fire',
                'link': url_for('workouts.add_workout')
            }
        ]

    return suggestions


def get_recent_activities(user_id, limit=5):
    """Haal recente activiteiten op"""
    activities = []

    # Workout sessies
    sessions = WorkoutSession.query.filter_by(
        user_id=user_id,
        is_completed=True
    ).order_by(WorkoutSession.completed_at.desc()).limit(3).all()

    for session in sessions:
        time_ago = format_time_ago(session.completed_at)
        activities.append({
            'type': 'workout',
            'icon': 'fas fa-dumbbell',
            'text': f'Workout "{session.workout_plan.name}" voltooid',
            'time': time_ago
        })

    # Gewicht logs
    weight_logs = WeightLog.query.filter_by(
        user_id=user_id
    ).order_by(WeightLog.logged_at.desc()).limit(2).all()

    for log in weight_logs:
        time_ago = format_time_ago(log.logged_at)
        activities.append({
            'type': 'weight',
            'icon': 'fas fa-weight',
            'text': f'Gewicht bijgewerkt: {log.weight}kg',
            'time': time_ago
        })

    # Sorteer op tijd en beperk
    activities.sort(key=lambda x: x['time'], reverse=False)
    return activities[:limit]


def format_time_ago(timestamp):
    """Format timestamp naar 'x tijd geleden' """
    if not timestamp:
        return "Onbekend"

    # Zorg dat timestamp timezone-aware is
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    diff = now - timestamp

    if diff.days > 7:
        return timestamp.strftime('%d %B')
    elif diff.days > 0:
        return f"{diff.days} {'dag' if diff.days == 1 else 'dagen'} geleden"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} {'uur' if hours == 1 else 'uur'} geleden"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} {'minuut' if minutes == 1 else 'minuten'} geleden"
    else:
        return "Zojuist"


def enhance_workout_data(workout_data):
    """Voeg extra data toe aan workout plannen"""
    for workout_info in workout_data:
        plan_id = workout_info['plan'].id

        # Laatste keer uitgevoerd
        last_session = WorkoutSession.query.filter_by(
            workout_plan_id=plan_id,
            is_completed=True
        ).order_by(WorkoutSession.completed_at.desc()).first()

        if last_session:
            workout_info['last_performed'] = format_time_ago(last_session.completed_at)
        else:
            workout_info['last_performed'] = None

        # Geschatte duur en calorieën
        exercise_count = len(workout_info['exercises'])
        workout_info['estimated_duration'] = exercise_count * 5  # 5 min per oefening geschat
        workout_info['estimated_calories'] = exercise_count * 50  # 50 cal per oefening geschat

        # Categorie bepalen
        if any('cardio' in ex.name.lower() for ex in workout_info['exercises']):
            workout_info['category'] = 'cardio'
        else:
            workout_info['category'] = 'strength'

    return workout_data


@main.route('/')
def landing():
    """Toon de landingspagina of redirect naar juiste dashboard voor ingelogde gebruikers."""
    logger.debug(f"Landing route, is_authenticated: {current_user.is_authenticated}")

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

    # Check of gebruiker een trainer is
    if hasattr(current_user, 'account_type') and current_user.account_type == 'trainer':
        logger.debug("Trainer probeert user index te bereiken - redirect naar admin")
        return redirect(url_for('admin.dashboard'))

    # Check of profiel compleet is
    if not current_user.name or not current_user.current_weight or not current_user.fitness_goal:
        logger.debug("Profiel niet compleet - redirect naar signup particular")
        return redirect(url_for('signup.signup_particular'))

    # Haal workout data op
    workout_plans = get_user_workout_plans(current_user.id, archived=False)
    workout_data = get_workout_data(workout_plans)
    workout_data = enhance_workout_data(workout_data)

    # Bereken statistieken
    stats = calculate_workout_stats(current_user.id)

    # Extra data voor nieuwe features
    context = {
        'workout_data': workout_data,
        'delete_form': DeleteWorkoutForm(),
        'motivational_quote': get_motivational_quote(),
        'workouts_this_month': stats['workouts_this_month'],
        'workouts_this_week': stats['workouts_this_week'],
        'streak_days': stats['streak_days'],
        'weight_progress': stats['weight_progress'],
        'last_workout': get_last_workout(current_user.id),
        'week_activity': get_week_activity(current_user.id),
        'goal_progress': calculate_goal_progress(current_user),
        'weekly_goal': current_user.weekly_workouts or 3,
        'personal_records': get_personal_records(current_user.id),
        'workout_suggestions': get_workout_suggestions(current_user),
        'recent_activities': get_recent_activities(current_user.id)
    }

    return render_template('index.html', **context)