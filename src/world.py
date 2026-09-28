"""Tile world: every area (farm, town, mine, meadow ...) with collision, warps and objects."""
import math
import random
from .settings import (TILE, AREA_FARM, AREA_TOWN, AREA_MINE, AREA_HOME, AREA_FOREST,
                       AREA_TEMPLE, AREA_COOP, AREA_BEACH, AREA_MEADOW,
                       COL_GRASS, COL_GRASS2, COL_PATH, COL_WATER, COL_WATER2,
                       COL_STONE, COL_STONE_DARK, COL_WALL, COL_FLOOR,
                       COL_TILLED, COL_TILLED_WET, COL_DIRT, COL_SAND, COL_SAND2)

# Tile codes
GRASS, GRASS2, PATH, WATER, STONE, WALL, FLOOR, DIRT = ".", ",", "P", "W", "S", "#", "F", "d"
# temple tiles: ornate floor, red prayer-mat runner, lacquered red wall
TFLOOR, TMAT, TWALL = "T", "m", "@"
# beach tiles: dry sand + damp sand at the tideline (both walkable)
SAND, SAND2 = "n", "N"
# wooden pier/boardwalk planks (walkable, can be laid over sand AND sea).  Two
# alternating plank shades give a decking look when laid in stripes.
PIER, PIER2 = "k", "K"
# mine biome floor tiles (all WALKABLE -- NOT added to SOLID_TILES).  The mine
# borders stay WALL ('#') in every biome so collision is unchanged.
ICE, LAVA, CRYSTAL = "i", "l", "c"
# 2026-09 level-up (World): deep mine floors, cobbled farm paths, meadow snow
ABYSS, RUINS = "v", "u"      # mine floors for depths 20-29 / 30+ (walkable)
COBBLE = "o"                 # stone path (walkable, NOT tillable -> never farmed over)
SNOW = "*"                   # winter meadow grass (walkable)
SNOWPATH = "~"               # winter meadow path: packed snow (walkable)

SOLID_TILES = {WATER, STONE, WALL, TWALL}
TILE_COLORS = {
    GRASS: COL_GRASS, GRASS2: COL_GRASS2, PATH: COL_PATH, WATER: COL_WATER,
    STONE: COL_STONE, WALL: COL_WALL, FLOOR: COL_FLOOR, DIRT: COL_DIRT,
    TFLOOR: (228, 206, 150), TMAT: (176, 60, 56), TWALL: (150, 70, 60),
    SAND: COL_SAND, SAND2: COL_SAND2, PIER: (176, 132, 84), PIER2: (150, 110, 68),
    ICE: (176, 214, 232), LAVA: (54, 46, 50), CRYSTAL: (74, 52, 102),
    ABYSS: (40, 34, 62), RUINS: (168, 150, 118), COBBLE: (178, 168, 150),
    SNOW: (238, 243, 251), SNOWPATH: (216, 212, 214),
}

# Mine biome look (World -> UI renderer contract, docs/UPGRADE_2026-09.md):
# floor tile, boulder tint (None = plain stone) and the ambient particle flavour.
BIOME_STYLE = {
    "rock":    {"floor": FLOOR,   "rock_tint": None,            "ambient": "dust"},
    "ice":     {"floor": ICE,     "rock_tint": (150, 190, 218), "ambient": "snow"},
    "lava":    {"floor": LAVA,    "rock_tint": (156, 72, 54),   "ambient": "ember"},
    "crystal": {"floor": CRYSTAL, "rock_tint": (126, 94, 168),  "ambient": "sparkle"},
    "abyss":   {"floor": ABYSS,   "rock_tint": (84, 62, 132),   "ambient": "void"},
    "ruins":   {"floor": RUINS,   "rock_tint": (196, 176, 136), "ambient": "ruin"},
}
# hazard tile kinds (area.hazards[(gx, gy)] = kind): walkable, hurt ~6 HP/s
HAZARD_DPS = {"lava": 6, "rift": 6}


class Area:
    def __init__(self, name, grid):
        self.name = name
        self.grid = grid
        self.h = len(grid)
        self.w = len(grid[0])
        self.trees = set()        # (gx, gy) occupies tile + tile above (visual)
        self.rocks = {}           # (gx, gy) -> ore type or None
        self.buildings = []       # (gx, gy, w, h, wall, roof, label)
        self.warps = []           # dict: rect tile (gx,gy), target, spawn (gx,gy)
        self.npc_spawns = []      # (name, gx, gy)
        self.bed = None           # (gx, gy)
        self.shop = None          # (gx, gy) interact to buy/sell
        self.ladder = None        # (gx, gy) for mine
        self.props = []           # visual interaction objects: (kind, gx, gy)
        self.solid_extra = set()  # extra solid cells (e.g. placed furniture)
        self.crab_spawns = []     # (gx, gy) sand tiles where ambient crabs wander
        self.mist_gate = None     # (gx, gy) ruined gate -> Mist City (forest only)
        self.mist_return = None   # (gx, gy) where players reappear after a mist run
        self.festival_stall = None  # (gx, gy) festival reward stall (town only)
        self.anniv_cabana = None    # (gx, gy) right beach cabana -> two-player gift
        self.biome = None         # mine biome: rock|ice|lava|crystal|abyss|ruins
        self.hazards = {}         # (gx, gy) -> "lava"|"rift" walkable damage tiles (mine)
        self.dyn_solid = set()    # runtime solids (farm outdoor decor, synced by WorldMixin)

    def tile(self, gx, gy):
        if 0 <= gy < self.h and 0 <= gx < self.w:
            return self.grid[gy][gx]
        return WALL

    def is_solid(self, gx, gy):
        if self.tile(gx, gy) in SOLID_TILES:
            return True
        if (gx, gy) in self.solid_extra:
            return True
        if self.dyn_solid and (gx, gy) in self.dyn_solid:
            return True
        if (gx, gy) in self.trees:
            return True
        if (gx, gy) in self.rocks:
            return True
        for (bx, by, bw, bh, *_rest) in self.buildings:
            if bx <= gx < bx + bw and by <= gy < by + bh:
                return True
        return False

    def is_water(self, gx, gy):
        return self.tile(gx, gy) == WATER


