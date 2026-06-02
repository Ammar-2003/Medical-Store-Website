from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.sales'

    def ready(self):
        from . import signals
        logger.info("Sales signals registered ✅")