"""Marks other ways of working the night up against the sealed figures.

    python rival_readings.py <app dir> <sealed.json>

Each rival is a way somebody might reasonably work the same files up. None of
them may reach the pass mark; the reference must. The script also checks that
the records show plainly which bath a chamber hangs in, and that nothing
simpler than the thermostat swing shows it.
"""
import csv
import json
import pathlib
import statistics
import sys

import smr_night as ref

SHARE, MAY_BE_OUT = 0.015, 1
REAL_BATH = {"R03": "B", "R15": "B"}            # every other chamber is where the sheet says


def load(app):
    app = pathlib.Path(app)
    with open(app / "bench_sheet.csv", newline="") as fh:
        sheet = list(csv.DictReader(fh))
    baths = {p.stem.split("_")[-1]: ref.read_two_columns(p)
             for p in sorted((app / "baths").glob("*.csv"))}
    air = ref.read_two_columns(app / "barometer.csv")
    logs = {name: ref.read_optode(app / "optodes" / (name + ".txt"))
            for name in sorted({r["logger"] for r in sheet})}
    return sheet, baths, air, logs


def phases_of(app, settle=True):
    if settle:
        return ref.closed_phases(pathlib.Path(app) / "relay.log")
    keep = ref.SETTLED_FROM
    ref.SETTLED_FROM = ref.EPOCH
    try:
        return ref.closed_phases(pathlib.Path(app) / "relay.log")
    finally:
        ref.SETTLED_FROM = keep


def night(app, homes, units=True, temperature="phase mean", blank=True, settle=True, standard="q"):
    sheet, baths, air, logs = load(app)
    phases = phases_of(app, settle)
    setpoint = {"A": 12.0, "B": 16.0, "C": 20.0}
    decline = {}
    for row in sheet:
        when, cols = logs[row["logger"]]
        raw = cols[int(row["channel"])]
        unit = ref.unit_of(raw) if units else "sat"
        home = homes.get(row["chamber"], row["bath"])
        bath = baths[home]
        per_phase = []
        for begin, end in phases:
            i, j = ref.slice_of(when, begin, end)
            flat, p_mid = ref.phase_conditions(bath, air, begin, end)
            conc = []
            for t, r in zip(when[i:j], raw[i:j]):
                if temperature == "phase mean":
                    t_c, p = flat, p_mid
                elif temperature == "moment":
                    t_c, p = bath.at(t), air.at(t)
                else:
                    t_c, p = setpoint[home], p_mid
                sat = ref.air_saturation(r, unit, t_c, p)
                conc.append(sat / 100.0 * ref.saturation_umol_l(t_c, p))
            per_phase.append(-ref.line_fit([t / 3600.0 for t in when[i:j]], conc)[0])
        decline[row["chamber"]] = (home, per_phase)
    blank_of = {decline[r["chamber"]][0]: r["chamber"] for r in sheet if r["fish"] == "blank"}
    figures = {}
    for row in sheet:
        if row["fish"] == "blank":
            continue
        home, own = decline[row["chamber"]]
        empty = decline[blank_of[home]][1] if blank else [0.0] * len(own)
        grams = float(row["mass_g"])
        litres = (float(row["volume_ml"]) - grams) / 1000.0
        rates = [(a - b) * litres * ref.MG_PER_UMOL / (grams / 1000.0) for a, b in zip(own, empty)]
        smr = ref.quantile(rates, ref.SMR_QUANTILE) if standard == "q" else min(rates)
        figures[row["fish"]] = {"smr": smr, "rmr": statistics.fmean(rates)}
    return figures


def right(figures, sealed):
    return sum(all(abs(figures[f][k] - sealed[f][k]) <= SHARE * sealed[f][k] for k in ("smr", "rmr"))
               for f in sealed)


def swing_table(app):
    """For each chamber: share of what is left about the line that each bath accounts for."""
    sheet, baths, air, logs = load(app)
    phases = phases_of(app)
    table = {}
    for row in sheet:
        when, cols = logs[row["logger"]]
        raw = cols[int(row["channel"])]
        table[row["chamber"]] = ref.bath_a_chamber_follows(when, raw, phases, baths)[1]
    return table


def main(app, sealed_path):
    sealed = json.loads(pathlib.Path(sealed_path).read_text())
    need = len(sealed) - MAY_BE_OUT
    rivals = [
        ("exports taken as per cent air saturation, sheet believed", dict(homes={}, units=False)),
        ("units put right, sheet believed", dict(homes={})),
        ("units put right, sheet believed, setpoint temperatures", dict(homes={}, temperature="setpoint")),
        ("real baths, blank not taken off", dict(homes=REAL_BATH, blank=False)),
        ("real baths, evening phases kept", dict(homes=REAL_BATH, settle=False)),
        ("real baths, lowest rate as the standard rate", dict(homes=REAL_BATH, standard="min")),
    ]
    report = {}
    for label, how in rivals:
        report[label] = right(night(app, **how), sealed)
        assert report[label] < need, (label, report[label])
    for label, how in [("real baths, the note followed", dict(homes=REAL_BATH)),
                       ("real baths, temperature and pressure of the moment",
                        dict(homes=REAL_BATH, temperature="moment")),
                       ("real baths, setpoint temperatures",
                        dict(homes=REAL_BATH, temperature="setpoint"))]:
        report[label] = right(night(app, **how), sealed)
    assert report["real baths, the note followed"] == len(sealed)
    mine, _ = ref.work_night(app)
    report["reference solution"] = right({f["fish"]: f for f in mine}, sealed)
    assert report["reference solution"] == len(sealed)

    table = swing_table(app)
    with open(pathlib.Path(app) / "bench_sheet.csv", newline="") as fh:
        listed = {r["chamber"]: r["bath"] for r in csv.DictReader(fh)}
    own, other = [], []
    for chamber, shares in table.items():
        real = REAL_BATH.get(chamber, listed[chamber])
        assert max(shares, key=shares.get) == real, (chamber, shares)
        own.append(shares[real])
        other.append(max(v for k, v in shares.items() if k != real))
    report["swing: least share explained by a chamber's own bath"] = round(min(own), 2)
    report["swing: most explained by any other bath"] = round(max(other), 2)
    assert min(own) > max(other) + 0.25
    print(json.dumps(report, indent=1))
    return report


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
