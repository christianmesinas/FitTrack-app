# app/admin/routes.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from datetime import datetime, timedelta
import json




# Create admin blueprint



# Mock data for development
def get_mock_user():
    """Return mock trainer data"""
    return {
        'id': 1,
        'name': 'John Doe',
        'email': 'john.doe@fitpro.nl',
        'role': 'Personal Trainer',
        'avatar': None
    }


def get_mock_clients():
    """Return mock clients data"""
    return [
        {
            'id': 1,
            'name': 'Emma de Vries',
            'email': 'emma.devries@email.com',
            'status': 'active',
            'program': 'Afvallen',
            'progress': 75,
            'last_activity': '2 uur geleden',
            'next_session': 'Morgen 10:00'
        },
        {
            'id': 2,
            'name': 'Jan Jansen',
            'email': 'j.jansen@email.com',
            'status': 'active',
            'program': 'Spieropbouw',
            'progress': 60,
            'last_activity': '1 dag geleden',
            'next_session': 'Vandaag 14:00'
        },
        {
            'id': 3,
            'name': 'Lisa Bakker',
            'email': 'lisa.b@email.com',
            'status': 'inactive',
            'program': 'Conditie',
            'progress': 30,
            'last_activity': '1 week geleden',
            'next_session': None
        },
        {
            'id': 4,
            'name': 'Mark Peters',
            'email': 'm.peters@email.com',
            'status': 'pending',
            'program': 'Krachttraining',
            'progress': 0,
            'last_activity': 'Nieuw',
            'next_session': 'Dinsdag 09:00'
        },
        {
            'id': 5,
            'name': 'Sophie van den Berg',
            'email': 'sophie.vdb@email.com',
            'status': 'active',
            'program': 'Yoga & Flexibiliteit',
            'progress': 90,
            'last_activity': 'Vandaag',
            'next_session': 'Woensdag 18:00'
        }
    ]


def get_mock_workouts():
    """Return mock workouts data"""
    return [
        {
            'id': 1,
            'title': 'Full Body Strength',
            'category': 'Krachttraining',
            'description': 'Complete full body workout gericht op kracht en spieropbouw.',
            'duration': 45,
            'calories': 350,
            'exercises': 8,
            'level': 'Beginner',
            'location': 'Gym'
        },
        {
            'id': 2,
            'title': 'HIIT Cardio Blast',
            'category': 'HIIT',
            'description': 'Intensieve interval training voor maximale vetverbranding.',
            'duration': 30,
            'calories': 450,
            'exercises': 6,
            'level': 'Gevorderd',
            'location': 'Thuis'
        },
        {
            'id': 3,
            'title': 'Morning Yoga Flow',
            'category': 'Yoga',
            'description': 'Rustige yoga flow om de dag mee te beginnen.',
            'duration': 20,
            'calories': 100,
            'exercises': 12,
            'level': 'Beginner',
            'location': 'Thuis'
        },
        {
            'id': 4,
            'title': 'Upper Body Power',
            'category': 'Upper Body',
            'description': 'Focus op bovenlichaam ontwikkeling.',
            'duration': 50,
            'calories': 300,
            'exercises': 10,
            'level': 'Intermediate',
            'location': 'Gym'
        }
    ]


def get_mock_videos():
    """Return mock videos data"""
    return [
        {
            'id': 1,
            'title': 'Full Body HIIT Workout - 30 Minuten Vetverbranding',
            'duration': '12:45',
            'views': 1200,
            'likes': 245,
            'status': 'live',
            'uploaded': '2 dagen geleden',
            'category': 'HIIT'
        },
        {
            'id': 2,
            'title': 'Morning Yoga Flow voor Beginners',
            'duration': '8:30',
            'views': 856,
            'likes': 189,
            'status': 'live',
            'uploaded': '1 week geleden',
            'category': 'Yoga'
        },
        {
            'id': 3,
            'title': 'Krachttraining Upper Body - Complete Workout',
            'duration': '45:00',
            'views': 0,
            'likes': 0,
            'status': 'processing',
            'uploaded': 'Vandaag',
            'category': 'Krachttraining'
        },
        {
            'id': 4,
            'title': 'Abs & Core Workout - 20 Minuten Buikspieren',
            'duration': '20:15',
            'views': 0,
            'likes': 0,
            'status': 'draft',
            'uploaded': '3 dagen geleden',
            'category': 'Core'
        }
    ]


