import logging
from app import create_app

# Configureer logging
logger = logging.getLogger(__name__)

application = create_app()
logger.debug("create_app() uitgevoerd, app gemaakt")

if __name__ == '__main__':
    application.run(host='0.0.0.0', port=8080, debug=True)