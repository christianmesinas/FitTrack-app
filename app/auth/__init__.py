from flask import Blueprint
import logging

logger = logging.getLogger(__name__)
logger.debug("Initialiseren van auth blueprint")
bp = Blueprint('auth', __name__)
from . import routes