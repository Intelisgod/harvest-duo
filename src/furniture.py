"""Furniture catalog, recolour palettes and procedural sprites (Sims-style).

Sprites are drawn in a base 'facing-up' orientation onto a Surface sized to the
item's footprint, then rotated in 90 degree steps with pygame.transform.rotate,
so rotation works for any item without per-direction art.
"""
import math
import pygame
from .settings import TILE

# ---- recolour options for furniture ----
PALETTE = [
    ("White", (236, 236, 240)), ("Red", (200, 70, 70)), ("Orange", (226, 140, 60)),
    ("Yellow", (230, 200, 84)), ("Green", (96, 172, 96)), ("Teal", (70, 170, 168)),
    ("Blue", (84, 124, 200)), ("Navy", (62, 72, 120)), ("Purple", (150, 92, 180)),
    ("Pink", (226, 142, 172)), ("Brown", (140, 96, 60)), ("Gray", (138, 140, 150)),
]

# ---- house wall / floor recolour options ----
WALL_COLORS = [
    (210, 196, 176), (224, 208, 198), (200, 210, 214), (208, 196, 214),
    (196, 214, 196), (226, 214, 188), (190, 200, 214), (214, 198, 188),
]
FLOOR_COLORS = [
    (170, 128, 84), (150, 110, 72), (196, 160, 120), (138, 100, 70),
    (180, 176, 168), (156, 168, 150), (160, 150, 170), (200, 188, 160),
]

# ---- catalogue (ordered) ----
# id: (label, w, h, price, category, layer)
#   layer "floor"  -> rugs, drawn under everything, never block movement
#   layer "ground" -> normal furniture on the floor, blocks movement
#   layer "wall"   -> hangs on the top wall row, never blocks movement
CATALOG = [
    ("sofa",         "Sofa",          2, 1, 220, "Living",  "ground"),
    ("armchair",     "Armchair",      1, 1, 120, "Living",  "ground"),
    ("coffee_table", "Coffee Table",  1, 1, 90,  "Living",  "ground"),
    ("tv",           "TV",            1, 1, 240, "Living",  "ground"),
    ("bookshelf",    "Bookshelf",     1, 1, 160, "Living",  "ground"),
    ("lamp",         "Floor Lamp",    1, 1, 70,  "Living",  "ground"),
    ("rug",          "Rug",           2, 2, 110, "Living",  "floor"),

    ("bed",          "Bed",           2, 1, 250, "Bedroom", "ground"),
    ("dresser",      "Dresser",       1, 1, 140, "Bedroom", "ground"),
    ("wardrobe",     "Wardrobe",      1, 1, 200, "Bedroom", "ground"),
    ("nightstand",   "Nightstand",    1, 1, 70,  "Bedroom", "ground"),
    ("vanity",       "Vanity",        1, 1, 150, "Bedroom", "ground"),

    ("fridge",       "Fridge",        1, 1, 260, "Kitchen", "ground"),
    ("stove",        "Stove",         1, 1, 220, "Kitchen", "ground"),
    ("counter",      "Counter",       1, 1, 120, "Kitchen", "ground"),
    ("dining_table", "Dining Table",  2, 1, 200, "Kitchen", "ground"),
    ("chair",        "Chair",         1, 1, 60,  "Kitchen", "ground"),
    ("stool",        "Stool",         1, 1, 40,  "Kitchen", "ground"),

    ("plant",        "Plant",         1, 1, 50,  "Decor",   "ground"),
    ("fireplace",    "Fireplace",     2, 1, 300, "Decor",   "ground"),
    ("bench",        "Bench",         2, 1, 120, "Decor",   "ground"),
    ("bin_decor",    "Trash Can",     1, 1, 30,  "Decor",   "ground"),
    # wall-mounted decor (hang on the back wall)
    ("painting",     "Painting",      1, 1, 80,  "Decor",   "wall"),
    ("clock",        "Wall Clock",    1, 1, 90,  "Decor",   "wall"),
    ("window",       "Window",        1, 1, 100, "Decor",   "wall"),
    ("wall_shelf",   "Wall Shelf",    1, 1, 70,  "Decor",   "wall"),
    ("wall_lamp",    "Wall Lamp",     1, 1, 60,  "Decor",   "wall"),
    # functional crafting furniture
    ("workbench",    "Workbench",     2, 1, 400, "Crafting", "ground"),
    ("chest",        "Storage Chest", 1, 1, 180, "Crafting", "ground"),

    # ---- expansion pack (2026-06-04): more pieces per room ----
    ("piano",         "Piano",          2, 1, 320, "Living",  "ground"),
    ("piano_bench",   "Piano Bench",    1, 1, 80,  "Living",  "ground"),
    ("aquarium",      "Aquarium",       1, 1, 220, "Living",  "ground"),
    ("record_player", "Record Player",  1, 1, 140, "Living",  "ground"),
    ("crib",          "Crib",           1, 1, 140, "Bedroom", "ground"),
    ("toy_chest",     "Toy Chest",      1, 1, 90,  "Bedroom", "ground"),
    ("sink",          "Sink",           1, 1, 130, "Kitchen", "ground"),
    ("microwave",     "Microwave",      1, 1, 110, "Kitchen", "ground"),
    ("kitchen_island","Kitchen Island", 2, 1, 240, "Kitchen", "ground"),
    ("easel",         "Easel",          1, 1, 90,  "Decor",   "ground"),
    ("globe",         "Globe",          1, 1, 80,  "Decor",   "ground"),
    ("cat_tower",     "Cat Tower",      1, 1, 130, "Decor",   "ground"),
    ("standing_fan",  "Fan",            1, 1, 70,  "Decor",   "ground"),
    ("wall_mirror",   "Wall Mirror",    1, 1, 90,  "Decor",   "wall"),
    ("neon_sign",     "Neon Sign",      1, 1, 130, "Decor",   "wall"),

    # ---- tabletop decor (2026-06-11): small items that sit ON furniture ----
    # layer "top" -> placed on a flat-topped piece (SURFACES), up to 4 per cell,
    # never blocks movement; ox/oy hold the quarter-slot offset
    ("desk_mirror",   "Desk Mirror",    1, 1, 45,  "Tabletop", "top"),
    ("paper_stack",   "Papers",         1, 1, 10,  "Tabletop", "top"),
    ("pen_holder",    "Pen Holder",     1, 1, 15,  "Tabletop", "top"),
    ("photo_frame",   "Photo Frame",    1, 1, 35,  "Tabletop", "top"),
    ("candle_small",  "Candle",         1, 1, 20,  "Tabletop", "top"),
    ("book_stack",    "Book Stack",     1, 1, 25,  "Tabletop", "top"),
    ("vase_flowers",  "Flower Vase",    1, 1, 40,  "Tabletop", "top"),
    ("fruit_bowl",    "Fruit Bowl",     1, 1, 30,  "Tabletop", "top"),
    ("coffee_mug",    "Coffee Mug",     1, 1, 12,  "Tabletop", "top"),
    ("desk_lamp",     "Desk Lamp",      1, 1, 35,  "Tabletop", "top"),
    ("cactus_small",  "Mini Cactus",    1, 1, 25,  "Tabletop", "top"),
    ("music_sheet",   "Music Sheet",    1, 1, 15,  "Tabletop", "top"),

    # ---- showpieces (2026-09-28): systems/showpiece_system.py ----
    ("telescope",      "Telescope",      1, 1, 260, "Decor",   "ground"),
    ("arcade_cabinet", "Arcade Cabinet", 1, 1, 380, "Decor",   "ground"),
]
CAT = {c[0]: {"label": c[1], "w": c[2], "h": c[3], "price": c[4],
              "cat": c[5], "layer": c[6]} for c in CATALOG}
