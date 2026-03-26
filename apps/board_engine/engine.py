"""
Draught board engine: 10x10 board, move validation, captures, kings, win/loss.

Cell values:
    0 = empty
    1 = player1 piece
    2 = player2 piece
    3 = player1 king
    4 = player2 king

Board layout (matches spec): first tile (0,0) has a piece. Pieces sit on (row+col)%2==0.
Rows 0-3 = player2, rows 6-9 = player1. Player1 moves up (row decreases), player2 down (row increases).

Uncrowned men slide forward only, but may capture (and continue multi-jumps) along any diagonal,
including backward, when an opponent presents itself — same as typical international-style rules.

Kings ("flying kings"): may slide any distance along diagonals through empty squares. They capture
by jumping over an opponent on a diagonal and landing on any empty square beyond (forward, backward,
or combined in a multi-jump sequence).

Promotion: a man becomes a king only when the full move (including the entire capture chain) ends
on the opponent's back rank — passing through that rank mid-sequence does not crown.
"""

from typing import Optional

EMPTY = 0
P1_PIECE = 1
P2_PIECE = 2
P1_KING = 3
P2_KING = 4

BOARD_SIZE = 10
PIECES_PER_PLAYER = 20

# Player1 at bottom (rows 6-9) moves UP (row decreases). Player2 at top (rows 0-3) moves DOWN (row increases).
P1_FORWARD = [(-1, -1), (-1, 1)]
P2_FORWARD = [(1, -1), (1, 1)]
BOTH = P1_FORWARD + P2_FORWARD


def create_initial_board() -> list[list[int]]:
    """
    Create 10x10 board matching spec. (0,0) has a piece; pieces on (row+col)%2==0.
    First 4 rows = player2, last 4 rows = player1. 20 pieces per side.
    """
    board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    for row in range(4):
        for col in range(BOARD_SIZE):
            if (row + col) % 2 == 0:
                board[row][col] = P2_PIECE
    for row in range(6, BOARD_SIZE):
        for col in range(BOARD_SIZE):
            if (row + col) % 2 == 0:
                board[row][col] = P1_PIECE
    return board


def _is_playable_tile(row: int, col: int) -> bool:
    """Tile that can hold a piece: (row+col)%2 == 0. (0,0) is playable."""
    return (row + col) % 2 == 0


