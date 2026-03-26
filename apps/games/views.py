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
from django.contrib.auth import get_user_model
from django.db.models import Count, Q

User = get_user_model()

from .models import Game, GameChallenge, Move
from .serializers import (
    GameChallengeCreateSerializer,
    GameChallengeSerializer,
    GameSerializer,
    GameListSerializer,
    MoveSerializer,
)
from apps.ai.services import get_ai_move
from apps.social.services import (
    notify_game_challenge_accepted,
    notify_game_challenge_created,
    notify_game_challenge_declined,
)

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .clock_utils import clock_payload, freeze_clock_on_game_over
from .services import create_game, apply_move, get_moves_for_piece, undo_last_move, resolve_clock_timeout_if_needed
from .ws_payload import build_game_state_message
from .permissions import can_access_game, is_guest_game
from apps.ratings.services import update_ratings


class GameDetailView(generics.RetrieveAPIView):
    """GET /api/games/<id>/ - game state. Allowed for guest games or own games."""

    queryset = Game.objects.prefetch_related("moves")
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
        raw_tc = request.data.get("time_control_sec")
        raw_min = request.data.get("minutes")
        raw_use_clock = request.data.get("use_clock", True)
        use_clock = True
        if isinstance(raw_use_clock, bool):
            use_clock = raw_use_clock
        elif isinstance(raw_use_clock, str):
            use_clock = raw_use_clock.strip().lower() not in ("0", "false", "no", "")
        time_control_sec = 600
        try:
            if raw_tc is not None:
                time_control_sec = int(raw_tc)
            elif raw_min is not None:
                time_control_sec = int(raw_min) * 60
        except (TypeError, ValueError):
            time_control_sec = 600
        game = create_game(
            player_one=user,
            player_two=None,
            is_ranked=is_ranked and not is_ai,
            is_ai=is_ai,
            ai_difficulty=ai_difficulty if is_ai else "",
            is_local_2p=is_local_2p,
            time_control_sec=time_control_sec,
            use_clock=use_clock,
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
        ok, new_board, captured, winner, captured_values = apply_move(
            game, player_num, from_pos, to_pos
        )
        if not ok:
            if winner is not None:
                game.refresh_from_db()
                return Response(
                    {
                        "detail": "timeout",
                        "end_reason": "timeout",
                        "board": game.board_state,
                        "current_turn": game.current_turn,
                        "winner": winner,
                        "status": game.status,
                        "captured": [],
                        "captured_piece_values": [],
                        "move_count": game.moves.count(),
                        **clock_payload(game),
                    },
                    status=status.HTTP_200_OK,
                )
            return Response({"detail": "Invalid move"}, status=400)
        game.refresh_from_db()
        return Response({
            "board": new_board,
            "current_turn": game.current_turn,
            "winner": winner,
            "status": game.status,
            "captured": [{"row": r, "col": c} for (r, c) in captured],
            "captured_piece_values": captured_values,
            "move_count": game.moves.count(),
            **clock_payload(game),
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
        resolve_clock_timeout_if_needed(game)
        game.refresh_from_db()
        if game.status != Game.Status.ACTIVE:
            return Response({"moves": []})
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
        ok, new_board, captured, winner, captured_values = apply_move(game, 2, fr, to)
        if not ok:
            if winner is not None:
                game.refresh_from_db()
                return Response(
                    {
                        "detail": "timeout",
                        "end_reason": "timeout",
                        "board": game.board_state,
                        "current_turn": game.current_turn,
                        "winner": winner,
                        "status": game.status,
                        "captured": [],
                        "captured_piece_values": [],
                        "move_count": game.moves.count(),
                        **clock_payload(game),
                    },
                    status=status.HTTP_200_OK,
                )
            return Response({"detail": "Invalid AI move"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        game.refresh_from_db()
        return Response(
            {
                "board": new_board,
                "current_turn": game.current_turn,
                "winner": winner,
                "status": game.status,
                "captured": [{"row": r, "col": c} for (r, c) in captured],
                "captured_piece_values": captured_values,
                "move_count": game.moves.count(),
                **clock_payload(game),
            }
        )


def _broadcast_game_state_ws(game):
    """Notify WebSocket room so the other client sees undo (same as join payload)."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    msg = build_game_state_message(game, undo_applied=True)
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
        freeze_clock_on_game_over(game)
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
        return (
            Game.objects.filter(
                Q(player_one=self.request.user) | Q(player_two=self.request.user),
                status=Game.Status.FINISHED,
            )
            .select_related("player_one", "player_two")
            .annotate(move_count=Count("moves"))
            .order_by("-finished_at")[:50]
        )


class ChallengeIncomingListView(generics.ListAPIView):
    """GET /api/games/challenges/incoming/ — pending invites for the current user."""

    serializer_class = GameChallengeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            GameChallenge.objects.filter(
                to_user=self.request.user,
                status=GameChallenge.Status.PENDING,
            )
            .select_related("from_user", "to_user")
        )


class ChallengeOutgoingListView(generics.ListAPIView):
    """GET /api/games/challenges/outgoing/ — pending invites plus accepted games still active."""

    serializer_class = GameChallengeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            GameChallenge.objects.filter(from_user=user)
            .filter(
                Q(status=GameChallenge.Status.PENDING)
                | Q(
                    status=GameChallenge.Status.ACCEPTED,
                    result_game__status=Game.Status.ACTIVE,
                )
            )
            .select_related("from_user", "to_user", "result_game")
            .order_by("-created_at")[:50]
        )


class ChallengeCreateView(APIView):
    """POST /api/games/challenges/ — send a game request to another user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = GameChallengeCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        to_id = ser.validated_data["to_user_id"]
        rematch_gid = ser.validated_data.get("rematch_game_id")
        if to_id == request.user.id:
            return Response({"detail": "Cannot challenge yourself"}, status=400)
        try:
            to_user = User.objects.get(pk=to_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)
        if GameChallenge.objects.filter(
            from_user=request.user,
            to_user=to_user,
            status=GameChallenge.Status.PENDING,
        ).exists():
            return Response({"detail": "Challenge already pending"}, status=400)
        rematch = None
        if rematch_gid:
            rematch = Game.objects.filter(id=rematch_gid).first()
        ch = GameChallenge.objects.create(
            from_user=request.user,
            to_user=to_user,
            rematch_game=rematch,
        )
        notify_game_challenge_created(ch)
        return Response(GameChallengeSerializer(ch).data, status=status.HTTP_201_CREATED)


class ChallengeAcceptView(APIView):
    """POST /api/games/challenges/<uuid>/accept/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, challenge_id):
        ch = (
            GameChallenge.objects.filter(
                id=challenge_id,
                to_user=request.user,
                status=GameChallenge.Status.PENDING,
            )
            .select_related("from_user", "to_user", "rematch_game")
            .first()
        )
        if not ch:
            return Response({"detail": "Not found"}, status=404)
        tc = 600
        use_clock = True
        if ch.rematch_game_id:
            g = ch.rematch_game
            tc = int(getattr(g, "time_control_sec", 600) or 600)
            use_clock = bool(getattr(g, "use_clock", True))
        game = create_game(
            player_one=ch.from_user,
            player_two=ch.to_user,
            is_ranked=False,
            time_control_sec=tc,
            use_clock=use_clock,
        )
        ch.status = GameChallenge.Status.ACCEPTED
        ch.result_game = game
        ch.save(update_fields=["status", "result_game"])
        notify_game_challenge_accepted(ch, game)
        return Response(
            {"game_id": str(game.id), "game": GameSerializer(game).data},
            status=status.HTTP_200_OK,
        )


class ChallengeDeclineView(APIView):
    """POST /api/games/challenges/<uuid>/decline/"""

    permission_classes = [IsAuthenticated]

    def post(self, request, challenge_id):
        ch = GameChallenge.objects.filter(
            id=challenge_id,
            to_user=request.user,
            status=GameChallenge.Status.PENDING,
        ).first()
        if not ch:
            return Response({"detail": "Not found"}, status=404)
        ch.status = GameChallenge.Status.DECLINED
        ch.save(update_fields=["status"])
        notify_game_challenge_declined(ch)
        return Response({"ok": True})


class ChallengeCancelView(APIView):
    """POST /api/games/challenges/<uuid>/cancel/ — withdraw a pending invite you sent."""

    permission_classes = [IsAuthenticated]

    def post(self, request, challenge_id):
        ch = GameChallenge.objects.filter(
            id=challenge_id,
            from_user=request.user,
            status=GameChallenge.Status.PENDING,
        ).first()
        if not ch:
            return Response({"detail": "Not found"}, status=404)
        ch.status = GameChallenge.Status.CANCELLED
        ch.save(update_fields=["status"])
        return Response({"ok": True})
