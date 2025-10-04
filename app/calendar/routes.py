from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
from . import bp
from app import db
from app.models import CalendarEvent, WorkoutPlan, WorkoutSession
import logging
import uuid

logger = logging.getLogger(__name__)


@bp.route('/agenda')
@login_required
def agenda():
    """Affiche l'agenda principal"""
    # Récupérer les workout plans de l'utilisateur pour le formulaire
    workout_plans = WorkoutPlan.query.filter_by(
        user_id=current_user.id,
        is_archived=False
    ).all()

    return render_template('calendar/agenda.html', workout_plans=workout_plans)


@bp.route('/events')
@login_required
def get_events():
    """API endpoint pour récupérer les événements du calendrier"""
    start = request.args.get('start')
    end = request.args.get('end')

    query = CalendarEvent.query.filter_by(user_id=current_user.id)

    if start:
        start_date = datetime.fromisoformat(start.replace('Z', '+00:00'))
        query = query.filter(CalendarEvent.start_datetime >= start_date)

    if end:
        end_date = datetime.fromisoformat(end.replace('Z', '+00:00'))
        query = query.filter(CalendarEvent.end_datetime <= end_date)

    events = query.all()

    # Ajouter aussi les workout sessions complétées comme événements
    if start and end:
        completed_sessions = WorkoutSession.query.filter(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.is_completed == True,
            WorkoutSession.completed_at >= start_date,
            WorkoutSession.completed_at <= end_date
        ).all()

        for session in completed_sessions:
            events.append({
                'id': f'session_{session.id}',
                'title': f'✅ {session.workout_plan.name if session.workout_plan else "Workout"}',
                'start': session.completed_at.isoformat(),
                'end': (session.completed_at + timedelta(minutes=session.duration_minutes or 60)).isoformat(),
                'color': '#4CAF50',
                'editable': False,
                'event_type': 'completed_workout'
            })

    # Convertir les événements en format pour FullCalendar
    events_data = []
    for event in events:
        if isinstance(event, dict):
            events_data.append(event)
        else:
            event_dict = event.to_dict()
            # Ajouter des propriétés pour FullCalendar
            event_dict['editable'] = event.status != 'completed'
            events_data.append(event_dict)

    return jsonify(events_data)


