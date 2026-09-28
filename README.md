# Work up intermittent-flow respirometry into SMR and RMR

A harbor-format benchmark task, authored for the AfterQuery Experts programme as data
annotation for AI evaluation. Task slug `afterquery/derive-trout-respiration` — **Science / Biology**.

An AI agent gets a container, this brief and nothing else. It works alone for
4 hours. Then a sealed verifier it never sees scores the result `0` or `1`.

## What it asks for

A fish physiology lab has run seventeen juvenile brown trout through a single night of intermittent-flow respirometry, and the night now has to be worked up. The trout had been acclimated to three temperatures, twelve, sixteen and twenty degrees Celsius. Twenty glass chambers were hung in three water baths, with one chamber in each bath left empty as that bath's blank. Five four-channel optode loggers read the oxygen in every chamber every five seconds, while one relay opened and closed the flush pumps on all of them together through the night. What the lab wants out of it is two figures for each fish: its standard metabolic rate and its routine metabolic rate, both in milligrams of oxygen per kilogram per hour.

The full brief is in [`instruction.md`](instruction.md).

| | |
| --- | --- |
| **Deliverable** | `/app/metabolic_rates.json` |
| **Agent budget** | 4 hours (14400s) |
| **Expert estimate** | 4 hours |
| **Machine** | 1 CPU, 2048 MB RAM, 0 GPU |
| **Verifier budget** | 300s |
| **Tags** | `respirometry`, `metabolic-rate`, `oxygen-solubility`, `time-series`, `python` |

## Why it is hard

Who does this: a fish physiologist, or the technician who runs the respirometry room, working a night of intermittent-flow respirometry up into standard and routine metabolic rates for a thermal acclimation study. Where the data comes from: it is synthetic, from a seeded generator shipped in /tests, and it was made truth first. Every chamber's oxygen was stepped second by second from what its fish really used - a resting level, handling stress that dies away over the evening, bouts of activity - in the water of the bath the chamber really hung in, whose chiller cycles about its setpoint.

<details>
<summary>Full note</summary>

The five loggers, three thermometers, the relay and the barometer then wrote down what they saw. The sealed figures are the lab note's own arithmetic on those files with every chamber in its real bath. The routine part of the work is real but findable. Three of the five loggers were left exporting oxygen partial pressure in hPa, partial pressure in Torr and per cent oxygen instead of per cent air saturation, and the files do not say so; the conversions need the vapour pressure of water and the barometer. Solubility comes from the Benson and Krause polynomial and the density of water, closed phases from the relay log with a wait and a minimum length, an extra manual flush in the small hours spoils two of them, the blank of the same bath comes off phase by phase, and the standard rate is a defined quantile. Taking the exports as written gets 3 of 17 fish; undoing the units and believing the bench sheet gets 15. The last 2 fish fail silently. Two chambers - one listed in the 12 degree bath, one in the 20 degree bath - were hung in the 16 degree bath, and the bench sheet was never corrected. Their oxygen is turned into concentration with the wrong bath's temperature and cleared with the wrong bath's blank, which moves both rates by 9 to 11 per cent against a tolerance of 1.5. Nothing in the ordinary working shows it: both fish come out with believable rates for the treatment the sheet gives them, because fish differ by more than that, every line fit is as good as the others, and flushed chambers return to the same range of saturation whichever bath is assumed. What does show it is something the note's arithmetic never forms. A closed chamber's reading breathes with its water temperature, by about two per cent per degree, and each bath's chiller cycles with its own period, so what is left of a trace about its fitted line follows one bath's thermometer and not the others: the bath a chamber hangs in accounts for at least 0.75 of it, any other bath for at most 0.41, and the two misplaced chambers follow the 16 degree bath. Somebody who has watched optode traces wobble with a cycling chiller knows to look; the reporting work does not pass through it. tests/rival_readings.py marks six other ways of working the night up against the sealed figures and asserts that none reaches the pass mark of 16 while the reference gets 17, and that temperature taken moment by moment or at the setpoint, with the right baths, also gets 17, so the pass does not hang on a fine point of method.

</details>

## How it is verified

tests/grader.py reads /app/metabolic_rates.json with the json module and nothing else; the agent's code is never imported or run. The file has to be a list of objects naming each of the seventeen fish exactly once. A fish is right when its smr and its rmr are each within 1.5 per cent of the figures in /tests/sealed.json, and tests/test_night.py passes when no more than one fish is out, so the reward is 1 for sixteen or seventeen right fish and 0 otherwise.

<details>
<summary>Full note</summary>

The 1.5 per cent is several times what separates honest variants of the method - temperature by the moment, by the phase or at the setpoint all agree with the sealed figures far inside it - and a sixth of the smallest error the wrong bath makes, so a correct working cannot fall out and a wrong one cannot fall in. One fish may be out so that a single slip in a long chain of conversions does not decide the reward; the two misplaced chambers are two fish, so believing the sheet still fails. The sealed figures exist only in the verifier image, under /tests with mode 700, which the agent's container never mounts, and /app holds no totals or expected ranges to test an answer against. test.sh writes 0 to /logs/verifier/reward.txt before pytest starts and 1 only after a clean pass; an empty container scores 0, the bench sheet believed scores 0 and the reference scores 1.

</details>

<details>
<summary>Reference approach (spoiler)</summary>

solution/smr_night.py is standard-library Python. It reads the bench sheet, the five exports, the thermometers, the relay log and the barometer, and tells each channel's export unit from the size of its figures. Closed phases run from 60 seconds after a FLUSH OFF to the next FLUSH ON; those under 300 seconds or starting before 21:00 are dropped, which leaves 43. Before any chemistry it decides which bath each chamber hangs in: within every closed phase it takes the chamber's readings about their fitted line and each bath's thermometer about its own line, and asks what share of the chamber's leftover each bath accounts for; the largest share names the bath. That moves chambers R03 and R15 to bath B and leaves the other eighteen where the sheet has them. Each phase then gets its bath's mean temperature and the mid-phase pressure, readings go to air saturation and to umol/L, a least-squares line gives the decline, the same bath's blank comes off, and volume less fish over mass gives MO2. The routine rate is the mean over the 43 phases and the standard rate their 0.2 quantile. In the task's container it scores 17 of 17 in about a second.

</details>

## Layout

```
instruction.md          the brief - the only thing the agent is told
task.toml               artifacts, timeouts, resources, metadata
environment/            Dockerfile and data for the agent's container
solution/solve.sh       reference solution; scores 1 by construction
tests/                  verifier image, grading logic and ground truth
```

## Running it

With [harbor](https://github.com/laude-institute/harbor) installed and Docker running:

```bash
uv tool install harbor

harbor run -p . -a oracle -e docker   # reference solution - must score 1
harbor run -p . -a nop    -e docker   # nothing happens    - must score 0
```

Those two runs are the calibration the bundle has to satisfy: the oracle run substitutes
`solution/solve.sh` for the agent and must score `1`, the nop run does nothing and must
score `0`. Anything in between means the verifier is measuring the wrong thing.

## Reading this

`tests/` and `solution/` hold the answers. To try the task honestly, read only
`instruction.md` and `environment/`.

---

Part of a set of 38 tasks indexed at
[afterquery-data-annotation](https://github.com/helexdev1004/afterquery-data-annotation).