def _in_bounds(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def _is_player1(cell: int) -> bool:
    return cell in (P1_PIECE, P1_KING)


def _is_player2(cell: int) -> bool:
    return cell in (P2_PIECE, P2_KING)


def _get_directions(cell: int) -> list[tuple[int, int]]:
    if cell == P1_KING or cell == P2_KING:
        return BOTH
    if cell == P1_PIECE:
        return P1_FORWARD
    return P2_FORWARD


def _get_opponent(cell: int) -> set[int]:
    if _is_player1(cell):
        return {P2_PIECE, P2_KING}
    return {P1_PIECE, P1_KING}


def _get_same_player(cell: int) -> set[int]:
    if _is_player1(cell):
        return {P1_PIECE, P1_KING}
    return {P2_PIECE, P2_KING}


def _is_king_cell(cell: int) -> bool:
    return cell in (P1_KING, P2_KING)


def enumerate_king_flying_hops(board: list[list[int]], fr: tuple[int, int]) -> list[tuple]:
    """
    One-hop flying-king captures: along each diagonal, jump the closest opponent and land on any
    empty playable square beyond it on the same ray.
    Returns [((dest_row, dest_col), [captured_squares]), ...].
    """
    r, c = fr
    cell = board[r][c]
    if not _is_king_cell(cell):
        return []
    opponent = _get_opponent(cell)
    captures: list[tuple[tuple[int, int], list]] = []
    for dr, dc in BOTH:
        k = 1
        while True:
            nr, nc = r + dr * k, c + dc * k
            if not _in_bounds(nr, nc):
                break
            here = board[nr][nc]
            if here in opponent:
                lr, lc = nr + dr, nc + dc
                while (
                    _in_bounds(lr, lc)
                    and board[lr][lc] == EMPTY
                    and _is_playable_tile(lr, lc)
                ):
                    captures.append(((lr, lc), [(nr, nc)]))
                    lr, lc = lr + dr, lc + dc
                break
            if here != EMPTY:
                break
            k += 1
    return captures


def enumerate_men_adjacent_hops(board: list[list[int]], fr: tuple[int, int]) -> list[tuple]:
    """Adjacent jump captures for uncrowned men (any diagonal)."""
    r, c = fr
    cell = board[r][c]
    if cell not in (P1_PIECE, P2_PIECE):
        return []
    opponent = _get_opponent(cell)
    captures: list[tuple[tuple[int, int], list]] = []
    for dr, dc in BOTH:
        nr, nc = r + dr, c + dc
        if not _in_bounds(nr, nc):
            continue
        ncell = board[nr][nc]
        if ncell in opponent:
            jr, jc = nr + dr, nc + dc
            if _in_bounds(jr, jc) and board[jr][jc] == EMPTY and _is_playable_tile(jr, jc):
                captures.append(((jr, jc), [(nr, nc)]))
    return captures


def get_next_capture_hops(board: list[list[int]], pos: tuple[int, int]) -> list[tuple]:
    """Legal single capture hops from pos (king: flying; men: adjacent)."""
    r, c = pos
    cell = board[r][c]
    if cell == EMPTY:
        return []
    if _is_king_cell(cell):
        return enumerate_king_flying_hops(board, pos)
    return enumerate_men_adjacent_hops(board, pos)


def enumerate_king_quiet_slides(board: list[list[int]], fr: tuple[int, int]) -> list[tuple]:
    """All empty diagonal slides (any distance) for a king — completing such a move removes the king."""
    r, c = fr
    cell = board[r][c]
    if not _is_king_cell(cell):
        return []
    moves: list[tuple[tuple[int, int], list]] = []
    for dr, dc in BOTH:
        k = 1
        while True:
            nr, nc = r + dr * k, c + dc * k
            if not _in_bounds(nr, nc):
                break
            if board[nr][nc] != EMPTY or not _is_playable_tile(nr, nc):
                break
            moves.append(((nr, nc), []))
            k += 1
    return moves


def _extend_generic_captures(
    board: list[list[int]], start: tuple[int, int], partial: list[tuple]
) -> list[tuple[tuple[int, int], list]]:
    """
    Extend capture sequences (men: adjacent jumps; kings: flying hops).
    Only terminal squares (no further mandatory capture from landing) are legal destinations.
    """
    result: list[tuple[tuple[int, int], list]] = []
    for (dest, captured) in partial:
        b2 = _apply_capture(board, start, dest, captured)
        next_hops = get_next_capture_hops(b2, dest)
        if not next_hops:
            result.append((dest, captured))
            continue
        for nh_dest, nh_cap in next_hops:
            new_cap = captured + nh_cap
            extended = _extend_generic_captures(b2, dest, [(nh_dest, new_cap)])
            result.extend(extended)
    return result


def _get_king_legal_moves(
    board: list[list[int]], fr: tuple[int, int], must_capture: bool
) -> list[tuple]:
    row, col = fr
    cell = board[row][col]
    if not _is_king_cell(cell):
        return []
    captures = enumerate_king_flying_hops(board, fr)
    if captures:
        return _extend_generic_captures(board, fr, captures)
    if must_capture:
        return []
    return enumerate_king_quiet_slides(board, fr)


def count_pieces(board: list[list[int]], player: int) -> int:
    """Count pieces for player (1 or 2)."""
    p1 = {1, 3} if player == 1 else {2, 4}
    c = 0
    for row in board:
        for cell in row:
            if cell in p1:
                c += 1
    return c


def get_legal_moves(board: list[list[int]], fr: tuple[int, int], must_capture: bool = False) -> list[tuple]:
    """
    Return list of legal destinations from (row, col).
    Returns simple moves and/or captures. If must_capture, only captures.
    Each dest is ((row, col), captured_positions_list).

    Men: slide forward only; capture with adjacent jumps (any diagonal).
    Kings: flying slides and flying captures; non-capturing king moves remove the king.
    """
    row, col = fr
    cell = board[row][col]
    if cell == EMPTY:
        return []
    if _is_king_cell(cell):
        return _get_king_legal_moves(board, fr, must_capture)
    slide_dirs = _get_directions(cell)
    captures = enumerate_men_adjacent_hops(board, fr)
    moves: list[tuple[tuple[int, int], list]] = []
    for dr, dc in slide_dirs:
        nr, nc = row + dr, col + dc
        if not _in_bounds(nr, nc):
            continue
        ncell = board[nr][nc]
        if ncell == EMPTY and _is_playable_tile(nr, nc):
            if not must_capture:
                moves.append(((nr, nc), []))
    if captures:
        return _extend_generic_captures(board, fr, captures)
    if must_capture:
        return []
    return moves


def _apply_capture(
    board: list[list[int]], start: tuple[int, int], dest: tuple[int, int], captured: list
) -> list[list[int]]:
    import copy
    b = copy.deepcopy(board)
    r0, c0 = start
    r1, c1 = dest
    cell = b[r0][c0]
    b[r1][c1] = cell
    b[r0][c0] = EMPTY
    for (r, c) in captured:
        b[r][c] = EMPTY
    # No promotion here — multi-jump sequences may pass through the promotion row;
    # crowning only when the full move ends on that row (see apply_move).
    return b


def any_captures_available(board: list[list[int]], player: int) -> bool:
    """Check if player has any capture move."""
    cells = {P1_PIECE, P1_KING} if player == 1 else {P2_PIECE, P2_KING}
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] in cells:
                moves = get_legal_moves(board, (r, c))
                if any(cap for _, cap in moves if cap):
                    return True
    return False


