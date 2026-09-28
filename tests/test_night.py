"""The graded checks for the respirometry night."""
import json

import pytest

import grader


def test_answer_is_a_list_with_one_object_for_each_fish():
    named = grader.entries()
    sealed = json.loads(grader.SEALED.read_text())
    assert sorted(named) == sorted(sealed), "fish named: %s" % sorted(named)


def test_no_more_than_one_fish_is_out():
    try:
        named = grader.entries()
    except grader.Unreadable as why:
        pytest.fail(str(why))
    wrong = grader.fish_out(named)
    print("OUT %d" % len(wrong))
    assert len(wrong) <= grader.MAY_BE_OUT, "; ".join(
        "%s: %s" % item for item in sorted(wrong.items()))
