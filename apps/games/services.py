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

from .clock_utils import (
    active_player_remaining_seconds,
    apply_clock_before_move,
    clock_payload,
    freeze_clock_on_game_over,
    init_clock_for_active_game,
    reset_per_turn_clock_for_player_to_move,
    stamp_turn_started_now,
)
from .models import Game, MatchSession, Move


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


def get_moves_payload_for_client(game: Game) -> list[dict]:
    """
    Ordered plies with `captured` squares each — for WebSocket/API clients and replay UI.
    """
    board = create_initial_board()
    turn = 1
    out: list[dict] = []
    for m in game.moves.order_by("created_at"):
        fr = (m.from_row, m.from_col)
        to = (m.to_row, m.to_col)
        result = validate_and_get_move(board, turn, fr, to)
        if result is None:
            break
        new_board, captured = result
        out.append(
            {
                "from_row": m.from_row,
                "from_col": m.from_col,
                "to_row": m.to_row,
                "to_col": m.to_col,
                "player": turn,
                "captured": [{"row": r, "col": c} for (r, c) in captured],
            }
        )
        board = new_board
        turn = 2 if turn == 1 else 1
    return out


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
            freeze_clock_on_game_over(game)
            if not game.is_ai_game and game.player_one and game.player_two:
                game.winner = game.player_one if winner == 1 else game.player_two
                if game.is_ranked and not game.match_session_id:
                    update_ratings(game)
        else:
            game.status = Game.Status.ACTIVE
            game.finished_at = None
            game.winner = None
            init_clock_for_active_game(game)
        game.save()

    payload = {
        "board": game.board_state,
        "current_turn": game.current_turn,
        "winner": winner,
        "status": game.status,
        "p1_captured_piece_values": p1_caps,
        "p2_captured_piece_values": p2_caps,
        "can_undo": can_undo_game(game),
        **clock_payload(game),
    }
    return True, None, payload


def winner_seat_from_finished_mini_game(game: Game) -> int | None:
    """Seat (1 or 2) that won the just-finished mini-game."""
    if game.status != Game.Status.FINISHED:
        return None
    if game.winner_id and game.player_one_id and game.winner_id == game.player_one_id:
        return 1
    if game.winner_id and game.player_two_id and game.winner_id == game.player_two_id:
        return 2
    w = get_game_status(game.board_state, game.current_turn)
    if w in (1, 2):
        return w
    return None


def match_state_public(game: Game) -> dict | None:
    """Stable match snapshot for REST / game_state (no duplicate of win flags)."""
    if not game.match_session_id:
        return None
    ms = game.match_session
    return {
        "p1_wins": ms.p1_wins,
        "p2_wins": ms.p2_wins,
        "target_wins": ms.target_wins,
        "status": ms.status,
        "is_raw": ms.is_raw,
        "winner_id": ms.match_winner_id,
    }


def match_ws_extras_for_session(
    game: Game,
    ms: MatchSession,
    *,
    match_finished: bool,
    mini_game_ended: bool,
) -> dict:
    out = {
        "match_mode": True,
        "match_p1_wins": ms.p1_wins,
        "match_p2_wins": ms.p2_wins,
        "match_target_wins": ms.target_wins,
        "match_status": ms.status,
        "match_finished": match_finished,
        "match_is_raw": bool(match_finished and ms.is_raw),
        "mini_game_ended": bool(mini_game_ended or match_finished),
    }
    if match_finished and ms.match_winner_id:
        if game.player_one_id and ms.match_winner_id == game.player_one_id:
            out["match_winner_seat"] = 1
        elif game.player_two_id and ms.match_winner_id == game.player_two_id:
            out["match_winner_seat"] = 2
    return out


