"""Standard and routine metabolic rate of each trout from one respirometry night.

    python3 smr_night.py /app

Reads the bench sheet, the optode exports, the bath thermometers, the relay log
and the barometer, and writes /app/metabolic_rates.json. Standard library only.
"""
import bisect
import csv
import datetime as dt
import json
import math
import pathlib
import sys

O2_IN_DRY_AIR = 0.20946
MG_PER_UMOL = 31.9988e-3
WAIT_S = 60
SHORTEST_S = 300
SETTLED_FROM = dt.datetime(2027, 3, 14, 21, 0, 0)
SMR_QUANTILE = 0.2


# ---------------------------------------------------------------- water


def vapour_hpa(t_c):
    return 6.112 * math.exp(17.62 * t_c / (243.12 + t_c))


def density_kg_l(t_c):
    poly = (999.842594, 6.793952e-2, -9.095290e-3, 1.001685e-4,
            -1.120083e-6, 6.536332e-9)
    return sum(a * t_c ** n for n, a in enumerate(poly)) / 1000.0


def saturation_umol_l(t_c, p_hpa):
    """Oxygen held by air-saturated fresh water (Benson and Krause 1984)."""
    k = t_c + 273.15
    per_kg = math.exp(-135.29996 + 1.572288e5 / k - 6.637149e7 / k ** 2
                      + 1.243678e10 / k ** 3 - 8.621061e11 / k ** 4)
    wet = vapour_hpa(t_c)
    return per_kg * density_kg_l(t_c) * (p_hpa - wet) / (1013.25 - wet)


# ---------------------------------------------------------------- reading files


class Trace:
    """A record of (seconds, value) that can be read off at any moment."""

    def __init__(self, seconds, values):
        self.s = seconds
        self.v = values

    def at(self, when):
        i = bisect.bisect_right(self.s, when)
        if i <= 0:
            return self.v[0]
        if i >= len(self.s):
            return self.v[-1]
        a, b = self.s[i - 1], self.s[i]
        share = (when - a) / (b - a)
        return self.v[i - 1] + share * (self.v[i] - self.v[i - 1])


EPOCH = dt.datetime(2027, 3, 14, 0, 0, 0)


def seconds(stamp):
    return (dt.datetime.strptime(stamp.strip(), "%Y-%m-%d %H:%M:%S") - EPOCH).total_seconds()


def read_two_columns(path):
    with open(path, newline="") as fh:
        rows = list(csv.reader(fh))[1:]
    return Trace([seconds(r[0]) for r in rows], [float(r[1]) for r in rows])


def read_optode(path):
    """-> seconds, {channel number: readings}"""
    when, cols = [], {1: [], 2: [], 3: [], 4: []}
    for line in pathlib.Path(path).read_text().splitlines():
        cell = line.split("\t")
        if line.startswith("#") or len(cell) < 6 or cell[0] == "Date":
            continue
        when.append(seconds(cell[0] + " " + cell[1]))
        for n in cols:
            cols[n].append(float(cell[1 + n]))
    return when, cols


def closed_phases(path):
    """(start, end) of each usable closed phase, in seconds."""
    events = []
    for line in pathlib.Path(path).read_text().splitlines():
        part = line.split()
        if len(part) >= 4 and part[2] == "FLUSH":
            events.append((seconds(part[0] + " " + part[1]), part[3]))
    events.sort()
    phases = []
    for (t_a, what_a), (t_b, what_b) in zip(events, events[1:]):
        if what_a == "OFF" and what_b == "ON":
            begin = t_a + WAIT_S
            if t_b - begin >= SHORTEST_S and begin >= (SETTLED_FROM - EPOCH).total_seconds():
                phases.append((begin, t_b))
    return phases


# ---------------------------------------------------------------- arithmetic


def air_saturation(reading, unit, t_c, p_hpa):
    if unit == "sat":
        return reading
    if unit == "torr":
        reading = reading / 0.750062
    elif unit == "pct_o2":
        reading = reading / 100.0 * p_hpa
    return 100.0 * reading / (O2_IN_DRY_AIR * (p_hpa - vapour_hpa(t_c)))


def unit_of(readings):
    """Which of the software's four oxygen units a channel was exported in."""
    top = sorted(readings)[int(0.98 * len(readings))]
    if top < 30:
        return "pct_o2"
    if top < 125:
        return "sat"
    if top < 175:
        return "torr"
    return "hpa"


def line_fit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return slope, my - slope * mx


