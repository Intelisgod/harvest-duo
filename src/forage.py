"""Seasonal forageables: the catalogue + spawn rules (pure data, no pygame).

Owner: Fishing & Foraging (Chat 3). Registered with ``loot.register_item``
(cat "forage") at import time so labels / sell prices / gallery / quest pools
all pick them up from the single registry. Icons are painted in
``forage_art.py`` and registered from ``systems/forage_system.py``.

Where things grow:
  * land forage   -> forest (6-8/day), meadow (5-7/day), farm edges (2-3/day),
                     the beach headland (0-1/day); by season.
  * beach forage  -> the sand near the tideline (4-6/day), all year, with a
                     little seasonal flavour (nautilus in winter, rainbow shell
                     mostly in summer, urchins in summer/fall).
"""
import random
from . import loot

SEASON_NAMES = ("Spring", "Summer", "Fall", "Winter")

# id: (label, sell, colour, seasons, weight, habitat)
#   habitat: "any" | "woods" (mushrooms: common in the forest, rare elsewhere) |
#            "beach" (tideline only)
FORAGE = {
    # ---- spring ----
    "wild_leek":      ("Wild Leek",       60, (150, 206, 120), ("Spring",), 10, "any"),
    "daffodil":       ("Daffodil",        30, (250, 222, 90),  ("Spring",), 10, "any"),
    "morel":          ("Morel",          150, (186, 146, 100), ("Spring",), 4,  "woods"),
    "dandelion":      ("Dandelion",       40, (250, 206, 64),  ("Spring",), 10, "any"),
    # ---- summer ----
    "spice_berry":    ("Spice Berry",     80, (224, 76, 64),   ("Summer",), 10, "any"),
    "sweet_pea":      ("Sweet Pea",       50, (232, 146, 204), ("Summer",), 10, "any"),
    "wild_grape":     ("Wild Grape",      80, (136, 96, 186),  ("Summer",), 8,  "any"),
    # ---- fall ----
    "blackberry":     ("Blackberry",      25, (92, 58, 120),   ("Fall",),   10, "any"),
    "chanterelle":    ("Chanterelle",    160, (240, 172, 72),  ("Fall",),   4,  "woods"),
    "hazelnut":       ("Hazelnut",        90, (176, 124, 76),  ("Fall",),   8,  "any"),
    "wild_plum":      ("Wild Plum",       80, (156, 84, 156),  ("Fall",),   8,  "any"),
    # ---- winter ----
    "crystal_fruit":  ("Crystal Fruit",  150, (170, 222, 246), ("Winter",), 5,  "any"),
    "holly":          ("Holly",           80, (70, 150, 86),   ("Winter",), 10, "any"),
    "snow_mushroom":  ("Snow Mushroom",   90, (232, 236, 250), ("Winter",), 6,  "woods"),
    # ---- beach (all year; weights nudged per season in BEACH_WEIGHTS) ----
    "clam":           ("Clam",            50, (214, 192, 170), SEASON_NAMES, 10, "beach"),
    "coral":          ("Coral",           80, (250, 132, 122), SEASON_NAMES, 8,  "beach"),
    "sea_urchin":     ("Sea Urchin",     160, (104, 70, 140),  SEASON_NAMES, 3,  "beach"),
    "nautilus_shell": ("Nautilus Shell", 120, (242, 212, 182), SEASON_NAMES, 2,  "beach"),
    "rainbow_shell":  ("Rainbow Shell",  300, (236, 184, 232), SEASON_NAMES, 1,  "beach"),
}

# seasonal flavour for the beach: {id: {season: weight}} overriding FORAGE weight
BEACH_WEIGHTS = {
    "sea_urchin":     {"Summer": 5, "Fall": 5},
    "nautilus_shell": {"Winter": 7},
    "rainbow_shell":  {"Summer": 2},
}

# wild snacks: eat one from the hotbar (action key) for a little energy.
# Shells, coral, flowers and holly are not food.
EDIBLE = {
    "wild_leek": 20, "morel": 30, "dandelion": 12, "spice_berry": 22, "wild_grape": 18,
    "blackberry": 12, "chanterelle": 30, "hazelnut": 20, "wild_plum": 20,
    "crystal_fruit": 40, "snow_mushroom": 24,
}

# area name -> (min, max) spawns per day.  "meadow" only if World built it.
SPAWN_COUNTS = {"forest": (6, 8), "beach": (4, 6), "farm": (2, 3), "meadow": (5, 7)}

for _id, (_lab, _sell, _col, _seas, _w, _hab) in FORAGE.items():
    loot.register_item(_id, _lab, _sell, _col, "forage")


def label(item_id):
    return FORAGE[item_id][0] if item_id in FORAGE else loot.label(item_id)


def is_forage(item_id):
    return item_id in FORAGE


def is_beach(item_id):
    return item_id in FORAGE and FORAGE[item_id][5] == "beach"


def land_items(season):
    """Land forage ids in season, in catalogue order."""
    return [k for k, v in FORAGE.items() if v[5] != "beach" and season in v[3]]


def beach_items():
    return [k for k, v in FORAGE.items() if v[5] == "beach"]


def by_season():
    """[(heading, [ids...])] for the collection page: 4 seasons + beach."""
    out = [(s, land_items(s)) for s in SEASON_NAMES]
    out.append(("Beach", beach_items()))
    return out


def xp_for(item_id):
    """Foraging XP: pricier finds teach you more."""
    sell = FORAGE[item_id][1] if item_id in FORAGE else 40
    return 6 if sell < 70 else 9 if sell < 140 else 14


def _weight(item_id, season, area_name, wet=False):
    lab, sell, col, seas, w, hab = FORAGE[item_id]
    if hab == "beach":
        return BEACH_WEIGHTS.get(item_id, {}).get(season, w)
    if hab == "woods":
        # mushrooms: forest floor lovers, and they pop up after rain
        return w * (2.2 if area_name == "forest" else 0.35) * (2.5 if wet else 1.0)
    return w


def pick(area_name, season, beach=False, rng=random, wet=False):
    """Weighted random forage id for this area/season (None if nothing grows)."""
    pool = beach_items() if beach else land_items(season)
    if not pool:
        return None
    ws = [_weight(i, season, area_name, wet) for i in pool]
    return rng.choices(pool, weights=ws, k=1)[0]


def extra_for_weather(area_name, weather):
    """Rain brings up a few more finds in the woods; storms wash shells ashore."""
    if weather in ("rain", "storm") and area_name in ("forest", "meadow"):
        return 1
    if weather == "storm" and area_name == "beach":
        return 2
    return 0