def continue_match_after_mini_game_end(
    game: Game,
    *,
    winner_seat_override: int | None = None,
) -> dict | None:
    """
    After a mini-game ends (`game` is FINISHED with a decided winner). Updates match
    scores; either completes the match or resets `game` for the next mini-game.
    `winner_seat_override`: use for resign / guest when `game.winner` is unset.
    """
    if not game.match_session_id:
        return None
    ms = game.match_session
    if ms.status != MatchSession.Status.ACTIVE:
        return None
    ws = (
        winner_seat_override
        if winner_seat_override in (1, 2)
        else winner_seat_from_finished_mini_game(game)
    )
    if ws not in (1, 2):
        return None
    if ws == 1:
        ms.p1_wins += 1
    else:
        ms.p2_wins += 1
    target = int(ms.target_wins or 5)
    done = ms.p1_wins >= target or ms.p2_wins >= target
    if done:
        ms.status = MatchSession.Status.FINISHED
        ms.match_winner = game.winner
        if not ms.match_winner_id:
            if ws == 1 and game.player_one_id:
                ms.match_winner = game.player_one
            elif ws == 2 and game.player_two_id:
                ms.match_winner = game.player_two
        ms.is_raw = (
            min(ms.p1_wins, ms.p2_wins) == 0 and max(ms.p1_wins, ms.p2_wins) >= target
        )
        ms.save(
            update_fields=[
                "p1_wins",
                "p2_wins",
                "status",
                "match_winner_id",
                "is_raw",
            ],
        )
        # One Elo update for the full match (same K / games_played as one ranked game).
        if game.is_ranked and game.player_one and game.player_two:
            w = ms.match_winner or game.winner
            if w:
                game.winner = w
                update_ratings(game)
        return match_ws_extras_for_session(
            game,
            ms,
            match_finished=True,
            mini_game_ended=True,
        )
    ms.save(update_fields=["p1_wins", "p2_wins"])
    Move.objects.filter(game=game).delete()
    game.board_state = create_initial_board()
    game.current_turn = 1
    game.status = Game.Status.ACTIVE
    game.winner = None
    game.finished_at = None
    init_clock_for_active_game(game)
    game.save()
    return match_ws_extras_for_session(
        game,
        ms,
        match_finished=False,
        mini_game_ended=True,
    )


def resolve_clock_timeout_pair(game: Game) -> tuple[int | None, dict | None]:
    """
    If the active player's time has run out, end the mini-game and maybe advance the match.
    Returns (winner_seat, match_extra). winner_seat is set only if the board game is still
    FINISHED after handling (single-game or match just completed).
    """
    if game.status != Game.Status.ACTIVE:
        return None, None
    if not getattr(game, "use_clock", True):
        return None, None
    remaining = active_player_remaining_seconds(game)
    if remaining is None or remaining > 0:
        return None, None
    loser_seat = game.current_turn
    winner_seat = 2 if loser_seat == 1 else 1
    extras: dict | None = None
    with transaction.atomic():
        apply_clock_before_move(game, loser_seat)
        finish_game_on_timeout(game, loser_seat)
        if game.match_session_id:
            extras = continue_match_after_mini_game_end(game)
        game.refresh_from_db()
    return (winner_seat if game.status == Game.Status.FINISHED else None, extras)


def finish_game_on_timeout(game: Game, loser_seat: int) -> int:
    """
    Persist game over by flag: opponent of loser_seat wins.
    Returns winner seat (1 or 2). Caller must hold a transaction if needed.
    """
    winner_seat = 2 if loser_seat == 1 else 1
    game.status = Game.Status.FINISHED
    game.finished_at = datetime.utcnow()
    freeze_clock_on_game_over(game)
    if not game.is_ai_game and game.player_one and game.player_two:
        game.winner = game.player_one if winner_seat == 1 else game.player_two
        if game.is_ranked and not game.match_session_id:
            update_ratings(game)
    elif game.is_ai_game and game.player_one:
        if winner_seat == 1:
            game.winner = game.player_one
    game.save()
    return winner_seat


def resolve_clock_timeout_if_needed(game: Game) -> int | None:
    """
    If the active player's time has run out, end the mini-game (and maybe advance the match).
    Returns winner seat if the `Game` row is still finished afterward, else None.
    """
    ws, _ = resolve_clock_timeout_pair(game)
    game.refresh_from_db()
    if game.status == Game.Status.FINISHED:
        return ws
    return None


