from flask import jsonify
from flask_login import login_required, current_user

from . import bp
from ..models import WeightLog
from ..profile.routes import generate_weight_chart_data


@bp.route('/weight_chart', methods=['GET'])
@login_required
def api_weight_chart():
    """API endpoint voor het ophalen van gewichtsgrafiek als json"""
    try:
        weights = WeightLog.query.filter_by(user_id=current_user.id) \
            .order_by(WeightLog.logged_at).all()

        if not weights or len(weights) < 2:
            return jsonify({
                'error': 'Insufficient data',
                'message': 'Je hebt minimaal 2 gewichtsmetingen nodig voor een grafiek'
            }), 400

        chart_data = generate_weight_chart_data(weights, current_user)

        if chart_data:
            return jsonify({
                'success': True,
                'data': chart_data
            })
        else:
            return jsonify({
                'error': 'Error generating chart',
                'message': 'Er is een fout opgetreden bij het genereren van de grafiek'
            }), 500

    except Exception as e:
        print(f"Error in weight_chart: {e}")  # Voor debugging
        return jsonify({
            'error': 'Server error',
            'message': str(e)
        }), 500