import uuid
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

    exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(WorkoutPlanExercise.order).all()
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
    form = ActiveWorkoutForm()
    if not form.validate_on_submit():
        errors = form.errors
        logger.error(f"Form validation failed: {errors}")
        return jsonify({'success': False, 'message': f'Ongeldige formuliergegevens: {errors}'}), 400

    workout_plan = WorkoutPlan.query.get_or_404(plan_id)

    wpes = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).all()
    session_id = session.get('current_workout_session')
    if not session_id:
        logger.error("No active workout session found")
        return jsonify({'success': False, 'message': 'Geen actieve workout sessie gevonden.'}), 400

    # Verwijder bestaande SetLogs om herschrijven mogelijk te maken
    existing_logs = SetLog.query.filter_by(workout_session_id=session_id).all()
    for log in existing_logs:
        db.session.delete(log)

    # Verwerk dynamische set-data uit formulier - nu met cardio/strength onderscheid
    for wpe in wpes:
        set_num = 0
        while True:
            completed_key = f'completed_{wpe.id}_{set_num}'
            if completed_key not in request.form:
                break
            if request.form[completed_key]:
                # Bepaal of dit cardio of strength is
                if wpe.exercise.is_cardio:  # Gebruikt je bestaande @property
                    logger.debug(f"Processing cardio exercise: {wpe.exercise.name}")
                    # Verwerk cardio data
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
                            reps=1,  # Voor cardio: 1 "rep" = hele sessie
                            weight=0.0,
                            completed=True,
                            completed_at=datetime.now(timezone.utc)
                        )
                        db.session.add(log)
                        logger.debug(
                            f"Added cardio SetLog: wpe_id={wpe.id}, set_num={set_num}, duration={duration}, distance={distance}")
                else:
                    logger.debug(f"Processing strength exercise: {wpe.exercise.name}")
                    # Verwerk strength training data (je bestaande logica)
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
                        logger.debug(
                            f"Added strength SetLog: wpe_id={wpe.id}, set_num={set_num}, reps={reps}, weight={weight}")
            set_num += 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error: {str(e)}")
        return jsonify({'success': False, 'message': f'Database fout: {str(e)}'}), 500

    # Update sessie-statistieken
    workout_session = WorkoutSession.query.get(session_id)
    if workout_session:
        workout_session.calculate_statistics()
        try:
            db.session.commit()
            logger.debug(f"Updated statistics for session_id={session_id}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Statistics update error: {str(e)}")
            return jsonify({'success': False, 'message': f'Statistics update fout: {str(e)}'}), 500

    logger.info("Workout succesvol opgeslagen met cardio support!")
    return jsonify({'success': True, 'message': 'Workout succesvol opgeslagen!'})



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
        # Haal WorkoutPlanExercise op
        wpe = WorkoutPlanExercise.query.get_or_404(wpe_id)

        # Controleer autorisatie
        if wpe.workout_plan.user_id != current_user.id:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        # Haal huidige workout session op
        session_id = session.get('current_workout_session')
        if not session_id:
            return jsonify({'success': False, 'message': 'No active workout session'}), 400

        # Check of deze set al bestaat
        existing_set = SetLog.query.filter_by(
            workout_plan_exercise_id=wpe_id,
            set_number=set_number,
            workout_session_id=session_id
        ).first()

        # Bepaal welke data we verwachten gebaseerd op exercise type
        if wpe.exercise.is_cardio:  # Gebruikt je bestaande @property
            logger.debug(f"Saving cardio set for {wpe.exercise.name}")
            # Voor cardio verwachten we duration en optioneel distance
            duration_minutes = data.get('duration_minutes')
            distance_km = data.get('distance_km', 0.0)

            if not duration_minutes and completed:
                return jsonify({'success': False, 'message': 'Duration is required for cardio exercises'}), 400

            if existing_set:
                existing_set.duration_minutes = duration_minutes
                existing_set.distance_km = distance_km
                existing_set.completed = completed
                existing_set.reps = 1  # Voor cardio: 1 "rep" = hele sessie
                existing_set.weight = 0.0  # Niet relevant voor cardio
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
                    reps=1,  # Voor cardio: 1 "rep" = hele sessie
                    weight=0.0,
                    completed=completed,
                    workout_session_id=session_id,
                    completed_at=datetime.now(timezone.utc) if completed else None
                )
                db.session.add(set_log)
        else:
            logger.debug(f"Saving strength set for {wpe.exercise.name}")
            # Voor strength training verwachten we reps en weight
            reps = data.get('reps')
            weight = data.get('weight', 0.0)

            if not reps and completed:
                return jsonify({'success': False, 'message': 'Reps are required for strength exercises'}), 400

            if existing_set:
                existing_set.reps = reps
                existing_set.weight = weight
                existing_set.completed = completed
                existing_set.duration_minutes = None  # Niet relevant voor strength
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
            'exercise_category': wpe.exercise.category.value
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving set: {str(e)}")
        return jsonify({'success': False, 'message': f'Error saving set: {str(e)}'}), 500



