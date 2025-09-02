from flask import Blueprint
import logging 

logger = logging.getLogger(__name__)
logger.debug("Initialiseren van calendar blueprint")
bp = Blueprint('calendar', __name__)
from . import routes