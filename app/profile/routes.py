import base64
import io
import os
from datetime import datetime, timedelta, date
from werkzeug.utils import secure_filename

import numpy as np
from markupsafe import escape

from flask import flash, redirect, url_for, request, render_template, current_app
from flask_login import login_required, current_user
from matplotlib import pyplot as plt

from . import bp
from .. import logger, db
from ..decorators import get_user_workout_plans, get_workout_data
from ..forms import EditProfileForm, AddWeightForm
from ..models import WeightLog, WorkoutSession, SetLog

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    """Check of bestand een toegestane extensie heeft"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Beheer gebruikersprofiel en gewichtslog."""
    logger.debug(f"Profile route, user: {current_user.name}")

    form = EditProfileForm(original_name=current_user.name)
    weight_form = AddWeightForm()

    # Handle profile photo upload
    if 'profile_photo' in request.files:
        file = request.files['profile_photo']
        if file and file.filename and allowed_file(file.filename):
            # Create upload directory if it doesn't exist
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
            os.makedirs(upload_folder, exist_ok=True)

            # Generate unique filename
            filename = secure_filename(
                f"user_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file.filename.rsplit('.', 1)[1].lower()}")
            filepath = os.path.join(upload_folder, filename)

            # Delete old photo if exists
            if current_user.profile_photo:
                old_path = os.path.join(upload_folder, current_user.profile_photo)
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except:
                        pass

            # Save new photo
            file.save(filepath)
            current_user.profile_photo = filename
            db.session.commit()
            flash('Profielfoto bijgewerkt!', 'success')
            return redirect(url_for('profile.profile'))

    # Handle personal info update
    if request.method == 'POST' and 'update_personal' in request.form:
        current_user.name = escape(request.form.get('name', ''))
        current_user.bio = escape(request.form.get('bio', ''))
        current_user.gender = request.form.get('gender', '')

        # Parse birth_date
        birth_date_str = request.form.get('birth_date', '')
        if birth_date_str:
            try:
                current_user.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            except:
                pass

        db.session.commit()
        flash('Persoonlijke informatie bijgewerkt!', 'success')
        return redirect(url_for('profile.profile'))

    # Handle fitness profile update
    elif request.method == 'POST' and 'update_fitness' in request.form:
        old_weight = current_user.current_weight

        # Update weight
        new_weight = request.form.get('current_weight', type=float)
        if new_weight:
            current_user.current_weight = new_weight

            # Set start_weight if not set
            if not current_user.start_weight:
                current_user.start_weight = new_weight

            # Log weight if changed
            if old_weight != new_weight:
                weight_log = WeightLog(
                    user_id=current_user.id,
                    weight=new_weight,
                    notes=escape("Bijgewerkt via fitness profiel")
                )
                db.session.add(weight_log)

        # Update other fields
        current_user.fitness_goal = request.form.get('fitness_goal', type=float)
        current_user.height = request.form.get('height', type=int)
        current_user.fitness_level = request.form.get('fitness_level', '')
        current_user.weekly_workouts = request.form.get('weekly_workouts', type=int)

        # Handle goals (checkboxes)
        goals = request.form.getlist('goals')
        current_user.goals = ','.join(goals) if goals else None

        db.session.commit()
        flash('Fitness profiel bijgewerkt!', 'success')
        return redirect(url_for('profile.profile'))

    # Handle weight logging
    elif weight_form.validate_on_submit() and weight_form.submit.data:
        weight_log = WeightLog(
            user_id=current_user.id,
            weight=weight_form.weight.data,
            notes=escape(weight_form.notes.data) if weight_form.notes.data else None
        )
        current_user.current_weight = weight_form.weight.data

        # Set start_weight if not set
        if not current_user.start_weight:
            current_user.start_weight = weight_form.weight.data

        db.session.add(weight_log)
        db.session.commit()
        flash('Gewicht succesvol toegevoegd!', 'success')
        return redirect(url_for('profile.profile'))

    elif request.method == 'GET':
        # Pre-fill form with current user data
        form.name.data = current_user.name
        form.current_weight.data = current_user.current_weight
        form.weekly_workouts.data = current_user.weekly_workouts
        form.fitness_goal.data = current_user.fitness_goal
        form.bio.data = current_user.bio
        form.gender.data = current_user.gender
        form.height.data = current_user.height
        form.fitness_level.data = current_user.fitness_level

    # Calculate statistics
    update_user_statistics(current_user)

    # Get recent weights
    recent_weights = WeightLog.query.filter_by(user_id=current_user.id) \
        .order_by(WeightLog.logged_at.desc()) \
        .limit(10).all()

    # Generate chart
    chart_data = None
    weight_stats = None

    if recent_weights:
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


