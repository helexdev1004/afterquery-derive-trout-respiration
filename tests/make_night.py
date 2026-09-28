"""Seeded generator for the respirometry night. Truth first, files afterwards.

    python make_night.py <app dir> <sealed.json>

Every chamber's oxygen is stepped second by second from what the fish inside
really used and the water it really hangs in; the loggers, thermometers, relay
and barometer then write down what they saw, each in its own way. The sealed
figures are the lab note's arithmetic on those files with every chamber in its
real bath.
"""
import datetime as dt
import json
import math
import pathlib
import random
import sys

import smr_night as ref

SEED = 270314
DAY = dt.datetime(2027, 3, 14)
T_FIRST = 17 * 3600 + 25 * 60          # simulation starts 17:25:00
T_LAST = 32 * 3600 + 6 * 60            # and ends 08:06:00 next morning
NIGHT_ON = 18 * 3600                   # first flush
CYCLE, FLUSH = 900, 240

SETPOINT = {"A": 12.0, "B": 16.0, "C": 20.0}
# half-width of the thermostat's band, warming and cooling rates in deg C per s
STAT = {"A": (0.12, 0.00090, 0.00160),
        "B": (0.15, 0.00060, 0.00110),
        "C": (0.10, 0.00120, 0.00140)}
SMR_AT = {"A": 55.0, "B": 72.0, "C": 95.0}

# logger, channel, chamber, bath on the sheet, bath it hangs in, fish
BENCH = [
    ("L1", 1, "R01", "A", "A", "T01"), ("L1", 2, "R02", "A", "A", "T02"),
    ("L1", 3, "R03", "A", "B", "T03"), ("L1", 4, "R04", "A", "A", "T04"),
    ("L2", 1, "R05", "A", "A", "T05"), ("L2", 2, "R06", "A", "A", "T06"),
    ("L2", 3, "R07", "A", "A", "blank"), ("L2", 4, "R08", "B", "B", "T07"),
    ("L3", 1, "R09", "B", "B", "T08"), ("L3", 2, "R10", "B", "B", "T09"),
    ("L3", 3, "R11", "B", "B", "blank"), ("L3", 4, "R12", "B", "B", "T10"),
    ("L4", 1, "R13", "B", "B", "T11"), ("L4", 2, "R14", "C", "C", "T12"),
    ("L4", 3, "R15", "C", "B", "T13"), ("L4", 4, "R16", "C", "C", "T14"),
    ("L5", 1, "R17", "C", "C", "T15"), ("L5", 2, "R18", "C", "C", "T16"),
    ("L5", 3, "R19", "C", "C", "T17"), ("L5", 4, "R20", "C", "C", "blank"),
]
EXPORT_UNIT = {"L1": "sat", "L2": "hpa", "L3": "sat", "L4": "torr", "L5": "pct_o2"}
LOGGER_START = {"L1": 17 * 3600 + 41 * 60 + 15, "L2": 17 * 3600 + 43 * 60 + 52,
                "L3": 17 * 3600 + 38 * 60 + 7, "L4": 17 * 3600 + 46 * 60 + 33,
                "L5": 17 * 3600 + 49 * 60 + 21}
BATH_LOG_START = {"A": 17 * 3600 + 30 * 60 + 4, "B": 17 * 3600 + 31 * 60 + 47,
                  "C": 17 * 3600 + 29 * 60 + 18}
CHAMBER_LAG_S = 20.0
OPTODE_NOISE = 0.03                     # per cent air saturation


def stamp(sec):
    return (DAY + dt.timedelta(seconds=sec)).strftime("%Y-%m-%d %H:%M:%S")


def relay_events(rng):
    events = []
    k = 0
    while NIGHT_ON + k * CYCLE < 32 * 3600 + 1:
        on = NIGHT_ON + k * CYCLE + rng.choice((-2, -1, 0, 0, 1, 2))
        events.append((on, "ON"))
        if on + FLUSH < T_LAST:
            events.append((on + FLUSH + rng.choice((-1, 0, 0, 1)), "OFF"))
        k += 1
    # somebody pressed the manual flush button in the small hours
    events += [(26 * 3600 + 39 * 60 + 30, "ON"), (26 * 3600 + 41 * 60, "OFF")]
    return sorted(events)


