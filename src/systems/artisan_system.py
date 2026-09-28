"""Artisan machines, fertilizer and buff foods (farm economy extras).

Owner: Farming, Animals & Cooking (Chat 2). See docs/UPGRADE_2026-09.md and
src/systems/hooks.py -- everything here plugs in through hooks, no seam edits.
Rules: no ``__init__``; state is created in ``_on_reset_artisan``.

MACHINES (items ``machine_<name>``, bought in the shop's Farm Supplies section)
  * placed by using the item on free farm ground  -> ``world.farm_objects[(gx,gy)]``
  * face a machine + Action: insert the selected input / collect the product
  * pickaxe on a machine: pick it back up (contents are returned)
  * jobs live in ``self.artisan_jobs`` {"gx|gy": {in,out,qty,mins,days}} and are
    saved under the ``artisan_jobs`` key (farm_objects positions are saved by Core)
FERTILIZER  ``fertilizer`` / ``quality_fertilizer`` used on tilled soil; stored in
  ``self.fert_tiles`` {(area,gx,gy): kind} (saved as "area|x|y"), copied onto the
  Crop (``crop.fert``) so crops.py growth can read it.
BUFF FOODS  cooking.BUFFS -- applied by an ``_on_tool_`` hook that returns False so
  Core's normal eat logic still runs.
"""
import math
import random

import pygame

from ..settings import TILE, AREA_FARM
try:
    from ..settings import AREA_MEADOW
except ImportError:                    # pragma: no cover - older settings
    AREA_MEADOW = "meadow"
from ..world import GRASS, GRASS2, DIRT
from .. import world as _world
from .. import loot, cooking, assets
from ..crops import CROPS, is_fruit, FERTILIZERS

# Short abbreviations ('GtChWhl', 'Fertlzr'), kept LOCAL on purpose: Core's
# inventory.ITEM_LABELS is now a full display-name override table that
# Inventory.label / shop_system.item_label read first, so writing these into it
# leaked the abbreviations into the HUD, seltags and the sell list.
_ITEM_LABELS = {}

# ---------------------------------------------------------------------------
#  REGISTRY
# ---------------------------------------------------------------------------
MACHINES = {
    "machine_preserves_jar": {"label": "Preserves Jar", "price": 450, "short": "PrsvJar",
                              "hint": "a fruit or vegetable",
                              "desc": "Fruit -> jam, veg -> pickles (next morning)"},
    "machine_keg":           {"label": "Keg", "price": 700, "short": "Keg",
                              "hint": "a crop, wild fruit or honey",
                              "desc": "Fruit -> wine (2 days); veg -> juice, honey -> mead (1 day)"},
    "machine_cheese_press":  {"label": "Cheese Press", "price": 800, "short": "ChsPress",
                              "hint": "milk or goat milk",
                              "desc": "Milk -> cheese wheel (~3 hours)"},
    "machine_mayo_machine":  {"label": "Mayo Machine", "price": 600, "short": "MayoMch",
                              "hint": "an egg or duck egg",
                              "desc": "Egg -> mayonnaise (~4 hours)"},
    "machine_bee_house":     {"label": "Bee House", "price": 700, "short": "BeeHse",
                              "hint": None,
                              "desc": "Makes honey every 2 days (flowers nearby = better)"},
}
SUPPLIES = {   # other Farm Supplies items: id -> (label, price)
    "fertilizer": ("Fertilizer (grow faster)", 40),
    "quality_fertilizer": ("Quality Fertilizer (x2)", 90),
}
BEE_DAYS = 2
FLOWER_RADIUS = 4
TOGETHER_CHANCE = 0.35     # collecting while both players are "In Sync" (Core) -> +1

GOODS = {}      # artisan good id -> {"label","sell","color","form"}
GOOD_SOURCE = {}   # artisan good id -> input item id (jam_melon -> melon); animal goods absent

# Inputs for the Preserves Jar / Keg: every crop, plus the forageables that make
# sense (fruit -> jam/wine, mushrooms & leek -> pickles). id -> label/sell/colour.
SOURCES = {}
_FORAGE_FRUIT = ("spice_berry", "wild_grape", "blackberry", "wild_plum", "crystal_fruit")
_FORAGE_VEG = ("wild_leek", "morel", "chanterelle", "snow_mushroom")


def _collect_sources():
    for crop, d in CROPS.items():
        SOURCES[crop] = {"label": crop.replace("_", " ").title(), "sell": d["sell"],
                         "color": d["color"], "fruit": is_fruit(crop), "keg": True}
    try:                                   # Fishing & Foraging's registry (pure data)
        from .. import forage as _fg
        for fid in _FORAGE_FRUIT + _FORAGE_VEG:
            if fid in _fg.FORAGE:
                lab, sell, col = _fg.FORAGE[fid][0], _fg.FORAGE[fid][1], _fg.FORAGE[fid][2]
                SOURCES[fid] = {"label": lab, "sell": sell, "color": col,
                                "fruit": fid in _FORAGE_FRUIT, "keg": fid in _FORAGE_FRUIT}
    except Exception:
        pass


def _reg_good(gid, label, sell, color, form, short, source=None):
    GOODS[gid] = {"label": label, "sell": int(sell), "color": tuple(color), "form": form}
    if source:
        GOOD_SOURCE[gid] = source
    loot.register_item(gid, label, int(sell), color, "artisan")
    _ITEM_LABELS[gid] = short


# Artisan pricing (x = the input's base sell price). The Keg (700g) always pays
# more per item than the Preserves Jar (450g): juice beats pickles by x/2 and is
# also ready next morning; wine is 1.6x the jam price but ages 2 days (~80% of
# the jar's per-day value -- the classic "value per crop vs throughput" choice).
KEG_DAYS = {"wine": 2, "juice": 1, "mead": 1}


def jam_value(x):          # jam / pickles (Preserves Jar, next morning)
    return int(x * 2 + 50)


def wine_value(x):         # Keg, 2 mornings
    return int(x * 3.2 + 80)


def juice_value(x):        # Keg, next morning
    return int(x * 2.5 + 50)


def _reg_source_goods(src, d):
    """Register the jar (+ keg) products of one input; returns the new good ids."""
    nice = d["label"]
    tag = src.replace("_", "")[:3]
    out = []
    if d["fruit"]:
        _reg_good(f"jam_{src}", f"{nice} Jam", jam_value(d["sell"]), d["color"], "jam",
                  "Jam-" + tag, src)
        out.append(f"jam_{src}")
        if d["keg"]:
            _reg_good(f"wine_{src}", f"{nice} Wine", wine_value(d["sell"]), d["color"],
                      "wine", "Wine-" + tag, src)
            out.append(f"wine_{src}")
    else:
        _reg_good(f"pickles_{src}", f"Pickled {nice}", jam_value(d["sell"]), d["color"],
                  "pickles", "Pkl-" + tag, src)
        out.append(f"pickles_{src}")
        if d["keg"]:
            _reg_good(f"juice_{src}", f"{nice} Juice", juice_value(d["sell"]), d["color"],
                      "juice", "Jce-" + tag, src)
            out.append(f"juice_{src}")
    return out


# World's orchard fruit (registered by world_system at ITS import, which may come
# after ours) -> jam / wine too; picked up late by _register_late_sources().
_ORCHARD_FRUIT = ("apple", "persimmon")


def _register_late_sources():
    """Add any orchard fruit that is registered now but was not at import time
    (idempotent; cheap). Returns the newly registered good ids."""
    new = []
    for fid in _ORCHARD_FRUIT:
        if fid in SOURCES or not loot.is_material(fid):
            continue
        m = loot.MATERIALS[fid]
        if int(m.get("sell", 0)) <= 0:
            continue
        SOURCES[fid] = {"label": str(m["label"]).split()[-1], "sell": int(m["sell"]),
                        "color": tuple(m.get("color", (200, 120, 120))),
                        "fruit": True, "keg": True}
        new += _reg_source_goods(fid, SOURCES[fid])
    if new:
        reg = getattr(assets, "register_item_icon", None)
        if reg:
            for gid in new:
                reg(gid, _paint_good(gid))
    return new