@bp.route('/complete_workout/<int:plan_id>', methods=['POST'])
@login_required
@owns_workout_plan
#    Voltooi een workout en aggregeer set-logs naar exercise-logs.

def complete_workout(plan_id):
    logger.debug(f"Attempting to complete workout for plan_id={plan_id}, user_id={current_user.id}")
    try:
        session_id = session.get('current_workout_session')
        logger.debug(f"Session ID: {session_id}")
        if not session_id:
            logger.error("No active workout session found")
            return jsonify({'success': False, 'message': 'No active workout session'}), 400

        workout_session = WorkoutSession.query.get_or_404(session_id)
        logger.debug(f"Found workout_session: id={workout_session.id}, user_id={workout_session.user_id}")
        if workout_session.user_id != current_user.id:
            logger.error(f"Unauthorized: session_user_id={workout_session.user_id}, current_user_id={current_user.id}")
            return jsonify({'success': False, 'message': 'Unauthorized'}), 403

        # Markeer sessie als voltooid

        workout_session.completed_at = datetime.now(timezone.utc)
        workout_session.is_completed = True
        workout_session.calculate_statistics()

        # Haal voltooide sets op

        completed_sets = SetLog.query.filter_by(
            workout_session_id=session_id,
            completed=True
        ).all()
        logger.debug(f"Found {len(completed_sets)} completed sets for session_id={session_id}")

        # Groepeer sets per oefening

        exercise_groups = {}
        for set_log in completed_sets:
            exercise_id = set_log.exercise_id
            if exercise_id not in exercise_groups:
                exercise_groups[exercise_id] = []
            exercise_groups[exercise_id].append(set_log)

        # Maak ExerciseLogs voor elke oefening

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
                logger.debug(f"Created ExerciseLog: exercise_id={exercise_id}, sets={len(sets)}")

        db.session.commit()
        session.pop('current_workout_session', None)
        logger.info(f"Completed workout_session: id={workout_session.id}, plan_id={plan_id}")
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


@bp.route('/workout_session/<session_id>')
@login_required
#    Toon details van een workout-sessie.

def workout_session_detail(session_id):
    workout_session = WorkoutSession.query.get_or_404(session_id)

    if workout_session.user_id != current_user.id:
        flash("Je hebt geen toegang tot deze workout sessie.", "error")
        return redirect(url_for('profile.workout_history'))

    # Haal alle voltooide sets op voor deze sessie
    set_logs = SetLog.query.filter_by(
        workout_session_id=session_id,
        completed=True
    ).options(
        db.joinedload(SetLog.exercise)
    ).order_by(SetLog.exercise_id, SetLog.set_number).all()

    # Groepeer sets per oefening en bereken statistieken
    exercise_groups = {}
    total_sets = 0
    total_reps = 0
    total_weight = 0

    for set_log in set_logs:
        exercise_id = set_log.exercise_id
        if exercise_id not in exercise_groups:
            exercise_groups[exercise_id] = {
                'exercise': set_log.exercise,
                'sets': [],
                'total_reps': 0,
                'total_weight': 0,
                'max_weight': 0
            }

        exercise_groups[exercise_id]['sets'].append(set_log)
        exercise_groups[exercise_id]['total_reps'] += set_log.reps
        exercise_groups[exercise_id]['total_weight'] += (set_log.weight * set_log.reps)

        if set_log.weight > exercise_groups[exercise_id]['max_weight']:
            exercise_groups[exercise_id]['max_weight'] = set_log.weight

        total_sets += 1
        total_reps += set_log.reps
        total_weight += (set_log.weight * set_log.reps)

    # Bereken workout duur
    if workout_session.completed_at and workout_session.started_at:
        duration = workout_session.completed_at - workout_session.started_at
        duration_minutes = round(duration.total_seconds() / 60)
    else:
        duration_minutes = 0

    # Update workout session statistieken als ze nog niet bestaan
    if not workout_session.total_sets:
        workout_session.total_sets = total_sets
        workout_session.total_reps = total_reps
        workout_session.total_weight = total_weight
        workout_session.duration_minutes = duration_minutes
        db.session.commit()

    return render_template('workout_session_detail.html',
                           workout_session=workout_session,
                           exercise_groups=exercise_groups,
                           total_sets=total_sets,
                           total_reps=total_reps,
                           total_weight=total_weight,
                           duration_minutes=duration_minutes)



