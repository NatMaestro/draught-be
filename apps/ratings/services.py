"""
ELO rating update service.
"""

from django.conf import settings

from apps.users.models import User


def update_ratings(game):
    """
    Update ELO ratings for both players after ranked game.
    Winner gets +K*(1-expected), loser gets +K*(0-expected).
    """
    if not game.is_ranked or not game.winner:
        return
    p1 = game.player_one
    p2 = game.player_two
    if not p1 or not p2:
        return
    k = getattr(settings, "ELO_K_FACTOR", 32)
    r1 = p1.rating
    r2 = p2.rating
    e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
    e2 = 1 - e1
    if game.winner == p1:
        s1, s2 = 1, 0
    else:
        s1, s2 = 0, 1
    p1.rating = max(100, int(r1 + k * (s1 - e1)))
    p2.rating = max(100, int(r2 + k * (s2 - e2)))
    p1.games_played += 1
    p2.games_played += 1
    if game.winner == p1:
        p1.games_won += 1
    else:
        p2.games_won += 1
    User.objects.bulk_update([p1, p2], ["rating", "games_played", "games_won"])
