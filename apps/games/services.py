"""
Game services: create game, apply move, update ratings.
"""

from datetime import datetime

from django.db import transaction

from apps.board_engine.engine import (
    create_initial_board,
    validate_and_get_move,
    get_game_status,
    any_captures_available,
    get_legal_moves,
)
from apps.ratings.services import update_ratings

from .models import Game, Move


def can_undo_game(game: Game) -> bool:
    """Undo only for vs AI or same-device local 2P — not online PvP or ranked."""
    if game.is_ranked or game.status != Game.Status.ACTIVE:
        return False
    if not (game.is_ai_game or game.is_local_2p):
        return False
    return game.moves.exists()


def replay_game_state_from_moves(moves):
    """
    Rebuild board and capture tallies from an ordered iterable of Move rows.
    Returns (board, next_turn, winner_or_none, p1_captured_values, p2_captured_values).
    """
    board = create_initial_board()
    turn = 1
    p1_caps: list[int] = []
    p2_caps: list[int] = []
    for m in moves:
        fr = (m.from_row, m.from_col)
        to = (m.to_row, m.to_col)
        result = validate_and_get_move(board, turn, fr, to)
        if result is None:
            raise ValueError("Stored moves do not form a valid game")
        new_board, captured = result
        for (r, c) in captured:
            val = board[r][c]
            if turn == 1:
                p1_caps.append(val)
            else:
                p2_caps.append(val)
        board = new_board
        turn = 2 if turn == 1 else 1
    winner = get_game_status(board, turn)
    return board, turn, winner, p1_caps, p2_caps


def replay_game_state(game: Game):
    """Rebuild from all moves on the game (ordered)."""
    return replay_game_state_from_moves(game.moves.order_by("created_at"))


def undo_last_move(game: Game):
    """
    Delete the last move row and rebuild game.board_state from remaining moves.
    Returns (ok, error_message_or_none, payload_or_none).
    payload keys: board, current_turn, winner, status, p1_captured_piece_values, p2_captured_piece_values
    """
    if game.status != Game.Status.ACTIVE:
        return False, "Game is not active", None
    if not can_undo_game(game):
        return False, "Undo is not available for this game", None

    ordered = list(game.moves.order_by("created_at"))
    if not ordered:
        return False, "No moves to undo", None

    remaining = ordered[:-1]
    try:
        board, turn, winner, p1_caps, p2_caps = replay_game_state_from_moves(remaining)
    except ValueError as e:
        return False, str(e), None

    with transaction.atomic():
        ordered[-1].delete()
        game.board_state = board
        game.current_turn = turn
        if winner:
            game.status = Game.Status.FINISHED
            game.finished_at = datetime.utcnow()
            if not game.is_ai_game and game.player_one and game.player_two:
                game.winner = game.player_one if winner == 1 else game.player_two
                if game.is_ranked:
                    update_ratings(game)
        else:
            game.status = Game.Status.ACTIVE
            game.finished_at = None
            game.winner = None
        game.save()

    payload = {
        "board": game.board_state,
        "current_turn": game.current_turn,
        "winner": winner,
        "status": game.status,
        "p1_captured_piece_values": p1_caps,
        "p2_captured_piece_values": p2_caps,
        "can_undo": can_undo_game(game),
    }
    return True, None, payload


def create_game(
    player_one=None,
    player_two=None,
    is_ranked=False,
    is_ai=False,
    ai_difficulty="",
    is_local_2p=False,
):
    """Create new game with initial board."""
    board = create_initial_board()
    # ACTIVE: has opponent, vs AI, or same-device hot-seat (no second account).
    is_playable = bool(player_two or is_ai or is_local_2p)
    game = Game.objects.create(
        player_one=player_one,
        player_two=player_two,
        board_state=board,
        current_turn=1,
        status=Game.Status.ACTIVE if is_playable else Game.Status.WAITING,
        is_ranked=is_ranked,
        is_ai_game=is_ai,
        is_local_2p=is_local_2p,
        ai_difficulty=ai_difficulty or "",
    )
    return game


def apply_move(game: Game, player_num: int, from_pos: tuple[int, int], to_pos: tuple[int, int]):
    """
    Apply move if valid. Returns
    (success, new_board_state, captured_list, winner, captured_piece_values).
    """
    if game.status != Game.Status.ACTIVE:
        return (False, None, [], None, [])
    if game.current_turn != player_num:
        return (False, None, [], None, [])
    board = game.board_state
    result = validate_and_get_move(board, player_num, from_pos, to_pos)
    if result is None:
        return (False, None, [], None, [])
    new_board, captured = result
    # Cell values on the pre-move board (for client trophies without relying on snapshots).
    captured_piece_values = [board[r][c] for (r, c) in captured]
    winner = get_game_status(new_board, 2 if player_num == 1 else 1)
    with transaction.atomic():
        game.board_state = new_board
        game.current_turn = 2 if player_num == 1 else 1
        if winner:
            game.status = Game.Status.FINISHED
            game.finished_at = datetime.utcnow()
            if not game.is_ai_game and game.player_one and game.player_two:
                game.winner = game.player_one if winner == 1 else game.player_two
                if game.is_ranked:
                    update_ratings(game)
        game.save()
        cr, cc = (captured[0] if captured else (None, None))
        Move.objects.create(
            game=game,
            player=game.player_one if player_num == 1 else game.player_two,
            from_row=from_pos[0],
            from_col=from_pos[1],
            to_row=to_pos[0],
            to_col=to_pos[1],
            captured_row=cr,
            captured_col=cc,
        )
    return (True, new_board, captured, winner, captured_piece_values)


def get_moves_for_piece(game: Game, row: int, col: int) -> list[dict]:
    """Return legal moves for piece at (row, col) as list of {to_row, to_col, captured}."""
    board = game.board_state
    must_capture = any_captures_available(board, game.current_turn)
    moves = get_legal_moves(board, (row, col), must_capture=must_capture)
    return [
        {"to_row": dr, "to_col": dc, "captured": [{"row": r, "col": c} for (r, c) in cap]}
        for ((dr, dc), cap) in moves
    ]