def _register_all():
    _collect_sources()
    for src, d in SOURCES.items():
        _reg_source_goods(src, d)
    _reg_good("cheese_wheel", "Cheese Wheel", 230, (246, 208, 96), "cheese", "ChsWhl")
    _reg_good("goat_cheese_wheel", "Goat Cheese Wheel", 340, (244, 236, 208), "goat_cheese", "GtChWhl")
    _reg_good("mayonnaise", "Mayonnaise", 130, (250, 244, 214), "mayo", "Mayo")
    _reg_good("duck_mayonnaise", "Duck Mayonnaise", 190, (226, 238, 204), "mayo", "DkMayo")
    _reg_good("honey", "Honey", 120, (240, 176, 60), "honey", "Honey")
    _reg_good("wildflower_honey", "Wildflower Honey", 180, (246, 150, 96), "honey", "WfHoney")
    _reg_good("mead", "Mead", 300, (236, 180, 80), "wine", "Mead")
    for mid, m in MACHINES.items():
        loot.register_item(mid, m["label"], 0, (170, 130, 90), "machine")
        _ITEM_LABELS[mid] = m["short"]
    loot.register_item("fertilizer", "Fertilizer", 0, (150, 118, 80), "farming")
    loot.register_item("quality_fertilizer", "Quality Fertilizer", 0, (190, 150, 80), "farming")
    _ITEM_LABELS["fertilizer"] = "Fertlzr"
    _ITEM_LABELS["quality_fertilizer"] = "QFertlz"


def machine_recipe(kind, item):
    """What ``kind`` makes from ``item``: (product, qty, minutes, mornings) or None."""
    src = SOURCES.get(item)
    if kind == "machine_preserves_jar" and src:
        return (f"jam_{item}" if src["fruit"] else f"pickles_{item}"), 1, 0, 1
    if kind == "machine_keg" and src and src["keg"]:
        if src["fruit"]:
            return f"wine_{item}", 1, 0, KEG_DAYS["wine"]
        return f"juice_{item}", 1, 0, KEG_DAYS["juice"]
    if kind == "machine_keg" and item in ("honey", "wildflower_honey"):
        return "mead", 1, 0, KEG_DAYS["mead"]
    if kind == "machine_cheese_press":
        if item == "milk":
            return "cheese_wheel", 1, 200, 0
        if item == "goat_milk":
            return "goat_cheese_wheel", 1, 200, 0
    if kind == "machine_mayo_machine":
        if item == "egg":
            return "mayonnaise", 1, 240, 0
        if item == "duck_egg":
            return "duck_mayonnaise", 1, 240, 0
    return None


def good_label(gid):
    return GOODS[gid]["label"] if gid in GOODS else loot.label(gid)


_FENCE = []


def _fence_tiles():
    """World's farm fence frame (walk-over decor -- machines never go on it)."""
    if not _FENCE:
        _FENCE.append(frozenset(getattr(_world, "FARM_FENCE", ()) or ()))
    return _FENCE[0]


def _ks(gx, gy):
    return f"{gx}|{gy}"


def _kp(s):
    a, b = s.split("|")
    return int(a), int(b)


# ---------------------------------------------------------------------------
#  ART  (procedural, cached -- matches the pastel pixel style of assets/)
# ---------------------------------------------------------------------------
_CACHE = {}
_WOOD = (150, 104, 62)
_WOOD_LT = (186, 138, 88)
_WOOD_DK = (104, 70, 42)
_IRON = (96, 100, 112)


def _lt(c, f=1.25):
    return tuple(min(255, int(v * f)) for v in c)


def _dk(c, f=0.72):
    return tuple(max(0, int(v * f)) for v in c)


def _machine_surface(kind, working=False, frame=0, fill=None):
    """48x64 machine sprite (bottom row sits on the tile)."""
    key = ("mach", kind, working, frame, fill)
    s = _CACHE.get(key)
    if s is not None:
        return s
    s = pygame.Surface((TILE, 64), pygame.SRCALPHA)
    # soft ground shadow
    pygame.draw.ellipse(s, (0, 0, 0, 70), (7, 54, 34, 9))
    if kind == "machine_preserves_jar":
        pygame.draw.rect(s, _WOOD_DK, (9, 50, 30, 8), border_radius=2)          # stand
        pygame.draw.rect(s, _WOOD, (9, 49, 30, 5), border_radius=2)
        glass = pygame.Surface((26, 32), pygame.SRCALPHA)
        pygame.draw.rect(glass, (214, 236, 240, 150), (0, 0, 26, 32), border_radius=7)
        if working:
            col = fill or (220, 120, 90)
            lvl = 18 if frame == 0 else 17
            pygame.draw.rect(glass, col + (235,), (2, 32 - lvl - 2, 22, lvl), border_radius=5)
            for bx, by in ((7, 24), (16, 20), (11, 16)):
                pygame.draw.circle(glass, _lt(col, 1.35) + (255,), (bx, by + frame), 1)
        pygame.draw.rect(glass, (160, 190, 200, 255), (0, 0, 26, 32), 2, border_radius=7)
        pygame.draw.line(glass, (250, 255, 255, 200), (5, 5), (5, 22), 2)       # glint
        s.blit(glass, (11, 18))
        pygame.draw.rect(s, (224, 96, 96), (10, 13, 28, 7), border_radius=3)      # cloth lid
        for cx in range(12, 38, 5):
            pygame.draw.rect(s, (250, 236, 226), (cx, 14, 2, 2))
        pygame.draw.line(s, (170, 60, 60), (10, 20), (38, 20), 1)
        pygame.draw.rect(s, (252, 246, 226), (16, 32, 16, 9), border_radius=2)   # label
        pygame.draw.line(s, (200, 170, 120), (19, 36), (29, 36), 1)
    elif kind == "machine_keg":
        body = pygame.Rect(9, 16, 30, 40)
        pygame.draw.ellipse(s, _WOOD_DK, (9, 50, 30, 8))
        pygame.draw.rect(s, _WOOD, body, border_radius=9)
        for sx in (15, 21, 27, 33):                                               # staves
            pygame.draw.line(s, _WOOD_DK, (sx, 18), (sx, 54), 1)
        pygame.draw.line(s, _WOOD_LT, (12, 20), (12, 50), 2)
        for hy in (22, 45):                                                        # iron hoops
            pygame.draw.rect(s, _IRON, (9, hy, 30, 4), border_radius=1)
            pygame.draw.line(s, (150, 156, 168), (10, hy), (38, hy), 1)
        pygame.draw.ellipse(s, _WOOD_LT, (10, 12, 28, 10))                        # top lid
        pygame.draw.ellipse(s, _WOOD_DK, (10, 12, 28, 10), 1)
        pygame.draw.circle(s, _WOOD_DK, (24, 17), 2)
        pygame.draw.rect(s, (200, 200, 208), (20, 34, 8, 4), border_radius=1)     # tap
        pygame.draw.rect(s, (160, 90, 60), (26, 31, 3, 4))
        if working:
            dc = fill or (170, 60, 90)
            pygame.draw.circle(s, dc, (22, 41 + frame * 2), 2)                    # drip
            pygame.draw.circle(s, (120, 220, 120), (33, 29), 2)                   # status light
        else:
            pygame.draw.circle(s, (120, 110, 100), (33, 29), 2)
    elif kind == "machine_cheese_press":
        pygame.draw.rect(s, _WOOD_DK, (7, 50, 34, 7), border_radius=2)            # base
        pygame.draw.rect(s, _WOOD, (7, 48, 34, 5), border_radius=2)
        pygame.draw.rect(s, _WOOD, (9, 14, 5, 36))                                # posts
        pygame.draw.rect(s, _WOOD, (34, 14, 5, 36))
        pygame.draw.rect(s, _WOOD_LT, (7, 11, 34, 6), border_radius=2)            # crossbar
        py = 30 + (2 if (working and frame) else 0)
        pygame.draw.rect(s, (160, 164, 176), (22, 15, 4, py - 15))                # screw
        for yy in range(17, py, 3):
            pygame.draw.line(s, (110, 114, 126), (22, yy), (25, yy + 1), 1)
        pygame.draw.circle(s, (200, 70, 60), (24, 9), 4)                          # crank knob
        pygame.draw.line(s, (120, 120, 130), (14, 9), (34, 9), 2)
        pygame.draw.rect(s, _WOOD_LT, (14, py, 20, 5), border_radius=1)           # press plate
        if working:
            pygame.draw.ellipse(s, (246, 212, 110), (15, py + 6, 18, 11))         # curd wheel
            pygame.draw.ellipse(s, (210, 170, 70), (15, py + 6, 18, 11), 1)
        else:
            pygame.draw.rect(s, (230, 230, 236), (16, 42, 16, 6), border_radius=2)  # empty mould
    elif kind == "machine_mayo_machine":
        pygame.draw.rect(s, (208, 214, 224), (10, 24, 28, 32), border_radius=6)   # steel body
        pygame.draw.rect(s, (150, 156, 170), (10, 24, 28, 32), 2, border_radius=6)
        pygame.draw.line(s, (240, 244, 250), (13, 28), (13, 50), 2)
        pygame.draw.polygon(s, (190, 196, 208), [(14, 12), (34, 12), (29, 24), (19, 24)])  # hopper
        pygame.draw.polygon(s, (140, 146, 160), [(14, 12), (34, 12), (29, 24), (19, 24)], 1)
        pygame.draw.ellipse(s, (250, 246, 232), (19, 6, 10, 12))                  # egg on top
        pygame.draw.rect(s, (60, 64, 76), (16, 33, 16, 10), border_radius=2)      # window
        if working:
            swirl = (250, 240, 196)
            pygame.draw.circle(s, swirl, (24, 38), 4)
            pygame.draw.circle(s, (230, 214, 150), (22 + frame * 3, 37), 2)
        led = (120, 230, 130) if working else (230, 110, 100)
        pygame.draw.circle(s, led, (32, 48), 2)
        ang = 0.6 if frame else -0.6                                              # crank
        ex, ey = 38 + int(math.cos(ang) * 6), 36 + int(math.sin(ang) * 6)
        pygame.draw.line(s, (120, 120, 130), (38, 36), (ex, ey), 2)
        pygame.draw.circle(s, (200, 70, 60), (ex, ey), 2)
    elif kind == "machine_bee_house":
        pygame.draw.rect(s, _WOOD_DK, (13, 44, 3, 13))                             # legs
        pygame.draw.rect(s, _WOOD_DK, (32, 44, 3, 13))
        pygame.draw.rect(s, (236, 206, 120), (10, 22, 28, 24), border_radius=3)   # hive box
        pygame.draw.rect(s, (186, 150, 70), (10, 22, 28, 24), 2, border_radius=3)
        pygame.draw.line(s, (200, 166, 86), (11, 33), (37, 33), 1)
        pygame.draw.polygon(s, (188, 92, 70), [(6, 23), (24, 9), (42, 23)])       # roof
        pygame.draw.polygon(s, (140, 64, 50), [(6, 23), (24, 9), (42, 23)], 2)
        pygame.draw.line(s, (220, 130, 104), (12, 21), (24, 12), 1)
        pygame.draw.ellipse(s, (70, 48, 30), (20, 37, 8, 5))                      # entrance
        pygame.draw.rect(s, (200, 166, 86), (18, 42, 12, 2))                      # landing board
        for hx, hy in ((15, 26), (31, 27)):                                       # comb dots
            pygame.draw.circle(s, (246, 222, 150), (hx, hy), 2)
    _CACHE[key] = s
    return s


