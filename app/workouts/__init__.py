from flask import Blueprint
import logging

logger = logging.getLogger(__name__)
logger.debug("Initialiseren van workouts blueprint")
bp = Blueprint('workouts', __name__)
from . import routes