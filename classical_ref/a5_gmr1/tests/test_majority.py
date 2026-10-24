"""
tests/test_majority.py
=======================

Exhaustive unit tests for ``majority.majority``: all eight possible
single-bit input combinations are checked against the expected result.
"""

import itertools

import pytest

from majority import majority


@pytest.mark.parametrize(
    "a, b, c, expected",
    [
        (0, 0, 0, 0),
        (0, 0, 1, 0),
        (0, 1, 0, 0),
        (0, 1, 1, 1),
        (1, 0, 0, 0),
        (1, 0, 1, 1),
        (1, 1, 0, 1),
        (1, 1, 1, 1),
    ],
)
def test_majority_all_combinations(a: int, b: int, c: int, expected: int) -> None:
    assert majority(a, b, c) == expected


def test_majority_covers_all_eight_combinations() -> None:
    """Sanity check that our parametrized cases really are exhaustive."""
    all_combinations = set(itertools.product((0, 1), repeat=3))
    tested_combinations = {
        (0, 0, 0),
        (0, 0, 1),
        (0, 1, 0),
        (0, 1, 1),
        (1, 0, 0),
        (1, 0, 1),
        (1, 1, 0),
        (1, 1, 1),
    }
    assert all_combinations == tested_combinations


def test_majority_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        majority(2, 0, 0)
    with pytest.raises(ValueError):
        majority(0, -1, 0)
