from flask import Blueprint
import logging

logger = logging.getLogger(__name__)
logger.debug("Initialiseren van sessions blueprint")
bp = Blueprint('sessions', __name__)
from . import routes