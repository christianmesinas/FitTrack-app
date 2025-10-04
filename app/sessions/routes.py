import uuid
import json
from datetime import timezone, datetime

from flask import jsonify, session, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from . import bp, logger
from .. import db
from ..decorators import owns_workout_plan, get_user_workout_plans, get_workout_data
from ..forms import ActiveWorkoutForm
from ..models import WorkoutPlan, WorkoutSession, WorkoutPlanExercise, SetLog, ExerciseLog


@bp.route('/start_workout/<int:plan_id>', methods=['GET'])
@login_required
@owns_workout_plan
def start_workout(plan_id):
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)

    # Maak een nieuwe workout sessie aan
    session_id = str(uuid.uuid4())
    workout_session = WorkoutSession(
        id=session_id,
        user_id=current_user.id,
        workout_plan_id=plan_id,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(workout_session)
    try:
        db.session.commit()
        logger.debug(f"Created workout_session: id={session_id}, started_at={workout_session.started_at}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create workout session: {str(e)}")
        return jsonify({'success': False, 'message': 'Failed to start workout'}), 500

    # Sla session_id op in browser session voor tracking
    session['current_workout_session'] = session_id

    # Haal oefeningen op met de bijbehorende Exercise objecten
    exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(WorkoutPlanExercise.order).all()

    # Parse images en instructions voor elke exercise
    for wpe in exercises:
        exercise = wpe.exercise

        # Parse images
        if exercise.images:
            try:
                if isinstance(exercise.images, str):
                    images_list = json.loads(exercise.images)
                else:
                    images_list = exercise.images

                # Fix image paths
                fixed_images = []
                for img in images_list:
                    if img and img != 'img/exercises/default.jpg' and 'default.jpg' not in img:
                        if img.startswith('img/exercises/'):
                            fixed_images.append(img)
                        elif img.startswith('img/'):
                            fixed_images.append(img.replace('img/', 'img/exercises/'))
                        else:
                            fixed_images.append(f'img/exercises/{img}')

                exercise.images_list = fixed_images if fixed_images else ['img/placeholder.png']
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse images for exercise {exercise.id}: {str(e)}")
                exercise.images_list = ['img/placeholder.png']
        else:
            exercise.images_list = ['img/placeholder.png']

        # Parse instructions
        if exercise.instructions:
            try:
                if isinstance(exercise.instructions, str):
                    exercise.instructions_list = json.loads(exercise.instructions)
                else:
                    exercise.instructions_list = exercise.instructions
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse instructions for exercise {exercise.id}: {str(e)}")
                exercise.instructions_list = []
        else:
            exercise.instructions_list = []

    form = ActiveWorkoutForm()
    return render_template('active_workout.html',
                           workout_plan=workout_plan,
                           exercises=exercises,
                           session_id=session_id,
                           form=form)


@bp.route('/save_workout/<int:plan_id>', methods=['POST'])
@login_required
@owns_workout_plan
def save_workout(plan_id):
    """Sla een actieve workout op met set-logs - nu met cardio support"""
    logger.debug(
        f"Saving workout for plan_id={plan_id}, user_id={current_user.id}, session_id={session.get('current_workout_session')}")

    try:
        workout_plan = WorkoutPlan.query.get_or_404(plan_id)
        session_id = session.get('current_workout_session')
        if not session_id:
            logger.error("No active workout session found")
            return jsonify({'success': False, 'message': 'Geen actieve workout sessie gevonden.'}), 400

        # Verwijder bestaande SetLogs om herschrijven mogelijk te maken
        existing_logs = SetLog.query.filter_by(workout_session_id=session_id).all()
        for log in existing_logs:
            db.session.delete(log)

        wpes = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).all()
        for wpe in wpes:
            set_num = 0
            while True:
                completed_key = f'completed_{wpe.id}_{set_num}'
                if completed_key not in request.form:
                    break
                if request.form.get(completed_key) == 'on':
                    if wpe.exercise.is_cardio:
                        logger.debug(f"Processing cardio exercise: {wpe.exercise.name}")
                        duration_key = f'duration_{wpe.id}_{set_num}'
                        distance_key = f'distance_{wpe.id}_{set_num}'
                        duration = request.form.get(duration_key, type=float)
                        distance = request.form.get(distance_key, type=float, default=0.0)

                        if duration and duration > 0:
                            log = SetLog(
                                user_id=current_user.id,
                                workout_plan_id=plan_id,
                                exercise_id=wpe.exercise_id,
                                workout_plan_exercise_id=wpe.id,
                                workout_session_id=session_id,
                                set_number=set_num,
                                duration_minutes=duration,
                                distance_km=distance,
                                reps=1,
                                weight=0.0,
                                completed=True,
                                completed_at=datetime.now(timezone.utc)
                            )
                            db.session.add(log)
                    else:
                        logger.debug(f"Processing strength exercise: {wpe.exercise.name}")
                        reps_key = f'reps_{wpe.id}_{set_num}'
                        weight_key = f'weight_{wpe.id}_{set_num}'
                        reps = request.form.get(reps_key, type=float)
                        weight = request.form.get(weight_key, type=float, default=0.0)

                        if reps and reps > 0:
                            log = SetLog(
                                user_id=current_user.id,
                                workout_plan_id=plan_id,
                                exercise_id=wpe.exercise_id,
                                workout_plan_exercise_id=wpe.id,
                                workout_session_id=session_id,
                                set_number=set_num,
                                reps=reps,
                                weight=weight,
                                duration_minutes=None,
                                distance_km=None,
                                completed=True,
                                completed_at=datetime.now(timezone.utc)
                            )
                            db.session.add(log)
                set_num += 1

        db.session.commit()

        workout_session = WorkoutSession.query.get(session_id)
        if workout_session:
            workout_session.calculate_statistics()
            db.session.commit()

        return jsonify({'success': True, 'message': 'Workout succesvol opgeslagen!'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error: {str(e)}")
        return jsonify({'success': False, 'message': f'Database fout: {str(e)}'}), 500


@bp.route('/save_set', methods=['POST'])
@login_required
def save_set():
    """Sla een individuele set op tijdens een actieve workout - nu met cardio support"""
    data = request.get_json()

    wpe_id = data.get('wpe_id')
    set_number = data.get('set_number')
    completed = data.get('completed', False)

    if not all([wpe_id, set_number is not None]):
        return jsonify({'success': False, 'message': 'Missing required data'}), 400

    try:
        wpe = WorkoutPlanExercise.query.get_or_404(wpe_id)

        if wpe.workout_plan.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        session_id = session.get('current_workout_session')
        if not session_id:
            return jsonify({'success': False, 'message': 'No active workout session'}), 400

        existing_set = SetLog.query.filter_by(
            workout_plan_exercise_id=wpe_id,
            set_number=set_number,
            workout_session_id=session_id
        ).first()

        if wpe.exercise.is_cardio:
            logger.debug(f"Saving cardio set for {wpe.exercise.name}")
            duration_minutes = data.get('duration_minutes')
            distance_km = data.get('distance_km', 0.0)

            if not duration_minutes and completed:
                return jsonify({'success': False, 'message': 'Duration is required for cardio exercises'}), 400

            if existing_set:
                existing_set.duration_minutes = duration_minutes
                existing_set.distance_km = distance_km
                existing_set.completed = completed
                existing_set.reps = 1
                existing_set.weight = 0.0
                if completed:
                    existing_set.completed_at = datetime.now(timezone.utc)
                set_log = existing_set
            else:
                set_log = SetLog(
                    user_id=current_user.id,
                    workout_plan_id=wpe.workout_plan_id,
                    exercise_id=wpe.exercise_id,
                    workout_plan_exercise_id=wpe_id,
                    set_number=set_number,
                    duration_minutes=duration_minutes,
                    distance_km=distance_km,
                    reps=1,
                    weight=0.0,
                    completed=completed,
                    workout_session_id=session_id,
                    completed_at=datetime.now(timezone.utc) if completed else None
                )
                db.session.add(set_log)
        else:
            logger.debug(f"Saving strength set for {wpe.exercise.name}")
            reps = data.get('reps')
            weight = data.get('weight', 0.0)

            if not reps and completed:
                return jsonify({'success': False, 'message': 'Reps are required for strength exercises'}), 400

            if existing_set:
                existing_set.reps = reps
                existing_set.weight = weight
                existing_set.completed = completed
                existing_set.duration_minutes = None
                existing_set.distance_km = None
                if completed:
                    existing_set.completed_at = datetime.now(timezone.utc)
                set_log = existing_set
            else:
                set_log = SetLog(
                    user_id=current_user.id,
                    workout_plan_id=wpe.workout_plan_id,
                    exercise_id=wpe.exercise_id,
                    workout_plan_exercise_id=wpe_id,
                    set_number=set_number,
                    reps=reps,
                    weight=weight,
                    duration_minutes=None,
                    distance_km=None,
                    completed=completed,
                    workout_session_id=session_id,
                    completed_at=datetime.now(timezone.utc) if completed else None
                )
                db.session.add(set_log)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Set saved successfully',
            'set_id': set_log.id,
            'is_cardio': wpe.exercise.is_cardio,
            'exercise_category': wpe.exercise.category.value,
            "status": "Set saved"
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving set: {str(e)}")
        return jsonify({'success': False, 'message': f'Error saving set: {str(e)}'}), 500


@bp.route('/complete_workout/<int:plan_id>', methods=['POST'])
@login_required
@owns_workout_plan
def complete_workout(plan_id):
    logger.debug(f"Attempting to complete workout for plan_id={plan_id}, user_id={current_user.id}")
    try:
        session_id = session.get('current_workout_session')
        if not session_id:
            logger.error("No active workout session found")
            return jsonify({'success': False, 'message': 'No active workout session'}), 400

        workout_session = WorkoutSession.query.get_or_404(session_id)
        if workout_session.user_id != current_user.id:
            logger.error(f"Unauthorized: session_user_id={workout_session.user_id}, current_user_id={current_user.id}")
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        workout_session.completed_at = datetime.now(timezone.utc)
        workout_session.is_completed = True
        workout_session.calculate_statistics()

        completed_sets = SetLog.query.filter_by(
            workout_session_id=session_id,
            completed=True
        ).all()

        exercise_groups = {}
        for set_log in completed_sets:
            exercise_id = set_log.exercise_id
            if exercise_id not in exercise_groups:
                exercise_groups[exercise_id] = []
            exercise_groups[exercise_id].append(set_log)

        for exercise_id, sets in exercise_groups.items():
            if sets:
                avg_reps = sum(s.reps for s in sets) / len(sets)
                avg_weight = sum(s.weight for s in sets) / len(sets)
                exercise_log = ExerciseLog(
                    user_id=current_user.id,
                    exercise_id=exercise_id,
                    workout_plan_id=plan_id,
                    sets=len(sets),
                    reps=avg_reps,
                    weight=avg_weight,
                    completed=True,
                    completed_at=datetime.now(timezone.utc)
                )
                db.session.add(exercise_log)

        db.session.commit()
        session.pop('current_workout_session', None)
        flash("Workout succesvol voltooid!", "success")
        return jsonify({
            'success': True,
            'message': 'Workout completed successfully',
            'session_stats': workout_session.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error completing workout: {str(e)}")
        return jsonify({'success': False, 'message': f'Error completing workout: {str(e)}'}), 500

# Rest van je routes blijven hetzelfde...
# (workout_session_detail, get_workout_progress, archive_workout_session, etc.)