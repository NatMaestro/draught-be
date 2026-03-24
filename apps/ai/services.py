"""
AI opponent: heuristic + minimax with depth by difficulty.

Not machine-learned — strength comes from search depth and hand-tuned evaluation.
"""

import random
from typing import Optional

from apps.board_engine.engine import (
    get_legal_moves,
    any_captures_available,
    apply_move,
    get_game_status,
    EMPTY,
    P1_PIECE,
    P2_PIECE,
    P1_KING,
    P2_KING,
    BOARD_SIZE,
)


def _normalize_difficulty(difficulty: str) -> str:
    """Map API / UI aliases to internal mode names."""
    if not difficulty:
        return "medium"
    d = difficulty.strip().lower()
    aliases = {
        "beginner": "easy",
        "novice": "easy",
        "intermediate": "medium",
        "advanced": "hard",
        "top": "top_players",
    }
    return aliases.get(d, d)


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

    mode = _normalize_difficulty(difficulty)

    if mode == "easy":
        return random.choice(all_moves)
    if mode == "medium":
        captures = [m for m in all_moves if m[2]]
        if captures:
            return random.choice(captures)
        return random.choice(all_moves)
    if mode == "adaptive":
        return _adaptive_move(all_moves)
    # Depth tuned for responsive turns on a 10×10 board (deeper = slower API).
    if mode == "hard":
        d = 3 if _is_tricky(board, player, all_moves) else 2
        return _minimax_move(board, player, all_moves, depth=d)
    if mode == "expert":
        d = 5 if _is_tricky(board, player, all_moves) else 4
        return _minimax_move(board, player, all_moves, depth=d)
    if mode == "master":
        d = 6 if _is_tricky(board, player, all_moves) else 5
        return _minimax_move(board, player, all_moves, depth=d)
    if mode == "top_players":
        d = 7 if _is_tricky(board, player, all_moves) else 6
        return _minimax_move(board, player, all_moves, depth=d)
    # Unknown label — default to medium-strong search
    d = 3 if _is_tricky(board, player, all_moves) else 2
    return _minimax_move(board, player, all_moves, depth=d)


def _is_tricky(
    board: list[list[int]],
    player: int,
    all_moves: list[tuple[tuple[int, int], tuple[int, int], list]],
) -> bool:
    """
    Use full minimax depth when tactics or high branching — otherwise search one ply shallower.
    """
    if any_captures_available(board, player):
        return True
    if len(all_moves) >= 14:
        return True
    capture_moves = sum(1 for m in all_moves if m[2])
    if capture_moves >= 3:
        return True
    return False


def _adaptive_move(all_moves: list) -> tuple:
    """Blend random legal moves with capture preference (no user modelling yet)."""
    if random.random() < 0.5:
        return random.choice(all_moves)
    captures = [m for m in all_moves if m[2]]
    if captures:
        return random.choice(captures)
    return random.choice(all_moves)


def _order_moves_for_search(
    board: list[list[int]], moves: list[tuple]
) -> list[tuple]:
    """Prefer captures and high-value takes first — better alpha–beta pruning."""

    def sort_key(m: tuple) -> tuple:
        fr, to, cap = m
        cap = cap or []
        cap_val = 0
        for p in cap:
            pr, pc = int(p[0]), int(p[1])
            cell = board[pr][pc]
            if cell in (P1_KING, P2_KING):
                cap_val += 4
            elif cell in (P1_PIECE, P2_PIECE):
                cap_val += 2
        return (len(cap), cap_val)

    return sorted(moves, key=sort_key, reverse=True)


def _minimax_move(
    board: list[list[int]],
    player: int,
    moves: list[tuple],
    depth: int,
) -> tuple[tuple[int, int], tuple[int, int], list]:
    """Pick best move via minimax at root for `player` (alpha–beta inside search)."""
    ordered = _order_moves_for_search(board, moves)
    best_score = float("-inf")
    best_move = ordered[0]
    next_p = 2 if player == 1 else 1
    for (fr, to, cap) in ordered:
        new_board = apply_move(board, fr, to, cap)
        score = _minimax_ab(
            new_board, next_p, depth - 1, False, float("-inf"), float("inf")
        )
        if score > best_score:
            best_score = score
            best_move = (fr, to, cap)
    return best_move


def _minimax_ab(
    board: list[list[int]],
    player: int,
    depth: int,
    is_max: bool,
    alpha: float,
    beta: float,
) -> float:
    """Minimax with alpha–beta pruning. Positive score = good for P2 (AI)."""
    w = get_game_status(board, 2 if player == 1 else 1)
    if w == 2:
        return 1000.0
    if w == 1:
        return -1000.0
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
    moves = _order_moves_for_search(board, moves)
    next_p = 2 if player == 1 else 1
    if is_max:
        best = float("-inf")
        for (fr, to, cap) in moves:
            nb = apply_move(board, fr, to, cap)
            v = _minimax_ab(nb, next_p, depth - 1, False, alpha, beta)
            best = max(best, v)
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best
    best = float("inf")
    for (fr, to, cap) in moves:
        nb = apply_move(board, fr, to, cap)
        v = _minimax_ab(nb, next_p, depth - 1, True, alpha, beta)
        best = min(best, v)
        beta = min(beta, best)
        if beta <= alpha:
            break
    return best


def _evaluate(board: list[list[int]]) -> float:
    """
    Heuristic: material + advancement for men + centralization for kings.
    Positive score = good for P2 (AI).
    """
    score = 0.0
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            cell = board[r][c]
            if cell == EMPTY:
                continue
            center = abs(r - 4.5) + abs(c - 4.5)
            king_center = (10.0 - center) * 0.035
            if cell == P1_PIECE:
                score -= 1.0
                score -= 0.14 * (9 - r) / 9.0
            elif cell == P1_KING:
                score -= 2.2
                score -= king_center
            elif cell == P2_PIECE:
                score += 1.0
                score += 0.14 * r / 9.0
            elif cell == P2_KING:
                score += 2.2
                score += king_center
    return score
