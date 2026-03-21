from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(username="test", email="test@example.com", password="pass123")
        self.assertEqual(user.rating, 1000)
        self.assertEqual(user.games_played, 0)
        self.assertEqual(user.games_won, 0)
