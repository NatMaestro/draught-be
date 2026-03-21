from django.test import TestCase
from apps.board_engine.engine import (
    create_initial_board,
    count_pieces,
    validate_and_get_move,
    get_legal_moves,
    get_game_status,
    any_captures_available,
    P1_PIECE,
    P2_PIECE,
    EMPTY,
    BOARD_SIZE,
)


class BoardEngineTests(TestCase):
    def test_initial_board(self):
        board = create_initial_board()
        self.assertEqual(len(board), 10)
        self.assertEqual(len(board[0]), 10)
        self.assertEqual(count_pieces(board, 1), 20)
        self.assertEqual(count_pieces(board, 2), 20)
        # (0,0) has a piece (player2) per spec
        self.assertEqual(board[0][0], P2_PIECE)
        self.assertEqual(board[0][1], EMPTY)
        self.assertEqual(board[6][0], P1_PIECE)

    def test_simple_move(self):
        board = create_initial_board()
        # P1 moves up (row decrease). Place P1 at (5,1), empty (4,0) and (4,2). (row+col)%2==0 for playable.
        board[5][1] = P1_PIECE
        board[4][0] = EMPTY
        board[4][2] = EMPTY
        moves = get_legal_moves(board, (5, 1))
        self.assertGreater(len(moves), 0)

    def test_validate_move(self):
        board = create_initial_board()
        board[5][1] = P1_PIECE
        board[4][0] = EMPTY
        result = validate_and_get_move(board, 1, (5, 1), (4, 0))
        self.assertIsNotNone(result)
        new_board, captured = result
        self.assertEqual(len(captured), 0)
        self.assertEqual(new_board[4][0], P1_PIECE)
        self.assertEqual(new_board[5][1], EMPTY)

    def test_compulsory_capture_rejects_simple_move(self):
        """If any capture exists for the side, non-capturing moves are illegal."""
        board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        # P1 at (5,1): can step to (4,0) or capture P2 at (4,2) to (3,3).
        board[5][1] = P1_PIECE
        board[4][2] = P2_PIECE
        self.assertTrue(any_captures_available(board, 1))
        moves = get_legal_moves(board, (5, 1), must_capture=True)
        self.assertTrue(all(len(cap) > 0 for _, cap in moves))
        self.assertFalse(any(dest == (4, 0) for dest, cap in moves if not cap))
        result = validate_and_get_move(board, 1, (5, 1), (4, 0))
        self.assertIsNone(result)

    def test_multi_jump_only_terminal_destination(self):
        """
        If a second jump is possible from the landing square, stopping after the
        first jump is illegal; only full chain endpoints are legal.
        """
        board = [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        # P2 chain: (3,3) -> over (4,4) -> (5,5) -> over (6,6) -> (7,7)
        board[3][3] = P2_PIECE
        board[4][4] = P1_PIECE
        board[6][6] = P1_PIECE
        # (5,5) and (7,7) stay empty
        moves = get_legal_moves(board, (3, 3))
        dests = {dest for dest, cap in moves}
        self.assertIn((7, 7), dests)
        self.assertNotIn((5, 5), dests)
        full = next((cap for dest, cap in moves if dest == (7, 7)), None)
        self.assertIsNotNone(full)
        self.assertEqual(full, [(4, 4), (6, 6)])
        bad = validate_and_get_move(board, 2, (3, 3), (5, 5))
        self.assertIsNone(bad)
        good = validate_and_get_move(board, 2, (3, 3), (7, 7))
        self.assertIsNotNone(good)
