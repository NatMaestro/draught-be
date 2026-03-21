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
    """
    row, col = fr
    cell = board[row][col]
    if cell == EMPTY:
        return []
    directions = _get_directions(cell)
    opponent = _get_opponent(cell)
    captures: list[tuple[tuple[int, int], list]] = []
    moves: list[tuple[tuple[int, int], list]] = []
    for dr, dc in directions:
        nr, nc = row + dr, col + dc
        if not _in_bounds(nr, nc):
            continue
        ncell = board[nr][nc]
        if ncell == EMPTY and _is_playable_tile(nr, nc):
            if not must_capture:
                moves.append(((nr, nc), []))
        elif ncell in opponent:
            jr, jc = nr + dr, nc + dc
            if _in_bounds(jr, jc) and board[jr][jc] == EMPTY and _is_playable_tile(jr, jc):
                captures.append(((jr, jc), [(nr, nc)]))
    if captures:
        extended = _extend_captures(board, fr, captures)
        return extended
    if must_capture:
        return []
    return moves


def _extend_captures(
    board: list[list[int]], start: tuple[int, int], partial: list[tuple]
) -> list[tuple[tuple[int, int], list]]:
    """
    Extend capture sequences with multi-jumps.
    Only *terminal* squares (no further mandatory capture from landing) are legal destinations.
    """
    result: list[tuple[tuple[int, int], list]] = []
    for (dest, captured) in partial:
        if not _has_further_capture(board, start, dest, captured):
            result.append((dest, captured))
            continue
        b2 = _apply_capture(board, start, dest, captured)
        pr, pc = dest
        cell = b2[pr][pc]
        opponent = _get_opponent(cell)
        for dr, dc in _get_directions(cell):
            nr, nc = pr + dr, pc + dc
            if not _in_bounds(nr, nc):
                continue
            jr, jc = nr + dr, nc + dc
            if not _in_bounds(jr, jc):
                continue
            if (
                b2[nr][nc] in opponent
                and b2[jr][jc] == EMPTY
                and _is_playable_tile(jr, jc)
            ):
                new_cap = captured + [(nr, nc)]
                extended = _extend_captures(b2, dest, [((jr, jc), new_cap)])
                result.extend(extended)
    return result


def _has_further_capture(
    board: list[list[int]], start: tuple[int, int], dest: tuple[int, int], captured: list
) -> bool:
    b2 = _apply_capture(board, start, dest, captured)
    cell = b2[dest[0]][dest[1]]
    opponent = _get_opponent(cell)
    for dr, dc in _get_directions(cell):
        nr, nc = dest[0] + dr, dest[1] + dc
        if not _in_bounds(nr, nc):
            continue
        jr, jc = nr + dr, nc + dc
        if not _in_bounds(jr, jc):
            continue
        if b2[nr][nc] in opponent and b2[jr][jc] == EMPTY and _is_playable_tile(jr, jc):
            return True
    return False


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
    # King promotion: P1 reaches row 0, P2 reaches row 9
    if cell == P1_PIECE and r1 == 0:
        b[r1][c1] = P1_KING
    elif cell == P2_PIECE and r1 == BOARD_SIZE - 1:
        b[r1][c1] = P2_KING
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


def apply_move(
    board: list[list[int]], fr: tuple[int, int], to: tuple[int, int], captured: list
) -> list[list[int]]:
    """Apply move and return new board state. Promotes to king if needed."""
    import copy
    b = copy.deepcopy(board)
    r0, c0 = fr
    r1, c1 = to
    cell = b[r0][c0]
    b[r1][c1] = cell
    b[r0][c0] = EMPTY
    for (r, c) in captured:
        b[r][c] = EMPTY
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
