"""WebSocket `game_state` payload — shared with HTTP undo broadcast."""

from apps.board_engine.engine import get_game_status

from .models import Game


def build_game_state_message(game: Game) -> dict:
    """Matches GameConsumer.build_game_state_dict (+ type field for clients)."""
    winner_num = None
    if game.status == Game.Status.FINISHED:
        if game.winner_id:
            if game.player_one_id and game.winner_id == game.player_one_id:
                winner_num = 1
            elif game.player_two_id and game.winner_id == game.player_two_id:
                winner_num = 2
        if winner_num is None:
            winner_num = get_game_status(game.board_state, 1)

    return {
        "type": "game_state",
        "board": game.board_state,
        "current_turn": game.current_turn,
        "status": game.status,
        "winner": winner_num,
        "is_ai_game": game.is_ai_game,
        "ai_difficulty": game.ai_difficulty or "medium",
    }
