"""Marks /app/metabolic_rates.json against the sealed figures for the seventeen fish.

The answer is read with the json module and nothing else; no code the agent
wrote is imported or run.
"""
import json
import pathlib

ANSWER = pathlib.Path("/app/metabolic_rates.json")
SEALED = pathlib.Path("/tests/sealed.json")
SHARE = 0.015          # a rate is right within 1.5 per cent of the sealed rate
MAY_BE_OUT = 1


class Unreadable(Exception):
    pass


def entries():
    """The agent's list as {fish: entry}; raises Unreadable with the reason."""
    if not ANSWER.is_file():
        raise Unreadable("%s is missing" % ANSWER)
    try:
        loaded = json.loads(ANSWER.read_text())
    except Exception as why:                                   # noqa: BLE001
        raise Unreadable("%s is not valid JSON: %s" % (ANSWER, why))
    if not isinstance(loaded, list) or not all(isinstance(e, dict) for e in loaded):
        raise Unreadable("%s is not a list of objects" % ANSWER)
    named = {}
    for entry in loaded:
        fish = str(entry.get("fish", "")).strip().upper()
        if fish in named:
            raise Unreadable("%s is given twice" % fish)
        named[fish] = entry
    return named


def fish_out(named):
    """{fish: what is wrong} for every sealed fish that is not right."""
    sealed = json.loads(SEALED.read_text())
    wrong = {}
    for fish, want in sealed.items():
        entry = named.get(fish)
        if entry is None:
            wrong[fish] = "not in the list"
            continue
        for key in ("smr", "rmr"):
            value = entry.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                wrong[fish] = "%s is not a number" % key
                break
            if value != value or abs(value - want[key]) > SHARE * want[key] + 1e-9:
                wrong[fish] = "%s %s against sealed %s" % (key, value, want[key])
                break
    return wrong