def get_mock_stats():
    """Return mock statistics data"""
    return {
        'total_clients': 24,
        'active_clients': 18,
        'new_this_week': 3,
        'retention_rate': 87,
        'total_workouts': 156,
        'calories_burned': 45280,
        'weight_loss_total': -38.5,
        'attendance_rate': 92,
        'monthly_workouts': [32, 38, 42, 44],
        'weekly_labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4']
    }


# ADMIN ROUTES

@admin.route('/')
@admin.route('/dashboard')
def dashboard():
    """Admin dashboard homepage"""
    context = {
        'current_user': get_mock_user(),
        'client_count': 24,
        'recent_activities': [
            {
                'type': 'new_client',
                'description': 'Nieuwe klant toegevoegd: Emma de Vries',
                'time': '2 uur geleden',
                'icon': 'user-plus',
                'color': 'primary'
            },
            {
                'type': 'workout_completed',
                'description': 'Jan Jansen heeft workout voltooid',
                'time': '3 uur geleden',
                'icon': 'check-circle',
                'color': 'success'
            },
            {
                'type': 'video_uploaded',
                'description': 'Nieuwe video geüpload: "Full Body HIIT"',
                'time': '5 uur geleden',
                'icon': 'video',
                'color': 'warning'
            }
        ],
        'upcoming_sessions': [
            {'time': '09:00', 'client': 'Sophie van den Berg', 'type': 'Personal Training'},
            {'time': '10:30', 'client': 'Tom Hendriks', 'type': 'Krachttraining'},
            {'time': '14:00', 'client': 'Groepsles', 'type': 'HIIT Training (8 personen)'},
            {'time': '16:00', 'client': 'Anna de Jong', 'type': 'Voedingsconsult'}
        ]
    }
    return render_template('admin_dashboard.html', **context)


@admin.route('/profile', methods=['GET', 'POST'])
def profile():
    """Trainer profile management"""
    if request.method == 'POST':
        # Handle profile update
        flash('Profiel succesvol bijgewerkt!', 'success')
        return redirect(url_for('admin.profile'))

    context = {
        'current_user': get_mock_user(),
        'specializations': ['Krachttraining', 'Cardio', 'HIIT', 'Voedingsadvies'],
        'certifications': [
            {'name': 'NASM Certified Personal Trainer', 'date': 'Maart 2019'},
            {'name': 'Voedingscoach Diploma', 'date': 'Juni 2020'}
        ]
    }
    return render_template('admin_profile.html', **context)


@admin.route('/workouts')
def workouts():
    """Workout management page"""
    context = {
        'current_user': get_mock_user(),
        'workouts': get_mock_workouts()
    }
    return render_template('admin_workouts.html', **context)


@admin.route('/workouts/add', methods=['GET', 'POST'])
def add_workout():
    """Add new workout"""
    if request.method == 'POST':
        # Handle workout creation
        flash('Workout succesvol toegevoegd!', 'success')
        return redirect(url_for('admin.workouts'))

    return render_template('admin_workouts.html', current_user=get_mock_user())


@admin.route('/workouts/<int:workout_id>/edit', methods=['GET', 'POST'])
def edit_workout(workout_id):
    """Edit existing workout"""
    if request.method == 'POST':
        # Handle workout update
        flash('Workout succesvol bijgewerkt!', 'success')
        return redirect(url_for('admin.workouts'))

    # Get workout by ID (mock)
    workout = next((w for w in get_mock_workouts() if w['id'] == workout_id), None)
    if not workout:
        flash('Workout niet gevonden.', 'danger')
        return redirect(url_for('admin.workouts'))

    return render_template('admin_workouts.html', workout=workout, current_user=get_mock_user())


@admin.route('/workouts/<int:workout_id>/delete', methods=['POST'])
def delete_workout(workout_id):
    """Delete workout"""
    # Handle workout deletion
    flash('Workout succesvol verwijderd!', 'success')
    return redirect(url_for('admin.workouts'))