def bath_second_by_second(rng, name):
    half, warm, cool = STAT[name]
    temp = SETPOINT[name] + rng.uniform(-half, half)
    chilling = rng.random() < 0.5
    room = 0.0
    out = []
    for _ in range(T_FIRST, T_LAST + 1):
        room += -room / 5400.0 + rng.gauss(0, 0.0022)      # slow wander of the room
        if chilling:
            temp -= cool * (1 - 0.6 * room) * (1 + rng.gauss(0, 0.05))
            if temp < SETPOINT[name] - half:
                chilling = False
        else:
            temp += warm * (1 + 0.6 * room) * (1 + rng.gauss(0, 0.05))
            if temp > SETPOINT[name] + half:
                chilling = True
        out.append(temp)
    return out


def pressure_by_hour(rng):
    p = 1006.3
    hours = {}
    for h in range(17, 34):
        hours[h * 3600] = round(p, 1)
        p += rng.gauss(-0.35, 0.3)
    return hours


def pressure_at(hours, sec):
    base = int(sec // 3600) * 3600
    a, b = hours[base], hours[base + 3600]
    return a + (b - a) * (sec - base) / 3600.0


def fish_table(rng):
    table = {}
    for _, _, chamber, _, real, fish in BENCH:
        volume = round(rng.uniform(452, 561), 1)
        if fish == "blank":
            table[chamber] = {"volume": volume, "mass": None}
            continue
        mass = round(rng.uniform(24, 52), 1)
        smr = SMR_AT[real] * (mass / 40.0) ** -0.15 * math.exp(rng.gauss(0, 0.17))
        table[chamber] = {"volume": volume, "mass": mass, "smr": smr,
                          "stress": rng.uniform(0.5, 1.1), "calm_after": rng.uniform(2400, 5400),
                          "restless": rng.uniform(0.12, 0.3)}
    return table


def aeration_second_by_second(rng):
    """How near to air saturation a bath's airstones keep its water, 0.965 to 0.995."""
    level, out = rng.uniform(-0.6, 0.6), []
    for _ in range(T_FIRST, T_LAST + 1):
        level += -level / 7200.0 + rng.gauss(0, 0.012)
        out.append(0.98 + 0.015 * math.tanh(level))
    return out


def chamber_second_by_second(rng, who, bath_temp, relay, hours, blank_growth, aired):
    """True oxygen (umol/L) and chamber temperature for every second."""
    state = False
    pending = list(relay)
    conc = None
    inside = bath_temp[0]
    use = 0.0
    flushes_to = rng.uniform(0.988, 1.0)          # how fully this chamber's pump turns its water over
    out_c, out_t = [], []
    for n, sec in enumerate(range(T_FIRST, T_LAST + 1)):
        while pending and pending[0][0] <= sec:
            _, what = pending.pop(0)
            was = state
            state = what == "ON"
            if was and not state:                         # a closed phase begins
                if who.get("mass") is None:
                    # microbes on the walls, more of them as the night goes on
                    per_h = blank_growth[0] + blank_growth[1] * (sec - NIGHT_ON) / 3600.0
                    per_h *= 1 + rng.gauss(0, 0.06)
                    use = per_h / ref.MG_PER_UMOL / 3600.0            # mg/L/h -> umol/L/s
                else:
                    lively = abs(rng.gauss(0, 0.05))
                    if rng.random() < who["restless"]:
                        lively += rng.expovariate(1 / 0.35)
                    handled = who["stress"] * math.exp(-(sec - NIGHT_ON) / who["calm_after"])
                    mo2 = who["smr"] * (1 + handled + lively)
                    litres = (who["volume"] - who["mass"]) / 1000.0
                    use = mo2 * who["mass"] / 1000.0 / litres / ref.MG_PER_UMOL / 3600.0
        inside += (bath_temp[n] - inside) / CHAMBER_LAG_S
        p = pressure_at(hours, sec)
        full = aired[n] * flushes_to * ref.saturation_umol_l(bath_temp[n], p)
        if conc is None:
            conc = full
        if state or sec < NIGHT_ON:
            conc += (full - conc) / 45.0
        else:
            conc -= use
        out_c.append(conc)
        out_t.append(inside)
    return out_c, out_t


def as_exported(unit, sat, t_c, p):
    if unit == "sat":
        return "%.2f" % sat
    hpa = sat / 100.0 * ref.O2_IN_DRY_AIR * (p - ref.vapour_hpa(t_c))
    if unit == "hpa":
        return "%.2f" % hpa
    if unit == "torr":
        return "%.2f" % (hpa * 0.750062)
    return "%.3f" % (hpa / p * 100.0)


def build(app, sealed_path):
    rng = random.Random(SEED)
    app = pathlib.Path(app)
    (app / "optodes").mkdir(parents=True, exist_ok=True)
    (app / "baths").mkdir(parents=True, exist_ok=True)

    relay = relay_events(rng)
    hours = pressure_by_hour(rng)
    bath_temp = {b: bath_second_by_second(rng, b) for b in "ABC"}
    fish = fish_table(rng)
    aired = {b: aeration_second_by_second(rng) for b in "ABC"}
    growth = {"A": (0.10, 0.006), "B": (0.16, 0.010), "C": (0.24, 0.015)}

    truth = {}
    for _, _, chamber, _, real, _ in BENCH:
        truth[chamber] = chamber_second_by_second(
            rng, fish[chamber], bath_temp[real], relay, hours, growth[real], aired[real])

    for logger in sorted(EXPORT_UNIT):
        lines = ["# Optode logger %s, four channels" % logger,
                 "# Export of the night of 14 March 2027, one reading every 5 s",
                 "Date\tTime\tCh1\tCh2\tCh3\tCh4"]
        rows = [b for b in BENCH if b[0] == logger]
        sec = LOGGER_START[logger]
        while sec <= T_LAST - 60:
            n = sec - T_FIRST
            p = pressure_at(hours, sec)
            cells = []
            for _, _, chamber, _, _, _ in rows:
                conc, inside = truth[chamber][0][n], truth[chamber][1][n]
                sat = 100.0 * conc / ref.saturation_umol_l(inside, p) + rng.gauss(0, OPTODE_NOISE)
                cells.append(as_exported(EXPORT_UNIT[logger], sat, inside, p))
            date, clock = stamp(sec).split(" ")
            lines.append("\t".join([date, clock] + cells))
            sec += 5
        (app / "optodes" / (logger + ".txt")).write_text("\n".join(lines) + "\n", newline="\n")

    for b in "ABC":
        lines = ["time,temp_c"]
        sec = BATH_LOG_START[b]
        while sec <= T_LAST - 30:
            seen = bath_temp[b][sec - T_FIRST] + rng.gauss(0, 0.004)
            lines.append("%s,%.2f" % (stamp(sec), seen))
            sec += 10
        (app / "baths" / ("bath_%s.csv" % b)).write_text("\n".join(lines) + "\n", newline="\n")

    # the relay's record was copied off during the morning's first flush
    written = relay[:-1] if relay[-1][1] == "OFF" else relay
    (app / "relay.log").write_text(
        "".join("%s FLUSH %s\n" % (stamp(t), what) for t, what in written), newline="\n")
    (app / "barometer.csv").write_text(
        "time,pressure_hpa\n" + "".join("%s,%.1f\n" % (stamp(t), v) for t, v in sorted(hours.items())),
        newline="\n")

    sheet = ["logger,channel,chamber,bath,volume_ml,fish,mass_g"]
    for logger, channel, chamber, listed, _, who in BENCH:
        f = fish[chamber]
        sheet.append("%s,%d,%s,%s,%.1f,%s,%s" % (
            logger, channel, chamber, listed, f["volume"], who,
            "" if f["mass"] is None else "%.1f" % f["mass"]))
    (app / "bench_sheet.csv").write_text("\n".join(sheet) + "\n", newline="\n")

    # the sealed figures: the note's arithmetic with each chamber in its real bath
    real = {chamber: bath for _, _, chamber, _, bath, _ in BENCH}
    figures = seal(app, real)
    pathlib.Path(sealed_path).write_text(json.dumps(figures, indent=1) + "\n", newline="\n")
    return figures


def seal(app, real):
    """work_night() with the sheet's bath column replaced by the real baths."""
    import csv
    import shutil
    import tempfile
    room = pathlib.Path(tempfile.mkdtemp())
    try:
        shutil.copytree(app, room / "app")
        path = room / "app" / "bench_sheet.csv"
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            r["bath"] = real[r["chamber"]]
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        figures, _ = ref.work_night(room / "app", believe_sheet=True)
    finally:
        shutil.rmtree(room, ignore_errors=True)
    return {f["fish"]: {"smr": f["smr"], "rmr": f["rmr"]} for f in figures}


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