CATEGORIES = ["Living", "Bedroom", "Kitchen", "Decor", "Crafting", "Tabletop"]

# flat-topped ground furniture that tabletop decor may sit on
SURFACES = {"dining_table", "coffee_table", "counter", "kitchen_island",
            "dresser", "nightstand", "vanity",
            "piano", "aquarium", "fireplace", "bookshelf", "wardrobe"}
# ---- tabletop placement (free-form, 2026-09-28) ----
# The usable top of each surface kind, as a rect in the piece's CANONICAL
# (rot 0) footprint space, in tiles: (x0, y0, x1, y1). Items may sit anywhere
# inside it (minus their own radius). Default = the whole top, a hair inset.
SURFACE_TOP = {
    "piano": (0.08, 0.06, None, 0.46),      # the lid only, never the keys
    "fireplace": (0.06, 0.08, None, 0.60),  # the mantel shelf
    "bookshelf": (0.08, 0.08, None, None),
    "wardrobe": (0.08, 0.08, None, None),
    "aquarium": (0.10, 0.10, None, None),
}
SURFACE_INSET = 0.07
# footprint radius (tiles) of each tabletop item: they never overlap, and they
# stay this far inside the surface edge. Unlisted kinds use TOP_RADIUS_DEFAULT.
TOP_RADIUS = {
    "paper_stack": 0.16, "music_sheet": 0.15, "book_stack": 0.14,
    "fruit_bowl": 0.13, "desk_mirror": 0.13, "photo_frame": 0.13,
    "desk_lamp": 0.10, "vase_flowers": 0.09, "pen_holder": 0.08,
    "candle_small": 0.07, "coffee_mug": 0.07, "cactus_small": 0.07,
}
TOP_RADIUS_DEFAULT = 0.11
# how fine free placement snaps (tiles); Shift in Build mode = no snapping
TOP_SNAP = 0.0625


def top_radius(kind):
    return TOP_RADIUS.get(kind, TOP_RADIUS_DEFAULT)


def surface_top_rect(kind, fw, fh):
    """Canonical usable top rect of a `kind` whose canonical footprint is
    (fw, fh) tiles -- None entries in SURFACE_TOP mean 'full extent'."""
    x0, y0, x1, y1 = SURFACE_TOP.get(kind, (None, None, None, None))
    i = SURFACE_INSET
    return (i if x0 is None else x0, i if y0 is None else y0,
            fw - i if x1 is None else x1, fh - i if y1 is None else y1)


# seats the players can actually SIT on (interact -> sit, move/action -> stand).
# (2026-09-28: chairs and the piano bench joined -- homeiso._sitter_ops lifts a
# side-facing sitter clear of the chair's narrow backrest.)
SEATS = {"stool", "bench", "sofa", "armchair", "chair", "piano_bench"}
# cushion-top height (px) per seat kind -- the sitter's hips land here
SEAT_TOP = {"chair": 15, "stool": 15, "piano_bench": 18, "bench": 20,
            "sofa": 16, "armchair": 16}
# things a sitter naturally turns to face when they're right next to them
SIT_FACE = {"piano", "dining_table", "coffee_table", "counter",
            "kitchen_island", "workbench", "vanity"}
# only BACKLESS seats may swivel toward a SIT_FACE neighbour -- on an
# armchair or sofa you always sit the way the backrest points
SWIVEL_SEATS = {"stool", "bench", "piano_bench"}
# appliances/lights that toggle on/off with interact (visual state on Placed.on)
TOGGLE = {"tv", "lamp", "wall_lamp", "desk_lamp", "neon_sign", "fireplace",
          "microwave", "standing_fan", "record_player", "candle_small"}
TOGGLE.add("arcade_cabinet")        # showpieces: its screen glows while it's on

# ---- merging & centre-snapping ----
# MERGE kinds placed orthogonally adjacent with the SAME colour fuse into one
# big seamless piece (Sims counters / Minecraft double chests), L/T shapes too.
MERGE = {"rug", "chest", "counter", "kitchen_island", "dining_table", "bookshelf",
         "dresser", "wardrobe", "bench", "sofa",
         "nightstand", "tv", "coffee_table", "aquarium"}
# 1-tile seats that snap a half tile sideways to face the CENTRE of an
# even-length piece (chair at a 2-tile dining table, piano bench at a piano).
SNAP_SEATS = {"chair", "stool", "piano_bench"}


def merge_groups(pieces):
    """Connected groups of mergeable pieces (same kind + colour, cells touching
    orthogonally or overlapping). Returns a list of lists of Placed; groups of
    one are included -- callers usually only care about len(group) > 1."""
    pool = [pl for pl in pieces if pl.kind in MERGE]
    cellmap = {}
    for pl in pool:
        for c in pl.cells():
            cellmap.setdefault((pl.kind, pl.ci, c), []).append(pl)
    seen, groups = set(), []
    for pl in pool:
        if id(pl) in seen:
            continue
        seen.add(id(pl))
        grp, stack = [], [pl]
        while stack:
            q = stack.pop()
            grp.append(q)
            for (cx, cy) in q.cells():
                for nb in ((cx, cy), (cx + 1, cy), (cx - 1, cy),
                           (cx, cy + 1), (cx, cy - 1)):
                    for other in cellmap.get((q.kind, q.ci, nb), ()):
                        if id(other) not in seen:
                            seen.add(id(other))
                            stack.append(other)
        groups.append(grp)
    return groups


