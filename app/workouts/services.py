from app.models import WorkoutPlan, Exercise, WorkoutPlanExercise
from app import db
import logging
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class WorkoutService:
    @staticmethod
    def create_workout_plan(user_id, name, exercises_data=None):
        """Create a new workout plan with exercises"""
        try:
            workout = WorkoutPlan(name=name, user_id=user_id)
            db.session.add(workout)
            db.session.flush()

            if exercises_data:
                for idx, exercise_data in enumerate(exercises_data):
                    plan_exercise = WorkoutPlanExercise(
                        workout_plan_id=workout.id,
                        exercise_id=exercise_data['exercise_id'],
                        sets=exercise_data.get('sets', 3),
                        reps=exercise_data.get('reps', 10),
                        weight=exercise_data.get('weight', 0.0),
                        order=idx
                    )
                    db.session.add(plan_exercise)

            db.session.commit()
            return workout
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating workout plan: {str(e)}")
            raise

    @staticmethod
    def add_exercise_to_plan(plan_id, exercise_id, **kwargs):
        """Add an exercise to an existing workout plan"""
        try:
            # Valideer dat de workout plan bestaat
            workout_plan = WorkoutPlan.query.get(plan_id)
            if not workout_plan:
                raise ValueError(f"Workout plan with id {plan_id} not found")

            # Valideer dat de exercise bestaat
            exercise = Exercise.query.get(exercise_id)
            if not exercise:
                raise ValueError(f"Exercise with id {exercise_id} not found")

            # Check voor duplicaten
            existing = WorkoutPlanExercise.query.filter_by(
                workout_plan_id=plan_id,
                exercise_id=exercise_id
            ).first()

            if existing:
                raise ValueError("Exercise already exists in this workout plan")

            # Bepaal de volgende order waarde
            max_order = db.session.query(db.func.max(WorkoutPlanExercise.order)).filter_by(
                workout_plan_id=plan_id
            ).scalar() or -1
            next_order = max_order + 1

            # Maak onderscheid tussen cardio en strength exercises
            if exercise.is_cardio:
                logger.debug(f"Adding cardio exercise: {exercise.name}")
                plan_exercise = WorkoutPlanExercise(
                    workout_plan_id=plan_id,
                    exercise_id=exercise_id,
                    sets=kwargs.get('sets', 1),
                    reps=None,  # Niet relevant voor cardio
                    weight=None,  # Niet relevant voor cardio
                    duration_minutes=kwargs.get('duration_minutes', 30.0),
                    distance_km=kwargs.get('distance_km', 5.0),
                    order=kwargs.get('order', next_order)
                )
            else:
                logger.debug(f"Adding strength exercise: {exercise.name}")
                plan_exercise = WorkoutPlanExercise(
                    workout_plan_id=plan_id,
                    exercise_id=exercise_id,
                    sets=kwargs.get('sets', 3),
                    reps=kwargs.get('reps', 10),
                    weight=kwargs.get('weight', 0.0),
                    duration_minutes=None,  # Niet relevant voor strength
                    distance_km=None,  # Niet relevant voor strength
                    order=kwargs.get('order', next_order)
                )

            db.session.add(plan_exercise)
            db.session.commit()

            logger.info(f"Exercise {exercise.name} added to workout plan {workout_plan.name}")
            return plan_exercise

        except IntegrityError as e:
            db.session.rollback()
            logger.error(f"Database integrity error: {str(e)}")
            raise ValueError("Database constraint violation")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding exercise to plan: {str(e)}")
            raise

    @staticmethod
    def remove_exercise_from_plan(plan_id, exercise_id):
        """Remove an exercise from a workout plan"""
        try:
            plan_exercise = WorkoutPlanExercise.query.filter_by(
                workout_plan_id=plan_id,
                exercise_id=exercise_id
            ).first()

            if not plan_exercise:
                raise ValueError("Exercise not found in workout plan")

            db.session.delete(plan_exercise)

            # Herorden de resterende exercises
            remaining_exercises = WorkoutPlanExercise.query.filter_by(
                workout_plan_id=plan_id
            ).filter(WorkoutPlanExercise.order > plan_exercise.order).all()

            for exercise in remaining_exercises:
                exercise.order -= 1

            db.session.commit()
            logger.info(f"Exercise removed from workout plan {plan_id}")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error removing exercise from plan: {str(e)}")
            raise

    @staticmethod
    def update_exercise_in_plan(plan_id, exercise_id, **updates):
        """Update an exercise within a workout plan"""
        try:
            plan_exercise = WorkoutPlanExercise.query.filter_by(
                workout_plan_id=plan_id,
                exercise_id=exercise_id
            ).first()

            if not plan_exercise:
                raise ValueError("Exercise not found in workout plan")

            # Update alleen de velden die zijn opgegeven
            allowed_fields = ['sets', 'reps', 'weight', 'duration_minutes', 'distance_km', 'order']

            for field, value in updates.items():
                if field in allowed_fields and hasattr(plan_exercise, field):
                    setattr(plan_exercise, field, value)

            db.session.commit()
            logger.info(f"Exercise updated in workout plan {plan_id}")
            return plan_exercise

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating exercise in plan: {str(e)}")
            raise

    @staticmethod
    def reorder_exercises_in_plan(plan_id, exercise_orders):
        """
        Reorder exercises in a workout plan

        Args:
            plan_id (int): ID of the workout plan
            exercise_orders (list): List of dicts with 'exercise_id' and 'order' keys
        """
        try:
            for item in exercise_orders:
                exercise_id = item.get('exercise_id')
                new_order = item.get('order')

                plan_exercise = WorkoutPlanExercise.query.filter_by(
                    workout_plan_id=plan_id,
                    exercise_id=exercise_id
                ).first()

                if plan_exercise:
                    plan_exercise.order = new_order

            db.session.commit()
            logger.info(f"Exercises reordered in workout plan {plan_id}")
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error reordering exercises: {str(e)}")
            raise

    @staticmethod
    def get_plan_exercises(plan_id, ordered=True):
        """Get all exercises for a workout plan"""
        try:
            query = WorkoutPlanExercise.query.filter_by(workout_plan_id=plan_id)

            if ordered:
                query = query.order_by(WorkoutPlanExercise.order)

            return query.all()

        except Exception as e:
            logger.error(f"Error getting plan exercises: {str(e)}")
            raise

    @staticmethod
    def copy_exercise_from_plan(source_plan_id, target_plan_id, exercise_id):
        """Copy an exercise from one plan to another"""
        try:
            # Haal source exercise op
            source_exercise = WorkoutPlanExercise.query.filter_by(
                workout_plan_id=source_plan_id,
                exercise_id=exercise_id
            ).first()

            if not source_exercise:
                raise ValueError("Source exercise not found")

            # Check of exercise al bestaat in target plan
            existing = WorkoutPlanExercise.query.filter_by(
                workout_plan_id=target_plan_id,
                exercise_id=exercise_id
            ).first()

            if existing:
                raise ValueError("Exercise already exists in target plan")

            # Bepaal order voor target plan
            max_order = db.session.query(db.func.max(WorkoutPlanExercise.order)).filter_by(
                workout_plan_id=target_plan_id
            ).scalar() or -1

            # Maak kopie
            new_exercise = WorkoutPlanExercise(
                workout_plan_id=target_plan_id,
                exercise_id=exercise_id,
                sets=source_exercise.sets,
                reps=source_exercise.reps,
                weight=source_exercise.weight,
                duration_minutes=source_exercise.duration_minutes,
                distance_km=source_exercise.distance_km,
                order=max_order + 1
            )

            db.session.add(new_exercise)
            db.session.commit()

            logger.info(f"Exercise copied from plan {source_plan_id} to plan {target_plan_id}")
            return new_exercise

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error copying exercise: {str(e)}")
            raise


class ExerciseService:
    @staticmethod
    def search_exercises(search_term=None, category=None, difficulty=None, **filters):
        """Search exercises with filters"""
        query = Exercise.query

        if search_term:
            query = query.filter(Exercise.name.ilike(f"%{search_term}%"))
        if category:
            query = query.filter_by(category=category)
        if difficulty:
            query = query.filter_by(level=difficulty)

        return query