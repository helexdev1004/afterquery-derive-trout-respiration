# Overnight respirometry - how a night is worked up

Twenty glass chambers hang in three water baths held at 12, 16 and 20 degrees
Celsius. Each bath has its own chiller, its own thermometer and its own flush
pumps; all the pumps hang off one relay, so every chamber in the
room is flushed and closed at the same moments. One chamber in each bath is run
empty as that bath's blank. A chamber's water is the bath's water: glass walls,
a mixing loop, and the same temperature as the bath around it.

## What a logger holds

Every export has two header lines that begin with `#`, a line of column names,
then one tab-separated line every five seconds: date, time, and the oxygen on
the four channels. The optode software can export oxygen as per cent air
saturation, as oxygen partial pressure in hPa, as oxygen partial pressure in
Torr, or as per cent oxygen. The lab template is per cent air saturation, but
an export comes out in whatever that logger's software was last left on and
the file does not say, so look at the figures before using them. The four are
tied together by

    pO2 [hPa]  = (air saturation / 100) x 0.20946 x (P - pW)
    pO2 [Torr] = pO2 [hPa] x 0.750062
    per cent oxygen = 100 x pO2 [hPa] / P

where P is the barometer's pressure in hPa and pW the vapour pressure of water,

    pW [hPa] = 6.112 x exp(17.62 t / (243.12 + t)),   t in degrees Celsius.

## From air saturation to concentration

Fresh water saturated with air at 1013.25 hPa holds (Benson and Krause 1984)

    ln C* = -135.29996 + 1.572288e5 / T - 6.637149e7 / T^2
            + 1.243678e10 / T^3 - 8.621061e11 / T^4        T in kelvin, C* in umol/kg

and a litre of it weighs

    rho [kg/L] = (999.842594 + 6.793952e-2 t - 9.095290e-3 t^2 + 1.001685e-4 t^3
                  - 1.120083e-6 t^4 + 6.536332e-9 t^5) / 1000.

At pressure P it holds C* x rho x (P - pW) / (1013.25 - pW), and the oxygen in a
chamber is its air saturation over a hundred times that, in umol/L.

The conditions are taken once for each closed phase (see below): t is the mean
of the bath thermometer's readings stamped inside the closed phase, and P is the
barometer's pressure at the middle of it, read along the straight line between
the barometer readings either side. The same t and P serve for turning a
partial pressure or a per cent oxygen into air saturation.

## Closed phases

`relay.log` has a line each time the flush pumps go on or off. A closed phase
starts 60 seconds after a FLUSH OFF, which gives the chamber time to mix, and
ends at the next FLUSH ON; the readings that belong to it are those stamped at
or after its start and before its end. A closed phase shorter than 300 seconds
is not used. The fish need the evening to settle after handling, so a closed
phase that starts before 21:00 is not used either.

## Rates

For each closed phase fit a least-squares straight line to a chamber's oxygen
in umol/L against time; the fall of that line per hour is the chamber's
decline. Walls and water use a little oxygen of their own, so the decline of
the blank in the same bath over the same closed phase is taken off the fish's
chamber. What is left, times the water in the chamber, is what the fish used:

    MO2 [mg O2 / kg / h] = (decline - blank decline) x (V - m) / 1000 x 0.0319988 / (m / 1000)

with V the chamber volume in mL and m the mass of the fish in grams, a gram of
fish displacing a millilitre of water, and 0.0319988 mg in a umol of oxygen.

## The two figures

A fish's routine rate is the mean of its MO2 over the night's closed phases.
Its standard rate is their 0.2 quantile: rank the n values from the lowest,
numbered 0 to n - 1, go to position 0.2 x (n - 1) and take the straight line
between the two values either side of it. Both are given to two decimals.
