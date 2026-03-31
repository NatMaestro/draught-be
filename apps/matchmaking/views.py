"""
Matchmaking API: join and cancel queues.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.games.services import create_game
from .services import (
    add_to_queue,
    get_and_clear_match_ready,
    get_pending_match,
    is_matchmaking_redis_available,
    notify_match_ready,
    remove_from_queue,
)
from .serializers import JoinQueueSerializer


class JoinMatchmakingView(APIView):
    """POST /api/matchmaking/join - add to queue, create game if matched."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = JoinQueueSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ranked = ser.validated_data.get("ranked", False)
        user = request.user
        if not is_matchmaking_redis_available():
            return Response(
                {
                    "detail": (
                        "Matchmaking needs Redis. Start it (e.g. "
                        "`docker run -d -p 6379:6379 redis` on Windows/Mac) "
                        "and set REDIS_URL in draught-be/.env (default "
                        "redis://127.0.0.1:6379/0)."
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        user_rating = getattr(request.user, "rating", None)
        rating_val = (
            int(user_rating)
            if user_rating is not None and ranked
            else None
        )
        tc = ser.validated_data.get("time_control_sec", 600)
        uc = ser.validated_data.get("use_clock", True)
        is_match = bool(ser.validated_data.get("is_match"))
        match_target_wins = int(ser.validated_data.get("match_target_wins", 5))
        paired = add_to_queue(
            user.id,
            ranked,
            rating=rating_val,
            time_control_sec=tc,
            use_clock=uc,
            is_match=is_match,
            match_target_wins=match_target_wins,
        )
        if paired:
            match = get_pending_match(user.id)
            if match:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                p1 = User.objects.get(id=match["player1"])
                p2 = User.objects.get(id=match["player2"])
                is_mm = bool(match.get("is_match"))
                game = create_game(
                    player_one=p1,
                    player_two=p2,
                    is_ranked=bool(match["ranked"]),
                    time_control_sec=match.get("time_control_sec", 600),
                    use_clock=match.get("use_clock", True),
                    is_match=is_mm,
                    match_target_wins=int(match.get("match_target_wins", 5)),
                )
                gid = str(game.id)
                notify_match_ready(gid, p1.id, p2.id)
                return Response(
                    {"status": "matched", "game_id": gid},
                    status=status.HTTP_201_CREATED,
                )
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class MatchReadyView(APIView):
    """GET /api/matchmaking/ready/ — poll for game_id after POST join returned queued."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        gid = get_and_clear_match_ready(request.user.id)
        if gid:
            return Response({"status": "matched", "game_id": gid})
        return Response({"status": "waiting"})


class CancelMatchmakingView(APIView):
    """POST /api/matchmaking/cancel - leave queue."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = JoinQueueSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ranked = ser.validated_data.get("ranked", False)
        removed = remove_from_queue(request.user.id, ranked)
        return Response({"removed": removed})
