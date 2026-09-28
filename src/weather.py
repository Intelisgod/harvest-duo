"""Daily weather. Rain (and storms) auto-water crops; snow falls in winter.

Kinds: sunny, rain, storm (summer/fall: heavy rain + lightning), fog (spring/fall
mornings, clears by noon), windy (spring/fall: blowing petals / leaves), snow
(winter). ``pick`` rolls one for a season; ``valid`` says whether a (pre-rolled)
kind can happen in a season. Visuals live in systems/weather_system.py (Core) and
render_system._draw_weather (rain/snow, UI).
"""
import random

SUNNY = "sunny"
RAIN = "rain"
SNOW = "snow"
STORM = "storm"
FOG = "fog"
WINDY = "windy"
LABEL = {SUNNY: "Sunny", RAIN: "Rainy", SNOW: "Snowy", STORM: "Stormy",
         FOG: "Foggy", WINDY: "Windy"}
ALL = (SUNNY, RAIN, STORM, FOG, WINDY, SNOW)

# season -> [(kind, weight)]; sunny fills the rest. Rain odds stay close to the
# old 32/18/30 % (storm counts as rain for the crops).
_WEIGHTS = {
    "Spring": [(RAIN, 0.28), (FOG, 0.10), (WINDY, 0.12)],
    "Summer": [(RAIN, 0.12), (STORM, 0.08)],
    "Fall":   [(RAIN, 0.20), (STORM, 0.08), (FOG, 0.10), (WINDY, 0.14)],
    "Winter": [(SNOW, 0.40)],
}


def pick(season, rng=random):
    r = rng.random()
    acc = 0.0
    for kind, w in _WEIGHTS.get(season, [(RAIN, 0.2)]):
        acc += w
        if r < acc:
            return kind
    return SUNNY


def valid(kind, season):
    """Can ``kind`` happen in ``season``? (sunny always can)."""
    return kind == SUNNY or any(k == kind for k, _w in _WEIGHTS.get(season, ()))


def waters(w):
    return w in (RAIN, STORM)