def quantile(values, q):
    ranked = sorted(values)
    h = (len(ranked) - 1) * q
    low = int(math.floor(h))
    high = min(low + 1, len(ranked) - 1)
    return ranked[low] + (h - low) * (ranked[high] - ranked[low])


def slice_of(when, begin, end):
    return bisect.bisect_left(when, begin), bisect.bisect_left(when, end)


def phase_conditions(bath, air, begin, end):
    """One temperature and one pressure for a closed phase."""
    i, j = bisect.bisect_left(bath.s, begin), bisect.bisect_left(bath.s, end)
    return sum(bath.v[i:j]) / (j - i), air.at((begin + end) / 2.0)


def bath_a_chamber_follows(when, raw, phases, baths):
    """The bath whose thermostat swing shows in the chamber's closed phases.

    Inside a closed phase a chamber's reading falls along a line and, on top of
    it, breathes with the water temperature, because warmer water holds less
    oxygen at the same pressure of it. Whatever is left about the line is laid
    against what each bath's thermometer did about its own line over the same
    minutes; the bath that accounts for most of it is the one the chamber is
    hanging in.
    """
    explained = {}
    for name, bath in baths.items():
        got = total = 0.0
        for begin, end in phases:
            i, j = slice_of(when, begin, end)
            xs, ys = when[i:j], raw[i:j]
            ts = [bath.at(x) for x in xs]
            s1, c1 = line_fit(xs, ys)
            s2, c2 = line_fit(xs, ts)
            ry = [y - (s1 * x + c1) for x, y in zip(xs, ys)]
            rt = [t - (s2 * x + c2) for x, t in zip(xs, ts)]
            stt = sum(t * t for t in rt)
            sty = sum(t * y for t, y in zip(rt, ry))
            got += sty * sty / stt if stt else 0.0
            total += sum(y * y for y in ry)
        explained[name] = got / total
    return max(explained, key=explained.get), explained


def work_night(app, believe_sheet=False):
    app = pathlib.Path(app)
    with open(app / "bench_sheet.csv", newline="") as fh:
        sheet = list(csv.DictReader(fh))
    baths = {p.stem.split("_")[-1]: read_two_columns(p)
             for p in sorted((app / "baths").glob("*.csv"))}
    air = read_two_columns(app / "barometer.csv")
    phases = closed_phases(app / "relay.log")
    conditions = {name: [phase_conditions(bath, air, b, e) for b, e in phases]
                  for name, bath in baths.items()}

    logs = {}
    for row in sheet:
        if row["logger"] not in logs:
            logs[row["logger"]] = read_optode(app / "optodes" / (row["logger"] + ".txt"))

    declines = {}          # chamber -> [umol/L/h per phase]
    hangs_in = {}
    for row in sheet:
        when, cols = logs[row["logger"]]
        raw = cols[int(row["channel"])]
        unit = unit_of(raw)
        if believe_sheet:
            home = row["bath"]
        else:
            home, _ = bath_a_chamber_follows(when, raw, phases, baths)
        hangs_in[row["chamber"]] = home
        per_phase = []
        for (begin, end), (t_c, p_hpa) in zip(phases, conditions[home]):
            i, j = slice_of(when, begin, end)
            hours = [t / 3600.0 for t in when[i:j]]
            full = saturation_umol_l(t_c, p_hpa)
            conc = [air_saturation(r, unit, t_c, p_hpa) / 100.0 * full for r in raw[i:j]]
            per_phase.append(-line_fit(hours, conc)[0])
        declines[row["chamber"]] = per_phase

    blank_of = {hangs_in[r["chamber"]]: r["chamber"] for r in sheet
                if r["fish"].strip().lower() == "blank"}
    out = []
    for row in sheet:
        if row["fish"].strip().lower() == "blank":
            continue
        grams = float(row["mass_g"])
        litres = (float(row["volume_ml"]) - grams) / 1000.0
        blank = declines[blank_of[hangs_in[row["chamber"]]]]
        rates = [(own - empty) * litres * MG_PER_UMOL / (grams / 1000.0)
                 for own, empty in zip(declines[row["chamber"]], blank)]
        out.append({"fish": row["fish"],
                    "smr": round(quantile(rates, SMR_QUANTILE), 2),
                    "rmr": round(sum(rates) / len(rates), 2)})
    return out, hangs_in


if __name__ == "__main__":
    where = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/app")
    figures, _ = work_night(where)
    (where / "metabolic_rates.json").write_text(json.dumps(figures, indent=1) + "\n")