def _blank(w, h, fill=GRASS):
    return [[fill for _ in range(w)] for _ in range(h)]


def _rows(grid):
    return ["".join(r) for r in grid]


def build_farm():
    w, h = 42, 30
    g = _blank(w, h)
    # border of trees handled as objects; add a pond
    for y in range(4, 9):
        for x in range(30, 37):
            g[y][x] = WATER
    # path from house down to town warp
    for y in range(6, h):
        g[y][6] = PATH
        g[y][7] = PATH
    # sandy trail off the right edge leading down to the beach
    for x in range(w - 4, w):
        g[22][x] = PATH
        g[23][x] = PATH
    area = Area(AREA_FARM, _rows(g))
    # farmhouse building (top-left, width 5 -> door centred on x5, above the
    # house-door warps at (5,6)/(6,6) -- consistent with the coop entrance)
    area.buildings.append((3, 2, 5, 4, COL_WALL, (150, 70, 60), "Home"))
    # animal coop (right side) + the spot animals gather / you buy & collect
    area.buildings.append((32, 11, 5, 4, (200, 168, 132), (150, 96, 70), "Coop"))
    area.coop = (34, 16)
    # the bed now lives inside the house interior (enter via the door)
    area.shop = (10, 5)
    # shipping bin + farm decor (the livestock collector now lives inside the coop)
    area.props = [
        ("bin", 10, 5),
        ("windmill", 38, 4),
        ("scarecrow", 12, 25), ("scarecrow", 27, 11),
        ("flowerbed", 2, 7), ("flowerbed", 9, 8), ("flowerbed", 3, 9),
    ]
    decor_tiles = {(38, 4), (12, 25), (27, 11), (2, 7), (9, 8), (3, 9)}
    beach_trail = {(x, 22) for x in range(w - 4, w)} | {(x, 23) for x in range(w - 4, w)}
    beauty = _beautify_farm(area, g, w, h)       # 2026-09: paths, pond, orchard, lamps...
    area.grid = _rows(g)                          # cobble path tiles were painted into g
    protected = ({(10, 5), (10, 6), (5, 6), (6, 6)} | decor_tiles
                 | {(34, 15), (35, 15)} | beach_trail | beauty)
    # scatter trees around edges
    random.seed(7)
    for _ in range(40):
        x = random.randint(1, w - 2); y = random.randint(1, h - 2)
        if 12 <= x <= 28 and 10 <= y <= 26:
            continue            # keep central field clear for farming
        if 30 <= x <= 37 and 10 <= y <= 20:
            continue            # keep the coop yard clear for animals
        if area.tile(x, y) == GRASS and (x, y) not in protected:
            area.trees.add((x, y))
    # door to the house interior (just below the front door)
    # entrance directly below the farmhouse door (door is centred on tile x=6)
    area.warps.append({"gx": 5, "gy": 6, "to": AREA_HOME, "spawn": (6, 7)})
    area.warps.append({"gx": 6, "gy": 6, "to": AREA_HOME, "spawn": (7, 7)})
    # warp to town at bottom of path
    area.warps.append({"gx": 6, "gy": h - 1, "to": AREA_TOWN, "spawn": (20, 2)})
    area.warps.append({"gx": 7, "gy": h - 1, "to": AREA_TOWN, "spawn": (21, 2)})
    # door into the coop interior (tiles just below the coop building)
    area.warps.append({"gx": 34, "gy": 15, "to": AREA_COOP, "spawn": (7, 8)})
    area.warps.append({"gx": 35, "gy": 15, "to": AREA_COOP, "spawn": (8, 8)})
    # sandy trail off the right edge down to the beach
    area.warps.append({"gx": w - 1, "gy": 22, "to": AREA_BEACH, "spawn": (3, 4)})
    area.warps.append({"gx": w - 1, "gy": 23, "to": AREA_BEACH, "spawn": (3, 5)})
    # north gate up the cobbled lane to the Flower Meadow (2026-09)
    area.warps.append({"gx": 20, "gy": 0, "to": AREA_MEADOW, "spawn": (20, 27)})
    area.warps.append({"gx": 21, "gy": 0, "to": AREA_MEADOW, "spawn": (21, 27)})
    return area


# ---------------------------------------------------------------- farm beautification
# Everything sits OFF the central field (12..28 x 10..26) except the low, walk-over
# fence rail that frames it (drawn by WorldMixin, skipped on tilled tiles).  Solid
# features only go on edge tiles; WorldMixin._world_unblock_tilled() also frees any
# of them that an old save had already tilled, so no crop is ever walled in.
FARM_FENCE = ([(x, 10) for x in range(11, 30) if not 18 <= x <= 22]
              + [(x, 27) for x in range(11, 30) if not 18 <= x <= 21]
              + [(11, y) for y in range(11, 27) if y not in (17, 18)]
              + [(29, y) for y in range(11, 27) if y not in (15, 16)])
FARM_LAMPS = [(9, 10), (15, 8), (19, 7), (22, 7), (27, 8), (30, 17), (36, 20)]
FARM_NAME_SIGN = (8, 7)      # "<A> & <B>'s Farm" welcome sign (drawn by WorldMixin)


def _farm_path_cells():
    cells = []
    cells += [(x, y) for y in range(1, 9) for x in (20, 21)]          # north lane
    cells += [(x, 9) for x in range(8, 32)]                             # main walk
    cells += [(10, y) for y in range(6, 9)]                             # bin spur
    cells += [(31, y) for y in range(10, 17)]                           # coop lane
    cells += [(x, 16) for x in range(32, 37)]
    cells += [(37, y) for y in range(16, 24)]                           # beach spur
    return cells


