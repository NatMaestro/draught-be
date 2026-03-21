"""
Create a superuser if none exists. Use this if you can't see anything in admin
(e.g. you created a superuser before switching to custom User or a different database).

  python manage.py ensure_admin

Prompts for username/password, or set env vars: DJANGO_SUPERUSER_USERNAME,
DJANGO_SUPERUSER_PASSWORD, DJANGO_SUPERUSER_EMAIL (optional).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Create a superuser if none exists (for admin access)."

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.SUCCESS("A superuser already exists. You can log in at /admin/"))
            return
        self.stdout.write("No superuser found. Creating one now (required for admin).")
        from django.core.management import call_command
        call_command("createsuperuser", interactive=True)
