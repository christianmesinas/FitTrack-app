from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime, timedelta, timezone
from . import bp
from app import db
from app.models import CalendarEvent, WorkoutPlan, WorkoutSession
import logging

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
    """Marquer un événement comme complété"""
    try:
        event = CalendarEvent.query.filter_by(
            id=event_id,
            user_id=current_user.id
        ).first_or_404()

        event.status = 'completed'
        event.color = '#4CAF50'  # Vert pour complété

        db.session.commit()

        # Si c'est lié à un workout, proposer de démarrer la session
        if event.workout_plan_id:
            return jsonify({
                'success': True,
                'message': 'Événement marqué comme complété!',
                'workout_plan_id': event.workout_plan_id,
                'redirect_to_workout': True
            })

        return jsonify({
            'success': True,
            'message': 'Événement marqué comme complété!'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erreur: {str(e)}")
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