def _beautify_farm(area, g, w, h):
    """Paths, pond dressing, orchard, flowers, edge stumps/boulders, lamp posts and
    a picnic spot.  Paints COBBLE into ``g``; returns the tiles to keep tree-free."""
    used = set()
    paths = _farm_path_cells()
    for (x, y) in paths:
        g[y][x] = COBBLE
        area.props.append((("cobble", "cobble2", "cobble3")[(x * 7 + y * 3) % 3], x, y))
    used.update(paths)
    # softer pond: round off the four corners, dress it with lilies and reeds
    for (x, y) in ((30, 4), (36, 4), (30, 8), (36, 8)):
        g[y][x] = GRASS
    area.props += [("lily_pad", 31, 5), ("lily_flower", 33, 5), ("lily_pad", 35, 6),
                   ("lily_flower", 31, 7), ("reeds", 30, 4), ("reeds", 36, 8),
                   ("reeds", 29, 6), ("reeds", 37, 5)]
    # a little fishing dock from the main walk out over the water (walkable planks)
    for y in (7, 8):
        g[y][33] = PIER if y % 2 == 0 else PIER2
        area.props.append(("dock", 33, y))
    used.update({(30, 4), (36, 8), (29, 6), (37, 5), (30, 8), (36, 4)})
    # picnic spot on the knoll between the lane and the pond
    area.props += [("picnic_bench", 24, 2), ("picnic_blanket", 24, 4),
                   ("fruit_tree", 27, 3)]
    area.solid_extra |= {(24, 2), (25, 2), (27, 3)}
    used |= {(24, 2), (25, 2), (24, 4), (25, 4), (27, 3), (24, 3), (25, 3), (26, 3)}
    # orchard row along the bottom edge (fruit shows in summer & fall)
    orchard = [(10, 28), (13, 28), (16, 28), (23, 28), (26, 28), (29, 28)]
    for (x, y) in orchard:
        area.props.append(("fruit_tree", x, y))
        area.solid_extra.add((x, y))
    used.update(orchard)
    # wildflower patches around the homestead and the pond
    for i, (x, y) in enumerate([(1, 11), (4, 11), (9, 12), (2, 14), (28, 2), (32, 2),
                                (38, 8), (35, 2), (15, 2), (4, 26), (39, 13), (17, 4)]):
        area.props.append(("wildflowers" if i % 2 == 0 else "wildflowers2", x, y))
        used.add((x, y))
    # stumps + boulders at the edges (solid, well away from the field)
    for kind, x, y in (("stump", 15, 1), ("boulder", 40, 10), ("stump", 39, 2),
                       ("boulder", 1, 27), ("stump", 40, 27), ("boulder", 26, 1),
                       ("boulder", 1, 18)):
        area.props.append((kind, x, y))
        area.solid_extra.add((x, y))
        used.add((x, y))
    # lamp posts along the walk (glow at night via WorldMixin._lights_world_*)
    for (x, y) in FARM_LAMPS:
        area.props.append(("lamp_post", x, y))
        area.solid_extra.add((x, y))
        used.add((x, y))
    area.lamps = list(FARM_LAMPS)
    # the fence frame is walk-over decor; keep trees off it and its gaps
    used.update(FARM_FENCE)
    used |= {(x, y) for x in range(18, 23) for y in (10, 27)}
    used |= {(11, 17), (11, 18), (29, 15), (29, 16), (20, 1), (21, 1), (20, 0), (21, 0)}
    used.add(FARM_NAME_SIGN)
    return used


