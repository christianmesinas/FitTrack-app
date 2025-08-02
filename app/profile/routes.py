import base64
import io
from datetime import datetime, timedelta

import numpy as np
from markupsafe import escape

from flask import flash, redirect, url_for, request, render_template
from flask_login import login_required, current_user
from matplotlib import pyplot as plt

from . import bp
from .. import logger, db
from ..decorators import get_user_workout_plans, get_workout_data
from ..forms import EditProfileForm, AddWeightForm
from ..models import WeightLog, WorkoutSession, SetLog


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
#   Beheer gebruikersprofiel en gewichtslog.
def profile():
    logger.debug(f"Profile route, user: {current_user.name}")
    from app import db

    form = EditProfileForm(original_name=current_user.name)
    weight_form = AddWeightForm()

    # Handle profile update
    if form.validate_on_submit() and form.submit.data:
        old_weight = current_user.current_weight
        current_user.name = escape(form.name.data)
        current_user.current_weight = form.current_weight.data
        current_user.weekly_workouts = form.weekly_workouts.data
        current_user.fitness_goal = form.fitness_goal.data

        # Als het gewicht is veranderd, log het
        if form.current_weight.data and old_weight != form.current_weight.data:
            weight_log = WeightLog(
                user_id=current_user.id,
                weight=form.current_weight.data,
                notes=escape("Bijgewerkt via profiel")
            )
            db.session.add(weight_log)

        db.session.commit()
        logger.debug(f"Profiel bijgewerkt: {current_user.name}")
        flash('Je profiel is bijgewerkt!', 'success')
        return redirect(url_for('profile.profile'))

    # Handle weight logging
    elif weight_form.validate_on_submit() and weight_form.submit.data:
        weight_log = WeightLog(
            user_id=current_user.id,
            weight=weight_form.weight.data,
            notes=escape(weight_form.notes.data) if weight_form.notes.data else None
        )
        current_user.current_weight = weight_form.weight.data
        db.session.add(weight_log)
        db.session.commit()
        flash('Gewicht succesvol toegevoegd!', 'success')
        return redirect(url_for('profile.profile'))

    elif request.method == 'GET':
        # Vul formulier met huidige gebruikersgegevens
        form.name.data = current_user.name
        form.current_weight.data = current_user.current_weight
        form.weekly_workouts.data = current_user.weekly_workouts
        form.fitness_goal.data = current_user.fitness_goal

    # Haal recente gewichtsmetingen op
    recent_weights = WeightLog.query.filter_by(user_id=current_user.id) \
        .order_by(WeightLog.logged_at.desc()) \
        .limit(10).all()

    # Grafiek genereren
    chart_data = None
    weight_stats = None

    if recent_weights:
        # Alle gewichten voor grafiek
        all_weights = WeightLog.query.filter_by(user_id=current_user.id) \
            .order_by(WeightLog.logged_at).all()

        if len(all_weights) >= 2:
            chart_data = generate_weight_chart_data(all_weights, current_user)
            weight_stats = calculate_weight_statistics(all_weights)

    return render_template('user.html',
                           user=current_user,
                           form=form,
                           weight_form=weight_form,
                           recent_weights=recent_weights,
                           chart_data=chart_data,
                           weight_stats=weight_stats)


