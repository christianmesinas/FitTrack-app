from flask import render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFError
from markupsafe import escape
import logging
import json

from . import bp as workouts
from .services import WorkoutService, ExerciseService
from app.decorators import owns_workout_plan, get_user_workout_plans, fix_image_path, clean_instruction_text, \
    get_workout_data
from app.forms import WorkoutPlanForm, SearchExerciseForm, ExerciseForm, DeleteExerciseForm
from app.models import WorkoutPlan, Exercise, WorkoutPlanExercise
from app import db

logger = logging.getLogger(__name__)


@workouts.route('/add', methods=['GET', 'POST'])
@login_required
def add_workout():
    """Maak een nieuw workout-plan aan."""
    logger.debug(f"Add workout route, user: {current_user.name}, user_id: {current_user.id}")
    form = WorkoutPlanForm()

    if form.validate_on_submit():
        try:
            # Verzamel exercise data uit formulier
            exercises_data = []
            for exercise_form in form.exercises:
                if exercise_form.exercise_id.data:
                    exercises_data.append({
                        'exercise_id': exercise_form.exercise_id.data,
                        'sets': exercise_form.sets.data,
                        'reps': exercise_form.reps.data,
                        'weight': exercise_form.weight.data
                    })

            # Voeg tijdelijke oefeningen uit sessie toe
            temp_exercises = session.get('temp_exercises', [])
            for exercise_id in temp_exercises:
                exercises_data.append({
                    'exercise_id': exercise_id,
                    'sets': 3,
                    'reps': 10,
                    'weight': 0.0
                })

            # Maak workout via service
            new_workout = WorkoutService.create_workout_plan(
                user_id=current_user.id,
                name=escape(form.name.data),
                exercises_data=exercises_data
            )

            # Stel plan in als huidig plan van gebruiker
            current_user.current_workout_plan = new_workout
            db.session.commit()

            # Ruim tijdelijke data op
            session.pop('temp_exercises', None)

            flash("Workout aangemaakt!", "success")
            return redirect(url_for('workouts.edit_workout', plan_id=new_workout.id))

        except Exception as e:
            logger.error(f"Error creating workout: {str(e)}")
            flash("Er is iets fout gegaan bij het aanmaken van de workout.", "error")
            return redirect(url_for('workouts.add_workout'))

    # Laad tijdelijke oefeningen voor GET-verzoek
    temp_exercises = session.get('temp_exercises', [])
    exercises = []
    if temp_exercises:
        exercises = Exercise.query.filter(Exercise.id.in_(temp_exercises)).all()

    existing_plans = get_user_workout_plans(current_user.id, archived=None)

    return render_template('new_workout.html',
                           form=form,
                           plan=None,
                           workout_plan=None,
                           exercises=exercises,
                           existing_plans=existing_plans)


@workouts.route('/edit_workout/<int:plan_id>', methods=['GET', 'POST'])
@login_required
@owns_workout_plan
def edit_workout(plan_id):
    """Bewerk een bestaand workout-plan."""
    workout_plan = WorkoutPlan.query.get_or_404(plan_id)
    form = WorkoutPlanForm()

    plan_exercises = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id).order_by(
        WorkoutPlanExercise.order).all()

    delete_exercise_form = DeleteExerciseForm()

    if request.method == 'GET':
        # Vul formulier met huidige plan-data
        form.name.data = workout_plan.name
        while form.exercises.entries:
            form.exercises.pop_entry()

        for plan_exercise in plan_exercises:
            exercise_form = ExerciseForm()
            exercise_form.exercise_id.data = plan_exercise.exercise_id
            exercise_form.sets.data = plan_exercise.sets
            exercise_form.reps.data = plan_exercise.reps
            exercise_form.weight.data = plan_exercise.weight
            exercise_form.order.data = plan_exercise.order or 0
            exercise_form.is_edit.data = 1
            form.exercises.append_entry(exercise_form)

    # Laad alle oefeningen voor lookup
    exercises = Exercise.query.all()
    exercises_dict = {str(ex.id): ex for ex in exercises}

    # Verwerk afbeeldingen
    for ex in exercises:
        try:
            ex.images_list = json.loads(ex.images) if ex.images else []
        except Exception:
            ex.images_list = []

    if request.method == 'POST':
        if form.validate_on_submit():
            try:
                # Update workout naam
                workout_plan.name = escape(form.name.data)
                db.session.add(workout_plan)

                # Verwerk oefeningen uit formulier
                for idx, exercise_form in enumerate(form.exercises):
                    exercise_id = exercise_form.exercise_id.data
                    if exercise_id == 0:
                        continue

                    # Zoek bestaande WorkoutPlanExercise
                    plan_exercise = WorkoutPlanExercise.query.filter_by(
                        workout_plan_id=plan_id,
                        exercise_id=exercise_id,
                        order=exercise_form.order.data
                    ).first()

                    if plan_exercise:
                        # Update bestaande oefening
                        WorkoutService.update_exercise_in_plan(
                            plan_id=plan_id,
                            exercise_id=exercise_id,
                            sets=exercise_form.sets.data or 0,
                            reps=exercise_form.reps.data or 0,
                            weight=exercise_form.weight.data or 0.0,
                            order=idx
                        )
                    else:
                        # Voeg nieuwe oefening toe
                        WorkoutService.add_exercise_to_plan(
                            plan_id=plan_id,
                            exercise_id=exercise_id,
                            sets=exercise_form.sets.data or 0,
                            reps=exercise_form.reps.data or 0,
                            weight=exercise_form.weight.data or 0.0,
                            order=idx
                        )

                flash('Workout bijgewerkt!', 'success')
                return redirect(url_for('workouts.edit_workout', plan_id=plan_id))

            except Exception as e:
                logger.error(f"Error updating workout: {str(e)}")
                flash('Er is iets fout gegaan bij het opslaan.', 'error')
        else:
            logger.error(f"Form validation failed: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Fout in {field}: {error}", 'error')

    exercise_pairs = [(pe, form.exercises.entries[i]) for i, pe in enumerate(plan_exercises)]

    return render_template(
        'edit_workout.html',
        form=form,
        workout_plan=workout_plan,
        exercises_dict=exercises_dict,
        delete_exercise_form=delete_exercise_form,
        exercise_pairs=exercise_pairs,
        plan_exercises=plan_exercises
    )