def build_meadow():
    """The Flower Meadow north of the farm: pastel flower drifts, a winding hill
    path, a lily pond, the great Promise Tree (bench + swing for two) and a
    lookout deck over the valley."""
    w, h = 40, 30
    g = _blank(w, h)
    # winding two-wide path from the farm gate (bottom) up to the Promise Tree
    path = set()
    for y in range(10, h):
        cx = 20 + int(round(3 * math.sin((h - y) / 4.5)))
        if y >= h - 3:
            cx = 20
        for x in (cx, cx + 1):
            path.add((x, y))
    for y in range(9, 11):                             # small clearing under the tree
        for x in range(17, 25):
            path.add((x, y))
    # branch path east + north to the lookout on the hill
    for x in range(23, 35):
        path.add((x, 14))
    for y in range(4, 14):
        path.add((34, y))
    for (x, y) in path:
        g[y][x] = PATH
    # lily pond (lower-left), corners rounded
    pond = set()
    for y in range(17, 23):
        for x in range(4, 12):
            if (x in (4, 11)) and (y in (17, 22)):
                continue
            pond.add((x, y))
            g[y][x] = WATER
    area = Area(AREA_MEADOW, _rows(g))
    # the Promise Tree (3 wide x 4 tall sprite anchored on row 8, trunk at x=20)
    area.props.append(("promise_tree", 19, 8))
    area.solid_extra |= {(19, 8), (20, 8), (21, 8)}
    area.promise_tree = (20, 8)
    area.props += [("love_bench", 16, 9)]
    area.bench = (17, 9)          # sit together a while (WorldMixin rest spot)
    area.swing = (23, 8)          # rope swing under the right bough (drawn + swung by WorldMixin)
    # lookout deck over the valley (walk-on; interact for a breather)
    area.props.append(("lookout", 33, 3))
    area.lookout = (34, 3)
    # direction signs at the gate and at the lookout fork
    area.props += [("sign_tree", 18, 27), ("sign_lookout", 23, 13)]
    # pond dressing
    area.props += [("lily_pad", 6, 18), ("lily_flower", 9, 19), ("lily_pad", 7, 21),
                   ("reeds", 3, 18), ("reeds", 12, 20), ("reeds", 4, 23)]
    keep = set(path) | pond | {(16, 9), (17, 9), (23, 8), (33, 3), (34, 3), (3, 18),
                               (18, 27), (23, 13), (19, 27),
                               (12, 20), (4, 23), (20, 27), (21, 27), (20, 28), (21, 28)}
    keep |= {(x, y) for x in range(17, 25) for y in range(4, 9)}      # under the canopy
    # the lookout hill: a grassy ledge along its south + west rim (path = the ramp up)
    for (x, y, k) in ([(x, 9, "hill_s") for x in range(29, 39)]
                      + [(28, y, "hill_w") for y in range(1, 9)] + [(28, 9, "hill_sw")]):
        if (x, y) not in path:
            area.props.append((k, x, y))
            keep.add((x, y))
    # scattered edge trees + a few stumps (deterministic)
    rng = random.Random(23)
    for _ in range(46):
        x, y = rng.randint(1, w - 2), rng.randint(1, h - 2)
        edge = x < 4 or x > w - 5 or y < 3 or y > h - 4
        if edge and (x, y) not in keep and area.tile(x, y) == GRASS and not (18 <= x <= 23 and y >= h - 4):
            area.trees.add((x, y))
    for (x, y) in ((13, 3), (28, 24), (36, 18)):
        if (x, y) not in area.trees:
            area.props.append(("stump", x, y))
            area.solid_extra.add((x, y))
            keep.add((x, y))
    # flower drifts: colour bands that sweep across the field
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if (x, y) in keep or (x, y) in area.trees or area.tile(x, y) != GRASS:
                continue
            n = math.sin(x * 0.45 + y * 0.2) + math.cos(y * 0.5 - x * 0.15)
            if n > 0.35 or ((x * 13 + y * 7) % 11 == 0):
                band = int((x * 0.18 + y * 0.12 + math.sin(y * 0.3) * 1.5)) % 4
                lay = (x * 7 + y * 13) % 3              # 3 scatter layouts per colour
                kind = ("mflowers" if band == 0 else f"mflowers{band + 1}") \
                    + ("" if lay == 0 else chr(97 + lay))   # see world_art.MFLOWER_KINDS
                area.props.append((kind, x, y))
    # a few lamp posts along the path so evening walks glow
    area.lamps = []
    spots = [(20 + int(round(3 * math.sin((h - y) / 4.5))) - 1, y) for y in (25, 19)]
    for (x, y) in spots + [(25, 15), (33, 9)]:          # right beside the path
        if area.tile(x, y) == GRASS and (x, y) not in area.trees:
            area.props = [pr for pr in area.props if (pr[1], pr[2]) != (x, y)]
            area.props.append(("lamp_post", x, y))
            area.solid_extra.add((x, y))
            area.lamps.append((x, y))
    # season swap: winter turns the open grass to snow (WorldMixin swaps grids)
    area.grid_green = list(area.grid)
    area.grid_snow = [r.replace(GRASS, SNOW).replace(PATH, SNOWPATH) for r in area.grid]
    # back down to the farm (spawn one row in from the farm's north gate)
    area.warps.append({"gx": 20, "gy": h - 1, "to": AREA_FARM, "spawn": (20, 1)})
    area.warps.append({"gx": 21, "gy": h - 1, "to": AREA_FARM, "spawn": (20, 2)})
    return area


def build_home():
    # sized + centred (see Game._update_camera) so the room never sits under the HUD
    w, h = 14, 10
    g = _blank(w, h, FLOOR)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                g[y][x] = WALL
    area = Area(AREA_HOME, _rows(g))
    area.bed = (2, 2)                     # fixed bed (2 wide), sleep here
    # exit door back to the farm (centre of the bottom interior row)
    area.warps.append({"gx": 6, "gy": h - 2, "to": AREA_FARM, "spawn": (5, 7)})
    area.warps.append({"gx": 7, "gy": h - 2, "to": AREA_FARM, "spawn": (6, 7)})
    return area


def build_town():
    w, h = 42, 30
    g = _blank(w, h, PATH)
    # grassy borders
    for y in range(h):
        for x in range(w):
            if x < 2 or x >= w - 2 or y < 2 or y >= h - 2:
                g[y][x] = GRASS
    # town pond for fishing (right side)
    for y in range(18, 26):
        for x in range(30, 39):
            g[y][x] = WATER
    area = Area(AREA_TOWN, _rows(g))
    # shop building (width 7 -> door centred on tile x9, with the stall below it)
    area.buildings.append((6, 6, 7, 4, (120, 110, 150), (90, 80, 130), "Shop"))
    area.shop = (9, 10)
    area.props = [("stall", 9, 10)]
    # quest hall -- its "QUESTS" sign sits over the quest board in the doorway
    # (width 5 -> door centred on tile x24, exactly above the board)
    area.buildings.append((22, 5, 5, 4, (150, 130, 110), (120, 90, 70), "Quests"))
    area.quest_board = (24, 9)
    # festival reward stall (single source of truth per docs/TASK_no_hardcode.md --
    # actions_system + render_system read this attr instead of a hard-coded (20,12))
    area.festival_stall = (20, 12)
    # Buddhist temple gate (top-right, width 5 -> door centred on x34, above the
    # gate prop & entrance warp -- mirrors the coop layout)
    area.buildings.append((32, 3, 5, 5, (184, 72, 60), (214, 150, 64), "Temple"))
    area.props = area.props + [("temple_gate", 34, 8)]
    # Valley Restoration board (World <-> Story contract): an open, visible spot on
    # the plaza between the shop and the quest hall.  Story registers the prop
    # painter and handles the interaction via its own _interact_early_* hook.
    area.restoration_board = (17, 8)
    area.props = area.props + [("restoration_board", 17, 8)]
    area.solid_extra.add((17, 8))
    # NPC spawns
    area.npc_spawns = [
        ("Mira", 16, 14),
        ("Tomas", 25, 18),
        ("Elya", 12, 20),
    ]
    # warp back to farm (top) and to mine (bottom-left)
    area.warps.append({"gx": 20, "gy": 1, "to": AREA_FARM, "spawn": (6, 28)})
    area.warps.append({"gx": 21, "gy": 1, "to": AREA_FARM, "spawn": (7, 28)})
    area.warps.append({"gx": 3, "gy": h - 2, "to": AREA_MINE, "spawn": (5, 3)})
    area.warps.append({"gx": 4, "gy": h - 2, "to": AREA_MINE, "spawn": (6, 3)})
    # forest entrance on the right edge
    area.warps.append({"gx": w - 1, "gy": 14, "to": AREA_FOREST, "spawn": (18, 2)})
    area.warps.append({"gx": w - 1, "gy": 15, "to": AREA_FOREST, "spawn": (19, 2)})
    # temple entrance (door tiles just below the temple gate)
    area.warps.append({"gx": 34, "gy": 8, "to": AREA_TEMPLE, "spawn": (10, 14)})
    area.warps.append({"gx": 35, "gy": 8, "to": AREA_TEMPLE, "spawn": (11, 14)})
    return area


