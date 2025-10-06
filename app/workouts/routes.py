import os
import uuid

from flask import render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
from flask_wtf.csrf import CSRFError
from markupsafe import escape
import logging
import json

from werkzeug.utils import secure_filename

from . import bp as workouts
from .services import WorkoutService, ExerciseService
from app.decorators import owns_workout_plan, get_user_workout_plans, fix_image_path, clean_instruction_text, \
    get_workout_data
from app.forms import WorkoutPlanForm, SearchExerciseForm, ExerciseForm, DeleteExerciseForm, AddExerciseForm
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
            if form.difficulty.data and form.difficulty.data != 'NONE':
                filters['difficulty'] = form.difficulty.data
            if form.mechanic.data and form.mechanic.data != 'NONE':
                filters['mechanic'] = form.mechanic.data
            if form.equipment.data and form.equipment.data != 'NONE':
                filters['equipment'] = form.equipment.data
            if form.category.data and form.category.data != 'NONE':
                filters['category'] = form.category.data

        query = ExerciseService.search_exercises(**filters)

        # Pagination
        page = request.args.get('page', 1, type=int)
        pagination = query.paginate(page=page, per_page=10, error_out=False)
        exercises = pagination.items

        # Fix image paths - Dit is de belangrijke fix
        for exercise in exercises:
            try:
                image_url = None
                if exercise.images:
                    # Parse de images JSON
                    images_list = json.loads(exercise.images) if isinstance(exercise.images, str) else exercise.images

                    # Verwerk de afbeelding-paden
                    real_images = []
                    for img in images_list:
                        if img and img != 'img/exercises/default.jpg' and 'default.jpg' not in img:
                            # Als het pad al volledig is (begint met img/exercises/), gebruik direct
                            if img.startswith('img/exercises/'):
                                real_images.append(img)
                            # Als het alleen img/ heeft, voeg exercises/ toe
                            elif img.startswith('img/'):
                                # img/3_4_Sit-Up/0.jpg -> img/exercises/3_4_Sit-Up/0.jpg
                                real_images.append(img.replace('img/', 'img/exercises/'))
                            else:
                                # Voor paden zonder img/ prefix
                                real_images.append(f'img/exercises/{img}')

                    # Gebruik de eerste echte afbeelding
                    if real_images:
                        image_url = real_images[0]

                # Als we geen echte afbeelding hebben, gebruik placeholder
                if not image_url:
                    image_url = 'img/placeholder.png'

                exercise.image_url = image_url

            except (json.JSONDecodeError, IndexError, TypeError) as e:
                logger.warning(f"Failed to parse images for exercise {exercise.id}: {str(e)}")
                exercise.image_url = 'img/placeholder.png'

        # AJAX-verzoek? -> alleen oefeningen (HTML-fragment)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render_template('_exercise_items.html', exercises=exercises, plan_id=plan_id)

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


