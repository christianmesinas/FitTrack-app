from flask import Blueprint
import logging

logger = logging.getLogger(__name__)
logger.debug("Initialiseren van profile blueprint")
bp = Blueprint('profile', __name__)
from . import routes