def build_forest():
    w, h = 38, 28
    g = _blank(w, h, GRASS)
    # a quiet pond in the lower-right
    for y in range(20, 25):
        for x in range(28, 34):
            g[y][x] = WATER
    area = Area(AREA_FOREST, _rows(g))
    random.seed(11)
    for _ in range(110):                          # dense woodland
        x = random.randint(1, w - 2)
        y = random.randint(3, h - 2)
        if 13 <= x <= 25 and 9 <= y <= 18:        # central hunting clearing
            continue
        if area.tile(x, y) == GRASS and (x, y) not in {(18, 2), (19, 2)}:
            area.trees.add((x, y))
    # where wildlife gathers
    area.animal_spawns = [(random.randint(15, 24), random.randint(10, 17)) for _ in range(7)]
    # ---- the ruined warp gate to Mist City (docs/TASK_mist_city.md) ----
    # Tucked in the deep bottom-left corner, far from the town entrance.  NOTE:
    # Mist City is a side-scroller STATE ("mistcity"), not a tile area, so this is
    # deliberately NOT an area.warps entry (stepping on a warp to a non-area would
    # crash).  Like donation_box/collector, Core's actions_system reads
    # `area.mist_gate` to trigger self._mist_enter() (guarded), and MistMixin
    # respawns the players at `area.mist_return` when the run ends.
    gate = (3, 24)
    for cell in (gate, (2, 24), (4, 24), (3, 23), (2, 25), (3, 25), (4, 25), (3, 26)):
        area.trees.discard(cell)              # keep the gate and its approach clear
    area.props.append(("mist_gate", *gate))
    area.solid_extra.add(gate)                # the arch itself blocks movement
    area.mist_gate = gate                     # interaction anchor (Core seam)
    area.mist_return = (3, 25)                # players reappear here after a run
    # warp back to town (top)
    area.warps.append({"gx": 18, "gy": 0, "to": AREA_TOWN, "spawn": (39, 14)})
    area.warps.append({"gx": 19, "gy": 0, "to": AREA_TOWN, "spawn": (39, 15)})
    return area


def build_temple():
    """A small Buddhist temple (wat): lacquered red walls, an ornate floor with a
    red prayer-mat runner up to a golden Buddha altar, where a monk tells fortunes."""
    # taller hall (was 17) so the altar can sit a few rows BELOW the back wall --
    # otherwise the 3-tile principal Buddha, drawn bottom-anchored, pushes its head
    # and flame finial up off the top of the map / behind the HUD (it was invisible).
    w, h = 21, 19
    g = _blank(w, h, TFLOOR)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                g[y][x] = TWALL
    # wide red congregation carpet (kneeling area) in the lower hall
    for y in range(10, h - 2):
        for x in range(7, 14):
            g[y][x] = TMAT
    # runner connecting the altar down to the carpet
    for y in range(6, 10):
        g[y][10] = TMAT
    # door gap in the bottom wall (exit back to town)
    g[h - 1][10] = TFLOOR
    g[h - 1][11] = TFLOOR
    area = Area(AREA_TEMPLE, _rows(g))
    # a grand wihan: a large principal Buddha (phra pratan) raised on the altar a few
    # rows in from the back wall (head now well clear of the HUD), smaller disciple
    # Buddhas beside it, a colonnade lining the hall, and an offering table.
    area.props = [
        # ---- altar (raised, set down from the back wall) ----
        ("phra_pratan", 9, 5),                          # 3-wide principal Buddha
        ("buddha", 6, 5), ("buddha", 14, 5),            # flanking disciple images
        ("chatra", 8, 4), ("chatra", 12, 4),            # tiered umbrellas
        ("chedi", 2, 3), ("chedi", 18, 3),              # corner stupas
        ("tung", 5, 3), ("tung", 15, 3),                # hanging banners
        # ---- offering table in front of the altar ----
        ("candle", 6, 8), ("candle", 14, 8),
        ("offering_bowl", 8, 8), ("offering_bowl", 12, 8),
        ("incense", 8, 9), ("incense", 12, 9),
        ("donation_box", 13, 8),
        # ---- colonnade lining the hall + side lotuses ----
        ("pillar", 3, 7), ("pillar", 17, 7),
        ("pillar", 3, 11), ("pillar", 17, 11),
        ("pillar", 3, 15), ("pillar", 17, 15),
        ("lotus", 5, 11), ("lotus", 15, 11),
        # ---- bells + naga balustrades guarding the exit ----
        ("bell", 4, 16), ("bell", 16, 16),
        ("naga", 8, 17), ("naga", 12, 17),
    ]
    # solids: principal Buddha dais (3x2) + disciple statues + corner chedis + columns
    area.solid_extra = {(9, 4), (10, 4), (11, 4), (9, 5), (10, 5), (11, 5),
                        (6, 5), (14, 5), (2, 3), (18, 3),
                        (3, 7), (17, 7), (3, 11), (17, 11), (3, 15), (17, 15)}
    # alms / merit box -- donate gold to improve your fortune odds
    area.donation_box = (13, 8)
    # the fortune-telling monk sits before the altar
    area.npc_spawns = [("Luang Por", 10, 7)]
    # exit back to town (door tiles in the bottom wall)
    area.warps.append({"gx": 10, "gy": h - 1, "to": AREA_TOWN, "spawn": (34, 9)})
    area.warps.append({"gx": 11, "gy": h - 1, "to": AREA_TOWN, "spawn": (35, 9)})
    return area