def _machine_icon_painter(kind):
    def paint(s):
        spr = _machine_surface(kind)
        sm = pygame.transform.scale(spr.subsurface((4, 4, 40, 56)), (18, 26))
        s.blit(sm, (5, 1))
    return paint


def _paint_good(gid):
    g = GOODS[gid]
    col, form = g["color"], g["form"]

    def paint(s):
        if form in ("jam", "pickles", "mayo", "honey"):
            glass = (214, 234, 240)
            pygame.draw.rect(s, glass, (7, 9, 14, 16), border_radius=4)            # jar
            if form == "jam":
                inside = _dk(col, 0.85)
            elif form == "pickles":
                inside = (176, 196, 120)
            elif form == "mayo":
                inside = col
            else:
                inside = col
            pygame.draw.rect(s, inside, (8, 12, 12, 12), border_radius=3)
            if form == "pickles":
                for px, py in ((11, 16), (16, 19), (12, 21)):
                    pygame.draw.circle(s, col, (px, py), 2)
            if form == "honey":
                pygame.draw.circle(s, _lt(col, 1.3), (11, 15), 2)
            pygame.draw.rect(s, (150, 176, 186), (7, 9, 14, 16), 1, border_radius=4)
            pygame.draw.line(s, (250, 255, 255), (9, 13), (9, 20), 1)              # glint
            lid = {"jam": _lt(col, 1.15), "pickles": (120, 150, 90),
                   "mayo": (250, 216, 90) if gid == "mayonnaise" else (140, 196, 140),
                   "honey": (190, 120, 60)}[form]
            pygame.draw.rect(s, lid, (6, 5, 16, 5), border_radius=2)
            pygame.draw.rect(s, _dk(lid, 0.75), (6, 5, 16, 5), 1, border_radius=2)
            if form == "jam":                                                      # gingham dots
                for dx in (8, 12, 16, 20):
                    s.set_at((dx, 7), (255, 250, 245))
            if gid == "wildflower_honey":
                for ang in range(0, 360, 72):
                    a = math.radians(ang)
                    pygame.draw.circle(s, (250, 150, 190),
                                       (int(21 + math.cos(a) * 2), int(6 + math.sin(a) * 2)), 2)
                pygame.draw.circle(s, (255, 226, 110), (21, 6), 1)
            if form == "honey":                                                    # drip
                pygame.draw.line(s, col, (10, 10), (10, 13), 2)
        elif form == "wine":
            body = _dk(col, 0.6)
            pygame.draw.rect(s, body, (9, 11, 10, 15), border_radius=3)
            pygame.draw.rect(s, body, (12, 4, 4, 8))
            pygame.draw.rect(s, (170, 120, 80), (12, 2, 4, 3))                     # cork
            pygame.draw.rect(s, (246, 236, 210), (10, 16, 8, 6))                   # label
            pygame.draw.rect(s, _lt(col, 1.1), (11, 18, 6, 2))
            pygame.draw.line(s, _lt(body, 1.6), (10, 12), (10, 23), 1)
        elif form == "juice":
            pygame.draw.rect(s, (236, 244, 246), (8, 8, 12, 17), border_radius=3)
            pygame.draw.rect(s, _lt(col, 1.1), (9, 12, 10, 12), border_radius=2)
            pygame.draw.rect(s, (150, 176, 186), (8, 8, 12, 17), 1, border_radius=3)
            pygame.draw.line(s, (236, 110, 120), (17, 3), (15, 14), 2)             # straw
            pygame.draw.circle(s, (110, 180, 90), (11, 11), 2)                     # leaf
        elif form == "cheese":
            pygame.draw.polygon(s, col, [(4, 20), (24, 12), (24, 22), (4, 25)])
            pygame.draw.polygon(s, _lt(col, 1.12), [(4, 20), (24, 12), (19, 10), (4, 16)])
            pygame.draw.polygon(s, _dk(col, 0.8), [(4, 20), (24, 12), (24, 22), (4, 25)], 1)
            for hx, hy in ((10, 21), (17, 18), (20, 21)):
                pygame.draw.circle(s, _dk(col, 0.82), (hx, hy), 1)
        elif form == "goat_cheese":
            pygame.draw.ellipse(s, col, (4, 10, 20, 14))
            pygame.draw.ellipse(s, _dk(col, 0.82), (4, 10, 20, 14), 1)
            pygame.draw.ellipse(s, (255, 252, 240), (7, 11, 12, 5))
            for hx, hy in ((9, 18), (15, 19), (19, 16), (12, 15)):
                s.set_at((hx, hy), (110, 160, 90))
    return paint


def _paint_fertilizer(quality):
    def paint(s):
        sack = (196, 164, 116) if not quality else (214, 186, 120)
        pygame.draw.polygon(s, sack, [(7, 9), (21, 9), (23, 25), (5, 25)])
        pygame.draw.polygon(s, _dk(sack, 0.7), [(7, 9), (21, 9), (23, 25), (5, 25)], 1)
        pygame.draw.rect(s, _dk(sack, 0.8), (9, 6, 10, 4), border_radius=1)       # tied neck
        pygame.draw.line(s, (120, 80, 50), (8, 10), (20, 10), 1)
        pygame.draw.ellipse(s, (104, 172, 84), (10, 14, 8, 6))                    # leaf badge
        pygame.draw.line(s, (70, 130, 60), (11, 19), (16, 15), 1)
        if quality:
            c = (250, 214, 90)
            pts = []
            for i in range(10):
                a = -math.pi / 2 + i * math.pi / 5
                r = 4 if i % 2 == 0 else 2
                pts.append((20 + math.cos(a) * r, 21 + math.sin(a) * r))
            pygame.draw.polygon(s, c, pts)
    return paint