@bp.route('/event', methods=['POST'])
@login_required
def create_event():
    """Créer un nouvel événement"""
    try:
        data = request.get_json()

        # Parser les dates
        start_datetime = datetime.fromisoformat(data['start'].replace('Z', '+00:00'))
        end_datetime = datetime.fromisoformat(data['end'].replace('Z', '+00:00'))

        # Créer l'événement
        event = CalendarEvent(
            user_id=current_user.id,
            title=data['title'],
            description=data.get('description'),
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            workout_plan_id=data.get('workout_plan_id') if data.get('workout_plan_id') else None,
            event_type=data.get('event_type', 'workout'),
            color=data.get('color', '#FF6B35'),
            is_recurring=data.get('is_recurring', False),
            recurrence_pattern=data.get('recurrence_pattern'),
            reminder_minutes=data.get('reminder_minutes')
        )

        db.session.add(event)

        # Si c'est récurrent, créer les événements supplémentaires
        if event.is_recurring and event.recurrence_pattern:
            create_recurring_events(event, data.get('recurrence_count', 4))

        db.session.commit()

        return jsonify({
            'success': True,
            'event': event.to_dict(),
            'message': 'Événement créé avec succès!'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la création de l'événement: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/event/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    """Mettre à jour un événement"""
    try:
        event = CalendarEvent.query.filter_by(
            id=event_id,
            user_id=current_user.id
        ).first_or_404()

        data = request.get_json()

        # Mettre à jour les champs
        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            event.description = data['description']
        if 'start' in data:
            event.start_datetime = datetime.fromisoformat(data['start'].replace('Z', '+00:00'))
        if 'end' in data:
            event.end_datetime = datetime.fromisoformat(data['end'].replace('Z', '+00:00'))
        if 'workout_plan_id' in data:
            event.workout_plan_id = data['workout_plan_id'] if data['workout_plan_id'] else None
        if 'event_type' in data:
            event.event_type = data['event_type']
        if 'color' in data:
            event.color = data['color']
        if 'status' in data:
            event.status = data['status']

        db.session.commit()

        return jsonify({
            'success': True,
            'event': event.to_dict(),
            'message': 'Événement mis à jour!'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la mise à jour: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/event/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    """Supprimer un événement"""
    try:
        event = CalendarEvent.query.filter_by(
            id=event_id,
            user_id=current_user.id
        ).first_or_404()

        db.session.delete(event)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Événement supprimé!'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la suppression: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/event/<int:event_id>/complete', methods=['POST'])
@login_required
def complete_event(event_id):
    """Marquer un événement comme complété et créer optionnellement une WorkoutSession"""
    try:
        event = CalendarEvent.query.filter_by(
            id=event_id,
            user_id=current_user.id
        ).first_or_404()

        # Marquer l'événement comme complété
        event.status = 'completed'
        event.color = '#4CAF50'  # Vert pour complété

        # Si c'est lié à un workout plan, créer une WorkoutSession
        if event.workout_plan_id and event.event_type in ['workout', 'cardio']:
            # Calculer la durée
            duration = None
            if event.end_datetime and event.start_datetime:
                delta = event.end_datetime - event.start_datetime
                duration = int(delta.total_seconds() / 60)

            # Créer la session
            workout_session = WorkoutSession(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                workout_plan_id=event.workout_plan_id,
                started_at=event.start_datetime,
                completed_at=datetime.now(timezone.utc),
                duration_minutes=duration or 60,
                is_completed=True,
                total_sets=0,  # Ces valeurs peuvent être mises à jour plus tard
                total_reps=0,
                total_weight=0.0
            )

            db.session.add(workout_session)

            # Message personnalisé pour workout avec plan
            message = f'Training "{event.title}" voltooid! 🎉'
            response_data = {
                'success': True,
                'message': message,
                'workout_plan_id': event.workout_plan_id,
                'workout_session_id': workout_session.id,
                'redirect_to_workout': True
            }
        else:
            # Pour les événements sans workout plan ou non-workout
            message = f'Événement "{event.title}" marqué comme complété!'
            response_data = {
                'success': True,
                'message': message
            }

        db.session.commit()

        # Log pour debug
        logger.info(f"Event {event_id} marked as completed by user {current_user.id}")
        if event.workout_plan_id:
            logger.info(f"WorkoutSession created for workout_plan {event.workout_plan_id}")

        return jsonify(response_data)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la complétion de l'événement {event_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


def create_recurring_events(base_event, count=4):
    """Créer des événements récurrents basés sur un événement de base"""
    for i in range(1, count + 1):
        if base_event.recurrence_pattern == 'daily':
            delta = timedelta(days=i)
        elif base_event.recurrence_pattern == 'weekly':
            delta = timedelta(weeks=i)
        elif base_event.recurrence_pattern == 'monthly':
            delta = timedelta(days=30 * i)  # Approximation
        else:
            continue

        new_event = CalendarEvent(
            user_id=base_event.user_id,
            title=base_event.title,
            description=base_event.description,
            start_datetime=base_event.start_datetime + delta,
            end_datetime=base_event.end_datetime + delta,
            workout_plan_id=base_event.workout_plan_id,
            event_type=base_event.event_type,
            color=base_event.color,
            is_recurring=False,  # Les copies ne sont pas récurrentes
            reminder_minutes=base_event.reminder_minutes
        )
        db.session.add(new_event)


@bp.route('/week-view')
@login_required
def week_view():
    """Vue semaine pour mobile"""
    today = datetime.now(timezone.utc)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    events = CalendarEvent.query.filter(
        CalendarEvent.user_id == current_user.id,
        CalendarEvent.start_datetime >= start_of_week,
        CalendarEvent.start_datetime <= end_of_week
    ).order_by(CalendarEvent.start_datetime).all()

    # Grouper par jour
    events_by_day = {}
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        events_by_day[day_str] = []

    for event in events:
        day_str = event.start_datetime.strftime('%Y-%m-%d')
        if day_str in events_by_day:
            events_by_day[day_str].append(event)

    return render_template('calendar/week_view.html',
                           events_by_day=events_by_day,
                           start_of_week=start_of_week)


# Nieuwe functie voor synchronisatie
@bp.route('/sync-stats', methods=['POST'])
@login_required
def sync_workout_stats():
    """Synchroniser les statistiques entre CalendarEvents et WorkoutSessions"""
    try:
        # Compter les événements complétés qui n'ont pas de WorkoutSession correspondante
        completed_events = CalendarEvent.query.filter_by(
            user_id=current_user.id,
            status='completed'
        ).filter(
            CalendarEvent.event_type.in_(['workout', 'cardio'])
        ).all()

        synced_count = 0
        for event in completed_events:
            # Vérifier s'il existe déjà une session pour cette date
            existing_session = WorkoutSession.query.filter(
                WorkoutSession.user_id == current_user.id,
                WorkoutSession.workout_plan_id == event.workout_plan_id,
                db.func.date(WorkoutSession.completed_at) == db.func.date(event.start_datetime)
            ).first()

            if not existing_session and event.workout_plan_id:
                # Créer une session rétroactive
                duration = 60  # Par défaut
                if event.end_datetime and event.start_datetime:
                    delta = event.end_datetime - event.start_datetime
                    duration = int(delta.total_seconds() / 60)

                workout_session = WorkoutSession(
                    id=str(uuid.uuid4()),
                    user_id=current_user.id,
                    workout_plan_id=event.workout_plan_id,
                    started_at=event.start_datetime,
                    completed_at=event.start_datetime + timedelta(minutes=duration),
                    duration_minutes=duration,
                    is_completed=True,
                    total_sets=0,
                    total_reps=0,
                    total_weight=0.0
                )
                db.session.add(workout_session)
                synced_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'{synced_count} événements synchronisés avec succès!',
            'synced_count': synced_count
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur lors de la synchronisation: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500