def build_coop():
    """Cosy barn interior where the livestock live. Enter from the coop building
    on the farm. Holds the one-press produce collector, hay, feed and a trough."""
    w, h = 16, 11
    g = _blank(w, h, FLOOR)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                g[y][x] = WALL
    # a strip of straw-coloured dirt down the middle as a feeding lane
    for x in range(3, w - 3):
        g[h - 3][x] = DIRT
    # door gap in the bottom wall back to the farm
    g[h - 1][7] = FLOOR
    g[h - 1][8] = FLOOR
    area = Area(AREA_COOP, _rows(g))
    # barn fittings: collector by the door, hay bales + feed/water troughs
    area.props = [
        ("collector", 13, 2),
        ("haybale", 2, 2), ("haybale", 3, 2), ("haybale", 2, 3),
        ("trough", 3, 7), ("trough", 12, 7),   # one at each end of the feed lane,
                                               # symmetric about the door (x = 7.5)
    ]
    area.collector = (13, 2)                 # one-press produce collector
    area.solid_extra = {(2, 2), (3, 2), (2, 3), (13, 2)}   # hay bales + machine block
    # animals are re-homed into this room on entry (see Game._spawn_area_entities)
    area.coop = (8, 5)                        # where freshly bought animals appear
    # exit back to the farm (door tiles in the bottom wall)
    area.warps.append({"gx": 7, "gy": h - 1, "to": AREA_FARM, "spawn": (34, 16)})
    area.warps.append({"gx": 8, "gy": h - 1, "to": AREA_FARM, "spawn": (35, 16)})
    return area


def build_beach():
    """A sunny seaside: a grassy headland at the top (the farm trail comes in here),
    a wide stretch of sand, and an open sea along the bottom with a gently wavy
    shoreline. Great for fishing -- the whole tideline is castable water."""
    import math
    w, h = 42, 30
    g = _blank(w, h, SAND)
    # grassy headland along the top where the farm trail arrives
    for y in range(0, 4):
        for x in range(w):
            g[y][x] = GRASS
    # the sea fills the bottom with a softly undulating shoreline; the row just
    # above the waterline reads as darker, damp sand
    for x in range(w):
        sy = 23 + int(1.7 * math.sin(x * 0.5))
        for y in range(sy, h):
            g[y][x] = WATER
        if 4 <= sy - 1 < h:
            g[sy - 1][x] = SAND2
    # a wooden fishing pier reaching from the sand out over the open sea -- the
    # focal point of the beach (cf. Stardew's docks).  Planks override both sand
    # and water so the players can walk right out above the waves and cast.
    for px in (20, 21):
        for py in range(17, 28):
            g[py][px] = PIER if py % 2 == 0 else PIER2   # alternating plank stripes
    for px in range(19, 23):                 # small T-platform at the seaward end
        g[27][px] = PIER if px % 2 == 0 else PIER2
    area = Area(AREA_BEACH, _rows(g))
    # A busy, sun-soaked resort beach packed with holiday-makers' things (ref: a
    # lively cartoon beach -- rows of umbrellas, colourful mats, sun loungers,
    # sandcastles, beach balls & swim rings, with boats out on the water and palms
    # & shrubs framing the dunes).  Lots of variety, grouped so it still reads.
    # Composed seaside "vignettes": loungers tucked under umbrellas/cabanas facing
    # the sea, natural finds hugging the waterline, an open play lawn left clear, and
    # the pier as the central feature. (Redesigned 2026-06-08.)
    area.props = [
        # --- backdrop: keep the headland palm row + a few shrubs on the dunes ---
        ("palm", 1, 2), ("palm", 4, 2), ("palm", 8, 2), ("palm", 12, 2), ("palm", 16, 2),
        ("palm", 26, 2), ("palm", 30, 2), ("palm", 34, 2), ("palm", 38, 2), ("palm", 41, 2),
        ("bush", 5, 5), ("bush", 11, 5), ("bush", 31, 5), ("bush", 35, 5),
        # --- open play lawn (gy8-12 deliberately left clear): two beach balls ---
        ("beach_ball", 15, 10), ("beach_ball", 25, 9),
        # --- V1: left cabana, loungers under it, towel + ring beside ---
        ("cabana", 6, 14), ("sun_lounger", 5, 15), ("sun_lounger", 7, 15),
        ("towel_yellow", 6, 16), ("swim_ring", 4, 15),
        # --- V2: left-centre parasol ---
        ("parasol", 13, 14), ("sun_lounger", 12, 15), ("sun_lounger", 14, 15),
        ("bucket", 13, 16),
        # --- V3: right-centre parasol ---
        ("parasol", 28, 14), ("sun_lounger", 27, 15), ("sun_lounger", 29, 15),
        ("towel_pink", 28, 16),
        # --- V4: right cabana ---
        ("cabana", 34, 14), ("sun_lounger", 33, 15), ("sun_lounger", 35, 15),
        ("swim_ring", 36, 15),
        # --- kids' sandcastle corner near the left shore ---
        ("sandcastle", 9, 18), ("sandcastle", 10, 18), ("bucket", 8, 19),
        ("bucket", 11, 18), ("beach_ball", 9, 17),
        # --- the pier as the central feature (props on the sand beside its foot) ---
        ("lifebuoy", 19, 17), ("surfboard", 22, 17), ("driftwood", 22, 19),
        ("boat", 18, 26), ("boat", 37, 26),                 # sailboats out on the water
        # --- natural finds hugging the wet sand near the waterline ---
        ("seashell", 2, 20), ("seashell", 4, 19), ("seashell", 16, 20), ("seashell", 32, 19),
        ("starfish", 3, 20), ("starfish", 17, 20), ("starfish", 31, 20), ("starfish", 33, 20),
        ("message_bottle", 15, 21), ("driftwood", 30, 20),
    ]
    # only "structural" props block movement (you can stroll under umbrellas / past
    # towels & loungers); palms, shrubs, sandcastles, cabanas and the post are solid.
    area.solid_extra = {(gx, gy) for (k, gx, gy) in area.props
                        if k in ("palm", "bush", "sandcastle", "lifebuoy", "cabana")}
    # the RIGHT-most cabana is a hidden anniversary gift: standing beside it and
    # pressing together (both players) opens anniversary.html. Derive its tile from
    # the props so there's no second hard-coded coordinate -- the eastern-most cabana.
    _cabanas = [(gx, gy) for (k, gx, gy) in area.props if k == "cabana"]
    area.anniv_cabana = max(_cabanas) if _cabanas else None
    # small coastal-rock clusters hugging the waterline (decor -- walkable, so they
    # never wall off the beach; some poke a tile into the surf for a "rocks in the
    # waves" look). Positions snap to the LIVE shoreline so they always sit on the
    # wet-sand / water edge. (Replaces the 3 oversized grey boulders mid-sand.)
    def _shore_row(cx):
        return next((yy for yy in range(4, h) if g[yy][cx] == WATER), h)
    for cx in (3, 4, 8, 9, 27, 28, 37, 38):        # wet-sand edge of each cluster
        sy = _shore_row(cx)
        if 4 <= sy - 1 < h and g[sy - 1][cx] == SAND2:
            area.props.append(("shore_rock", cx, sy - 1))
    for cx in (4, 8, 28, 38):                       # one stone awash at the wave edge
        sy = _shore_row(cx)
        # only ever the very first water tile (the wave edge, <=1 past the sand) and
        # submerged so just the top pokes out -- never a full rock floating offshore
        if sy < h and g[sy][cx] == WATER and g[sy - 1][cx] == SAND2:
            area.props.append(("shore_rock_sub", cx, sy))
    area.rocks = {}                                 # no big mineable boulders on the beach
    # ambient crabs scuttle along the wet sand near the shore (Core reads this list
    # in _spawn_area_entities; purely decorative). Moved down to gy19-20, near water.
    area.crab_spawns = [(gx, gy) for (gx, gy) in
                        [(9, 19), (14, 19), (24, 20), (28, 19), (32, 20), (38, 19)]
                        if area.tile(gx, gy) in (SAND, SAND2) and (gx, gy) not in area.solid_extra]
    # warp back up the trail to the farm (top-left grass).  Spawn one tile IN from
    # the farm's right edge so neither co-op player lands on the farm->beach warp
    # tile (41,22/23) -- otherwise player 2 would instantly bounce back here.
    area.warps.append({"gx": 3, "gy": 0, "to": AREA_FARM, "spawn": (39, 22)})
    area.warps.append({"gx": 4, "gy": 0, "to": AREA_FARM, "spawn": (39, 23)})
    return area