def _paint_food(food):
    """Icons for the buff dishes (cooking.BUFFS)."""
    def plate(s, rim=(236, 236, 242)):
        pygame.draw.ellipse(s, rim, (3, 14, 22, 11))
        pygame.draw.ellipse(s, _dk(rim, 0.85), (3, 14, 22, 11), 1)

    def bowl(s, soup):
        pygame.draw.ellipse(s, (232, 232, 238), (4, 11, 20, 13))
        pygame.draw.rect(s, (232, 232, 238), (6, 17, 16, 6), border_radius=3)
        pygame.draw.ellipse(s, soup, (6, 12, 16, 7))
        pygame.draw.ellipse(s, (190, 190, 200), (4, 11, 20, 13), 1)

    def steam(s):
        for sx in (10, 15):
            pygame.draw.arc(s, (240, 240, 250), (sx, 2, 4, 8), 1.2, 4.6, 1)

    def paint(s):
        if food == "spicy_curry":
            bowl(s, (214, 116, 46))
            pygame.draw.circle(s, (250, 248, 240), (10, 14), 3)                 # rice
            for px, py in ((16, 14), (18, 16), (13, 16)):
                pygame.draw.circle(s, (220, 50, 40), (px, py), 1)
            steam(s)
        elif food == "lucky_dumplings":
            plate(s)
            for dx in (6, 12, 17):
                pygame.draw.ellipse(s, (248, 238, 214), (dx, 12, 8, 7))
                pygame.draw.line(s, (214, 196, 160), (dx + 2, 13), (dx + 6, 13), 1)
            pygame.draw.circle(s, (100, 190, 100), (22, 11), 2)                  # clover
            pygame.draw.circle(s, (100, 190, 100), (24, 12), 2)
        elif food == "miners_pie":
            plate(s)
            pygame.draw.ellipse(s, (214, 160, 84), (5, 11, 18, 10))
            for lx in (9, 13, 17):
                pygame.draw.line(s, (168, 110, 54), (lx, 12), (lx, 20), 1)
            pygame.draw.line(s, (168, 110, 54), (6, 16), (22, 16), 1)
            pygame.draw.circle(s, (205, 120, 70), (20, 12), 2)                   # copper nugget
        elif food == "sushi_roll":
            plate(s, (70, 60, 56))
            for dx in (8, 14, 20):
                pygame.draw.circle(s, (40, 70, 50), (dx, 16), 4)
                pygame.draw.circle(s, (250, 250, 246), (dx, 16), 3)
                pygame.draw.circle(s, (240, 130, 110), (dx, 16), 1)
        elif food == "farmers_lunch":
            plate(s)
            pygame.draw.ellipse(s, (252, 250, 244), (5, 13, 10, 7))              # egg
            pygame.draw.circle(s, (250, 200, 70), (10, 16), 2)
            pygame.draw.polygon(s, (220, 206, 150), [(15, 13), (22, 15), (16, 20)])  # parsnip
            pygame.draw.line(s, (100, 170, 80), (21, 14), (24, 11), 2)
        elif food == "hero_stew":
            bowl(s, (150, 70, 50))
            pygame.draw.rect(s, (190, 110, 80), (9, 13, 4, 3))
            pygame.draw.rect(s, (236, 150, 60), (15, 14, 4, 3))
            pygame.draw.line(s, (210, 214, 224), (19, 4), (23, 12), 2)            # tiny sword
            pygame.draw.line(s, (200, 170, 80), (18, 8), (22, 6), 2)
        elif food == "yam_porridge":
            bowl(s, (232, 220, 238))
            for px, py in ((10, 14), (15, 15), (18, 13)):
                pygame.draw.circle(s, (170, 130, 200), (px, py), 1)
            steam(s)
        elif food == "honey_tea":
            pygame.draw.rect(s, (240, 240, 245), (7, 9, 12, 14), border_radius=2)
            pygame.draw.rect(s, (230, 170, 70), (8, 11, 10, 6))
            pygame.draw.arc(s, (240, 240, 245), (16, 11, 7, 9), -1.2, 1.2, 2)
            pygame.draw.line(s, (170, 110, 60), (19, 3), (15, 12), 2)            # honey dipper
            pygame.draw.circle(s, (236, 180, 70), (19, 4), 2)
            steam(s)
        # ---- forage dishes (cooking.FORAGE_DISHES) ----
        elif food == "wild_salad":
            bowl(s, (126, 190, 96))
            for px, py, c in ((9, 14, (170, 222, 130)), (14, 13, (96, 160, 80)),
                              (18, 15, (150, 206, 120)), (12, 16, (110, 176, 90))):
                pygame.draw.ellipse(s, c, (px - 2, py - 1, 5, 3))                # leaves
            pygame.draw.circle(s, (250, 206, 64), (17, 13), 2)                   # dandelion
            pygame.draw.circle(s, (255, 236, 140), (17, 13), 1)
        elif food == "berry_tart":
            plate(s)
            pygame.draw.ellipse(s, (214, 164, 96), (5, 11, 18, 10))              # crust
            pygame.draw.ellipse(s, (120, 60, 120), (7, 12, 14, 7))               # filling
            for px, py in ((10, 14), (14, 13), (17, 15), (12, 16), (16, 17)):
                pygame.draw.circle(s, (70, 40, 90), (px, py), 1)                 # berries
            pygame.draw.circle(s, (150, 210, 110), (20, 11), 1)                  # mint leaf
        elif food == "hazelnut_cookies":
            plate(s)
            for cx, cy in ((9, 16), (15, 14), (19, 17)):
                pygame.draw.circle(s, (214, 164, 100), (cx, cy), 4)
                pygame.draw.circle(s, (176, 124, 76), (cx, cy), 4, 1)
                pygame.draw.circle(s, (120, 80, 50), (cx - 1, cy - 1), 1)        # nut bits
                pygame.draw.circle(s, (120, 80, 50), (cx + 1, cy + 1), 1)
        elif food == "mushroom_soup":
            bowl(s, (206, 170, 110))
            pygame.draw.ellipse(s, (240, 172, 72), (9, 12, 6, 3))                # chanterelle caps
            pygame.draw.ellipse(s, (226, 150, 60), (15, 13, 5, 3))
            pygame.draw.line(s, (120, 170, 90), (12, 16), (15, 16), 1)           # herbs
            steam(s)
    return paint


def _register_icons():
    reg = getattr(assets, "register_item_icon", None)
    if not reg:
        return
    for mid in MACHINES:
        reg(mid, _machine_icon_painter(mid))
    for gid in GOODS:
        reg(gid, _paint_good(gid))
    reg("fertilizer", _paint_fertilizer(False))
    reg("quality_fertilizer", _paint_fertilizer(True))
    for fid in dict.fromkeys(list(getattr(cooking, "BUFFS", {}))
                             + list(getattr(cooking, "FORAGE_DISHES", ()))):
        reg(fid, _paint_food(fid))


_register_all()
_register_icons()
_register_late_sources()


def _ready_bubble(product):
    key = ("bubble", product)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((32, 36), pygame.SRCALPHA)
        pygame.draw.rect(s, (255, 252, 244), (1, 1, 30, 28), border_radius=9)
        pygame.draw.polygon(s, (255, 252, 244), [(12, 28), (20, 28), (16, 34)])
        pygame.draw.rect(s, (200, 170, 120), (1, 1, 30, 28), 2, border_radius=9)
        pygame.draw.line(s, (200, 170, 120), (12, 29), (16, 34), 2)
        pygame.draw.line(s, (200, 170, 120), (20, 29), (16, 34), 2)
        try:
            ic = assets.item_icon(product)
            s.blit(pygame.transform.scale(ic, (24, 24)), (4, 3))
        except Exception:
            pass
        _CACHE[key] = s
    return s