@admin.route('/workout-videos')
def workout_videos():
    """Video gallery management"""
    context = {
        'current_user': get_mock_user(),
        'videos': get_mock_videos()
    }
    return render_template('admin_workout_videos.html', **context)


@admin.route('/videos/upload', methods=['POST'])
def upload_video():
    """Handle video upload"""
    # Handle file upload
    flash('Video succesvol geüpload!', 'success')
    return jsonify({'success': True, 'message': 'Video uploaded successfully'})


@admin.route('/clients')
def clients():
    """Client management page"""
    context = {
        'current_user': get_mock_user(),
        'clients': get_mock_clients(),
        'total_clients': 24,
        'active_clients': 18,
        'new_this_week': 3,
        'retention_rate': 87
    }
    return render_template('admin_clients.html', **context)


@admin.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    """Add new client - multi-step form"""
    if request.method == 'POST':
        # Handle client creation
        flash('Nieuwe klant succesvol toegevoegd!', 'success')
        return redirect(url_for('admin.clients'))

    context = {
        'current_user': get_mock_user(),
        'client_id': None  # For new client
    }
    return render_template('admin_add_client.html', **context)


@admin.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
def edit_client(client_id):
    """Edit existing client"""
    if request.method == 'POST':
        # Handle client update
        flash('Klant gegevens succesvol bijgewerkt!', 'success')
        return redirect(url_for('admin.clients'))

    # Get client by ID (mock)
    client = next((c for c in get_mock_clients() if c['id'] == client_id), None)
    if not client:
        flash('Klant niet gevonden.', 'danger')
        return redirect(url_for('admin.clients'))

    context = {
        'current_user': get_mock_user(),
        'client_id': client_id,
        'client': client
    }
    return render_template('admin_add_client.html', **context)


@admin.route('/clients/<int:client_id>/delete', methods=['POST'])
def delete_client(client_id):
    """Delete client"""
    # Handle client deletion
    flash('Klant succesvol verwijderd!', 'warning')
    return redirect(url_for('admin.clients'))


@admin.route('/clients/<int:client_id>/details')
def client_details(client_id):
    """Get client details (AJAX)"""
    client = next((c for c in get_mock_clients() if c['id'] == client_id), None)
    if not client:
        return jsonify({'error': 'Client not found'}), 404

    # Add additional client details
    client_data = {
        **client,
        'height': 168,
        'weight': 72,
        'goal': 'Afvallen (10 kg)',
        'start_date': '1 september 2024',
        'subscription': 'Premium (3x per week)',
        'medical_notes': 'Knieblessure (rechts)',
        'workouts_completed': 45,
        'weight_lost': -8.5,
        'attendance': 95
    }

    return jsonify(client_data)


@admin.route('/client-stats')
def client_stats():
    """Client statistics and analytics"""
    context = {
        'current_user': get_mock_user(),
        'stats': get_mock_stats(),
        'top_performers': [
            {'rank': 1, 'name': 'Emma de Vries', 'workouts': 28, 'initials': 'EV'},
            {'rank': 2, 'name': 'Jan Jansen', 'workouts': 25, 'initials': 'JJ'},
            {'rank': 3, 'name': 'Sophie van den Berg', 'workouts': 24, 'initials': 'SB'},
            {'rank': 4, 'name': 'Tom Hendriks', 'workouts': 22, 'initials': 'TH'},
            {'rank': 5, 'name': 'Lisa Bakker', 'workouts': 20, 'initials': 'LB'}
        ],
        'client_progress': get_mock_clients()
    }
    return render_template('admin_client_stats.html', **context)


