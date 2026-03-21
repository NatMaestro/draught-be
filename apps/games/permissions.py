"""
Guest play: allow unauthenticated access to guest games (player_one is None).
Account-only: history, profile, matchmaking remain IsAuthenticated.
"""


def can_access_game(request, game):
    """
    Allow access if:
    - Game is a guest game (player_one is None), or
    - Request user is player_one or player_two.
    """
    if game.player_one is None:
        return True
    if not request.user or not request.user.is_authenticated:
        return False
    return request.user in (game.player_one, game.player_two)


def is_guest_game(game):
    """Guest-created game: no linked user."""
    return game.player_one is None
