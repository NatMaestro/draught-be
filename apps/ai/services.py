"""
AI opponent: Easy (random), Medium (prioritize captures), Hard (minimax).
"""

import random
from typing import Optional

from apps.board_engine.engine import (
    get_legal_moves,
    any_captures_available,
    apply_move,
    get_game_status,
    count_pieces,
    P1_PIECE,
    P2_PIECE,
    P1_KING,
    P2_KING,
    EMPTY,
    BOARD_SIZE,
)


def get_ai_move(board: list[list[int]], player: int, difficulty: str) -> Optional[tuple[tuple, tuple, list]]:
    """
    Return (from_pos, to_pos, captured) or None if no moves.
    """
    cells = {P1_PIECE, P1_KING} if player == 1 else {P2_PIECE, P2_KING}
    must_capture = any_captures_available(board, player)
    all_moves: list[tuple[tuple[int, int], tuple[int, int], list]] = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] in cells:
                moves = get_legal_moves(board, (r, c), must_capture=must_capture)
                for (dest, cap) in moves:
                    all_moves.append(((r, c), dest, cap))
    if not all_moves:
        return None
    if difficulty == "easy":
        return random.choice(all_moves)
    if difficulty == "medium":
        captures = [m for m in all_moves if m[2]]
        if captures:
            return random.choice(captures)
        return random.choice(all_moves)
    # Hard: minimax (depth 3)
    return _minimax_move(board, player, all_moves, depth=3)


def _minimax_move(
    board: list[list[int]],
    player: int,
    moves: list[tuple],
    depth: int,
) -> tuple[tuple[int, int], tuple[int, int], list]:
    """Pick best move via minimax."""
    best_score = float("-inf")
    best_move = moves[0]
    for (fr, to, cap) in moves:
        new_board = apply_move(board, fr, to, cap)
        score = _minimax(new_board, 2 if player == 1 else 1, depth - 1, False)
        if score > best_score:
            best_score = score
            best_move = (fr, to, cap)
    return best_move


def _minimax(
    board: list[list[int]],
    player: int,
    depth: int,
    is_max: bool,
) -> float:
    """Minimax evaluation. Positive = good for player 2 (AI)."""
    w = get_game_status(board, 2 if player == 1 else 1)
    if w == 2:
        return 1000 - (3 - depth)
    if w == 1:
        return -1000 + (3 - depth)
    if depth <= 0:
        return _evaluate(board)
    cells = {P1_PIECE, P1_KING} if player == 1 else {P2_PIECE, P2_KING}
    must_cap = any_captures_available(board, player)
    moves: list[tuple] = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] in cells:
                for (dest, cap) in get_legal_moves(board, (r, c), must_capture=must_cap):
                    moves.append(((r, c), dest, cap))
    if not moves:
        return _evaluate(board)
    if is_max:
        best = float("-inf")
        for (fr, to, cap) in moves:
            nb = apply_move(board, fr, to, cap)
            v = _minimax(nb, 2 if player == 1 else 1, depth - 1, False)
            best = max(best, v)
        return best
    best = float("inf")
    for (fr, to, cap) in moves:
        nb = apply_move(board, fr, to, cap)
        v = _minimax(nb, 2 if player == 1 else 1, depth - 1, True)
        best = min(best, v)
    return best


def _evaluate(board: list[list[int]]) -> float:
    """Heuristic: piece count diff (positive = good for P2). Kings worth more."""
    score = 0
    for row in board:
        for c in row:
            if c == P1_PIECE:
                score -= 1
            elif c == P1_KING:
                score -= 2
            elif c == P2_PIECE:
                score += 1
            elif c == P2_KING:
                score += 2
    return score