def _speckle(kind):
    key = ("speck", kind)
    s = _CACHE.get(key)
    if s is None:
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        rng = random.Random(7 if kind == "fertilizer" else 11)
        dot = (238, 226, 200, 190) if kind == "fertilizer" else (250, 214, 110, 200)
        def edge_pt():                 # keep to the soil rim, clear of the crop sprite
            while True:
                x, y = rng.randint(5, TILE - 7), rng.randint(5, TILE - 7)
                if abs(x - TILE // 2) > 10 or abs(y - TILE // 2) > 10:
                    return x, y
        for _ in range(14):
            x, y = edge_pt()
            pygame.draw.rect(s, dot, (x, y, 2, 2))
        if kind == "quality_fertilizer":
            for _ in range(5):
                x, y = edge_pt()
                pygame.draw.rect(s, (255, 250, 220, 230), (x, y, 1, 1))
        _CACHE[key] = s
    return s


class _Bees:
    """Tiny bees buzzing around a bee house (drawn per frame -- 3 circles)."""
    __slots__ = ("wx", "wy", "t")

    def __init__(self, wx, wy, t):
        self.wx, self.wy, self.t = wx, wy, t

    def draw(self, screen, cam):
        for i in range(3):
            a = self.t * (2.2 + i * 0.7) + i * 2.1
            x = int(self.wx - cam.x + math.cos(a) * (12 + i * 3))
            y = int(self.wy - cam.y + math.sin(a * 1.3) * 7 - 4 * i)
            pygame.draw.circle(screen, (250, 214, 70), (x, y), 2)
            screen.set_at((x, y), (60, 44, 30))
            pygame.draw.circle(screen, (235, 245, 255), (x - 1, y - 2), 1)


# ---------------------------------------------------------------------------
#  MIXIN
# ---------------------------------------------------------------------------
class ArtisanMixin:
    """Artisan machines, fertilizer and buff foods."""

    # ---- lifecycle ----
    def _on_reset_artisan(self):
        _register_late_sources()      # orchard fruit (World) -> jam / wine
        self.artisan_jobs = {}        # "gx|gy" -> {"in","out","qty","mins","days"}
        self.fert_tiles = {}          # (area, gx, gy) -> fertilizer item id
        self.artisan_made = {}        # artisan good id -> how many ever collected
        self._art_fx_t = 0.0
        self._art_hop = {}            # (gx, gy) -> seconds left of a little "hop"
        self._art_sync_t = 0.0
        self._art_last_min = None

    def _on_save_artisan(self):
        jobs = {k: {"in": v.get("in"), "out": v.get("out"), "qty": int(v.get("qty", 1)),
                    "mins": int(v.get("mins", 0)), "days": int(v.get("days", 0))}
                for k, v in sorted(self.artisan_jobs.items())}
        fert = {f"{k[0]}|{k[1]}|{k[2]}": kind for k, kind in sorted(self.fert_tiles.items())}
        return {"artisan_jobs": jobs, "fert_tiles": fert,
                "artisan_made": {k: int(v) for k, v in sorted(self.artisan_made.items())}}

    def _on_load_artisan(self, d):
        self.artisan_jobs = {}
        for k, v in (d.get("artisan_jobs") or {}).items():
            if isinstance(v, dict) and v.get("out"):
                self.artisan_jobs[k] = {"in": v.get("in"), "out": v["out"],
                                        "qty": int(v.get("qty", 1)),
                                        "mins": int(v.get("mins", 0)),
                                        "days": int(v.get("days", 0))}
        self.fert_tiles = {}
        for k, kind in (d.get("fert_tiles") or {}).items():
            try:
                a, x, y = k.split("|")
                if kind in FERTILIZERS:
                    self.fert_tiles[(a, int(x), int(y))] = kind
            except ValueError:
                continue
        self.artisan_made = {k: int(v) for k, v in (d.get("artisan_made") or {}).items()
                             if isinstance(v, (int, float))}
        self._art_sync_solids()
        self._art_sync_fert()

    def _on_area_enter_artisan(self):
        self._art_sync_solids()

    # ---- helpers ----
    def _art_machines(self):
        """[(gx, gy, kind)] of every artisan machine on the farm."""
        return [(gx, gy, k) for (gx, gy), k in self.world.farm_objects.items()
                if isinstance(k, str) and k in MACHINES]

    def _art_sync_solids(self):
        farm = self.world.areas.get(AREA_FARM) if hasattr(self.world, "areas") else None
        if farm is None:
            return
        for gx, gy, _k in self._art_machines():
            farm.solid_extra.add((gx, gy))

    def _art_sync_fert(self):
        crops = self.world.crops
        tilled = self.world.tilled
        for key in list(self.fert_tiles):
            if key not in tilled:               # soil filled back in / single harvest done
                del self.fert_tiles[key]
                continue
            c = crops.get(key)
            if c is not None and getattr(c, "fert", None) != self.fert_tiles[key]:
                c.fert = self.fert_tiles[key]

    def _art_ready(self, job):
        return job is not None and job.get("mins", 0) <= 0 and job.get("days", 0) <= 0

    def _art_near_flowers(self, gx, gy):
        farm = self.world.areas.get(AREA_FARM)
        r = FLOWER_RADIUS
        for pr in getattr(farm, "props", []) or []:
            try:
                kind, px, py = pr[0], pr[1], pr[2]
            except Exception:
                continue
            if "flower" in str(kind) and abs(px - gx) <= r and abs(py - gy) <= r:
                return True
        for (ox, oy), k in self.world.farm_objects.items():
            if isinstance(k, str) and "flower" in k and abs(ox - gx) <= r and abs(oy - gy) <= r:
                return True
        for (a, cx, cy), c in self.world.crops.items():
            if a == AREA_FARM and c.name in ("crocus",) and abs(cx - gx) <= r and abs(cy - gy) <= r:
                return True
        for w in getattr(farm, "warps", []) or []:      # bees fly to the Flower Meadow
            near = (abs(w.get("gx", -99) - gx) <= r + 3 and abs(w.get("gy", -99) - gy) <= r + 3)
            if w.get("to") == AREA_MEADOW and near:
                return True
        return False

    def _art_start_bees(self, gx, gy):
        self.artisan_jobs[_ks(gx, gy)] = {"in": None, "out": "honey", "qty": 1,
                                         "mins": 0, "days": BEE_DAYS}

    def _art_center(self, gx, gy):
        return gx * TILE + TILE / 2, gy * TILE + TILE / 2

    _ART_POP_KEEP = 2          # at most this many machine status popups at once

    def _art_popup(self, wx, wy, text, color):
        """Machine status popup: goes through the shared ``_popup`` list but
        only the newest few machine popups stay (tapping a row of machines no
        longer piles their texts into one smear)."""
        pops = getattr(self, "popups", None)
        mine = [pu for pu in self.__dict__.get("_art_pops", []) if pops is not None
                and any(pu is q for q in pops) and pu[4] > 0]
        while len(mine) >= self._ART_POP_KEEP:          # drop the oldest
            old = mine.pop(0)
            if pops is not None:
                for i, q in enumerate(pops):
                    if q is old:
                        del pops[i]
                        break
        self._popup(wx, wy, text, color)        # (the shared pass spreads overlaps)
        if pops is not None and pops and pops[-1][2] == text:
            mine.append(pops[-1])
        self._art_pops = mine

    # ---- time ----
    def _on_update_artisan(self, dt):
        # game-minute ticks for hour-based machines (cheese / mayo)
        cur = self.time.minutes
        last = self._art_last_min
        self._art_last_min = cur
        if last is not None and cur > last and self.artisan_jobs:
            delta = cur - last
            for k, job in self.artisan_jobs.items():
                if job.get("mins", 0) > 0:
                    job["mins"] = max(0, job["mins"] - delta)
                    if self._art_ready(job) and self.world.current == AREA_FARM:
                        gx, gy = _kp(k)
                        wx, wy = self._art_center(gx, gy)
                        self.parts.sparkle(wx, wy - 40, n=10, color=(255, 236, 170))
                        self.audio.play("bell")
        self._art_sync_fert()
        if self._art_hop:
            for k in list(self._art_hop):
                self._art_hop[k] -= dt
                if self._art_hop[k] <= 0:
                    del self._art_hop[k]
        self._art_sync_t -= dt
        if self._art_sync_t <= 0:
            self._art_sync_t = 1.0
            self._art_sync_solids()
        if self.world.current != AREA_FARM:
            return
        # working puffs / bubbles (throttled)
        self._art_fx_t -= dt
        if self._art_fx_t > 0:
            return
        self._art_fx_t = 0.45
        for gx, gy, kind in self._art_machines():
            job = self.artisan_jobs.get(_ks(gx, gy))
            if not job or self._art_ready(job) or random.random() < 0.35:
                continue
            wx, wy = self._art_center(gx, gy)
            if kind == "machine_keg":
                self.parts.bubble(wx + random.uniform(-6, 6), wy - 34, n=1,
                                  color=_lt(SOURCES.get(job.get("in"), {}).get("color", (200, 120, 140))))
            elif kind == "machine_preserves_jar":
                self.parts.bubble(wx + random.uniform(-5, 5), wy - 22, n=1, color=(236, 244, 250))
            elif kind in ("machine_cheese_press", "machine_mayo_machine"):
                self.parts.smoke(wx + random.uniform(-4, 4), wy - 44, n=1, color=(236, 236, 242))

    def _on_new_day_artisan(self):
        finished = 0
        live = {_ks(gx, gy): kind for gx, gy, kind in self._art_machines()}
        for k in list(self.artisan_jobs):
            if k not in live:                      # machine vanished -> drop its job
                del self.artisan_jobs[k]
                continue
            job = self.artisan_jobs[k]
            was = self._art_ready(job)
            job["mins"] = 0                         # overnight finishes hour-based jobs
            job["days"] = max(0, job.get("days", 0) - 1)
            if not was and self._art_ready(job):
                finished += 1
                if live[k] == "machine_bee_house":
                    gx, gy = _kp(k)
                    job["out"] = "wildflower_honey" if self._art_near_flowers(gx, gy) else "honey"
        for k, kind in live.items():                # bee houses always work
            if kind == "machine_bee_house" and k not in self.artisan_jobs:
                self._art_start_bees(*_kp(k))
        if finished:
            self.ui.log(f"Your artisan machines finished {finished} batch"
                        f"{'es' if finished != 1 else ''} overnight!")

    # ---- interaction ----
    def _interact_early_40_artisan_machine(self, idx, p):
        if self.world.current != AREA_FARM:
            return False
        tx, ty = p.target_tile()
        kind = self.world.farm_objects.get((tx, ty))
        if kind not in MACHINES:
            # holding a machine and facing free ground: place it here (before the
            # shipping-bin / NPC branches can swallow the press)
            sel = p.inv.selected_entry()
            holding = bool(sel) and sel[0] == "item" and sel[1] in MACHINES
            if holding and self._art_place_ok(self.world.area, tx, ty):
                return self._on_tool_artisan_use(idx, p, sel[1], tx, ty)
            return False
        sel = p.inv.selected_entry()
        k = _ks(tx, ty)
        job = self.artisan_jobs.get(k)
        wx, wy = self._art_center(tx, ty)
        m = MACHINES[kind]
        if sel and sel[1] == "pickaxe":
            self._art_pickup(p, tx, ty, kind)
            return True
        if job and self._art_ready(job):
            out, qty = job["out"], int(job.get("qty", 1))
            together = bool(getattr(self, "in_sync", False)) and random.random() < TOGETHER_CHANCE
            if together:                              # the two of you, side by side
                qty += 1
                self._popup(wx, wy - 72, "Made together! +1", (255, 170, 200))
                hb = getattr(self.parts, "heart_burst", None)
                if hb:
                    hb(wx, wy - 40, n=10)
            p.inv.add(out, qty)
            self.parts.sparkle(wx, wy - 36, n=14, color=(255, 232, 160))
            sb = getattr(self.parts, "star_burst", None)
            if sb:
                sb(wx, wy - 40, color=GOODS.get(out, {}).get("color", (255, 226, 120)), n=6)
            self.audio.play("harvest")
            self._art_popup(wx, wy - 56, f"+{qty} {good_label(out)}", (255, 232, 160))
            self.ui.log(f"{p.name} collected {qty} {good_label(out)} from the {m['label']}.")
            try:
                self._grant_xp(p, "farming", 4)
            except Exception:
                pass
            first = out not in self.artisan_made
            self.artisan_made[out] = self.artisan_made.get(out, 0) + qty
            if first:
                self.toast("New artisan good!", f"{good_label(out)}  -  sells for "
                           f"{loot.sell_value(out)}g", icon=out, color=(255, 214, 140))
            self._art_hop[(tx, ty)] = 0.3
            self.emit("crafted", p=p, what=out, machine=kind)
            if kind == "machine_bee_house":
                self._art_start_bees(tx, ty)
            else:
                del self.artisan_jobs[k]
            return True
        if job:
            if job.get("days", 0) > 0:
                d = job["days"]
                left = "tomorrow" if d == 1 else f"in {d} days"
            else:
                mins = int(job.get("mins", 0))
                left = f"in {mins // 60}h {mins % 60:02d}m" if mins >= 60 else f"in {mins}m"
            self._art_popup(wx, wy - 56, f"{good_label(job['out'])} {left}", (220, 226, 240))
            self.audio.play("ui_move")
            return True
        item = sel[1] if sel and sel[0] == "item" else None
        rec = machine_recipe(kind, item) if item else None
        if rec:
            out, qty, mins, days = rec
            p.inv.remove(item, 1)
            self.artisan_jobs[k] = {"in": item, "out": out, "qty": qty,
                                    "mins": int(mins), "days": int(days)}
            p.trigger_item_use(item, "place", 0.45)
            self._art_hop[(tx, ty)] = 0.3
            self.parts.dust(wx, wy - 20, n=5, color=(236, 226, 206))
            ring = getattr(self.parts, "ring", None)
            if ring:
                ring(wx, wy - 24, color=(255, 240, 200), radius=14)
            self.audio.play("plant")
            when = "tomorrow" if days == 1 else f"in {days} days" if days else f"in ~{mins // 60}h"
            self._art_popup(wx, wy - 56, f"{good_label(out)} {when}", (200, 240, 200))
            self.ui.log(f"{p.name} put {SOURCES[item]['label'] if item in SOURCES else loot.label(item)}"
                        f" in the {m['label']}: {good_label(out)} ready {when}.")
            return True
        if kind == "machine_bee_house":
            self._art_popup(wx, wy - 56, "The bees are busy...", (250, 220, 120))
        else:
            self._art_popup(wx, wy - 56, f"Needs {m['hint']}", (230, 200, 190))
        self.audio.play("ui_move")
        return True

    def _art_pickup(self, p, gx, gy, kind):
        k = _ks(gx, gy)
        job = self.artisan_jobs.pop(k, None)
        self.world.farm_objects.pop((gx, gy), None)
        farm = self.world.areas.get(AREA_FARM)
        if farm is not None:
            farm.solid_extra.discard((gx, gy))
        p.inv.add(kind, 1)
        if job:
            if self._art_ready(job):
                p.inv.add(job["out"], int(job.get("qty", 1)))
            elif job.get("in"):
                p.inv.add(job["in"], 1)                  # unfinished: hand the input back
        wx, wy = self._art_center(gx, gy)
        self.parts.chips(wx, wy - 10, color=_WOOD)
        poof = getattr(self.parts, "poof", None)
        if poof:
            poof(wx, wy - 16)
        self.audio.play("mine")
        self.add_shake(1)
        self.ui.log(f"Picked up the {MACHINES[kind]['label']}.")

    def _art_place_ok(self, area, gx, gy):
        if area.name != AREA_FARM:
            return False
        if area.tile(gx, gy) not in (GRASS, GRASS2, DIRT) or area.is_solid(gx, gy):
            return False
        key = (AREA_FARM, gx, gy)
        if (gx, gy) in self.world.farm_objects or key in self.world.tilled or key in self.world.crops:
            return False
        for pl in self.players:
            if (int(pl.x // TILE), int(pl.y // TILE)) == (gx, gy):
                return False
        for w in getattr(area, "warps", []) or []:
            if (w.get("gx"), w.get("gy")) == (gx, gy):
                return False
        for pr in getattr(area, "props", []) or []:
            try:
                if (pr[1], pr[2]) == (gx, gy):
                    return False
            except Exception:
                continue
        if (gx, gy) in _fence_tiles():                 # World's walk-over fence frame
            return False
        fs = getattr(self, "forage_spawns", None)      # don't bury a forageable
        if isinstance(fs, dict) and (gx, gy) in (fs.get(AREA_FARM) or {}):
            return False
        for v in vars(area).values():                  # interaction points (bin, bed...)
            if isinstance(v, tuple) and v == (gx, gy):
                return False
        return True

    def _on_tool_artisan_use(self, idx, p, tool, gx, gy):
        entry = p.inv.selected_entry()
        if not entry or entry[0] != "item":
            return False
        name = entry[1]
        # --- place a machine ---
        if name in MACHINES:
            area = self.world.area
            if self._art_place_ok(area, gx, gy):
                self.world.farm_objects[(gx, gy)] = name
                area.solid_extra.add((gx, gy))
                self._art_hop[(gx, gy)] = 0.3
                p.inv.remove(name, 1)
                p.trigger_item_use(name, "place", 0.5)
                wx, wy = self._art_center(gx, gy)
                self.parts.dust(wx, wy + 8, n=8)
                self.parts.sparkle(wx, wy - 20, n=8, color=(255, 236, 190))
                self.audio.play("ui_select")
                if name == "machine_bee_house":
                    self._art_start_bees(gx, gy)
                    self.ui.log("Placed a Bee House. Honey every 2 days (flowers nearby = wildflower honey!).")
                else:
                    self.ui.log(f"Placed a {MACHINES[name]['label']}. Face it and press Action "
                                f"holding {MACHINES[name]['hint']}.")
            else:
                self.ui.log("Place machines on open farm grass (not soil, paths or objects).")
                self.audio.play("ui_move")
            return True
        # --- fertilize tilled soil ---
        if name in FERTILIZERS:
            area = self.world.area
            key = (area.name, gx, gy)
            if key not in self.world.tilled:
                self.ui.log("Use fertilizer on tilled soil.")
                self.audio.play("ui_move")
                return True
            if self.fert_tiles.get(key) == name:
                self.ui.log("This soil is already fertilized.")
                return True
            self.fert_tiles[key] = name
            c = self.world.crops.get(key)
            if c is not None:
                c.fert = name
            p.inv.remove(name, 1)
            p.trigger_item_use(name, "sow", 0.45)
            wx, wy = self._art_center(gx, gy)
            col = (238, 226, 200) if name == "fertilizer" else (250, 214, 110)
            self.parts.dust(wx, wy, n=6, color=(150, 118, 80))
            self.parts.sparkle(wx, wy - 4, n=6, color=col)
            self.audio.play("plant")
            self.ui.log("Fertilized: this crop grows faster." if name == "fertilizer"
                        else "Quality fertilizer: chance of a double harvest!")
            return True
        # --- buff dishes: apply the buff, then let Core eat it (return False) ---
        b = cooking.buff_of(name) if hasattr(cooking, "buff_of") else None
        if b:
            kind, amt, secs = b
            lab = cooking.BUFF_LABEL.get(kind, kind.title())
            add = getattr(p, "add_buff", None)
            if add:
                add(kind, secs, amt, lab)
            col = cooking.BUFF_COLOR.get(kind, (255, 226, 140))
            self._popup(p.x, p.y - 48, f"+{lab} buff ({int(secs) // 60}:{int(secs) % 60:02d})", col)
            sb = getattr(self.parts, "star_burst", None)
            if sb:
                sb(p.x, p.y - 20, color=col, n=6)
            self.audio.play("levelup")
        return False

    # ---- harvest bonus (quality fertilizer / farming & luck buffs) ----
    def _on_event_artisan_harvest(self, event, data):
        if event != "harvest":
            return
        p = data.get("p")
        item = data.get("item")
        if p is None or item not in CROPS or not data.get("qty"):
            return
        tx, ty = p.target_tile()
        key = (self.world.current, tx, ty)
        crop = self.world.crops.get(key)
        if crop is None or crop.name != item:
            return
        chance = 0.0
        if self.fert_tiles.get(key) == "quality_fertilizer":
            chance += 0.35
        buff = getattr(p, "buff", None)
        if buff:
            chance += buff("farming") * 0.8 + buff("luck") * 0.3
        if chance > 0 and random.random() < chance:
            p.inv.add(item, 1)
            wx, wy = self._art_center(tx, ty)
            self._popup(wx, wy - 28, "Quality x2!", (250, 220, 110))
            self.parts.sparkle(wx, wy - 8, n=10, color=(250, 220, 110))

    # ---- drawing ----
    def _world_sprites_artisan(self):
        if self.world.current != AREA_FARM:
            return []
        cam = self.cam
        out = []
        sw, sh = self.screen.get_size()
        t = self.anim_t
        frame = int(t * 2.5) % 2
        # fertilized soil speckles (flat: baseline far above -> drawn first)
        if self.fert_tiles:
            for (a, gx, gy), kind in self.fert_tiles.items():
                if a != AREA_FARM:
                    continue
                x, y = gx * TILE - cam.x, gy * TILE - cam.y
                if -TILE < x < sw and -TILE < y < sh:
                    out.append((-1e9, _speckle(kind), (x, y)))
        for gx, gy, kind in self._art_machines():
            x = gx * TILE - cam.x
            y = gy * TILE - cam.y - (64 - TILE)
            if not (-TILE < x < sw + TILE and -80 < y < sh + 20):
                continue
            job = self.artisan_jobs.get(_ks(gx, gy))
            ready = self._art_ready(job) if job else False
            working = bool(job) and not ready
            fill = None
            if working and kind in ("machine_preserves_jar", "machine_keg"):
                fill = SOURCES.get(job.get("in"), {}).get("color")
            spr = _machine_surface(kind, working, frame if working else 0, fill)
            base = (gy + 1) * TILE
            hop = self._art_hop.get((gx, gy), 0) if self._art_hop else 0
            if hop > 0:                               # a quick squash-hop on use
                h = math.sin(hop / 0.3 * math.pi)
                spr = pygame.transform.scale(spr, (TILE + int(4 * h), 64 - int(5 * h)))
                x -= int(2 * h)
                y += int(5 * h) - int(6 * h)
            out.append((base, spr, (x, y)))
            if kind == "machine_bee_house":
                out.append((base + 1, None, _Bees(gx * TILE + TILE / 2, gy * TILE - 6, t + gx)))
            if ready:
                bob = math.sin(t * 3 + gx) * 3
                out.append((base + 2, _ready_bubble(job["out"]),
                            (x + 8, y - 22 + bob)))
        return out

    def _lights_artisan(self):
        if self.world.current != AREA_FARM or not self.artisan_jobs:
            return []
        out = []
        for gx, gy, kind in self._art_machines():
            job = self.artisan_jobs.get(_ks(gx, gy))
            if job and self._art_ready(job):
                out.append((gx * TILE + TILE / 2, gy * TILE - 6, 30, (255, 226, 150)))
            elif job and kind == "machine_mayo_machine":
                out.append((gx * TILE + TILE / 2, gy * TILE + 12, 14, (150, 240, 160)))
        return out

    # ---- journal tab (J): market, machines, buff dishes, animals ----
    def _journal_tab_35_farming(self):
        return {"title": "Farm", "draw": self._art_journal_draw}

    def _art_journal_draw(self, surf, rect):
        """Cream journal page: market + machines on the left, buff dishes +
        animals on the right (ui_kit ink, readable sizes, full width)."""
        from .. import ui_kit as K
        rect = pygame.Rect(rect)
        head_f = K.font(17, True)
        body_f = K.font(15)
        bold_f = K.font(15, True)
        note_f = K.font(13)
        gap = 36
        col_w = (rect.w - gap) // 2

        def head(text, x, y, w):
            K.blit_text(surf, head_f, text, K.SPROUT, (x, y + 9), align="left")
            tw = head_f.size(text)[0]
            pygame.draw.line(surf, K.WELL_LINE, (x + tw + 12, y + 10), (x + w, y + 10), 2)
            return y + 28

        def dark(col, k=0.62):
            return tuple(int(c * k) for c in col[:3])

        # -------- left column: market + machines --------
        x, y = rect.x, rect.y
        y = head("MARKET TODAY", x, y, col_w)
        try:
            from .shop_system import HOT, HOT_MULT, sell_value, item_label
            hot = HOT.get("item")
        except Exception:
            hot = None
        box = pygame.Rect(x, y, col_w, 36)
        K.well(surf, box)
        if hot:
            ic = assets.item_icon(hot)
            surf.blit(ic, (box.x + 8, box.centery - ic.get_height() // 2))
            base = sell_value(hot)
            K.blit_text(surf, body_f, f"{item_label(hot)} sells +50%:", K.INK,
                        (box.x + 44, box.centery), align="left")
            K.blit_text(surf, bold_f, f"{base}g -> {int(base * HOT_MULT)}g", K.GOLD_TXT,
                        (box.right - 12, box.centery), align="right")
        else:
            K.blit_text(surf, body_f, "No special today.", K.INK_SOFT, box.center)
        y = box.bottom + 12
        y = head("ARTISAN MACHINES", x, y, col_w)
        help_txt = ("Buy them at the General Store (Farm Supplies). Use one on farm grass to "
                    "place it; face it + Action to fill or collect; a pickaxe picks it back up.")
        help_lines = K.wrap(note_f, help_txt, col_w)
        below = 4 + 52 + 10 + len(help_lines) * 17
        mrh = max(40, min(52, (rect.bottom - y - below) // max(1, len(MACHINES))))
        for mid, m in MACHINES.items():
            if y > rect.bottom - 60:
                break
            ry = y + (mrh - 38) // 2
            ic = assets.item_icon(mid)
            surf.blit(ic, (x + 2, ry + 4))
            lab = m["label"]
            surf.blit(bold_f.render(lab, True, K.INK), (x + 40, ry))
            surf.blit(body_f.render(f"{m['price']}g", True, K.GOLD_TXT),
                      (x + 48 + bold_f.size(lab)[0], ry))
            desc = K.ellipsize(note_f, m["desc"], col_w - 44)
            surf.blit(note_f.render(desc, True, K.INK_SOFT), (x + 40, ry + 19))
            y += mrh
        placed = self._art_machines()
        ready = sum(1 for gx, gy, _k in placed if self._art_ready(self.artisan_jobs.get(_ks(gx, gy))))
        busy = sum(1 for gx, gy, _k in placed
                   if _ks(gx, gy) in self.artisan_jobs and not self._art_ready(self.artisan_jobs[_ks(gx, gy)]))
        y += 4
        box = pygame.Rect(x, y, col_w, 52)
        K.well(surf, box)
        kinds = len(GOODS)
        K.blit_text(surf, body_f, f"Artisan goods discovered: {len(self.artisan_made)} / {kinds}",
                    K.INK, (box.x + 12, box.y + 15), align="left")
        nm = len(placed)
        K.blit_text(surf, body_f, f"On your farm: {nm} machine{'s' if nm != 1 else ''}  -  "
                                  f"{busy} working  -  {ready} ready",
                    K.SPROUT if ready else K.INK_SOFT, (box.x + 12, box.y + 37), align="left")
        y = box.bottom + 10
        for line in help_lines:
            if y > rect.bottom - 14:
                break
            surf.blit(note_f.render(line, True, K.INK_SOFT), (x, y))
            y += 17
        # -------- right column: buff dishes + animals --------
        x, y = rect.x + col_w + gap, rect.y
        y = head("BUFF DISHES  (cook at a stove)", x, y, col_w)
        an_rows = max(1, -(-min(12, len(self.animals)) // 2))
        brh = max(28, min(36, (rect.bottom - y - 8 - 28 - an_rows * 25)
                          // max(1, len(cooking.BUFFS))))
        for fid, (kind, amt, secs) in cooking.BUFFS.items():
            if y > rect.bottom - 110:
                break
            f = cooking.FOODS[fid]
            ic = assets.item_icon(fid)
            cy = y + brh // 2
            surf.blit(ic, (x + 2, cy - ic.get_height() // 2))
            K.blit_text(surf, body_f, K.ellipsize(body_f, f["label"], 154), K.INK,
                        (x + 38, cy), align="left")
            K.blit_text(surf, bold_f, cooking.buff_text(fid),
                        dark(cooking.BUFF_COLOR.get(kind, K.GOLD_TXT)), (x + 198, cy), align="left")
            need = "  ".join(f"{q} {loot.label(i) if i not in CROPS else i.replace('_', ' ').title()}"
                             for i, q in cooking.RECIPES.get(fid, {}).items())
            need = K.ellipsize(note_f, need, col_w - 320)
            K.blit_text(surf, note_f, need, K.INK_SOFT, (x + col_w, cy), align="right")
            y += brh
        y += 8
        y = head("ANIMALS", x, y, col_w)
        if not self.animals:
            K.blit_text(surf, body_f, "No livestock yet -- buy some at the General Store.",
                        K.INK_SOFT, (x, y + 9), align="left")
        from .. import animals as _animals
        cell = col_w // 2
        pet_f = K.font(13, True)
        for i, an in enumerate(self.animals[:12]):
            cx = x + (i % 2) * cell
            cy = y + (i // 2) * 25
            if cy > rect.bottom - 18:
                break
            K.blit_text(surf, body_f, K.ellipsize(body_f, an.label, 92), K.INK,
                        (cx, cy + 9), align="left")
            _animals.draw_heart_row(surf, cx + 128, cy + 3, an.friend, parchment=True)
            if not getattr(an, "petted", False):
                K.blit_text(surf, pet_f, "pet me!", (196, 78, 112), (cx + 164, cy + 9), align="left")

    # ---- facing a machine: a small contextual label above it ----
    def _art_pill(self, text, color):
        cache = self.__dict__.setdefault("_art_pills", {})
        key = (text, color)
        s = cache.get(key)
        if s is None:
            if len(cache) > 120:
                cache.clear()
            from .. import ui_kit as K
            f = self.ui.small
            s = pygame.Surface((f.size(text)[0] + 16, f.get_height() + 8), pygame.SRCALPHA)
            pygame.draw.rect(s, (40, 34, 54, 210), s.get_rect(), border_radius=9)
            pygame.draw.rect(s, color + (160,), s.get_rect(), 1, border_radius=9)
            K.blit_text(s, f, text, color, s.get_rect().center)
            cache[key] = s
        return s

    def _art_prompt_text(self, p, kind, job):
        if job and self._art_ready(job):
            return f"Collect {good_label(job['out'])}!", (255, 226, 140)
        if job:
            if job.get("days", 0) > 0:
                d = job["days"]
                left = "ready tomorrow" if d == 1 else f"{d} days left"
            else:
                mins = int(job.get("mins", 0))
                left = f"{mins // 60}h {mins % 60:02d}m left" if mins >= 60 else f"{mins}m left"
            return f"{good_label(job['out'])}: {left}", (214, 220, 236)
        sel = p.inv.selected_entry()
        if sel and sel[1] == "pickaxe":
            return "Pick up machine", (230, 200, 170)
        item = sel[1] if sel and sel[0] == "item" else None
        rec = machine_recipe(kind, item) if item else None
        if rec:
            return f"Fill: {good_label(rec[0])}", (170, 236, 160)
        if kind == "machine_bee_house":
            return "Bees at work...", (250, 220, 120)
        return f"Needs {MACHINES[kind]['hint']}", (230, 196, 190)

    def _draw_world_artisan_prompts(self):
        if self.world.current != AREA_FARM or getattr(self, "state", "play") != "play":
            return
        cam = self.cam
        shown = set()
        for p in self.players:
            tx, ty = p.target_tile()
            sel = p.inv.selected_entry()
            if sel and sel[0] == "item" and sel[1] in MACHINES                     and (tx, ty) not in self.world.farm_objects:
                self._art_draw_ghost(sel[1], tx, ty)      # placement preview
                continue
            kind = self.world.farm_objects.get((tx, ty))
            if kind not in MACHINES or (tx, ty) in shown:
                continue
            shown.add((tx, ty))
            job = self.artisan_jobs.get(_ks(tx, ty))
            text, col = self._art_prompt_text(p, kind, job)
            pill = self._art_pill(text, col)
            x = tx * TILE + TILE // 2 - cam.x - pill.get_width() // 2
            if p.fy > 0:                     # player stands north: label under the machine
                y = (ty + 1) * TILE - cam.y + 2
            else:                            # otherwise above it (over the ready bubble)
                lift = 40 if (job and self._art_ready(job)) else 0
                y = ty * TILE - cam.y - 16 - pill.get_height() - 6 - lift
            self.screen.blit(pill, (int(x), int(y)))
            f = getattr(self, "hud_reserve", None)          # popups keep clear of it
            f and f(pill.get_rect(topleft=(int(x), int(y))))

    def _art_draw_ghost(self, kind, tx, ty):
        """Translucent machine + tile outline where it would be placed
        (green = OK, red = not here)."""
        ok = self._art_place_ok(self.world.area, tx, ty)
        key = ("ghost", kind, ok)
        g = _CACHE.get(key)
        if g is None:
            g = _machine_surface(kind).copy()
            if not ok:
                g.fill((255, 120, 120, 255), special_flags=pygame.BLEND_RGBA_MULT)
            g.set_alpha(120)
            _CACHE[key] = g
        x = tx * TILE - self.cam.x
        y = ty * TILE - self.cam.y
        pulse = 0.5 + 0.5 * math.sin(self.anim_t * 5)
        col = (140, 236, 150) if ok else (240, 120, 120)
        box = pygame.Rect(int(x) + 3, int(y) + 3, TILE - 6, TILE - 6)
        pygame.draw.rect(self.screen, col, box, 2 if pulse > 0.5 else 1, border_radius=6)
        self.screen.blit(g, (int(x), int(y) - (64 - TILE)))