def _normalize_sq(sq: object) -> tuple[int, int]:
    if isinstance(sq, (tuple, list)) and len(sq) >= 2:
        return (int(sq[0]), int(sq[1]))
    raise TypeError("expected (row, col)")


def _apply_capture_sequence(
    board: list[list[int]],
    pos: tuple[int, int],
    final_to: tuple[int, int],
    caps: list[tuple[int, int]],
) -> list[list[int]]:
    """
    Replay a full capture chain hop-by-hop (men + flying kings).
    Intermediate landings on the promotion row do not crown — only the final square of
    the move can promote (handled in apply_move after this returns).
    """
    if not caps:
        if pos != final_to:
            raise ValueError("capture chain does not end at declared destination")
        return board
    want = caps[0]
    hops = get_next_capture_hops(board, pos)
    for dest, cap_list in hops:
        if not cap_list:
            continue
        first = _normalize_sq(cap_list[0])
        if first != want:
            continue
        b2 = _apply_capture(board, pos, dest, cap_list)
        try:
            return _apply_capture_sequence(b2, dest, final_to, caps[1:])
        except ValueError:
            continue
    raise ValueError("illegal or ambiguous capture chain")


def apply_move(
    board: list[list[int]], fr: tuple[int, int], to: tuple[int, int], captured: list
) -> list[list[int]]:
    """Apply move and return new board state. Promotes to king if needed."""
    import copy
    if not captured:
        b = copy.deepcopy(board)
        r0, c0 = fr
        r1, c1 = to
        cell = b[r0][c0]
        b[r1][c1] = cell
        b[r0][c0] = EMPTY
        if cell == P1_PIECE and r1 == 0:
            b[r1][c1] = P1_KING
        elif cell == P2_PIECE and r1 == BOARD_SIZE - 1:
            b[r1][c1] = P2_KING
        return b

    cap_sq = [_normalize_sq(x) for x in captured]
    b0 = copy.deepcopy(board)
    b = _apply_capture_sequence(b0, fr, to, cap_sq)
    r1, c1 = to
    cell = b[r1][c1]
    if cell == P1_PIECE and r1 == 0:
        b[r1][c1] = P1_KING
    elif cell == P2_PIECE and r1 == BOARD_SIZE - 1:
        b[r1][c1] = P2_KING
    return b


def validate_and_get_move(
    board: list[list[int]], current_player: int, fr: tuple[int, int], to: tuple[int, int]
) -> Optional[tuple[list[list[int]], list]]:
    """
    Validate move. Return (new_board, captured_list) or None if invalid.
    """
    row, col = fr
    if not _in_bounds(row, col) or not _in_bounds(to[0], to[1]):
        return None
    cell = board[row][col]
    if current_player == 1 and cell not in (P1_PIECE, P1_KING):
        return None
    if current_player == 2 and cell not in (P2_PIECE, P2_KING):
        return None
    must_capture = any_captures_available(board, current_player)
    moves = get_legal_moves(board, fr, must_capture=must_capture)
    for (dest, cap) in moves:
        if dest == to:
            new_board = apply_move(board, fr, to, cap)
            return (new_board, cap)
    return None


def check_win_loss(board: list[list[int]]) -> Optional[int]:
    """
    Return 1 if player2 loses, 2 if player1 loses, None if game continues.
    Loss = only 1 piece remaining.
    """
    p1_count = count_pieces(board, 1)
    p2_count = count_pieces(board, 2)
    if p1_count <= 1:
        return 2  # player1 loses
    if p2_count <= 1:
        return 1  # player2 loses
    return None


def has_legal_moves(board: list[list[int]], player: int) -> bool:
    """Check if player has any legal move (respects compulsory capture)."""
    must_capture = any_captures_available(board, player)
    cells = {P1_PIECE, P1_KING} if player == 1 else {P2_PIECE, P2_KING}
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] in cells:
                if get_legal_moves(board, (r, c), must_capture=must_capture):
                    return True
    return False


def get_game_status(board: list[list[int]], current_player: int) -> Optional[int]:
    """
    Return winner (1 or 2), or None if game continues.
    Checks: piece count loss, no legal moves.
    """
    wl = check_win_loss(board)
    if wl is not None:
        return wl
    if not has_legal_moves(board, current_player):
        return 2 if current_player == 1 else 1
    return None
