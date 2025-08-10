import os
import sys
import datetime
from django.apps import AppConfig
from django.conf import settings
import threading
import logging

logger = logging.getLogger(__name__)

class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.sales'

    backup_started = False  # Class variable to prevent duplicate thread launches

    def ready(self):
        from . import signals
        logger.info("Sales signals registered ✅")

        # Skip backup initialization in these cases
        if self._should_skip_backup_initialization():
            return

        # Only proceed if all backup conditions are met
        if self._should_start_backup():
            from .backup import BackupManager
            threading.Thread(
                target=BackupManager().run_backup_loop, 
                daemon=True,
                name="MonthlyBackup"
            ).start()
            SalesConfig.backup_started = True
            logger.info("🔁 Monthly Backup Thread Started")
        else:
            logger.info("⏩ Skipping backup initialization (conditions not met)")

    def _should_skip_backup_initialization(self):
        """Check if we should skip backup initialization entirely"""
        # Skip if backup system is disabled
        if not getattr(settings, 'ENABLE_BACKUP_SYSTEM', False):
            return True
            
        # Skip during test/migration/shell commands
        if any(cmd in sys.argv for cmd in ['test', 'testserver', 'migrate', 'makemigrations', 'shell', 'shell_plus']):
            return True
            
        # Skip if backup already started
        if SalesConfig.backup_started:
            return True
            
        return False

    def _should_start_backup(self):
        """Check all conditions for starting backup"""
        return (
            self._is_running_server() and
            self._is_first_day_of_month() and
            self._is_main_process()
        )

    def _is_first_day_of_month(self):
        """Check if today is the first day of the month"""
        return datetime.date.today().day == 1

    def _is_main_process(self):
        """Check if this is the main process (not reloader)"""
        # For runserver
        if 'runserver' in sys.argv:
            return os.environ.get("RUN_MAIN") == "true"
        # For other commands (like when packaged as executable)
        return True

    def _is_running_server(self):
        """Check if we're running the server (not other management commands)"""
        return 'runserver' in sys.argv