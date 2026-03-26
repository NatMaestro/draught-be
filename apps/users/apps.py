import logging
import os
import sys

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Users"

    def ready(self) -> None:
        """Log once when the default DB connection succeeds (skip tests + runserver parent)."""
        if "test" in sys.argv:
            return
        # Dev autoreloader: parent has no RUN_MAIN; child has RUN_MAIN=true — avoid double log.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        from django.conf import settings
        from django.db import connection

        connection.ensure_connection()
        if not settings.DEBUG:
            # Avoid leaking host/database identifiers in production logs.
            logger.info("Default database connection ready.")
            return

        cfg = connection.settings_dict
        host = cfg.get("HOST") or "default"
        port = cfg.get("PORT") or "5432"
        name = cfg.get("NAME") or ""
        logger.debug(
            "PostgreSQL connection established — %s:%s/%s",
            host,
            port,
            name,
        )