@workouts.route('/<int:plan_id>/add_exercise', methods=['POST'])
@login_required
@owns_workout_plan
def add_exercise_to_workout(plan_id):
    """Voeg een oefening toe aan een workout-plan."""
    logger.debug(f"Add exercise to plan, user: {current_user.name}, plan_id: {plan_id}")

    # Haal exercise_id uit JSON, querystring, of formulier
    data = request.get_json(silent=True) or {}
    exercise_id = data.get('exercise_id')
    if not exercise_id:
        try:
            exercise_id = int(request.args.get('exercise_id') or request.form.get('exercise_id'))
        except (ValueError, TypeError):
            logger.error(f"Invalid or missing exercise_id")
            return jsonify({'success': False, 'message': 'Exercise ID is required'}), 400

    next_url = data.get('next') or url_for('workouts.edit_workout', plan_id=plan_id)

    try:
        # Speciale case voor tijdelijke workouts (plan_id=0)
        if plan_id == 0:
            if 'temp_exercises' not in session:
                session['temp_exercises'] = []
            if exercise_id not in session['temp_exercises']:
                session['temp_exercises'].append(exercise_id)
                session.modified = True
            return jsonify({'success': True, 'message': 'Exercise added to temporary workout'})

        # Voeg exercise toe via service
        plan_exercise = WorkoutService.add_exercise_to_plan(
            plan_id=plan_id,
            exercise_id=exercise_id
        )

        exercise = Exercise.query.get(exercise_id)
        flash(f"{exercise.name} toegevoegd aan workout!", "success")
        return jsonify({
            'success': True,
            'message': f'{exercise.name} added to workout plan',
            'redirect': next_url
        })

    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except CSRFError as e:
        logger.error(f"CSRF error: {str(e)}")
        return jsonify({'success': False, 'message': 'Invalid or missing CSRF token'}), 403
    except Exception as e:
        logger.error(f"Error adding exercise: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': 'Error adding exercise'}), 500


@workouts.route('/<int:plan_id>/exercise/<int:exercise_id>/edit', methods=['POST'])
@login_required
@owns_workout_plan
def edit_exercise(plan_id, exercise_id):
    """Bewerk een oefening in een workout-plan."""
    data = request.get_json()

    try:
        updates = {}
        if data.get('sets') is not None:
            updates['sets'] = int(data['sets'])
        if data.get('reps') is not None:
            updates['reps'] = int(data['reps'])
        if data.get('weight') is not None:
            updates['weight'] = float(data['weight'])
        if data.get('duration_minutes') is not None:
            updates['duration_minutes'] = float(data['duration_minutes'])
        if data.get('distance_km') is not None:
            updates['distance_km'] = float(data['distance_km'])

        WorkoutService.update_exercise_in_plan(
            plan_id=plan_id,
            exercise_id=exercise_id,
            **updates
        )

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error editing exercise: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@workouts.route('/<int:plan_id>/exercise/<int:exercise_id>/remove', methods=['POST'])
@login_required
@owns_workout_plan
def remove_exercise_from_workout(plan_id, exercise_id):
    """Verwijder een oefening uit een workout-plan."""
    try:
        WorkoutService.remove_exercise_from_plan(plan_id, exercise_id)

        exercise = Exercise.query.get(exercise_id)
        flash(f"{exercise.name} verwijderd uit workout!", "success")
        return jsonify({'success': True, 'message': 'Exercise removed from workout'})

    except Exception as e:
        logger.error(f"Error removing exercise: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500


@workouts.route('/search_exercise')
@login_required
def search_exercise():
    """Zoek en toon oefeningen voor toevoeging aan een workout-plan."""
    form = SearchExerciseForm(request.args)
    plan_id = request.args.get('plan_id', type=int)

    if not plan_id:
        flash("Maak eerst een workout plan aan.", "info")
        return redirect(url_for('workouts.add_workout'))

    # Controleer of plan bestaat en van gebruiker is
    plan = WorkoutPlan.query.get(plan_id)
    if not plan or plan.user_id != current_user.id:
        flash("Workout plan niet gevonden.", "error")
        return redirect(url_for('workouts.add_workout'))

    # Zoek oefeningen via service
    try:
        filters = {}
        if form.validate():
            if form.search_term.data:
                filters['search_term'] = form.search_term.data
            if form.difficulty.data:
                filters['difficulty'] = form.difficulty.data
            if form.mechanic.data:
                filters['mechanic'] = form.mechanic.data
            if form.equipment.data:
                filters['equipment'] = form.equipment.data
            if form.category.data:
                filters['category'] = form.category.data

        query = ExerciseService.search_exercises(**filters)

        # Pagination
        page = request.args.get('page', 1, type=int)
        pagination = query.paginate(page=page, per_page=10, error_out=False)
        exercises = pagination.items

        # Fix image paths
        for exercise in exercises:
            if exercise.images and exercise.images.startswith('['):
                try:
                    images_list = json.loads(exercise.images)
                    exercise.image_url = fix_image_path(images_list[0])
                except Exception:
                    exercise.image_url = fix_image_path(exercise.images)
            else:
                exercise.image_url = fix_image_path(exercise.images) if exercise.images else 'default.jpg'

        # AJAX-verzoek? -> alleen oefeningen (HTML-fragment)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render_template('_exercise_items.html', exercises=exercises)

        return render_template(
            'search_exercise.html',
            form=form,
            exercises=exercises,
            plan_id=plan.id,
            pagination=pagination
        )

    except Exception as e:
        logger.error(f"Error searching exercises: {str(e)}")
        flash("Er is een fout opgetreden bij het zoeken naar oefeningen.", "error")
        return redirect(url_for('workouts.edit_workout', plan_id=plan_id))


@workouts.route('/exercise/<int:exercise_id>')
@login_required
def exercise_detail(exercise_id):
    """Toon details van een specifieke oefening."""
    exercise = Exercise.query.get_or_404(exercise_id)

    # Zet de images correct om naar lijst
    raw_images = exercise.images or []
    if isinstance(raw_images, str):
        try:
            raw_images = json.loads(raw_images)
        except Exception as e:
            logger.error(f"Kon images niet parsen: {raw_images} — fout: {e}")
            raw_images = []

    fixed_images = [fix_image_path(img) for img in raw_images]

    # Parseer instructies
    raw_instructions = exercise.instructions or []
    if isinstance(raw_instructions, str):
        try:
            raw_instructions = json.loads(raw_instructions)
        except Exception as e:
            logger.error(f"Kon instructies niet parsen: {raw_instructions} — fout: {e}")
            raw_instructions = []

    cleaned_instructions = [clean_instruction_text(step) for step in raw_instructions]

    exercise_dict = {
        'name': exercise.name,
        'images': fixed_images,
        'instructions': cleaned_instructions,
        'level': exercise.level,
        'equipment': exercise.equipment,
        'mechanic': exercise.mechanic,
        'category': exercise.category,
    }

    return render_template('exercise_detail.html', exercise=exercise_dict)


@workouts.route('/<int:plan_id>/archive', methods=['POST'])
@login_required
@owns_workout_plan
def archive_workout(plan_id):
    """Archiveer een workout-plan."""
    try:
        workout = WorkoutPlan.query.get_or_404(plan_id)
        workout.is_archived = True
        db.session.commit()

        logger.info(f"Workout archived: workout_id={plan_id}")
        return jsonify({'success': True, 'message': 'Workout succesvol gearchiveerd.'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error archiving workout: {str(e)}")
        return jsonify({'success': False, 'message': f'Fout bij het archiveren: {str(e)}'}), 500



@workouts.route('/archived')
@login_required
def archived_plans():
    """Toon gearchiveerde workout-plannen."""
    workout_plans = get_user_workout_plans(current_user.id, archived=True)
    workout_data = get_workout_data(workout_plans)
    return render_template('archived_workouts.html', workout_data=workout_data)