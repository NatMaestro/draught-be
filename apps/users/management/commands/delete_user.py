"""
Delete a user by username. Use if you have a stale test user and want to re-register.

  python manage.py delete_user testuser
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = "Delete a user by username (e.g. to re-register with a new password)."

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username to delete")

    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User '{username}' does not exist."))
            return
        user.delete()
        self.stdout.write(self.style.SUCCESS(f"User '{username}' deleted. You can now register again."))