def generate_weight_chart_data(weights, user):
    """Genereer grafiek data als base64 string"""
    try:
        # Data voorbereiden
        dates = [w.logged_at for w in weights]
        weight_values = [w.weight for w in weights]

        # Grafiek maken
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot hoofdlijn met gewichtspunten
        ax.plot(dates, weight_values, 'o-',
                linewidth=2.5, markersize=6,
                color='#ff6b35', markerfacecolor='white',
                markeredgecolor='#ff6b35', markeredgewidth=2,
                alpha=0.8)

        # Trendlijn
        if len(dates) > 2:
            x_numeric = np.arange(len(dates))
            z = np.polyfit(x_numeric, weight_values, 1)
            p = np.poly1d(z)
            ax.plot(dates, p(x_numeric),
                    '--', alpha=0.6, color='#666',
                    linewidth=1.5, label='Trend')

        # Doelgewicht lijn
        if user.fitness_goal:
            ax.axhline(y=user.fitness_goal,
                       color='#28a745', linestyle=':',
                       alpha=0.7, linewidth=2,
                       label=f'Doel: {user.fitness_goal} kg')

        # Configureer assen en styling
        ax.set_xlabel('Datum', fontsize=11)
        ax.set_ylabel('Gewicht (kg)', fontsize=11)
        ax.set_title('Jouw Gewichtsontwikkeling', fontsize=14, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        # Verbeter datum weergave
        fig.autofmt_xdate()

        # Legend
        if user.fitness_goal or len(dates) > 2:
            ax.legend(loc='best', framealpha=0.9)

        # Layout
        plt.tight_layout()

        # Y-as range aanpassen voor betere visualisatie
        y_range = max(weight_values) - min(weight_values)
        if y_range > 0:
            padding = y_range * 0.1
            ax.set_ylim(min(weight_values) - padding, max(weight_values) + padding)

        # Converteer naar base64
        img = io.BytesIO()
        plt.savefig(img, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close(fig)

        return plot_url

    except Exception as e:
        print(f"Fout bij het genereren van grafiek: {e}")
        plt.close('all')  # Sluit alle open figuren
        return None


def calculate_weight_statistics(weights):
    try:
        weight_values = [w.weight for w in weights]
        dates = [w.logged_at for w in weights]

        # Recente gewichten (laatste 30 dagen)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_weights = [w.weight for w in weights if w.logged_at >= thirty_days_ago]

        stats = {
            'current_weight': weight_values[-1],
            'start_weight': weight_values[0],
            'total_change': weight_values[-1] - weight_values[0],
            'average_weight': np.mean(weight_values),
            'min_weight': min(weight_values),
            'max_weight': max(weight_values),
            'recent_average': np.mean(recent_weights) if recent_weights else None,
            'total_measurements': len(weights),
            'measurement_period': (dates[-1] - dates[0]).days
        }

        return stats

    except Exception as e:
        print(f"Fout bij het berekenen van statistieken: {e}")
        return None

@bp.route('/weight_history')
@login_required
def weight_history():
    """Toon alle gewichtsmetingen van de gebruiker"""
    page = request.args.get('page', 1, type=int)

    weights = WeightLog.query.filter_by(user_id=current_user.id) \
        .order_by(WeightLog.logged_at.desc()) \
        .paginate(page=page, per_page=20, error_out=False)

    return render_template('weight_history.html',
                           weights=weights,
                           user=current_user)

@bp.route('/workout_history')
@login_required
def workout_history():
    page = request.args.get('page', 1, type=int)

    sessions = WorkoutSession.query.filter_by(
        user_id=current_user.id,
        is_completed=True,
        is_archived=False  # Alleen niet-gearchiveerde sessies
    ).options(
        db.joinedload(WorkoutSession.workout_plan)
    ).order_by(WorkoutSession.completed_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    for session in sessions.items:
        if not hasattr(session, '_stats_calculated'):
            completed_sets = SetLog.query.filter_by(
                workout_session_id=session.id,
                completed=True
            ).all()

            session.total_sets_count = len(completed_sets)
            session.total_reps_count = sum(s.reps for s in completed_sets)
            session.total_weight_count = sum(s.weight * s.reps for s in completed_sets)

            if session.completed_at and session.started_at:
                duration = session.completed_at - session.started_at
                session.duration_minutes = round(duration.total_seconds() / 60)
            else:
                session.duration_minutes = 0

            session._stats_calculated = True

    return render_template('workout_history.html', sessions=sessions)

@bp.route('/archived_plans')
@login_required
#     Toon gearchiveerde workout-plannen.
def archived_plans():
    logger.debug(f"Archived plans route aangeroepen voor {current_user.name}")
    workout_plans = get_user_workout_plans(current_user.id, archived=True)
    workout_data = get_workout_data(workout_plans)

    return render_template('archived_workouts.html', workout_data=workout_data)