"""
AI opponent: heuristic + minimax with depth by difficulty.

Advanced modes use iterative deepening, a time budget, evaluation memoization
(transpositions), and per-game adaptation when ``game_id`` is passed (repeated
positions the human steered us to get a small eval nudge — no ML).
"""

from __future__ import annotations

import random
import time
from collections import Counter, OrderedDict, deque
from dataclasses import dataclass, field
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

# --- Per-game “memory”: board fingerprints when AI was to move (after human play). ---
_MAX_GAMES_TRACKED = 1500
_MAX_PLIES_PER_GAME = 22
_ADAPT_VISITS: OrderedDict[int, deque[int]] = OrderedDict()


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


def _board_fingerprint(board: list[list[int]]) -> int:
    """Fast 64-bit-ish hash for TT / adaptation (not crypto-global across runs)."""
    h = 14695981039346656037
    for row in board:
        for cell in row:
            h ^= int(cell) & 0xFF
            h = (h * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return int(h)


def _adapt_touch_game(game_id: int) -> None:
    """LRU: mark game_id recently used; evict oldest if over capacity."""
    if game_id in _ADAPT_VISITS:
        _ADAPT_VISITS.move_to_end(game_id)
        return
    while len(_ADAPT_VISITS) >= _MAX_GAMES_TRACKED:
        _ADAPT_VISITS.popitem(last=False)
    _ADAPT_VISITS[game_id] = deque(maxlen=_MAX_PLIES_PER_GAME)


def _adapt_record_ai_turn_start(game_id: int | None, board: list[list[int]]) -> None:
    """Remember this position (AI to move) for later repeats in the same game."""
    if game_id is None:
        return
    _adapt_touch_game(game_id)
    fp = _board_fingerprint(board)
    _ADAPT_VISITS[game_id].append(fp)


def _adapt_repeat_fingerprints(game_id: int | None) -> frozenset[int]:
    """Fingerprints that occurred at least twice when AI was to move (same match)."""
    if game_id is None or game_id not in _ADAPT_VISITS:
        return frozenset()
    dq = _ADAPT_VISITS[game_id]
    counts = Counter(dq)
    return frozenset(fp for fp, n in counts.items() if n >= 2)


@dataclass
class _SearchContext:
    deadline: float
    repeat_fps: frozenset[int]
    eval_memo: dict[int, float] = field(default_factory=dict)
    node_counter: int = 0

    def timed_out(self) -> bool:
        return time.perf_counter() >= self.deadline

    def tick(self) -> bool:
        """Return True if search should soften (fallback to static eval)."""
        self.node_counter += 1
        return self.node_counter % 8192 == 0 and self.timed_out()


def get_ai_move(
    board: list[list[int]],
    player: int,
    difficulty: str,
    *,
    game_id: int | None = None,
) -> Optional[tuple[tuple, tuple, list]]:
    """
    Return (from_pos, to_pos, captured) or None if no moves.

    ``game_id`` enables per-match adaptation for strong tiers (repeat motifs).
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

    # Search modes: depth + budget + optional adaptation (budget = max seconds per move — lower = snappier)
    if mode == "hard":
        base = 3 if _is_tricky(board, player, all_moves) else 2
        budget = 0.09
        extra = 5
    elif mode == "expert":
        base = 5 if _is_tricky(board, player, all_moves) else 4
        budget = 0.18
        extra = 4
    elif mode == "master":
        base = 6 if _is_tricky(board, player, all_moves) else 5
        budget = 0.27
        extra = 4
    elif mode == "top_players":
        base = 7 if _is_tricky(board, player, all_moves) else 6
        budget = 0.38
        extra = 3
    else:
        base = 3 if _is_tricky(board, player, all_moves) else 2
        budget = 0.12
        extra = 4

    use_adapt = mode in ("hard", "expert", "master", "top_players") and game_id is not None
    repeat_fps = _adapt_repeat_fingerprints(game_id) if use_adapt else frozenset()
    deadline = time.perf_counter() + budget
    ctx = _SearchContext(deadline=deadline, repeat_fps=repeat_fps)

    best = _iterative_deepening_move(
        board, player, all_moves, start_depth=base, max_extra_depth=extra, ctx=ctx
    )
    if use_adapt:
        _adapt_record_ai_turn_start(game_id, board)
    return best


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


def _evaluate_static(
    board: list[list[int]], repeat_fps: frozenset[int]
) -> float:
    """
    Heuristic: material + advancement for men + centralization for kings.
    Positive score = good for P2 (AI).
    ``repeat_fps``: positions AI has seen twice+ this match—nudge toward solid replies.
    """
    score = 0.0
    if repeat_fps and _board_fingerprint(board) in repeat_fps:
        score += 0.09

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


def _evaluate_cached(board: list[list[int]], ctx: _SearchContext) -> float:
    fp = _board_fingerprint(board)
    cached = ctx.eval_memo.get(fp)
    if cached is not None:
        return cached
    v = _evaluate_static(board, ctx.repeat_fps)
    ctx.eval_memo[fp] = v
    return v


def _iterative_deepening_move(
    board: list[list[int]],
    player: int,
    moves: list[tuple],
    *,
    start_depth: int,
    max_extra_depth: int,
    ctx: _SearchContext,
) -> tuple[tuple[int, int], tuple[int, int], list]:
    """
    Deepen ply limit until time runs out; reorder root with previous iteration’s best.
    """
    ordered = _order_moves_for_search(board, moves)
    last_complete_best: tuple[tuple[int, int], tuple[int, int], list] = ordered[0]
    next_p = 2 if player == 1 else 1
    max_depth = start_depth + max_extra_depth

    for depth in range(start_depth, max_depth + 1):
        if ctx.timed_out():
            break
        best_score = float("-inf")
        best_at_depth = ordered[0]
        # Search best move from last finished iteration first (PV move ordering).
        primary = last_complete_best
        root_order = [primary] + [m for m in ordered if m is not primary]
        iteration_finished = True

        for (fr, to, cap) in root_order:
            if ctx.timed_out():
                iteration_finished = False
                break
            new_board = apply_move(board, fr, to, cap)
            score = _minimax_ab(
                new_board,
                next_p,
                depth - 1,
                False,
                float("-inf"),
                float("inf"),
                ctx,
            )
            if score > best_score:
                best_score = score
                best_at_depth = (fr, to, cap)

        if iteration_finished:
            last_complete_best = best_at_depth
        else:
            break

    return last_complete_best


def _minimax_ab(
    board: list[list[int]],
    player: int,
    depth: int,
    is_max: bool,
    alpha: float,
    beta: float,
    ctx: _SearchContext,
) -> float:
    """Minimax with alpha–beta pruning. Positive score = good for P2 (AI)."""
    if ctx.tick():
        return _evaluate_cached(board, ctx)

    w = get_game_status(board, 2 if player == 1 else 1)
    if w == 2:
        return 1000.0
    if w == 1:
        return -1000.0
    if depth <= 0:
        return _evaluate_cached(board, ctx)

    cells = {P1_PIECE, P1_KING} if player == 1 else {P2_PIECE, P2_KING}
    must_cap = any_captures_available(board, player)
    moves: list[tuple] = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] in cells:
                for (dest, cap) in get_legal_moves(board, (r, c), must_capture=must_cap):
                    moves.append(((r, c), dest, cap))
    if not moves:
        return _evaluate_cached(board, ctx)
    moves = _order_moves_for_search(board, moves)
    next_p = 2 if player == 1 else 1
    if is_max:
        best = float("-inf")
        for (fr, to, cap) in moves:
            if ctx.tick():
                return _evaluate_cached(board, ctx)
            nb = apply_move(board, fr, to, cap)
            v = _minimax_ab(nb, next_p, depth - 1, False, alpha, beta, ctx)
            best = max(best, v)
            alpha = max(alpha, best)
            if beta <= alpha:
                break
        return best
    best = float("inf")
    for (fr, to, cap) in moves:
        if ctx.tick():
            return _evaluate_cached(board, ctx)
        nb = apply_move(board, fr, to, cap)
        v = _minimax_ab(nb, next_p, depth - 1, True, alpha, beta, ctx)
        best = min(best, v)
        beta = min(beta, best)
        if beta <= alpha:
            break
    return best
