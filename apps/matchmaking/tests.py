"""Tests for ranked matchmaking helpers (no Redis required)."""

from django.test import SimpleTestCase, override_settings

from apps.matchmaking.services import (
    ranked_effective_delta_for_elapsed,
    _ranked_pair_allowed,
)


class RankedDeltaTests(SimpleTestCase):
    @override_settings(
        MATCHMAKING_RANKED_INITIAL_DELTA=150,
        MATCHMAKING_RANKED_MAX_DELTA=500,
        MATCHMAKING_RANKED_EXPAND_EVERY_SEC=15,
        MATCHMAKING_RANKED_EXPAND_STEP=25,
    )
    def test_delta_starts_at_initial(self):
        self.assertEqual(ranked_effective_delta_for_elapsed(0), 150)
        self.assertEqual(ranked_effective_delta_for_elapsed(-1), 150)

    @override_settings(
        MATCHMAKING_RANKED_INITIAL_DELTA=150,
        MATCHMAKING_RANKED_MAX_DELTA=500,
        MATCHMAKING_RANKED_EXPAND_EVERY_SEC=15,
        MATCHMAKING_RANKED_EXPAND_STEP=25,
    )
    def test_delta_expands_every_interval(self):
        # 0–14.9s → 150; 15–29.9s → 175; 30s → 200
        self.assertEqual(ranked_effective_delta_for_elapsed(14), 150)
        self.assertEqual(ranked_effective_delta_for_elapsed(15), 175)
        self.assertEqual(ranked_effective_delta_for_elapsed(30), 200)

    @override_settings(
        MATCHMAKING_RANKED_INITIAL_DELTA=150,
        MATCHMAKING_RANKED_MAX_DELTA=400,
        MATCHMAKING_RANKED_EXPAND_EVERY_SEC=15,
        MATCHMAKING_RANKED_EXPAND_STEP=100,
    )
    def test_delta_caps_at_max(self):
        self.assertEqual(ranked_effective_delta_for_elapsed(9999), 400)


class RankedPairAllowedTests(SimpleTestCase):
    @override_settings(
        MATCHMAKING_RANKED_INITIAL_DELTA=150,
        MATCHMAKING_RANKED_MAX_DELTA=500,
        MATCHMAKING_RANKED_EXPAND_EVERY_SEC=15,
        MATCHMAKING_RANKED_EXPAND_STEP=25,
    )
    def test_same_rating_always_allowed(self):
        self.assertTrue(_ranked_pair_allowed(1200, 1200, 0, 0))

    @override_settings(
        MATCHMAKING_RANKED_INITIAL_DELTA=150,
        MATCHMAKING_RANKED_MAX_DELTA=500,
        MATCHMAKING_RANKED_EXPAND_EVERY_SEC=15,
        MATCHMAKING_RANKED_EXPAND_STEP=25,
    )
    def test_200_gap_not_allowed_when_both_just_joined(self):
        self.assertFalse(_ranked_pair_allowed(1200, 1000, 0, 0))

    @override_settings(
        MATCHMAKING_RANKED_INITIAL_DELTA=150,
        MATCHMAKING_RANKED_MAX_DELTA=500,
        MATCHMAKING_RANKED_EXPAND_EVERY_SEC=15,
        MATCHMAKING_RANKED_EXPAND_STEP=25,
    )
    def test_wide_gap_allowed_if_one_waited_long(self):
        # waited 60s → delta 150 + 4*25 = 250
        self.assertTrue(_ranked_pair_allowed(1200, 1000, 0, 60))
