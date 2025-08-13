from flask import Blueprint
import logging

logger = logging.getLogger(__name__)
logger.debug("Initialiseren van api blueprint")
bp = Blueprint('api', __name__)
from . import routes