@workouts.route('/exercise/<exercise_id>')
@login_required
def exercise_detail(exercise_id):
    """Toon details van een specifieke oefening."""
    exercise = Exercise.query.get_or_404(exercise_id)

    # Debug logging
    logger.debug(f"Exercise {exercise_id}: raw images = {exercise.images}")

    # Verwerk de images van de exercise
    image_url = None
    fixed_images = []

    if exercise.images:
        if isinstance(exercise.images, str):
            try:
                raw_images = json.loads(exercise.images)
            except Exception as e:
                logger.error(f"Kon images niet parsen: {exercise.images} — fout: {e}")
                raw_images = []
        else:
            raw_images = exercise.images

        logger.debug(f"Exercise {exercise_id}: parsed raw_images = {raw_images}")

        # Verwerk de afbeelding-paden
        for img in raw_images:
            if img and img != 'img/exercises/default.jpg' and 'default.jpg' not in img:
                # Als het pad al volledig is (begint met img/exercises/), gebruik direct
                if img.startswith('img/exercises/'):
                    fixed_images.append(img)
                # Als het alleen img/ heeft, voeg exercises/ toe
                elif img.startswith('img/'):
                    # img/3_4_Sit-Up/0.jpg -> img/exercises/3_4_Sit-Up/0.jpg
                    fixed_images.append(img.replace('img/', 'img/exercises/'))
                else:
                    # Voor paden zonder img/ prefix
                    fixed_images.append(f'img/exercises/{img}')

        logger.debug(f"Exercise {exercise_id}: fixed_images = {fixed_images}")

        # Gebruik de eerste echte afbeelding
        if fixed_images:
            image_url = fixed_images[0]

    # Als we geen echte afbeelding hebben, gebruik placeholder
    if not image_url:
        image_url = 'img/placeholder.png'

    logger.debug(f"Exercise {exercise_id}: final image_url = {image_url}")

    # Parseer instructies
    raw_instructions = exercise.instructions or []
    if isinstance(raw_instructions, str):
        try:
            raw_instructions = json.loads(raw_instructions)
        except Exception as e:
            logger.error(f"Kon instructies niet parsen: {raw_instructions} — fout: {e}")
            raw_instructions = []

    # Gebruik clean_instruction_text als beschikbaar, anders gewoon de instructies
    try:
        cleaned_instructions = [clean_instruction_text(step) for step in raw_instructions]
    except NameError:
        cleaned_instructions = raw_instructions

    exercise_dict = {
        'name': exercise.name,
        'images': fixed_images,
        'image_url': image_url,
        'instructions': cleaned_instructions,
        'level': exercise.level,
        'equipment': exercise.equipment,
        'mechanic': exercise.mechanic,
        'category': exercise.category,
        'youtube_url': getattr(exercise, 'youtube_url', None),
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

@workouts.route('/add_new_exercise', methods=['GET', 'POST'])
@login_required
def add_new_exercise():
    """Maak een nieuwe oefening aan."""
    logger.debug(f"Add new exercise route, user: {current_user.name}, user_id: {current_user.id}")
    form = AddExerciseForm()
    plan_id = request.args.get('plan_id', type=int)
    existing_plans = WorkoutPlan.query.filter_by(user_id=current_user.id, is_archived=False).all()

    if form.validate_on_submit():
        try:
            # Genereer een unieke ID voor de oefening
            exercise_id = str(uuid.uuid4())[:50]

            # Verwerk instructies (als lijst)
            instructions = form.instructions.data.splitlines() if form.instructions.data else []
            instructions = [line.strip() for line in instructions if line.strip()]

            # Verwerk afbeeldingen
            images = []
            if form.images.data:
                for file in form.images.data:
                    if file:
                        filename = secure_filename(file.filename)
                        safe_name = secure_filename(form.name.data.replace(" ", "_")) or "unnamed_exercise"
                        upload_folder = os.path.join('app', 'static', 'img', 'exercises', safe_name)
                        absolute_upload_folder = os.path.abspath(upload_folder)
                        os.makedirs(absolute_upload_folder, exist_ok=True)
                        file_path = os.path.join('img', 'exercises', safe_name, filename)
                        absolute_file_path = os.path.abspath(os.path.join('app', 'static', file_path))
                        file.save(absolute_file_path)
                        images.append(file_path)

            # Verwerk video-upload
            video_path = None
            if form.video_file.data:
                video = form.video_file.data
                filename = secure_filename(video.filename)
                safe_name = secure_filename(form.name.data.replace(" ", "_")) or "unnamed_exercise"
                upload_folder = os.path.join('app', 'static', 'videos', 'exercises', safe_name)
                absolute_upload_folder = os.path.abspath(upload_folder)
                os.makedirs(absolute_upload_folder, exist_ok=True)
                video_path = os.path.join('videos', 'exercises', safe_name, filename)
                absolute_video_path = os.path.abspath(os.path.join('app', 'static', video_path))
                video.save(absolute_video_path)

            # Maak nieuwe oefening
            new_exercise = Exercise(
                id=exercise_id,
                name=escape(form.name.data),
                force=form.force.data if form.force.data != 'NONE' else None,
                level=form.difficulty.data,
                mechanic=form.mechanic.data if form.mechanic.data != 'NONE' else None,
                equipment=form.equipment.data if form.equipment.data != 'NONE' else None,
                category=form.category.data,
                instructions=json.dumps(instructions),
                images=json.dumps(images),
                is_public=form.is_public.data,
                user_id=current_user.id if not form.is_public.data else None
            )

            db.session.add(new_exercise)
            db.session.commit()

            # Haal workout_plan_id uit formulier of gebruik plan_id
            workout_plan_id = request.form.get('workout_plan', type=int) or plan_id
            if workout_plan_id:
                WorkoutService.add_exercise_to_plan(
                    plan_id=workout_plan_id,
                    exercise_id=exercise_id,
                    sets=3,
                    reps=10,
                    weight=0.0,
                    order=WorkoutPlanExercise.query.filter_by(workout_plan_id=workout_plan_id).count()
                )
                flash(f"Oefening '{new_exercise.name}' toegevoegd aan workout-plan!", "success")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': True,
                        'exercise_id': exercise_id,
                        'message': f"Oefening '{new_exercise.name}' aangemaakt en toegevoegd aan workout-plan"
                    })
                return redirect(url_for('workouts.edit_workout', plan_id=workout_plan_id))

            flash(f"Oefening '{new_exercise.name}' succesvol aangemaakt!", "success")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'exercise_id': exercise_id,
                    'message': f"Oefening '{new_exercise.name}' aangemaakt"
                })
            return redirect(url_for('workouts.search_exercise', plan_id=plan_id) if plan_id else url_for('workouts.add_workout'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Fout bij het aanmaken van oefening: {str(e)}")
            flash("Er is een fout opgetreden bij het aanmaken van de oefening.", "error")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)}), 500
            return render_template('add_exercise.html', form=form, plan_id=plan_id, existing_plans=existing_plans)

    return render_template('add_exercise.html', form=form, plan_id=plan_id, existing_plans=existing_plans)