@admin.route('/nutrition-plans')
def nutrition_plans():
    """Nutrition plans management"""
    context = {
        'current_user': get_mock_user(),
        'clients': get_mock_clients(),
        'active_plans': 18,
        'total_meals': 245,
        'avg_calories': 2150,
        'macro_split': '40/30/30',
        'selected_client': {
            'name': 'Emma de Vries',
            'goal': 'Afvallen',
            'daily_calories': 1850,
            'meal_plan': {
                'monday': [
                    {
                        'time': '07:30',
                        'type': 'Ontbijt',
                        'name': 'Havermout met Bessen en Noten',
                        'ingredients': '50g havermout, 200ml amandelmelk, 100g blauwe bessen, 15g amandelen, 1 tl honing',
                        'calories': 385,
                        'protein': 12,
                        'carbs': 58,
                        'fat': 11
                    },
                    {
                        'time': '10:00',
                        'type': 'Snack',
                        'name': 'Griekse Yoghurt met Appel',
                        'ingredients': '150g Griekse yoghurt 0%, 1 middelgrote appel, kaneel',
                        'calories': 180,
                        'protein': 15,
                        'carbs': 28,
                        'fat': 0.5
                    },
                    {
                        'time': '13:00',
                        'type': 'Lunch',
                        'name': 'Quinoa Salade met Gegrilde Kip',
                        'ingredients': '150g kipfilet, 80g quinoa, gemengde groenten, 1 el olijfolie',
                        'calories': 520,
                        'protein': 38,
                        'carbs': 45,
                        'fat': 18
                    },
                    {
                        'time': '16:00',
                        'type': 'Snack',
                        'name': 'Proteïne Shake',
                        'ingredients': '30g whey proteïne, 1 banaan, 200ml water',
                        'calories': 215,
                        'protein': 25,
                        'carbs': 27,
                        'fat': 1
                    },
                    {
                        'time': '19:00',
                        'type': 'Diner',
                        'name': 'Zalm met Zoete Aardappel',
                        'ingredients': '150g zalm, 200g zoete aardappel, 150g broccoli',
                        'calories': 550,
                        'protein': 35,
                        'carbs': 48,
                        'fat': 20
                    }
                ]
            }
        }
    }
    return render_template('admin_nutrition_plans.html', **context)


@admin.route('/nutrition-plans/<int:client_id>')
def client_nutrition_plan(client_id):
    """Get specific client nutrition plan (AJAX)"""
    # Mock nutrition plan for client
    plan = {
        'client_id': client_id,
        'daily_calories': 2000,
        'meals': []  # Would contain meal data
    }
    return jsonify(plan)


@admin.route('/meal-library')
def meal_library():
    """Meal database/library"""
    # This would show a library of meals that can be added to nutrition plans
    return render_template('admin_nutrition_plans.html', current_user=get_mock_user())


@admin.route('/library')
def library():
    """Workout library (internal database)"""
    # This would show pre-made workouts that trainers can use
    context = {
        'current_user': get_mock_user(),
        'library_workouts': get_mock_workouts()
    }
    return render_template('admin_workouts.html', **context)


@admin.route('/settings')
def settings():
    """General settings page"""
    context = {
        'current_user': get_mock_user(),
        'settings': {
            'company_name': 'FitPro Training',
            'timezone': 'Europe/Amsterdam',
            'language': 'Nederlands',
            'currency': 'EUR',
            'week_starts': 'Monday',
            'session_duration': 60,
            'buffer_time': 15,
            'cancellation_policy': 24
        }
    }
    return render_template('admin_settings.html', **context)


@admin.route('/settings/save', methods=['POST'])
def save_settings():
    """Save settings"""
    # Handle settings save
    flash('Instellingen succesvol opgeslagen!', 'success')
    return redirect(url_for('admin.settings'))


@admin.route('/appearance')
def appearance():
    """Appearance and theme customization"""
    context = {
        'current_user': get_mock_user(),
        'themes': ['Professional Blue', 'Dark Mode', 'Nature Green', 'Royal Purple'],
        'current_theme': 'Professional Blue',
        'colors': {
            'primary': '#6366f1',
            'secondary': '#22d3ee',
            'accent': '#f59e0b',
            'success': '#10b981',
            'warning': '#f59e0b',
            'danger': '#ef4444'
        }
    }
    return render_template('admin_appearance.html', **context)


@admin.route('/appearance/save', methods=['POST'])
def save_appearance():
    """Save appearance settings"""
    # Handle appearance settings save
    data = request.get_json()
    # Save theme, colors, logo, etc.
    return jsonify({'success': True, 'message': 'Appearance settings saved'})


@admin.route('/export/<export_type>')
def export_data(export_type):
    """Export data (clients, workouts, stats)"""
    # Handle different export types: csv, excel, pdf
    if export_type == 'clients':
        # Export clients data
        flash('Klanten data geëxporteerd!', 'success')
    elif export_type == 'workouts':
        # Export workouts data
        flash('Workouts geëxporteerd!', 'success')
    elif export_type == 'stats':
        # Export statistics
        flash('Statistieken geëxporteerd!', 'success')

    return redirect(request.referrer or url_for('admin.dashboard'))