def group_cells(grp):
    """Union of all cells covered by a merge group."""
    cells = set()
    for pl in grp:
        cells.update(pl.cells())
    return cells

_base_cache = {}


def _dark(c, f=0.7):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


def _light(c, f=1.25):
    return tuple(min(255, int(v * f)) for v in c)


def footprint(item_id, rot):
    d = CAT[item_id]
    return (d["w"], d["h"]) if rot % 2 == 0 else (d["h"], d["w"])


def _draw_base(item_id, color, t=TILE, on=True):
    """Draw item in base orientation onto a Surface of (w*t, h*t). `on` is the
    power state for wall lights/signs (icons default to lit)."""
    d = CAT[item_id]
    w, h = d["w"] * t, d["h"] * t
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    dk, lt = _dark(color), _light(color)
    wood = (140, 96, 60)
    metal = (180, 184, 192)

    if item_id == "sofa":
        pygame.draw.rect(s, dk, (4, 6, w - 8, h - 10), border_radius=7)
        pygame.draw.rect(s, color, (4, 14, w - 8, h - 18), border_radius=6)
        pygame.draw.rect(s, lt, (10, 18, w // 2 - 12, h - 26), border_radius=5)
        pygame.draw.rect(s, lt, (w // 2 + 2, 18, w // 2 - 12, h - 26), border_radius=5)
    elif item_id in ("armchair", "chair"):
        pygame.draw.rect(s, dk, (6, 4, w - 12, 10), border_radius=4)        # back (top = facing away)
        pygame.draw.rect(s, color, (6, 12, w - 12, h - 18), border_radius=5)
        pygame.draw.rect(s, lt, (10, 16, w - 20, h - 26), border_radius=4)
    elif item_id == "stool":
        pygame.draw.circle(s, color, (w // 2, h // 2), w // 3)
        pygame.draw.circle(s, lt, (w // 2, h // 2), w // 3 - 4)
    elif item_id == "bench":
        pygame.draw.rect(s, color, (4, h // 2 - 6, w - 8, 12), border_radius=4)
        for bx in (8, w - 14):
            pygame.draw.rect(s, dk, (bx, h // 2 + 6, 6, h // 2 - 8))
    elif item_id in ("coffee_table", "dining_table", "nightstand", "side_table"):
        pygame.draw.rect(s, color, (4, 6, w - 8, h - 12), border_radius=4)
        pygame.draw.rect(s, dk, (4, 6, w - 8, h - 12), 2, border_radius=4)
        for cx, cy in ((8, h - 10), (w - 12, h - 10)):
            pygame.draw.rect(s, dk, (cx, cy, 4, 8))
    elif item_id == "bed":
        pygame.draw.rect(s, wood, (4, 4, w - 8, h - 8), border_radius=6)
        pygame.draw.rect(s, (240, 240, 246), (8, 8, w // 3, h - 16), border_radius=4)  # pillow (head=left)
        pygame.draw.rect(s, color, (8 + w // 3, 8, w - 16 - w // 3, h - 16), border_radius=4)
        pygame.draw.rect(s, dk, (8 + w // 3, 8, w - 16 - w // 3, h - 16), 2, border_radius=4)
    elif item_id == "dresser":
        pygame.draw.rect(s, color, (5, 8, w - 10, h - 14), border_radius=3)
        for r in range(2):
            pygame.draw.rect(s, dk, (9, 12 + r * 12, w - 18, 9), 2)
            pygame.draw.circle(s, metal, (w // 2, 16 + r * 12), 2)
    elif item_id in ("wardrobe", "fridge"):
        pygame.draw.rect(s, color, (6, 4, w - 12, h - 8), border_radius=3)
        pygame.draw.line(s, dk, (w // 2, 6), (w // 2, h - 6), 2)
        pygame.draw.rect(s, metal, (w // 2 - 4, h // 2, 3, 10))
        pygame.draw.rect(s, metal, (w // 2 + 2, h // 2, 3, 10))
    elif item_id == "vanity":
        pygame.draw.rect(s, color, (6, h - 22, w - 12, 18), border_radius=3)
        pygame.draw.ellipse(s, (200, 230, 240), (10, 4, w - 20, 18))     # mirror
        pygame.draw.ellipse(s, dk, (10, 4, w - 20, 18), 2)
    elif item_id == "bookshelf":
        pygame.draw.rect(s, color, (5, 4, w - 10, h - 8), border_radius=2)
        for r in range(3):
            yy = 8 + r * 11
            for i, bc in enumerate([(200, 70, 70), (80, 130, 200), (90, 170, 90), (220, 190, 80)]):
                pygame.draw.rect(s, bc, (9 + i * 7, yy, 5, 9))
    elif item_id == "tv":
        pygame.draw.rect(s, (30, 30, 36), (4, 6, w - 8, h - 18), border_radius=3)
        pygame.draw.rect(s, (90, 150, 200), (7, 9, w - 14, h - 24))
        pygame.draw.rect(s, dk, (w // 2 - 8, h - 10, 16, 5))
    elif item_id == "stove":
        pygame.draw.rect(s, color, (5, 5, w - 10, h - 10), border_radius=3)
        for cx, cy in ((14, 14), (w - 14, 14)):
            pygame.draw.circle(s, (40, 40, 44), (cx, cy), 5)
        pygame.draw.rect(s, (40, 40, 44), (9, h - 18, w - 18, 12), border_radius=2)
    elif item_id == "counter":
        pygame.draw.rect(s, (235, 235, 238), (4, 5, w - 8, 8), border_radius=2)   # top
        pygame.draw.rect(s, color, (5, 13, w - 10, h - 18), border_radius=2)
        pygame.draw.line(s, dk, (w // 2, 15, ), (w // 2, h - 7), 2)
    elif item_id == "plant":
        pygame.draw.rect(s, (150, 100, 70), (w // 2 - 7, h - 16, 14, 12), border_radius=3)
        pygame.draw.circle(s, (60, 150, 80), (w // 2, h - 20), 11)
        pygame.draw.circle(s, (84, 180, 104), (w // 2 - 5, h - 24), 7)
        pygame.draw.circle(s, (84, 180, 104), (w // 2 + 6, h - 22), 6)
    elif item_id == "painting":
        pygame.draw.rect(s, (120, 92, 60), (6, 6, w - 12, h - 12))
        pygame.draw.rect(s, color, (10, 10, w - 20, h - 20))
        pygame.draw.circle(s, lt, (w // 2, h // 2), 5)
    elif item_id == "clock":
        pygame.draw.circle(s, color, (w // 2, h // 2), w // 3)
        pygame.draw.circle(s, (250, 250, 250), (w // 2, h // 2), w // 3 - 4)
        pygame.draw.line(s, (30, 30, 30), (w // 2, h // 2), (w // 2, h // 2 - 9), 2)
        pygame.draw.line(s, (30, 30, 30), (w // 2, h // 2), (w // 2 + 7, h // 2), 2)
    elif item_id == "window":
        pygame.draw.rect(s, color, (8, 6, w - 16, h - 20))               # frame
        pygame.draw.rect(s, (150, 200, 230), (12, 10, w - 24, h - 28))   # sky glass
        pygame.draw.polygon(s, (190, 222, 244), [(12, h - 18), (12, h - 26),
                                                 (w - 12, h - 18)])       # light glint
        pygame.draw.line(s, color, (w // 2, 10), (w // 2, h - 18), 2)
        pygame.draw.line(s, color, (12, (h - 8) // 2), (w - 12, (h - 8) // 2), 2)
        pygame.draw.rect(s, dk, (8, 6, w - 16, h - 20), 2)
    elif item_id == "wall_shelf":
        pygame.draw.rect(s, color, (6, h // 2 - 2, w - 12, 5), border_radius=2)  # board
        pygame.draw.rect(s, dk, (9, h // 2 + 3, 3, 6))
        pygame.draw.rect(s, dk, (w - 12, h // 2 + 3, 3, 6))
        pygame.draw.rect(s, (200, 70, 70), (13, h // 2 - 12, 4, 10))             # books
        pygame.draw.rect(s, (80, 130, 200), (18, h // 2 - 11, 4, 9))
        pygame.draw.rect(s, (90, 170, 90), (23, h // 2 - 13, 4, 11))
        pygame.draw.circle(s, (226, 190, 90), (w - 16, h // 2 - 6), 4)           # trinket
    elif item_id == "wall_lamp":
        pygame.draw.rect(s, (96, 96, 102), (w // 2 - 2, h // 2 - 2, 4, 12))      # mount arm
        pygame.draw.polygon(s, color, [(w // 2 - 10, h // 2 - 2), (w // 2 + 10, h // 2 - 2),
                                       (w // 2 + 6, h // 2 - 13), (w // 2 - 6, h // 2 - 13)])
        if on:
            pygame.draw.circle(s, (255, 238, 170), (w // 2, h // 2 + 3), 4)      # glow
            pygame.draw.circle(s, (255, 250, 220), (w // 2, h // 2 + 3), 2)
        else:
            pygame.draw.circle(s, (172, 170, 162), (w // 2, h // 2 + 3), 3)      # bulb off
    elif item_id == "desk_mirror":
        pygame.draw.rect(s, wood, (w // 2 - 6, h - 12, 12, 4), border_radius=2)        # base
        pygame.draw.rect(s, _dark(color), (w // 2 - 1, h - 16, 2, 6))                  # stand
        pygame.draw.ellipse(s, color, (w // 2 - 9, 6, 18, 24))                         # frame
        pygame.draw.ellipse(s, (205, 225, 235), (w // 2 - 6, 9, 12, 18))               # glass
        pygame.draw.line(s, (236, 246, 250), (w // 2 - 3, 22), (w // 2 + 3, 12), 2)    # glint
    elif item_id == "paper_stack":
        for i, (dx, dy) in enumerate(((3, 3), (-2, 1), (1, -1))):
            r = pygame.Rect(10 + dx, 12 + dy, w - 20, h - 24)
            pygame.draw.rect(s, (246, 244, 238) if i == 2 else (228, 226, 218), r)
            pygame.draw.rect(s, (180, 176, 166), r, 1)
        for ly in (18, 22, 26):                                                        # writing
            pygame.draw.line(s, (150, 150, 160), (15, ly), (w - 16, ly), 1)
    elif item_id == "pen_holder":
        pygame.draw.rect(s, color, (w // 2 - 6, h // 2, 12, 14), border_radius=3)      # cup
        pygame.draw.rect(s, _dark(color), (w // 2 - 6, h // 2, 12, 14), 1, border_radius=3)
        pygame.draw.line(s, (60, 70, 160), (w // 2 - 3, h // 2 + 2), (w // 2 - 6, 8), 3)   # pens
        pygame.draw.line(s, (170, 60, 60), (w // 2 + 3, h // 2 + 2), (w // 2 + 7, 10), 3)
    elif item_id == "photo_frame":
        pygame.draw.rect(s, wood, (9, 8, w - 18, h - 20), border_radius=2)             # frame
        pygame.draw.rect(s, (150, 200, 230), (13, 12, w - 26, h - 28))                 # sky
        pygame.draw.circle(s, (250, 220, 120), (w - 18, 17), 4)                        # sun
        pygame.draw.polygon(s, (110, 170, 110), [(13, h - 16), (22, 20), (w - 13, h - 16)])
    elif item_id == "candle_small":
        pygame.draw.rect(s, (240, 236, 224), (w // 2 - 4, h // 2 - 6, 8, 18), border_radius=2)
        pygame.draw.line(s, (140, 130, 110), (w // 2, h // 2 - 6), (w // 2, h // 2 - 9), 2)
        pygame.draw.circle(s, (255, 210, 120), (w // 2, h // 2 - 12), 4)               # flame
        pygame.draw.circle(s, (255, 245, 200), (w // 2, h // 2 - 11), 2)
    elif item_id == "book_stack":
        for i, bc in enumerate(((200, 90, 80), (90, 140, 200), (220, 190, 100))):
            r = pygame.Rect(10 + i, h - 14 - i * 7, w - 20, 6)
            pygame.draw.rect(s, bc, r, border_radius=2)
            pygame.draw.rect(s, _dark(bc), r, 1, border_radius=2)
            pygame.draw.line(s, (246, 242, 232), (r.x + 2, r.bottom - 2), (r.right - 2, r.bottom - 2), 1)
    elif item_id == "vase_flowers":
        pygame.draw.polygon(s, color, [(w // 2 - 6, h - 8), (w // 2 + 6, h - 8),
                                       (w // 2 + 4, h - 20), (w // 2 - 4, h - 20)])  # vase
        for dx, fc in ((-6, (236, 120, 130)), (0, (250, 210, 110)), (6, (190, 130, 220))):
            pygame.draw.line(s, (96, 160, 96), (w // 2, h - 20), (w // 2 + dx, 14), 2)
            pygame.draw.circle(s, fc, (w // 2 + dx, 12), 4)
    elif item_id == "fruit_bowl":
        pygame.draw.ellipse(s, color, (w // 2 - 12, h // 2 + 2, 24, 10))             # bowl
        for dx, fc in ((-6, (220, 80, 70)), (0, (240, 180, 70)), (6, (130, 190, 90))):
            pygame.draw.circle(s, fc, (w // 2 + dx, h // 2), 5)
    elif item_id == "coffee_mug":
        pygame.draw.rect(s, color, (w // 2 - 7, h // 2 - 4, 14, 16), border_radius=3)
        pygame.draw.arc(s, _dark(color), (w // 2 + 5, h // 2 - 1, 9, 10), -1.4, 1.4, 3)
        pygame.draw.arc(s, (210, 214, 220), (w // 2 - 5, 8, 5, 8), 0.4, 2.6, 2)      # steam
        pygame.draw.arc(s, (210, 214, 220), (w // 2 + 1, 5, 5, 8), 0.4, 2.6, 2)
    elif item_id == "desk_lamp":
        pygame.draw.rect(s, (90, 94, 102), (w // 2 - 8, h - 10, 16, 5), border_radius=2)
        pygame.draw.line(s, (130, 134, 142), (w // 2, h - 10), (w // 2 + 6, 14), 3)
        pygame.draw.polygon(s, color, [(w // 2 - 2, 16), (w // 2 + 14, 16),
                                       (w // 2 + 10, 6), (w // 2 + 2, 6)])
        pygame.draw.circle(s, (255, 238, 170), (w // 2 + 6, 19), 4)                  # glow
    elif item_id == "cactus_small":
        pygame.draw.polygon(s, (190, 120, 80), [(w // 2 - 8, h - 16), (w // 2 + 8, h - 16),
                                                (w // 2 + 6, h - 6), (w // 2 - 6, h - 6)])
        pygame.draw.rect(s, (96, 168, 96), (w // 2 - 3, 12, 7, 18), border_radius=3)
        pygame.draw.rect(s, (96, 168, 96), (w // 2 - 9, 18, 6, 4), border_radius=2)
        pygame.draw.circle(s, (236, 150, 170), (w // 2, 10), 3)
    elif item_id == "music_sheet":
        pygame.draw.rect(s, (248, 246, 240), (9, 9, w - 18, h - 18))
        pygame.draw.rect(s, (190, 186, 176), (9, 9, w - 18, h - 18), 1)
        for i in range(4):                                                           # staff
            pygame.draw.line(s, (150, 150, 160), (13, 15 + i * 5), (w - 14, 15 + i * 5), 1)
        pygame.draw.circle(s, (60, 60, 70), (18, 18), 2)
        pygame.draw.line(s, (60, 60, 70), (20, 18), (20, 10), 1)
        pygame.draw.circle(s, (60, 60, 70), (28, 24), 2)
        pygame.draw.line(s, (60, 60, 70), (30, 24), (30, 16), 1)
    elif item_id == "piano_bench":
        pygame.draw.rect(s, _dark(wood, 0.9), (8, h // 2 + 2, 4, h // 2 - 8))      # legs
        pygame.draw.rect(s, _dark(wood, 0.9), (w - 12, h // 2 + 2, 4, h // 2 - 8))
        pygame.draw.rect(s, wood, (5, h // 2 - 4, w - 10, 8), border_radius=3)     # seat
        pygame.draw.rect(s, color, (7, h // 2 - 7, w - 14, 6), border_radius=3)    # cushion
        pygame.draw.rect(s, _dark(color), (7, h // 2 - 7, w - 14, 6), 1, border_radius=3)
    elif item_id == "chest":
        body = (150, 108, 64)
        pygame.draw.rect(s, body, (6, 16, w - 12, h - 22), border_radius=3)        # box body
        pygame.draw.rect(s, _dark(body), (6, 16, w - 12, h - 22), 2, border_radius=3)
        pygame.draw.rect(s, _light(body), (6, 8, w - 12, 12), border_radius=4)      # rounded lid
        pygame.draw.rect(s, _dark(body), (6, 8, w - 12, 12), 2, border_radius=4)
        pygame.draw.line(s, _dark(body, 0.55), (6, 19), (w - 6, 19), 2)             # lid seam
        for bx in (12, w - 13):                                                     # metal bands
            pygame.draw.rect(s, (170, 174, 182), (bx, 9, 3, h - 16))
        pygame.draw.rect(s, (210, 196, 110), (w // 2 - 3, 17, 6, 7), border_radius=1)  # gold lock
        pygame.draw.circle(s, (120, 96, 40), (w // 2, 20), 1)
    elif item_id == "workbench":
        pygame.draw.rect(s, (150, 110, 70), (4, 10, w - 8, h - 16), border_radius=3)
        pygame.draw.rect(s, (108, 78, 48), (4, 10, w - 8, h - 16), 2, border_radius=3)
        pygame.draw.rect(s, (110, 80, 50), (8, h - 8, 5, 6))
        pygame.draw.rect(s, (110, 80, 50), (w - 13, h - 8, 5, 6))
        # saw + hammer + gear on the bench top
        pygame.draw.line(s, (150, 152, 160), (w // 2 - 14, 16), (w // 2 - 3, 16), 2)
        pygame.draw.rect(s, (185, 185, 195), (w // 2 + 4, 12, 8, 4))
        pygame.draw.line(s, (120, 90, 60), (w // 2 + 8, 15), (w // 2 + 8, 22), 2)
        pygame.draw.circle(s, (172, 172, 182), (w - 16, 17), 4)
        pygame.draw.circle(s, (120, 120, 132), (w - 16, 17), 2)
    elif item_id == "fireplace":
        pygame.draw.rect(s, color, (4, 4, w - 8, h - 8), border_radius=3)
        pygame.draw.rect(s, (40, 36, 40), (w // 2 - 16, h - 22, 32, 18), border_radius=3)
        pygame.draw.polygon(s, (240, 150, 50), [(w // 2, h - 8), (w // 2 - 8, h - 20), (w // 2 + 8, h - 20)])
        pygame.draw.polygon(s, (250, 210, 90), [(w // 2, h - 10), (w // 2 - 4, h - 18), (w // 2 + 4, h - 18)])
    elif item_id == "lamp":
        pygame.draw.rect(s, (90, 90, 96), (w // 2 - 2, h // 2, 4, h // 2 - 6))
        pygame.draw.polygon(s, color, [(w // 2 - 11, h // 2), (w // 2 + 11, h // 2),
                                       (w // 2 + 7, h // 2 - 14), (w // 2 - 7, h // 2 - 14)])
    elif item_id == "bin_decor":
        pygame.draw.polygon(s, color, [(w // 2 - 9, h - 6), (w // 2 + 9, h - 6),
                                       (w // 2 + 7, h - 24), (w // 2 - 7, h - 24)])
        pygame.draw.rect(s, dk, (w // 2 - 9, h - 26, 18, 4), border_radius=2)
    elif item_id == "rug":
        pygame.draw.rect(s, color, (3, 3, w - 6, h - 6), border_radius=8)
        pygame.draw.rect(s, lt, (10, 10, w - 20, h - 20), border_radius=6)
        pygame.draw.rect(s, dk, (3, 3, w - 6, h - 6), 3, border_radius=8)
    elif item_id == "piano":
        body = (34, 32, 38)
        pygame.draw.rect(s, body, (4, 6, w - 8, h - 12), border_radius=4)
        pygame.draw.rect(s, _light(body, 2.2), (4, 6, w - 8, 5), border_radius=4)   # lid sheen
        pygame.draw.rect(s, (242, 242, 246), (8, h - 18, w - 16, 12))               # white keys
        for kx in range(11, w - 12, 7):
            pygame.draw.rect(s, (22, 22, 26), (kx, h - 18, 3, 7))                    # black keys
        pygame.draw.line(s, (90, 90, 96), (8, h - 18), (w - 8, h - 18), 1)
    elif item_id == "aquarium":
        pygame.draw.rect(s, (120, 90, 60), (5, h - 10, w - 10, 8), border_radius=2)   # stand
        pygame.draw.rect(s, (150, 205, 225), (6, 6, w - 12, h - 16), border_radius=3)  # water
        pygame.draw.ellipse(s, (236, 150, 90), (15, 16, 10, 6))                        # fish
        pygame.draw.polygon(s, (236, 150, 90), [(15, 19), (11, 16), (11, 22)])
        pygame.draw.circle(s, (24, 24, 28), (22, 18), 1)
        pygame.draw.rect(s, (90, 170, 110), (12, h - 13, 3, 7))                        # plant
        pygame.draw.rect(s, (210, 235, 245), (6, 6, w - 12, h - 16), 2, border_radius=3)  # glass
    elif item_id == "record_player":
        pygame.draw.rect(s, color, (6, 10, w - 12, h - 16), border_radius=3)
        pygame.draw.circle(s, (28, 28, 32), (w // 2, h // 2 + 2), 10)                  # vinyl
        pygame.draw.circle(s, (210, 80, 80), (w // 2, h // 2 + 2), 3)
        pygame.draw.line(s, (180, 184, 192), (w - 12, 12), (w // 2 + 4, h // 2), 2)    # tonearm
    elif item_id == "crib":
        pygame.draw.rect(s, wood, (5, 8, w - 10, h - 14), border_radius=3)
        for bx in range(9, w - 8, 5):
            pygame.draw.line(s, _light(wood, 1.25), (bx, 10), (bx, h - 10), 1)         # bars
        pygame.draw.rect(s, color, (8, h - 16, w - 16, 8), border_radius=2)            # blanket
    elif item_id == "toy_chest":
        pygame.draw.rect(s, color, (6, 16, w - 12, h - 22), border_radius=3)
        pygame.draw.rect(s, lt, (6, 9, w - 12, 11), border_radius=4)
        pygame.draw.rect(s, dk, (6, 9, w - 12, 11), 1, border_radius=4)
        pygame.draw.polygon(s, (250, 220, 90),                                         # star sticker
                            [(w // 2, 22), (w // 2 + 4, 28), (w // 2 - 4, 28)])
    elif item_id == "sink":
        pygame.draw.rect(s, (228, 228, 234), (5, 8, w - 10, h - 14), border_radius=3)
        pygame.draw.ellipse(s, (170, 200, 215), (10, 12, w - 20, h - 26))              # basin
        pygame.draw.rect(s, (180, 184, 192), (w // 2 - 1, 6, 3, 8))                    # faucet
        pygame.draw.rect(s, (180, 184, 192), (w // 2 - 1, 6, 7, 2))
    elif item_id == "microwave":
        pygame.draw.rect(s, (60, 60, 66), (6, 12, w - 12, h - 18), border_radius=3)
        pygame.draw.rect(s, (120, 150, 170), (9, 15, w - 26, h - 24))                  # window
        pygame.draw.rect(s, (40, 40, 44), (w - 15, 15, 6, h - 24))                     # panel
        for by in range(18, h - 12, 5):
            pygame.draw.rect(s, (210, 200, 90), (w - 13, by, 2, 2))
    elif item_id == "kitchen_island":
        pygame.draw.rect(s, (235, 235, 238), (4, 6, w - 8, 8), border_radius=2)        # countertop
        pygame.draw.rect(s, color, (6, 14, w - 12, h - 20), border_radius=2)
        pygame.draw.line(s, dk, (w // 3, 15), (w // 3, h - 7), 1)
        pygame.draw.line(s, dk, (2 * w // 3, 15), (2 * w // 3, h - 7), 1)
    elif item_id == "easel":
        pygame.draw.line(s, wood, (w // 2, 8), (10, h - 6), 2)
        pygame.draw.line(s, wood, (w // 2, 8), (w - 10, h - 6), 2)
        pygame.draw.rect(s, (236, 232, 222), (12, 8, w - 24, h - 22))                  # canvas
        pygame.draw.polygon(s, color, [(16, h - 18), (w // 2, 12), (w - 16, h - 16)])  # paint
    elif item_id == "globe":
        pygame.draw.arc(s, (180, 150, 90), (w // 2 - 13, h // 2 - 15, 26, 26), 0.3, 3.1, 2)  # ring
        pygame.draw.circle(s, (90, 150, 200), (w // 2, h // 2 - 2), 11)
        pygame.draw.circle(s, (96, 180, 110), (w // 2 - 3, h // 2 - 4), 4)             # land
        pygame.draw.circle(s, (96, 180, 110), (w // 2 + 4, h // 2 + 1), 3)
        pygame.draw.rect(s, wood, (w // 2 - 2, h - 12, 4, 8))                          # stand
    elif item_id == "cat_tower":
        pygame.draw.rect(s, (200, 180, 150), (w // 2 - 3, 10, 6, h - 16))             # carpet post
        pygame.draw.rect(s, color, (w // 2 - 11, 7, 22, 6), border_radius=2)          # top platform
        pygame.draw.rect(s, color, (w // 2 - 1, h - 13, 13, 5), border_radius=2)      # lower shelf
        pygame.draw.circle(s, (120, 110, 100), (w // 2, 5), 4)                        # napping cat
        pygame.draw.circle(s, (120, 110, 100), (w // 2 + 4, 4), 2)                    # ear
    elif item_id == "standing_fan":
        pygame.draw.rect(s, (150, 152, 160), (w // 2 - 1, h // 2, 3, h // 2 - 6))      # pole
        pygame.draw.rect(s, (120, 122, 130), (w // 2 - 6, h - 7, 12, 3))              # base
        pygame.draw.circle(s, color, (w // 2, h // 2 - 6), 11, 2)                      # cage
        for a in (0, 120, 240):
            rad = math.radians(a)
            pygame.draw.line(s, (200, 205, 215), (w // 2, h // 2 - 6),
                             (w // 2 + int(math.cos(rad) * 8), h // 2 - 6 + int(math.sin(rad) * 8)), 3)
        pygame.draw.circle(s, (120, 120, 130), (w // 2, h // 2 - 6), 2)
    elif item_id == "wall_mirror":
        pygame.draw.ellipse(s, color, (8, 4, w - 16, h - 12))                          # frame
        pygame.draw.ellipse(s, (205, 225, 235), (11, 7, w - 22, h - 18))               # glass
        pygame.draw.polygon(s, (236, 246, 250), [(15, h - 14), (15, h - 20), (w - 16, h - 12)])  # glint
        pygame.draw.ellipse(s, dk, (8, 4, w - 16, h - 12), 2)
    elif item_id == "neon_sign":
        glow = _light(color, 1.5) if on else (74, 76, 86)        # dark tubes when off
        pygame.draw.rect(s, (24, 24, 30), (5, 8, w - 10, h - 18), border_radius=3)
        pygame.draw.rect(s, glow, (9, 12, w - 18, 4), border_radius=2)
        pygame.draw.rect(s, glow, (9, 18, w - 24, 3), border_radius=2)
        pygame.draw.circle(s, glow, (w - 12, 14), 2)
    elif item_id == "telescope":                                  # showpieces (2026-09-28)
        brass = (214, 170, 84)
        top = (w // 2, int(h * 0.60))
        for fx in (w // 2 - 15, w // 2 + 15, w // 2 + 2):            # tripod
            pygame.draw.line(s, _dark(wood, 0.8), (fx, h - 4), top, 3)
        a, b = (int(w * 0.22), int(h * 0.62)), (int(w * 0.84), int(h * 0.18))
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        nx, ny = -dy / ln, dx / ln
        tube = [(a[0] + nx * 3, a[1] + ny * 3), (b[0] + nx * 5, b[1] + ny * 5),
                (b[0] - nx * 5, b[1] - ny * 5), (a[0] - nx * 3, a[1] - ny * 3)]
        pygame.draw.polygon(s, brass, tube)
        pygame.draw.polygon(s, _dark(brass, 0.6), tube, 1)
        c0 = (a[0] + dx * 0.8, a[1] + dy * 0.8)
        pygame.draw.polygon(s, color, [(c0[0] + nx * 5, c0[1] + ny * 5), (b[0] + nx * 5, b[1] + ny * 5),
                                       (b[0] - nx * 5, b[1] - ny * 5), (c0[0] - nx * 5, c0[1] - ny * 5)])
        pygame.draw.line(s, _light(brass, 1.3), (a[0] - nx * 1, a[1] - ny * 1),
                         (c0[0] - nx * 2, c0[1] - ny * 2), 1)
        pygame.draw.circle(s, (60, 56, 66), top, 3)
        pygame.draw.line(s, (40, 38, 46), a, (a[0] - dx * 0.1, a[1] - dy * 0.1), 4)   # eyepiece
    elif item_id == "arcade_cabinet":
        pygame.draw.rect(s, _dark(color, 0.6), (w // 2 - 13, 4, 26, 7), border_radius=2)  # marquee
        pygame.draw.rect(s, (255, 222, 236), (w // 2 - 11, 5, 22, 5), border_radius=2)
        pygame.draw.rect(s, color, (w // 2 - 12, 11, 24, h - 15))                         # body
        pygame.draw.rect(s, _dark(color, 0.6), (w // 2 - 12, 11, 24, h - 15), 1)
        pygame.draw.rect(s, (26, 22, 32), (w // 2 - 9, 13, 18, 14), border_radius=2)       # screen
        pygame.draw.rect(s, (58, 34, 84), (w // 2 - 7, 15, 14, 10))
        pygame.draw.line(s, (255, 190, 220), (w // 2 - 5, 17), (w // 2 - 5, 21), 1)
        pygame.draw.line(s, (255, 190, 220), (w // 2 + 5, 18), (w // 2 + 5, 22), 1)
        pygame.draw.circle(s, (255, 110, 160), (w // 2 + 1, 19), 1)
        pygame.draw.rect(s, _dark(color, 0.55), (w // 2 - 15, 28, 30, 5), border_radius=2)  # panel
        pygame.draw.circle(s, (226, 70, 80), (w // 2 - 7, 28), 2)
        pygame.draw.circle(s, (255, 120, 170), (w // 2 + 4, 30), 2)
        pygame.draw.circle(s, (250, 214, 110), (w // 2 + 9, 30), 2)
        pygame.draw.rect(s, _dark(color, 0.62), (w // 2 - 5, 36, 10, 7))                  # coin door
        pygame.draw.rect(s, (255, 170, 80), (w // 2 - 3, 38, 2, 3))
        pygame.draw.rect(s, (255, 170, 80), (w // 2 + 1, 38, 2, 3))
    else:
        pygame.draw.rect(s, color, (5, 5, w - 10, h - 10), border_radius=4)
    return s


def base_sprite(item_id, color, t=TILE, on=True):
    key = (item_id, color, t, on)
    if key not in _base_cache:
        _base_cache[key] = _draw_base(item_id, color, t, on)
    return _base_cache[key]


def sprite(item_id, color, rot, t=TILE, on=True):
    """Footprint-correct, rotated sprite (rot in 0..3)."""
    base = base_sprite(item_id, color, t, on)
    if rot % 4 == 0:
        return base
    return pygame.transform.rotate(base, -90 * (rot % 4))


def icon(item_id, color, size=40):
    """Small catalogue icon scaled to fit `size`."""
    d = CAT[item_id]
    t = size // max(d["w"], d["h"])
    base = base_sprite(item_id, color, t)
    return base


class Placed:
    __slots__ = ("kind", "gx", "gy", "rot", "ci", "level", "store", "ox", "oy",
                 "on", "data")

    def __init__(self, kind, gx, gy, rot=0, ci=0, level=1, store=None,
                 ox=0.0, oy=0.0, on=False, data=None):
        self.kind = kind
        self.gx = gx
        self.gy = gy
        self.rot = rot
        self.ci = ci          # palette colour index
        self.level = level    # quality level 1..3 (boosts interaction buff)
        # storage chest contents: item_id -> qty (only used by "chest")
        self.store = dict(store) if store else {}
        # sub-tile offset (+-0.5) set by centre-snapping (build.snap_offset)
        self.ox = ox
        self.oy = oy
        self.on = bool(on)    # appliance/light power state (TOGGLE kinds)
        # free-form per-piece state for functional furniture (a painted canvas,
        # the fish in a tank, a plant's growth...). JSON-safe values only.
        self.data = dict(data) if data else {}

    @property
    def color(self):
        return PALETTE[self.ci % len(PALETTE)][1]

    def cells(self):
        """Integer cells covered by the footprint INCLUDING any half-tile
        offset (a centre-snapped seat straddles two cells and blocks both).
        Tabletop decor is the exception: its ox/oy are quarter-cell SLOTS on
        one surface tile, so it always occupies exactly its anchor cell."""
        fw, fh = footprint(self.kind, self.rot)
        if CAT[self.kind]["layer"] == "top":
            return [(self.gx + dx, self.gy + dy)
                    for dx in range(fw) for dy in range(fh)]
        x0 = int(math.floor(self.gx + self.ox))
        x1 = int(math.ceil(self.gx + self.ox + fw))
        y0 = int(math.floor(self.gy + self.oy))
        y1 = int(math.ceil(self.gy + self.oy + fh))
        return [(cx, cy) for cx in range(x0, x1) for cy in range(y0, y1)]

    def to_dict(self):
        d = {"kind": self.kind, "gx": self.gx, "gy": self.gy,
             "rot": self.rot, "ci": self.ci, "level": self.level}
        if self.store:
            d["store"] = dict(self.store)
        if self.ox or self.oy:
            d["ox"] = self.ox
            d["oy"] = self.oy
        if self.on:
            d["on"] = True
        if self.data:
            d["data"] = dict(self.data)
        return d


def is_wall(item_id):
    """True for wall-mounted decor that hangs on the back wall."""
    return CAT[item_id]["layer"] == "wall"


# ---- cozy pastel starter layout for a brand-new home (14x10 room) ----
# (kind, gx, gy, rot, colour-index)   door at (6-7,8)
DEFAULT_HOME = [
    # bedroom (top-left) -- the bed is a normal piece: move/rotate/recolour it
    # in Build mode like anything else (world derives the sleep spot from it)
    ("bed", 2, 2, 0, 9),
    ("wardrobe", 1, 1, 0, 6), ("nightstand", 1, 2, 0, 3),
    ("dresser", 4, 1, 0, 9), ("vanity", 4, 2, 0, 0),
    # living room (top-right)
    ("sofa", 8, 1, 0, 9), ("coffee_table", 9, 2, 0, 0),
    ("bookshelf", 11, 1, 0, 8), ("armchair", 12, 4, 1, 5), ("tv", 12, 2, 0, 11),
    ("rug", 5, 3, 0, 9),
    # kitchen (left wall) -- stove & fridge are functional
    ("counter", 1, 4, 0, 0), ("stove", 1, 5, 0, 11), ("fridge", 1, 6, 0, 5),
    # dining + storage + cosy bits (bottom)
    ("dining_table", 4, 7, 0, 4), ("chair", 4, 8, 2, 3), ("chair", 5, 8, 2, 3),
    ("chest", 11, 7, 0, 10), ("lamp", 12, 6, 0, 3),
    ("plant", 1, 8, 0, 4), ("plant", 12, 8, 0, 4),
    # wall-mounted decor on the BACK wall (top row, gy = 0)
    ("window", 2, 0, 0, 6), ("clock", 6, 0, 0, 0),
    ("painting", 9, 0, 0, 8), ("window", 11, 0, 0, 6),
    # wall-mounted decor on the LEFT wall (column 0)
    ("wall_shelf", 0, 2, 0, 3), ("painting", 0, 4, 0, 5), ("wall_lamp", 0, 6, 0, 3),
]


def default_home_furniture():
    """Fresh list of Placed pieces for a new game's house (saves load their own).
    Lights/appliances start switched ON so the starter home feels alive, and
    the fridge comes stocked with a few snacks (open it like a chest)."""
    pieces = [Placed(k, gx, gy, rot, ci, on=(k in TOGGLE))
              for (k, gx, gy, rot, ci) in DEFAULT_HOME]
    fridge = next((q for q in pieces if q.kind == "fridge"), None)
    if fridge:
        fridge.store = {"egg": 2, "milk": 1, "fried_egg": 1}
    return pieces


def draw_quality(surf, x, y, level):
    """Draw (level-1) small gold star pips at a piece's top-left (level 1..3)."""
    if level <= 1:
        return
    for i in range(level - 1):
        cx, cy = x + 7 + i * 9, y + 7
        pygame.draw.polygon(surf, (250, 215, 90),
                            [(cx, cy - 4), (cx + 4, cy), (cx, cy + 4), (cx - 4, cy)])
        pygame.draw.polygon(surf, (170, 130, 40),
                            [(cx, cy - 4), (cx + 4, cy), (cx, cy + 4), (cx - 4, cy)], 1)
