"""
WebSocket consumer: join, moves (via services.apply_move), AI, resign, chat.
"""

import json
import uuid
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from apps.ai.services import get_ai_move

from .permissions import is_guest_game
from .clock_utils import clock_payload, freeze_clock_on_game_over
from .services import resolve_clock_timeout_if_needed
from .ws_payload import build_game_state_message


def _can_user_access_game_ws(user, game) -> bool:
    """Mirror REST can_access_game without Request (WS scope user)."""
    if game.player_one_id is None:
        return True
    if not user or not user.is_authenticated:
        return False
    return user.id in (game.player_one_id, game.player_two_id)


def _resolve_player_num(user, game) -> tuple[int | None, str | None]:
    """
    Same rules as MoveView: guest games use current_turn; else seat from user.
    Returns (player_num, error_message).
    """
    if is_guest_game(game):
        return game.current_turn, None
    if not user or not user.is_authenticated:
        return None, "Authentication required"
    if game.player_one_id == user.id:
        return 1, None
    if game.player_two_id == user.id:
        return 2, None
    return None, "Not a player in this game"


class GameConsumer(AsyncWebsocketConsumer):
    """Handle WebSocket for game room."""

    async def connect(self):
        game_id = self.scope["url_route"]["kwargs"].get("game_id")
        if not game_id:
            await self.close()
            return
        try:
            self.game_id = uuid.UUID(str(game_id))
        except (ValueError, TypeError):
            await self.close()
            return
        self.room_name = f"game_{self.game_id}"
        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_name"):
            await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Invalid JSON"}),
            )
            return
        msg_type = data.get("type")
        if msg_type == "join_game":
            await self.handle_join(data)
        elif msg_type == "make_move":
            await self.handle_move(data)
        elif msg_type == "resign":
            await self.handle_resign(data)
        elif msg_type == "chat":
            await self.handle_chat(data)
        elif msg_type == "chat_typing":
            await self.handle_chat_typing(data)
        else:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Unknown message type"}),
            )

    async def handle_join(self, data):
        game = await self.get_game_orm()
        if not game:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Game not found"}),
            )
            return
        user = self.scope.get("user")
        if not await database_sync_to_async(_can_user_access_game_ws)(user, game):
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Access denied"}),
            )
            return
        await database_sync_to_async(resolve_clock_timeout_if_needed)(game)
        game = await self.get_game_orm()
        if not game:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Game not found"}),
            )
            return
        payload = await database_sync_to_async(build_game_state_message)(game)
        payload["chat"] = await self.get_recent_chat_messages()
        await self.send(text_data=json.dumps(payload, default=str))

    async def handle_move(self, data):
        fr = (data.get("from_row"), data.get("from_col"))
        to = (data.get("to_row"), data.get("to_col"))
        if None in fr or None in to:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "from/to required"}),
            )
            return
        user = self.scope.get("user")
        result = await self.apply_human_move(user, fr, to)
        if result.get("error"):
            await self.send(
                text_data=json.dumps({"type": "error", "detail": result["error"]}),
            )
            return
        if not result.get("ok"):
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Invalid move"}),
            )
            return

        await self.broadcast_move_update(result["payload"])

        if result.get("needs_ai"):
            ai_result = await self.apply_ai_move_if_needed()
            if ai_result and ai_result.get("payload"):
                await self.broadcast_move_update(ai_result["payload"])

    async def broadcast_move_update(self, payload: dict[str, Any]):
        await self.channel_layer.group_send(
            self.room_name,
            {"type": "broadcast", "message": payload},
        )

    async def handle_resign(self, data):
        user = self.scope.get("user")
        res = await self.resign_game_sync(user)
        if res.get("error"):
            await self.send(
                text_data=json.dumps({"type": "error", "detail": res["error"]}),
            )
            return
        await self.channel_layer.group_send(
            self.room_name,
            {
                "type": "broadcast",
                "message": {
                    "type": "game_over",
                    "reason": "resign",
                    "winner": res.get("winner"),
                    "winner_id": res.get("winner_id"),
                    "status": "finished",
                },
            },
        )

    async def handle_chat(self, data):
        body = (data.get("text") or "").strip()
        if not body:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Empty message"}),
            )
            return
        sender_label = (data.get("sender") or "Guest")[:64]
        user = self.scope.get("user")
        game = await self.get_game_orm()
        if not game:
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Game not found"}),
            )
            return
        if not await database_sync_to_async(_can_user_access_game_ws)(user, game):
            await self.send(
                text_data=json.dumps({"type": "error", "detail": "Access denied"}),
            )
            return
        msg = await self.save_chat_and_format(user, sender_label, body)
        await self.channel_layer.group_send(
            self.room_name,
            {"type": "broadcast", "message": msg},
        )

    async def handle_chat_typing(self, data):
        """Ephemeral typing indicator — not persisted."""
        user = self.scope.get("user")
        game = await self.get_game_orm()
        if not game:
            return
        if not await database_sync_to_async(_can_user_access_game_ws)(user, game):
            return
        sender_label = (data.get("sender") or "Guest")[:64]
        active = bool(data.get("active"))
        display = self._resolve_chat_display_name(user, sender_label)
        await self.channel_layer.group_send(
            self.room_name,
            {
                "type": "broadcast",
                "message": {
                    "type": "chat_typing",
                    "sender": display,
                    "active": active,
                },
            },
        )

    async def broadcast(self, event):
        await self.send(text_data=json.dumps(event["message"], default=str))

    @database_sync_to_async
    def get_game_orm(self):
        from .models import Game

        return Game.objects.filter(id=self.game_id).first()

    @database_sync_to_async
    def apply_human_move(self, user, fr, to):
        from django.db import transaction
        from .models import Game
        from .services import apply_move as apply_move_service

        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            if not _can_user_access_game_ws(user, game):
                return {"ok": False, "error": "Access denied"}
            player_num, err = _resolve_player_num(user, game)
            if err:
                return {"ok": False, "error": err}
            ok, new_board, captured, winner, captured_values = apply_move_service(
                game, player_num, fr, to
            )
            game.refresh_from_db()
            if not ok:
                if winner is not None:
                    payload = self._move_payload(
                        game, new_board, captured, winner, captured_values
                    )
                    return {"ok": True, "payload": payload, "needs_ai": False}
                return {"ok": False}
            payload = self._move_payload(game, new_board, captured, winner, captured_values)
            needs_ai = bool(
                game.is_ai_game
                and not winner
                and game.status == Game.Status.ACTIVE
                and game.current_turn == 2,
            )
            return {"ok": True, "payload": payload, "needs_ai": needs_ai}

    @database_sync_to_async
    def apply_ai_move_if_needed(self):
        from django.db import transaction
        from .models import Game
        from .services import apply_move as apply_move_service

        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=self.game_id)
            if (
                not game.is_ai_game
                or game.status != Game.Status.ACTIVE
                or game.current_turn != 2
            ):
                return None
            move = get_ai_move(game.board_state, 2, game.ai_difficulty or "medium")
            if not move:
                return None
            fr, to, _cap = move
            ok, new_board, captured, winner, captured_values = apply_move_service(
                game, 2, fr, to
            )
            game.refresh_from_db()
            if not ok:
                return None
            payload = self._move_payload(game, new_board, captured, winner, captured_values)
            return {"payload": payload}

    def _move_payload(self, game, new_board, captured, winner, captured_piece_values):
        from .models import Game

        board_out = new_board if new_board is not None else game.board_state
        end_reason = None
        if new_board is None and winner is not None and game.status == Game.Status.FINISHED:
            end_reason = "timeout"
        msg = {
            "type": "move_update",
            "board": board_out,
            "current_turn": game.current_turn,
            "winner": winner,
            "status": game.status,
            "captured": [{"row": r, "col": c} for (r, c) in captured],
            "captured_piece_values": captured_piece_values,
            "move_count": game.moves.count(),
            **clock_payload(game),
        }
        if end_reason:
            msg["end_reason"] = end_reason
        return msg

    @database_sync_to_async
    def resign_game_sync(self, user):
        from apps.ratings.services import update_ratings
        from .models import Game

        game = Game.objects.filter(id=self.game_id).first()
        if not game:
            return {"error": "Game not found"}
        if not _can_user_access_game_ws(user, game):
            return {"error": "Access denied"}
        if game.status != Game.Status.ACTIVE:
            return {"error": "Game not active"}
        game.status = Game.Status.FINISHED
        game.finished_at = timezone.now()
        freeze_clock_on_game_over(game)
        winner_id = None
        winner_player: int | None = None
        if is_guest_game(game):
            # Current player resigns; opponent wins (P1's turn → P2 wins).
            winner_player = 2 if game.current_turn == 1 else 1
        elif user and user.is_authenticated:
            game.winner = (
                game.player_two if user.id == game.player_one_id else game.player_one
            )
            winner_id = str(game.winner_id) if game.winner_id else None
            winner_player = 2 if user.id == game.player_one_id else 1
            if game.is_ranked and game.winner:
                update_ratings(game)
        game.save()
        return {"winner_id": winner_id, "winner": winner_player}

    def _resolve_chat_display_name(self, user, sender_label: str) -> str:
        """Match chat_message sender labels (authenticated username vs guest name)."""
        if user and user.is_authenticated:
            return (user.get_username() or str(user.id))[:64]
        return (sender_label or "Guest")[:64]

    @database_sync_to_async
    def save_chat_and_format(self, user, sender_label: str, body: str):
        from .models import GameChatMessage

        display = self._resolve_chat_display_name(user, sender_label)
        u = None
        if user and user.is_authenticated:
            u = user
        msg = GameChatMessage.objects.create(
            game_id=self.game_id,
            user=u,
            guest_name="" if u else sender_label[:64],
            body=body[:500],
        )
        return {
            "type": "chat_message",
            "id": str(msg.id),
            "sender": display,
            "text": msg.body,
            "created_at": msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def get_recent_chat_messages(self, limit: int = 50):
        from .models import GameChatMessage

        qs = (
            GameChatMessage.objects.filter(game_id=self.game_id)
            .order_by("-created_at")[:limit]
        )
        rows = list(qs)
        rows.reverse()
        out = []
        for m in rows:
            display = m.user.get_username() if m.user_id else (m.guest_name or "Guest")
            out.append(
                {
                    "id": str(m.id),
                    "sender": display,
                    "text": m.body,
                    "created_at": m.created_at.isoformat(),
                },
            )
        return out
