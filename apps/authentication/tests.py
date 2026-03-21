from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


class AuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register(self):
        r = self.client.post(
            "/api/auth/register/",
            {"username": "test", "email": "test@example.com", "password": "pass1234", "password_confirm": "pass1234"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("username", r.data)
        self.assertEqual(r.data["username"], "test")
