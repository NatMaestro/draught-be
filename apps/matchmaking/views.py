"""
Matchmaking API: join and cancel queues.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from apps.games.services import create_game
from .services import add_to_queue, remove_from_queue, get_pending_match
from .serializers import JoinQueueSerializer


class JoinMatchmakingView(APIView):
    """POST /api/matchmaking/join - add to queue, create game if matched."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = JoinQueueSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ranked = ser.validated_data.get("ranked", False)
        user = request.user
        paired = add_to_queue(user.id, ranked)
        if paired:
            match = get_pending_match(user.id)
            if match:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                p1 = User.objects.get(id=match["player1"])
                p2 = User.objects.get(id=match["player2"])
                game = create_game(player_one=p1, player_two=p2, is_ranked=match["ranked"])
                return Response(
                    {"status": "matched", "game_id": str(game.id)},
                    status=status.HTTP_201_CREATED,
                )
        return Response({"status": "queued"}, status=status.HTTP_202_ACCEPTED)


class CancelMatchmakingView(APIView):
    """POST /api/matchmaking/cancel - leave queue."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = JoinQueueSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        ranked = ser.validated_data.get("ranked", False)
        removed = remove_from_queue(request.user.id, ranked)
        return Response({"removed": removed})
