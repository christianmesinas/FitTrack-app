from flask import Blueprint

# Create the admin blueprint here
admin = Blueprint('admin', __name__, url_prefix='/admin')

# Import routes after creating the blueprint
from app.admin import routes