def update_user_statistics(user):
    """Update user statistics like total workouts and streak"""
    # Count total completed workouts
    total = WorkoutSession.query.filter_by(
        user_id=user.id,
        is_completed=True
    ).count()
    user.total_workouts = total

    # Calculate workout streak
    streak = calculate_workout_streak(user.id)
    user.workout_streak = streak

    # Achievements (simple count for now)
    user.achievements_count = total // 10  # 1 achievement per 10 workouts

    db.session.commit()


def calculate_workout_streak(user_id):
    """Calculate current workout streak in days"""
    sessions = WorkoutSession.query.filter_by(
        user_id=user_id,
        is_completed=True
    ).order_by(WorkoutSession.completed_at.desc()).all()

    if not sessions:
        return 0

    streak = 0
    current_date = date.today()

    for session in sessions:
        session_date = session.completed_at.date() if session.completed_at else None
        if not session_date:
            continue

        days_diff = (current_date - session_date).days

        if days_diff <= 1:  # Today or yesterday
            if days_diff == 0 or streak == 0:  # Only count once per day
                streak += 1
                current_date = session_date
        else:
            break

    return streak


def generate_weight_chart_data(weights, user):
    """Genereer grafiek data als base64 string"""
    try:
        dates = [w.logged_at for w in weights]
        weight_values = [w.weight for w in weights]

        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(dates, weight_values, 'o-',
                linewidth=2.5, markersize=6,
                color='#ff6b35', markerfacecolor='white',
                markeredgecolor='#ff6b35', markeredgewidth=2,
                alpha=0.8)

        if len(dates) > 2:
            x_numeric = np.arange(len(dates))
            z = np.polyfit(x_numeric, weight_values, 1)
            p = np.poly1d(z)
            ax.plot(dates, p(x_numeric),
                    '--', alpha=0.6, color='#666',
                    linewidth=1.5, label='Trend')

        if user.fitness_goal:
            ax.axhline(y=user.fitness_goal,
                       color='#28a745', linestyle=':',
                       alpha=0.7, linewidth=2,
                       label=f'Doel: {user.fitness_goal} kg')

        ax.set_xlabel('Datum', fontsize=11)
        ax.set_ylabel('Gewicht (kg)', fontsize=11)
        ax.set_title('Jouw Gewichtsontwikkeling', fontsize=14, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

        fig.autofmt_xdate()

        if user.fitness_goal or len(dates) > 2:
            ax.legend(loc='best', framealpha=0.9)

        plt.tight_layout()

        y_range = max(weight_values) - min(weight_values)
        if y_range > 0:
            padding = y_range * 0.1
            ax.set_ylim(min(weight_values) - padding, max(weight_values) + padding)

        img = io.BytesIO()
        plt.savefig(img, format='png', dpi=150, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close(fig)

        return plot_url

    except Exception as e:
        print(f"Fout bij het genereren van grafiek: {e}")
        plt.close('all')
        return None


def calculate_weight_statistics(weights):
    """Bereken statistieken van gewichtsmetingen"""
    try:
        weight_values = [w.weight for w in weights]
        dates = [w.logged_at for w in weights]

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
    """Toon workout geschiedenis van de gebruiker"""
    page = request.args.get('page', 1, type=int)

    sessions = WorkoutSession.query.filter_by(
        user_id=current_user.id,
        is_completed=True,
        is_archived=False
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
def archived_plans():
    """Toon gearchiveerde workout-plannen."""
    logger.debug(f"Archived plans route aangeroepen voor {current_user.name}")
    workout_plans = get_user_workout_plans(current_user.id, archived=True)
    workout_data = get_workout_data(workout_plans)

    return render_template('archived_workouts.html', workout_data=workout_data)