def create_game(
    player_one=None,
    player_two=None,
    is_ranked=False,
    is_ai=False,
    ai_difficulty="",
    is_local_2p=False,
    time_control_sec: int = 600,
    use_clock: bool = True,
    is_match: bool = False,
    match_target_wins: int = 5,
):
    """Create new game with initial board."""
    board = create_initial_board()
    # ACTIVE: has opponent, vs AI, or same-device hot-seat (no second account).
    is_playable = bool(player_two or is_ai or is_local_2p)
    if use_clock:
        tc = max(60, min(7200, int(time_control_sec or 600)))
    else:
        tc = 0
    ms = None
    if is_match:
        tw = max(1, min(9, int(match_target_wins or 5)))
        ms = MatchSession.objects.create(target_wins=tw)
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
        use_clock=use_clock,
        time_control_sec=tc,
        p1_time_remaining_sec=float(tc) if use_clock else 0.0,
        p2_time_remaining_sec=float(tc) if use_clock else 0.0,
        turn_started_at=None,
        match_session=ms,
    )
    if is_playable:
        init_clock_for_active_game(game)
        game.save(
            update_fields=[
                "p1_time_remaining_sec",
                "p2_time_remaining_sec",
                "turn_started_at",
            ],
        )
    return game


def apply_move(game: Game, player_num: int, from_pos: tuple[int, int], to_pos: tuple[int, int]):
    """
    Apply move if valid. Returns
    (success, new_board_state, captured_list, winner, captured_piece_values, match_extras).

    On loss by timeout, success is False; winner is the winning seat if the board game
    stays finished, else None when the match continues with a fresh mini-game.
    match_extras is a dict for WebSocket/API when match state changes, else None.
    """
    if game.status != Game.Status.ACTIVE:
        return (False, None, [], None, [], None)
    if game.current_turn != player_num:
        return (False, None, [], None, [], None)

    if getattr(game, "use_clock", True):
        wt, clk_extras = resolve_clock_timeout_pair(game)
        game.refresh_from_db()
        if wt is not None:
            return (False, game.board_state, [], wt, [], clk_extras)
        if clk_extras is not None:
            return (False, game.board_state, [], None, [], clk_extras)

    board = game.board_state
    result = validate_and_get_move(board, player_num, from_pos, to_pos)
    if result is None:
        return (False, None, [], None, [], None)
    new_board, captured = result
    # Cell values on the pre-move board (for client trophies without relying on snapshots).
    captured_piece_values = [board[r][c] for (r, c) in captured]
    winner = get_game_status(new_board, 2 if player_num == 1 else 1)
    with transaction.atomic():
        if getattr(game, "use_clock", True):
            apply_clock_before_move(game, player_num)
            remaining = (
                game.p1_time_remaining_sec if player_num == 1 else game.p2_time_remaining_sec
            )
            if remaining <= 0:
                finish_game_on_timeout(game, player_num)
                match_extras = None
                if game.match_session_id:
                    match_extras = continue_match_after_mini_game_end(game)
                game.refresh_from_db()
                ws = winner_seat_from_finished_mini_game(game) if (
                    game.status == Game.Status.FINISHED
                ) else None
                return (False, game.board_state, [], ws, [], match_extras)

        game.board_state = new_board
        game.current_turn = 2 if player_num == 1 else 1
        if winner:
            game.status = Game.Status.FINISHED
            game.finished_at = datetime.utcnow()
            freeze_clock_on_game_over(game)
            if not game.is_ai_game and game.player_one and game.player_two:
                game.winner = game.player_one if winner == 1 else game.player_two
                if game.is_ranked and not game.match_session_id:
                    update_ratings(game)
            elif game.is_ai_game and game.player_one:
                if winner == 1:
                    game.winner = game.player_one
        else:
            reset_per_turn_clock_for_player_to_move(game)
            stamp_turn_started_now(game)
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
        match_extras = None
        if winner and game.match_session_id:
            match_extras = continue_match_after_mini_game_end(game)
            game.refresh_from_db()
        out_winner = winner
        if (
            match_extras
            and match_extras.get("mini_game_ended")
            and not match_extras.get("match_finished")
        ):
            out_winner = None
        out_board = game.board_state if match_extras else new_board
        return (True, out_board, captured, out_winner, captured_piece_values, match_extras)


def get_moves_for_piece(game: Game, row: int, col: int) -> list[dict]:
    """Return legal moves for piece at (row, col) as list of {to_row, to_col, captured}."""
    board = game.board_state
    must_capture = any_captures_available(board, game.current_turn)
    moves = get_legal_moves(board, (row, col), must_capture=must_capture)
    return [
        {"to_row": dr, "to_col": dc, "captured": [{"row": r, "col": c} for (r, c) in cap]}
        for ((dr, dc), cap) in moves
    ]