def _mine_biome(level):
    """Map mine depth -> (biome name, walkable floor tile).  Borders stay WALL."""
    if level <= 4:
        return "rock", FLOOR
    if level <= 9:
        return "ice", ICE
    if level <= 14:
        return "lava", LAVA
    if level <= 19:
        return "crystal", CRYSTAL
    if level <= 29:
        return "abyss", ABYSS
    return "ruins", RUINS


def _mine_features(area, level, seed, w, h):
    """Biome hazards + decor (lava pools, void rifts, ancient ruins).  Uses its own
    RNG so the rock/monster layout of the older biomes is byte-for-byte unchanged.
    Hazards are walkable decals (never on the entry, warps, ladder or a rock), so
    they can never block the route; solid ruins decor keeps clear of both ends."""
    biome = area.biome
    if biome not in ("lava", "abyss", "ruins"):
        return
    rng = random.Random((seed if seed is not None else level * 99 + 1) * 7 + 13)
    lx, ly = area.ladder
    spawn_zone = {(x, y) for x in range(2, 11) for y in range(1, 7)}
    ladder_zone = {(x, y) for x in range(lx - 2, lx + 3) for y in range(ly - 2, ly + 3)}
    banned = spawn_zone | ladder_zone

    def free(x, y):
        return (1 <= x < w - 1 and 1 <= y < h - 1 and (x, y) not in banned
                and (x, y) not in area.rocks and (x, y) not in area.hazards
                and (x, y) not in area.solid_extra)

    if biome in ("lava", "abyss"):
        kind = "lava" if biome == "lava" else "rift"
        n_pools = rng.randint(4, 6) if kind == "lava" else rng.randint(5, 7)
        for _ in range(n_pools * 6):
            if n_pools <= 0:
                break
            x, y = rng.randint(3, w - 4), rng.randint(3, h - 4)
            if not free(x, y):
                continue
            n_pools -= 1
            area.hazards[(x, y)] = kind
            if kind == "lava":                         # pools spread over 1-3 tiles
                for (dx, dy) in rng.sample([(1, 0), (0, 1), (-1, 0), (0, -1)], rng.randint(0, 2)):
                    if free(x + dx, y + dy):
                        area.hazards[(x + dx, y + dy)] = kind
    if biome == "abyss":                               # jagged void crystals (solid)
        for _ in range(30):
            x, y = rng.randint(3, w - 4), rng.randint(3, h - 4)
            if free(x, y) and len([p for p in area.props if p[0] == "abyss_shard"]) < 5:
                area.props.append(("abyss_shard", x, y))
                area.solid_extra.add((x, y))
    if biome == "ruins":
        # broken colonnades: short rows of pillars with a gap you can walk through
        placed = 0
        for _ in range(40):
            if placed >= 3:
                break
            x, y = rng.randint(4, w - 9), rng.randint(4, h - 5)
            cells = [(x, y), (x + 3, y), (x + 6, y)]
            if all(free(cx, cy) and free(cx, cy - 1) for (cx, cy) in cells):
                for i, (cx, cy) in enumerate(cells):
                    kind = "ruin_broken" if (i + placed) % 3 == 1 else "ruin_pillar"
                    area.props.append((kind, cx, cy))
                    area.solid_extra.add((cx, cy))
                placed += 1
        for kind, n in (("ruin_statue", 2), ("ruin_rubble", 7), ("ruin_glyph", 4)):
            for _ in range(n * 8):
                if n <= 0:
                    break
                x, y = rng.randint(2, w - 3), rng.randint(2, h - 3)
                if free(x, y):
                    area.props.append((kind, x, y))
                    if kind == "ruin_statue":
                        area.solid_extra.add((x, y))
                    else:
                        area.hazards.pop((x, y), None)
                    n -= 1


