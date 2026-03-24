import os
import sys

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Users"

    def ready(self) -> None:
        """Log once when the default DB connection succeeds (skip tests + runserver parent)."""
        if "test" in sys.argv:
            return
        # Dev autoreloader: parent has no RUN_MAIN; child has RUN_MAIN=true — avoid double print.
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return

        from django.db import connection

        connection.ensure_connection()
        cfg = connection.settings_dict
        host = cfg.get("HOST") or "default"
        port = cfg.get("PORT") or "5432"
        name = cfg.get("NAME") or ""
        print(
            f"[Draught] PostgreSQL connection established - {host}:{port}/{name}",
            flush=True,
        )
