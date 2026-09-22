"""Throwaway: proves a failing test blocks the merge (quickstart V6, T025).

This file exists only to make `checks / quality` fail on a pull request. Delete it — and the
branch — once the merge button has been observed to be disabled.
"""


def test_deliberately_false() -> None:
    """Asserts something untrue on purpose."""
    expected_answer = 4
    assert 2 + 2 == expected_answer + 1