def build_mine(level=1, seed=None):
    w, h = 34, 26
    biome, floor = _mine_biome(level)
    g = _blank(w, h, floor)
    rng = random.Random(seed if seed is not None else level * 99 + 1)
    # stone walls border (WALL in every biome -> collision unchanged)
    for y in range(h):
        for x in range(w):
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                g[y][x] = WALL
    area = Area(AREA_MINE, _rows(g))
    area.level = level
    area.biome = biome
    # subtle per-biome ore bias (existing ore ids only, economy kept balanced):
    # ice favours copper a touch, lava favours iron, crystal favours gold.
    # abyss favours iron + gold a touch, the ancient ruins favour gold (still modest).
    cu_b = 0.01 if biome == "ice" else 0.0
    fe_b = {"lava": 0.01, "abyss": 0.015}.get(biome, 0.0)
    au_b = {"crystal": 0.01, "abyss": 0.012, "ruins": 0.02}.get(biome, 0.0)
    # scatter breakable rocks (objects) with chance of ore
    for _ in range(70 + level * 4):
        x = rng.randint(2, w - 2); y = rng.randint(2, h - 2)
        # keep the entry clear for BOTH players (warp puts P2 at sx+1) and the ladder
        if (x, y) in ((5, 3), (6, 3), (7, 3)) or (x, y) == (w - 4, h - 4):
            continue
        r = rng.random()
        ore = None
        if r < 0.10 + level * 0.01 + cu_b:
            ore = "copper"
        if r < 0.05 + level * 0.008 + fe_b:
            ore = "iron"
        if r < 0.02 + au_b:
            ore = "gold"
        area.rocks[(x, y)] = ore
    # ladder down (revealed after clearing? simple: fixed spot)
    area.ladder = (w - 4, h - 4)
    # warp back up to town from entrance
    area.warps.append({"gx": 5, "gy": 1, "to": AREA_TOWN, "spawn": (3, 27)})
    area.warps.append({"gx": 6, "gy": 1, "to": AREA_TOWN, "spawn": (4, 27)})
    # biome hazards / ruins decor (own RNG -> older biomes unchanged)
    _mine_features(area, level, seed, w, h)
    # monster spawn points
    area.monster_spawns = []
    for _ in range(3 + level):
        x = rng.randint(w // 2, w - 3); y = rng.randint(3, h - 3)
        if (x, y) not in area.rocks and (x, y) not in area.solid_extra:
            area.monster_spawns.append((x, y))
    return area


class World:
    def __init__(self):
        self.areas = {
            AREA_FARM: build_farm(),
            AREA_TOWN: build_town(),
            AREA_MINE: build_mine(1),
            AREA_HOME: build_home(),
            AREA_FOREST: build_forest(),
            AREA_TEMPLE: build_temple(),
            AREA_COOP: build_coop(),
            AREA_BEACH: build_beach(),
            AREA_MEADOW: build_meadow(),
        }
        self.current = AREA_FARM
        # farming state keyed by (area, gx, gy)
        self.tilled = set()
        self.watered = set()
        self.crops = {}           # (area, gx, gy) -> Crop
        self.farm_objects = {}    # (gx, gy) -> kind  (e.g. "sprinkler") on the farm
        self.mine_level = 1
        # house customisation (Sims-style) -- cosy pastel defaults + starter set.
        # (A loaded save replaces all of this with the player's own house.)
        from . import furniture as _Fdef
        self.home_furniture = _Fdef.default_home_furniture()
        self.home_wall_idx = 3     # lavender wallpaper
        self.home_floor_idx = 2    # light warm wood
        self.friend = {}           # npc name -> friendship points
        self.refresh_home_solids()

    @property
    def area(self):
        return self.areas[self.current]

    def regen_mine(self, level):
        self.mine_level = level
        self.areas[AREA_MINE] = build_mine(level)

    def furniture_at(self, gx, gy):
        """The piece to interact with on a cell: the newest real piece there,
        a rug only when nothing stands on it (a chair on a rug is sat on, the
        rug is never 'straightened' instead)."""
        from . import furniture as _F
        rug = None
        for pl in reversed(self.home_furniture):
            if (gx, gy) in pl.cells():
                if _F.CAT[pl.kind]["layer"] != "floor":
                    return pl
                rug = rug or pl
        return rug

    def refresh_home_solids(self):
        """Recompute which home cells block movement (non-floor furniture + bed)."""
        from . import furniture as _F
        home = self.areas[AREA_HOME]
        cells = set()
        for pl in self.home_furniture:
            if _F.CAT[pl.kind]["layer"] == "ground":   # rugs & wall decor never block
                cells.update(pl.cells())
        # the bed is a regular furniture piece; derive the sleep anchor from
        # wherever the player has moved it (its cells are already solid above)
        bed = next((pl for pl in self.home_furniture if pl.kind == "bed"), None)
        home.bed = (bed.gx, bed.gy) if bed else None
        # exit-door tiles must always stay walkable, even if an old save placed
        # furniture on them -- otherwise the players get trapped in the house
        for wdef in home.warps:
            cells.discard((wdef["gx"], wdef["gy"]))
        home.solid_extra = cells
        # clear mine crops/tilled (none expected) but keep farm
