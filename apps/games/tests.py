from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class GuestPlayTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_guest_can_create_game_without_auth(self):
        r = self.client.post(
            "/api/games/",
            {"is_ai": True, "ai_difficulty": "easy"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("id", r.data)
        self.assertIsNone(r.data.get("player_one"))
        self.assertTrue(r.data["board_state"])

    def test_guest_cannot_access_history(self):
        r = self.client.get("/api/games/history/")
        self.assertEqual(r.status_code, 401)
