from datetime import datetime, timezone
from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.calendar import bp
from app.models import CalendarEvent, WorkoutPlan
from dateutil import parser


@bp.route('/agenda')
@login_required
def agenda():
    """Page principale du calendrier"""
    # Récupère les workout plans de l'utilisateur pour le formulaire
    workout_plans = WorkoutPlan.query.filter_by(
        user_id=current_user.id,
        is_archived=False
    ).all()

    return render_template('calendar/agenda.html',
                           title='Mon Agenda',
                           workout_plans=workout_plans)


@bp.route('/api/events')
@login_required
def get_events():
    """API pour récupérer les événements du calendrier"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    query = CalendarEvent.query.filter_by(user_id=current_user.id)

    # Filtre par date si fourni
    if start_date:
        try:
            start_dt = parser.parse(start_date)
            query = query.filter(CalendarEvent.end_datetime >= start_dt)
        except:
            pass

    if end_date:
        try:
            end_dt = parser.parse(end_date)
            query = query.filter(CalendarEvent.start_datetime <= end_dt)
        except:
            pass

    events = query.all()

    # Convertit en format FullCalendar
    calendar_events = []
    for event in events:
        calendar_events.append({
            'id': event.id,
            'title': event.title,
            'start': event.start_datetime.isoformat(),
            'end': event.end_datetime.isoformat(),
            'backgroundColor': event.color,
            'borderColor': event.color,
            'textColor': '#ffffff',
            'extendedProps': {
                'description': event.description,
                'event_type': event.event_type,
                'status': event.status,
                'workout_plan_id': event.workout_plan_id,
                'workout_plan_name': event.workout_plan.name if event.workout_plan else None
            }
        })

    return jsonify(calendar_events)


@bp.route('/api/events', methods=['POST'])
@login_required
def create_event():
    """API pour créer un nouvel événement"""
    try:
        data = request.get_json()

        # Parse des dates
        start_datetime = parser.parse(data['start'])
        end_datetime = parser.parse(data['end'])

        # Création de l'événement
        event = CalendarEvent(
            user_id=current_user.id,
            title=data['title'],
            description=data.get('description', ''),
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            event_type=data.get('event_type', 'workout'),
            color=data.get('color', '#FF6B35'),
            workout_plan_id=data.get('workout_plan_id') if data.get('workout_plan_id') else None
        )

        db.session.add(event)
        db.session.commit()

        return jsonify({
            'success': True,
            'id': event.id,
            'message': 'Événement créé avec succès!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la création: {str(e)}'
        }), 400


@bp.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    """API pour modifier un événement existant"""
    try:
        event = CalendarEvent.query.filter_by(
            id=event_id,
            user_id=current_user.id
        ).first_or_404()

        data = request.get_json()

        # Mise à jour des champs
        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            event.description = data['description']
        if 'start' in data:
            event.start_datetime = parser.parse(data['start'])
        if 'end' in data:
            event.end_datetime = parser.parse(data['end'])
        if 'event_type' in data:
            event.event_type = data['event_type']
        if 'color' in data:
            event.color = data['color']
        if 'workout_plan_id' in data:
            event.workout_plan_id = data['workout_plan_id'] if data['workout_plan_id'] else None
        if 'status' in data:
            event.status = data['status']

        event.updated_at = datetime.now(timezone.utc)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Événement modifié avec succès!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la modification: {str(e)}'
        }), 400


@bp.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    """API pour supprimer un événement"""
    try:
        event = CalendarEvent.query.filter_by(
            id=event_id,
            user_id=current_user.id
        ).first_or_404()

        db.session.delete(event)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Événement supprimé avec succès!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la suppression: {str(e)}'
        }), 400


@bp.route('/api/events/<int:event_id>/complete', methods=['POST'])
@login_required
def complete_event(event_id):
    """API pour marquer un événement comme terminé"""
    try:
        event = CalendarEvent.query.filter_by(
            id=event_id,
            user_id=current_user.id
        ).first_or_404()

        event.status = 'completed'
        event.updated_at = datetime.now(timezone.utc)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Événement marqué comme terminé!'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 400