@admin.route('/notifications')
def notifications():
    """Get notifications (AJAX)"""
    notifications = [
        {
            'id': 1,
            'type': 'info',
            'message': 'Nieuwe klant aanmelding',
            'time': '5 minuten geleden',
            'read': False
        },
        {
            'id': 2,
            'type': 'success',
            'message': 'Workout voltooid door Emma',
            'time': '1 uur geleden',
            'read': False
        }
    ]
    return jsonify(notifications)


@admin.route('/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """Mark notification as read"""
    return jsonify({'success': True})


@admin.route('/search')
def search():
    """Global search functionality"""
    query = request.args.get('q', '')
    # Perform search across clients, workouts, videos
    results = {
        'clients': [],
        'workouts': [],
        'videos': []
    }
    return jsonify(results)


@admin.route('/calendar')
def calendar():
    """Calendar view for sessions"""
    # This could be an additional calendar view for managing sessions
    events = [
        {
            'title': 'PT Sessie - Emma',
            'start': '2024-11-20T10:00:00',
            'end': '2024-11-20T11:00:00'
        },
        {
            'title': 'Groepsles HIIT',
            'start': '2024-11-20T14:00:00',
            'end': '2024-11-20T15:00:00'
        }
    ]
    return jsonify(events)


@admin.route('/messages')
def messages():
    """Message center (if implementing chat)"""
    # This could be a messaging system between trainer and clients
    return render_template('admin_dashboard.html', current_user=get_mock_user())


# API Routes for AJAX calls

@admin.route('/api/stats/weekly')
def api_weekly_stats():
    """Get weekly statistics for charts"""
    data = {
        'labels': ['Ma', 'Di', 'Wo', 'Do', 'Vr', 'Za', 'Zo'],
        'workouts': [12, 19, 15, 25, 22, 30, 28],
        'clients': [8, 12, 10, 15, 14, 18, 16]
    }
    return jsonify(data)


@admin.route('/api/stats/monthly')
def api_monthly_stats():
    """Get monthly statistics"""
    data = {
        'total_workouts': 156,
        'total_clients': 24,
        'revenue': 5600,
        'growth': 15
    }
    return jsonify(data)


@admin.route('/api/clients/<int:client_id>/progress')
def api_client_progress(client_id):
    """Get client progress data"""
    progress = {
        'weight': [75, 74.5, 74, 73.2, 72.8, 72],
        'dates': ['Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6'],
        'measurements': {
            'chest': [95, 94, 93],
            'waist': [82, 80, 78],
            'hips': [98, 97, 96]
        }
    }
    return jsonify(progress)


@admin.route('/api/workouts/<int:workout_id>/assign', methods=['POST'])
def api_assign_workout(workout_id):
    """Assign workout to clients"""
    client_ids = request.json.get('client_ids', [])
    # Assign workout to selected clients
    return jsonify({'success': True, 'assigned_to': len(client_ids)})


# Error handlers for admin section

@admin.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors in admin section"""
    flash('Pagina niet gevonden.', 'warning')
    return redirect(url_for('admin.dashboard'))


@admin.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors in admin section"""
    flash('Je hebt geen toegang tot deze pagina.', 'danger')
    return redirect(url_for('admin.dashboard'))


@admin.errorhandler(500)
def internal_error(error):
    """Handle 500 errors in admin section"""
    flash('Er is een fout opgetreden. Probeer het later opnieuw.', 'danger')
    return redirect(url_for('admin.dashboard'))


# Utility functions

def get_client_count():
    """Get total client count for sidebar badge"""
    return len(get_mock_clients())


def get_unread_notifications():
    """Get unread notification count"""
    return 3  # Mock value


# Context processor to inject common variables
@admin.context_processor
def inject_common_variables():
    """Inject common variables into all admin templates"""
    return {
        'client_count': get_client_count(),
        'unread_notifications': get_unread_notifications(),
        'current_year': datetime.now().year
    }

# Register blueprint in your main app file:
# app.register_blueprint(admin)