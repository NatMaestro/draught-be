from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.games.serializers import PlayerPublicSerializer

from .models import User
from .serializers import UserProfileSerializer


def _competition_rank(base_qs, rating: int) -> int:
    """SQL RANK-style: ties share rank; next rank skips (e.g. 1,1,3)."""
    return 1 + base_qs.filter(rating__gt=rating).count()


class UserSearchView(APIView):
    """GET /api/users/search/?q=ab — usernames containing `q` (min 2 chars)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response([])
        users = (
            User.objects.filter(username__icontains=q)
            .exclude(id=request.user.id)
            .order_by("username")[:20]
        )
        return Response(PlayerPublicSerializer(users, many=True).data)


class LeaderboardView(APIView):
    """
    GET /api/users/leaderboard/
    Global rating leaderboard (competition ranking: same rating → same rank).

    Query: limit (default 50, max 100), offset (default 0), min_games (default 1).
    Public; when authenticated, `you` is the current user's row if they qualify.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = int(request.query_params.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0
        try:
            min_games = int(request.query_params.get("min_games", 1))
        except (TypeError, ValueError):
            min_games = 1

        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        min_games = max(0, min_games)

        base = User.objects.filter(is_active=True, games_played__gte=min_games)
        ordered = base.order_by("-rating", "username")
        total = ordered.count()
        page = list(ordered[offset : offset + limit])

        ratings_on_page = {row.rating for row in page}
        rank_cache = {r: _competition_rank(base, r) for r in ratings_on_page}

        results = [
            {
                "rank": rank_cache[row.rating],
                "id": row.id,
                "username": row.username,
                "rating": row.rating,
                "games_played": row.games_played,
                "games_won": row.games_won,
            }
            for row in page
        ]

        you = None
        if request.user.is_authenticated:
            # Fresh row from DB (not stale middleware user) so rank matches other players.
            try:
                u = User.objects.get(pk=request.user.pk)
            except User.DoesNotExist:
                u = None
            if u is not None and u.is_active and u.games_played >= min_games:
                you = {
                    "rank": _competition_rank(base, u.rating),
                    "id": u.id,
                    "username": u.username,
                    "rating": u.rating,
                    "games_played": u.games_played,
                    "games_won": u.games_won,
                }

        return Response(
            {
                "count": total,
                "results": results,
                "you": you,
            }
        )


class ProfileView(generics.RetrieveAPIView):
    """GET /api/users/profile - current user profile."""

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