@bp.route('/get_workout_progress/<session_id>')
@login_required
#    Haal voortgang van een workout-sessie op.
def get_workout_progress(session_id):
    workout_session = WorkoutSession.query.get_or_404(session_id)

    if workout_session.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    # Tel voltooide sets

    completed_sets = SetLog.query.filter_by(
        workout_session_id=session_id,
        completed=True
    ).count()

    # Haal totale geplande sets op

    total_planned_sets = db.session.query(db.func.sum(WorkoutPlanExercise.sets)).filter_by(
        workout_plan_id=workout_session.workout_plan_id
    ).scalar() or 0

    # Bereken voortgang

    progress_percentage = (completed_sets / total_planned_sets * 100) if total_planned_sets > 0 else 0

    return jsonify({
        'completed_sets': completed_sets,
        'total_planned_sets': total_planned_sets,
        'progress_percentage': round(progress_percentage, 1),
        'session_duration': (datetime.now(timezone.utc) - workout_session.started_at).total_seconds() / 60
    })

@bp.route('/archive_workout_session/<session_id>', methods=['POST'])
@login_required
#    Archiveer een workout-sessie.

def archive_workout_session(session_id):
    logger.debug(f"Archiving workout session: session_id={session_id}, user_id={current_user.id}")

    workout_session = WorkoutSession.query.get_or_404(session_id)
    if workout_session.user_id != current_user.id:
        logger.error(
            f"Unauthorized access: session_user_id={workout_session.user_id}, current_user_id={current_user.id}")
        flash("Je hebt geen toegang tot deze workout sessie.", "error")
        return redirect(url_for('profile.workout_history'))

    workout_session.is_archived = True
    try:
        db.session.commit()
        flash("Workout succesvol gearchiveerd.", "success")
        logger.info(f"Workout session archived: session_id={session_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error archiving workout session: {str(e)}")
        flash("Fout bij het archiveren van de workout.", "error")

    return redirect(url_for('profile.workout_history'))


@bp.route('/archive_workout/<int:workout_id>', methods=['POST'])
@login_required
#    Archiveer een workout-plan.

def archive_workout(workout_id):
    logger.debug(f"Archiving workout: workout_id={workout_id}, user_id={current_user.id}")
    workout = WorkoutPlan.query.get_or_404(workout_id)

    workout.is_archived = True
    try:
        db.session.commit()
        logger.info(f"Workout archived: workout_id={workout_id}")
        return jsonify({'success': True, 'message': 'Workout succesvol gearchiveerd.'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error archiving workout: {str(e)}")
        return jsonify({'success': False, 'message': f'Fout bij het archiveren: {str(e)}'}), 500

@bp.route('/archived_plans')
@login_required
#     Toon gearchiveerde workout-plannen.
def archived_plans():
    logger.debug(f"Archived plans route aangeroepen voor {current_user.name}")
    workout_plans = get_user_workout_plans(current_user.id, archived=True)
    workout_data = get_workout_data(workout_plans)

    return render_template('archived_workouts.html', workout_data=workout_data)