@workouts.route('/archived')
@login_required
def archived_plans():
    """Toon gearchiveerde workout-plannen."""
    workout_plans = get_user_workout_plans(current_user.id, archived=True)
    workout_data = get_workout_data(workout_plans)
    return render_template('archived_workouts.html', workout_data=workout_data)


@workouts.route('/<int:plan_id>/use_template', methods=['POST'])
@login_required
@owns_workout_plan
def use_template(plan_id):
    """Voeg een voorgemaakt workout template toe aan een plan."""
    try:
        data = request.get_json()
        template_key = data.get('template_key')

        if not template_key:
            return jsonify({'success': False, 'message': 'Template key is required'}), 400

        # Template definities met exercise namen en configuratie
        templates = {
            'fullbody': [
                {'name': 'Barbell Squat', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Bench Press', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Bent Over Barbell Row', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Shoulder Press', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Romanian Deadlift', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Pullups', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Dumbbell Bicep Curl', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Dips - Triceps Version', 'sets': 3, 'reps': 15, 'weight': 0}
            ],
            'push': [
                {'name': 'Barbell Bench Press - Medium Grip', 'sets': 4, 'reps': 8, 'weight': 0},
                {'name': 'Incline Dumbbell Press', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Cable Crossover', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Shoulder Press', 'sets': 4, 'reps': 8, 'weight': 0},
                {'name': 'Side Lateral Raise', 'sets': 4, 'reps': 15, 'weight': 0},
                {'name': 'Reverse Flyes', 'sets': 3, 'reps': 20, 'weight': 0},
                {'name': 'Close-Grip Barbell Bench Press', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Triceps Pushdown', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Overhead Cable Curl', 'sets': 3, 'reps': 15, 'weight': 0}
            ],
            'pull': [
                {'name': 'Deadlift', 'sets': 4, 'reps': 6, 'weight': 0},
                {'name': 'Pullups', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Bent Over Barbell Row', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Seated Cable Rows', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'T-Bar Row', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Face Pull', 'sets': 3, 'reps': 20, 'weight': 0},
                {'name': 'Barbell Curl', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Hammer Curls', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Cable Curl', 'sets': 3, 'reps': 15, 'weight': 0}
            ],
            'legs': [
                {'name': 'Barbell Squat', 'sets': 4, 'reps': 8, 'weight': 0},
                {'name': 'Romanian Deadlift', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Barbell Front Squat', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Leg Press', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Barbell Walking Lunge', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Lying Leg Curls', 'sets': 4, 'reps': 15, 'weight': 0},
                {'name': 'Leg Extensions', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Standing Calf Raises', 'sets': 4, 'reps': 20, 'weight': 0},
                {'name': 'Bulgarian Split Squat', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Plank', 'sets': 3, 'reps': 60, 'weight': 0}
            ],
            'upper': [
                {'name': 'Bench Press', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Bent Over Barbell Row', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Shoulder Press', 'sets': 3, 'reps': 10, 'weight': 0},
                {'name': 'Pullups', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Dumbbell Flyes', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Side Lateral Raise', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Barbell Curl', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Lying Triceps Press', 'sets': 3, 'reps': 12, 'weight': 0}
            ],
            'arms': [
                {'name': 'Barbell Curl', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Close-Grip Barbell Bench Press', 'sets': 4, 'reps': 10, 'weight': 0},
                {'name': 'Hammer Curls', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Overhead Cable Curl', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Preacher Curl', 'sets': 3, 'reps': 12, 'weight': 0},
                {'name': 'Triceps Pushdown', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Cable Curl', 'sets': 3, 'reps': 15, 'weight': 0},
                {'name': 'Pushups - Close Triceps Position', 'sets': 3, 'reps': 20, 'weight': 0}
            ]
        }

        if template_key not in templates:
            return jsonify({'success': False, 'message': 'Invalid template'}), 400

        template_exercises = templates[template_key]
        added_count = 0
        not_found = []

        # Bepaal huidige max order
        max_order = db.session.query(db.func.max(WorkoutPlanExercise.order)).filter_by(
            workout_plan_id=plan_id
        ).scalar() or -1

        for idx, exercise_config in enumerate(template_exercises):
            # Zoek exercise op naam (case-insensitive, flexibele matching)
            exercise_name = exercise_config['name']

            # Probeer eerst exacte match
            exercise = Exercise.query.filter(
                Exercise.name.ilike(exercise_name)
            ).first()

            # Als niet gevonden, probeer gedeeltelijke match
            if not exercise:
                exercise = Exercise.query.filter(
                    Exercise.name.ilike(f'%{exercise_name}%')
                ).first()

            if exercise:
                try:
                    # Check of exercise al bestaat in plan
                    existing = WorkoutPlanExercise.query.filter_by(
                        workout_plan_id=plan_id,
                        exercise_id=exercise.id
                    ).first()

                    if not existing:
                        WorkoutService.add_exercise_to_plan(
                            plan_id=plan_id,
                            exercise_id=exercise.id,
                            sets=exercise_config['sets'],
                            reps=exercise_config['reps'],
                            weight=exercise_config['weight'],
                            order=max_order + idx + 1
                        )
                        added_count += 1
                except Exception as e:
                    logger.error(f"Error adding exercise {exercise_name}: {str(e)}")
                    continue
            else:
                not_found.append(exercise_name)
                logger.warning(f"Exercise not found in database: {exercise_name}")

        message = f'{added_count} oefeningen toegevoegd aan je workout!'
        if not_found:
            message += f' ({len(not_found)} oefeningen niet gevonden in database)'

        return jsonify({
            'success': True,
            'message': message,
            'added_count': added_count,
            'not_found': not_found
        })

    except Exception as e:
        logger.error(f"Error using template: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


# Voeg deze route toe aan app/workouts/routes.py (onderaan, voor use_template)

@workouts.route('/<int:plan_id>/exercises', methods=['GET'])
@login_required
@owns_workout_plan
def get_plan_exercises(plan_id):
    """Haal alle exercise IDs op van een workout plan voor markering."""
    try:
        plan_exercises = WorkoutPlanExercise.query.filter_by(
            workout_plan_id=plan_id
        ).all()

        exercise_ids = [pe.exercise_id for pe in plan_exercises]

        return jsonify({
            'success': True,
            'exercise_ids': exercise_ids
        })
    except Exception as e:
        logger.error(f"Error getting plan exercises: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500