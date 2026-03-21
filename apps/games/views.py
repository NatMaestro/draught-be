"""
Games API: create, retrieve, resign, history, legal moves.
Guests can create and play games (vs AI or local); history, matchmaking, profile require auth.
"""

from datetime import datetime
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import NotFound, PermissionDenied
from django.db.models import Q

from .models import Game, Move
from .serializers import GameSerializer, GameListSerializer, MoveSerializer
from apps.ai.services import get_ai_move

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .services import create_game, apply_move, get_moves_for_piece, undo_last_move
from .ws_payload import build_game_state_message
from .permissions import can_access_game, is_guest_game
from apps.ratings.services import update_ratings


class GameDetailView(generics.RetrieveAPIView):
    """GET /api/games/<id>/ - game state. Allowed for guest games or own games."""

    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [AllowAny]
    lookup_field = "id"
    lookup_url_kwarg = "id"

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if not can_access_game(request, instance):
            raise PermissionDenied("You do not have access to this game.")
        return super().retrieve(request, *args, **kwargs)


class GameCreateView(APIView):
    """POST /api/games/ - create game. Guests can play as guest (vs AI or local); no auth required."""

    permission_classes = [AllowAny]

    def post(self, request):
        is_ai = request.data.get("is_ai", False)
        ai_difficulty = request.data.get("ai_difficulty", "medium")
        is_ranked = request.data.get("is_ranked", False)
        is_local_2p = bool(request.data.get("is_local_2p", False))
        user = request.user if request.user.is_authenticated else None
        if user is None:
            # Guest: only vs AI or local 2P; no ranked
            is_ranked = False
        game = create_game(
            player_one=user,
            player_two=None,
            is_ranked=is_ranked and not is_ai,
            is_ai=is_ai,
            ai_difficulty=ai_difficulty if is_ai else "",
            is_local_2p=is_local_2p,
        )
        return Response(GameSerializer(game).data, status=status.HTTP_201_CREATED)


class MoveView(APIView):
    """POST /api/games/<id>/move/ - make move. Allowed for guest games or own games."""

    permission_classes = [AllowAny]

    def post(self, request, id):
        game = Game.objects.filter(id=id).first()
        if not game:
            raise NotFound("Game not found")
        if not can_access_game(request, game):
            raise PermissionDenied("You do not have access to this game.")
        from_pos = (request.data.get("from_row"), request.data.get("from_col"))
        to_pos = (request.data.get("to_row"), request.data.get("to_col"))
        if None in from_pos or None in to_pos:
            return Response({"detail": "from_row, from_col, to_row, to_col required"}, status=400)
        if is_guest_game(game):
            player_num = game.current_turn
        else:
            player_num = 1 if request.user == game.player_one else 2
        ok, new_board, captured, winner = apply_move(game, player_num, from_pos, to_pos)
        if not ok:
            return Response({"detail": "Invalid move"}, status=400)
        return Response({
            "board": new_board,
            "current_turn": game.current_turn,
            "winner": winner,
            "status": game.status,
            "captured": [{"row": r, "col": c} for (r, c) in captured],
        })


class LegalMovesView(APIView):
    """GET /api/games/<id>/legal-moves/?row=&col= - legal moves for piece. Allowed for guest games or own games."""

    permission_classes = [AllowAny]

    def get(self, request, id):
        game = Game.objects.filter(id=id).first()
        if not game:
            raise NotFound("Game not found")
        if not can_access_game(request, game):
            raise PermissionDenied("You do not have access to this game.")
        row = request.query_params.get("row")
        col = request.query_params.get("col")
        if row is None or col is None:
            return Response({"detail": "row and col required"}, status=400)
        try:
            row, col = int(row), int(col)
        except (TypeError, ValueError):
            return Response({"detail": "row and col must be integers"}, status=400)
        moves = get_moves_for_piece(game, row, col)
        return Response({"moves": moves})


class AiMoveView(APIView):
    """
    POST /api/games/<id>/ai-move/ — apply AI move when is_ai_game and current_turn is 2.
    Used by web clients that use REST instead of WebSockets (REST /move/ does not trigger AI).
    """

    permission_classes = [AllowAny]

    def post(self, request, id):
        game = Game.objects.filter(id=id).first()
        if not game:
            raise NotFound("Game not found")
        if not can_access_game(request, game):
            raise PermissionDenied("You do not have access to this game.")
        if not game.is_ai_game:
            return Response({"detail": "Not an AI game"}, status=status.HTTP_400_BAD_REQUEST)
        if game.status != Game.Status.ACTIVE:
            return Response({"detail": "Game not active"}, status=status.HTTP_400_BAD_REQUEST)
        if game.current_turn != 2:
            return Response({"detail": "Not AI's turn"}, status=status.HTTP_400_BAD_REQUEST)
        move = get_ai_move(game.board_state, 2, game.ai_difficulty or "medium")
        if not move:
            return Response({"detail": "No moves"}, status=status.HTTP_400_BAD_REQUEST)
        fr, to, _cap = move
        ok, new_board, captured, winner = apply_move(game, 2, fr, to)
        if not ok:
            return Response({"detail": "Invalid AI move"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(
            {
                "board": new_board,
                "current_turn": game.current_turn,
                "winner": winner,
                "status": game.status,
                "captured": [{"row": r, "col": c} for (r, c) in captured],
            }
        )


def _broadcast_game_state_ws(game):
    """Notify WebSocket room so the other client sees undo (same as join payload)."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    msg = build_game_state_message(game)
    async_to_sync(channel_layer.group_send)(
        f"game_{game.id}",
        {"type": "broadcast", "message": msg},
    )


class UndoView(APIView):
    """POST /api/games/<id>/undo/ — take back last move (AI / local guest games only)."""

    permission_classes = [AllowAny]

    def post(self, request, id):
        game = Game.objects.filter(id=id).first()
        if not game:
            raise NotFound("Game not found")
        if not can_access_game(request, game):
            raise PermissionDenied("You do not have access to this game.")
        ok, err, payload = undo_last_move(game)
        if not ok:
            return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)
        game.refresh_from_db()
        _broadcast_game_state_ws(game)
        return Response(payload)


class ResignView(APIView):
    """POST /api/games/<id>/resign/ - resign game. Allowed for guest games or own games."""

    permission_classes = [AllowAny]

    def post(self, request, id):
        game = Game.objects.filter(id=id).first()
        if not game:
            raise NotFound("Game not found")
        if not can_access_game(request, game):
            raise PermissionDenied("You do not have access to this game.")
        if game.status != Game.Status.ACTIVE:
            return Response({"detail": "Game not active"}, status=400)
        game.status = Game.Status.FINISHED
        game.finished_at = timezone.now()
        if not is_guest_game(game):
            game.winner = game.player_two if request.user == game.player_one else game.player_one
            if game.is_ranked and game.winner:
                update_ratings(game)
        game.save()
        winner_id = game.winner_id if game.winner_id else None
        return Response({"status": "resigned", "winner": winner_id})


class GameHistoryView(generics.ListAPIView):
    """GET /api/games/history/ - user's game history. Requires sign-in."""

    serializer_class = GameListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Game.objects.filter(
            Q(player_one=self.request.user) | Q(player_two=self.request.user),
            status=Game.Status.FINISHED,
        ).order_by("-finished_at")[:50]
