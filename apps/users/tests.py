from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class UserModelTests(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(username="test", email="test@example.com", password="pass123")
        self.assertEqual(user.rating, 1000)
        self.assertEqual(user.games_played, 0)
        self.assertEqual(user.games_won, 0)


class LeaderboardViewTests(TestCase):
    """
    Leaderboard uses competition ("standard competition ranking"): rank =
    1 + count of players with strictly higher rating — ties share rank, next
    rank skips (e.g. 1, 1, 3). Implemented in Python (not DB window Rank()),
    which matches SQL RANK() on PostgreSQL but avoids SQLite row-number quirks.
    """

    def setUp(self):
        self.client = APIClient()

    def test_leaderboard_ties_share_rank_and_skips_after_gap(self):
        a = User.objects.create_user(username="a", email="a@x.com", password="p", rating=1200, games_played=1)
        b = User.objects.create_user(username="b", email="b@x.com", password="p", rating=1200, games_played=1)
        c = User.objects.create_user(username="c", email="c@x.com", password="p", rating=1100, games_played=1)
        res = self.client.get("/api/users/leaderboard/", {"limit": 10, "offset": 0})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["count"], 3)
        r = data["results"]
        self.assertEqual(len(r), 3)
        self.assertEqual(r[0]["rank"], 1)
        self.assertEqual(r[1]["rank"], 1)
        self.assertEqual(r[2]["rank"], 3)
        self.assertEqual(r[0]["rating"], 1200)
        self.assertEqual(r[0]["username"], "a")
        self.assertEqual(r[1]["username"], "b")

    def test_min_games_excludes_low_activity(self):
        User.objects.create_user(username="low", email="l@x.com", password="p", rating=2000, games_played=0)
        User.objects.create_user(username="ok", email="o@x.com", password="p", rating=1000, games_played=1)
        res = self.client.get("/api/users/leaderboard/", {"min_games": "1"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["count"], 1)
        self.assertEqual(res.json()["results"][0]["username"], "ok")

    def test_you_when_authenticated(self):
        me = User.objects.create_user(
            username="me", email="m@x.com", password="secret123", rating=900, games_played=1
        )
        User.objects.create_user(username="top", email="t@x.com", password="p", rating=1500, games_played=1)
        self.client.force_authenticate(user=me)
        res = self.client.get("/api/users/leaderboard/")
        self.assertEqual(res.status_code, 200)
        you = res.json()["you"]
        self.assertIsNotNone(you)
        self.assertEqual(you["username"], "me")
        self.assertEqual(you["rank"], 2)
