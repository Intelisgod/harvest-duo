"""Monster archetypes, biome/depth-banded spawning and stat scaling.

Data + pure helpers, so the spawn logic and scaling are unit-testable.
entities.Monster reads an archetype dict from here and builds itself.
Biome natives (ice/lava/crystal/abyss/ruins) + the deep bosses get their AI from
monster_ai.py and their art from monster_shapes.py (both imported at the bottom
and registered into BEHAVIORS / SHAPE_PAINTERS).
"""
import random

# ---- extension registries (read by entities.Monster; fill them from THIS file) ----
# SHAPE_PAINTERS[shape] = fn(monster, surf, cx, cy)   draw a new body shape
#   (cx, cy = screen-space centre; use monster.color/size/anim_t/facing_left/phase)
# BEHAVIORS[name] = fn(monster, dt, players, area, target, ux, uy, dist) -> (ux, uy) | None
#   steer a new AI behaviour; (ux, uy) is the unit direction toward the nearest player
SHAPE_PAINTERS = {}
BEHAVIORS = {}

# Each archetype:
#   shape   : how entities.Monster draws it ("slime"/"bat"/"skeleton"/"golem"/"spirit")
#   size    : body half-extent in px (collision + draw)
#   base_hp / hp_per_depth, base_damage / dmg_per_depth : stat scaling with depth
#   speed   : px/sec
#   behavior: "chase" (straight at nearest player) or "erratic" (weaving)
#   xp      : combat XP granted on kill
#   gold    : (min, max) coins dropped
#   drops   : list of (item_id, chance 0..1, (min_qty, max_qty))
#   min_depth / max_depth : mine levels where it can appear (max None = unlimited)
#   weight  : relative spawn weight while eligible
ARCHETYPES = {
    "green_slime": {
        "label": "Green Slime", "shape": "slime", "color": (96, 200, 120), "size": 16,
        "base_hp": 14, "hp_per_depth": 2, "speed": 60, "base_damage": 5, "dmg_per_depth": 0.4,
        "behavior": "chase", "xp": 4, "gold": (3, 9),
        "drops": [("slime_goo", 0.85, (1, 2))],
        "min_depth": 1, "max_depth": 8, "weight": 3.0, "biomes": ("rock",),
    },
    "bat": {
        "label": "Cave Bat", "shape": "bat", "color": (124, 96, 152), "size": 12,
        "base_hp": 10, "hp_per_depth": 1.5, "speed": 112, "base_damage": 6, "dmg_per_depth": 0.4,
        "behavior": "erratic", "xp": 6, "gold": (5, 12),
        "drops": [("bat_wing", 0.75, (1, 2))],
        "min_depth": 3, "max_depth": 13, "weight": 2.2, "biomes": ("rock",),
    },
    "frost_slime": {
        "label": "Frost Jelly", "shape": "slime", "color": (92, 152, 222), "size": 17,
        "base_hp": 22, "hp_per_depth": 2.5, "speed": 72, "base_damage": 7, "dmg_per_depth": 0.5,
        "behavior": "chase", "xp": 8, "gold": (8, 16),
        "drops": [("slime_goo", 0.9, (1, 3)), ("iron", 0.15, (1, 1))],
        "min_depth": 5, "max_depth": 15, "weight": 2.0, "biomes": ("ice",),
    },
    "skeleton": {
        "label": "Skeleton", "shape": "skeleton", "color": (226, 222, 210), "size": 15,
        "base_hp": 30, "hp_per_depth": 3, "speed": 82, "base_damage": 10, "dmg_per_depth": 0.6,
        "behavior": "chase", "xp": 11, "gold": (12, 24),
        "drops": [("bone", 0.8, (1, 2)), ("gold_ore", 0.10, (1, 1))],
        "min_depth": 7, "max_depth": None, "weight": 2.0, "biomes": ("ice", "lava", "ruins"),
    },
    "zombie": {
        "label": "Cleaver Zombie", "shape": "zombie", "color": (104, 150, 96), "size": 16,
        "base_hp": 44, "hp_per_depth": 3, "speed": 50, "base_damage": 13, "dmg_per_depth": 0.6,
        "behavior": "chase", "xp": 13, "gold": (14, 28),
        "drops": [("bone", 0.6, (1, 2)), ("essence", 0.18, (1, 1)), ("gold_ore", 0.06, (1, 1))],
        "min_depth": 6, "max_depth": None, "weight": 1.4, "biomes": ("ice", "lava", "abyss"),
    },
    "golem": {
        "label": "Stone Golem", "shape": "golem", "color": (122, 122, 136), "size": 20,
        "base_hp": 55, "hp_per_depth": 4, "speed": 46, "base_damage": 14, "dmg_per_depth": 0.7,
        "behavior": "chase", "xp": 16, "gold": (18, 30),
        "drops": [("stone", 0.9, (2, 5)), ("essence", 0.4, (1, 1)), ("iridium_ore", 0.08, (1, 1))],
        "min_depth": 10, "max_depth": None, "weight": 1.5, "biomes": ("lava", "crystal"),
    },
    "void_spirit": {
        "label": "Void Spirit", "shape": "spirit", "color": (124, 80, 178), "size": 16,
        "base_hp": 45, "hp_per_depth": 3.5, "speed": 96, "base_damage": 13, "dmg_per_depth": 0.6,
        "behavior": "erratic", "xp": 22, "gold": (25, 45),
        "drops": [("void_essence", 0.7, (1, 2)), ("essence", 0.5, (1, 2)), ("gold_ore", 0.2, (1, 1))],
        "min_depth": 14, "max_depth": None, "weight": 1.6, "biomes": ("crystal", "abyss"),
    },

    # ---- BIOME natives (Chat 1 level-up): each biome has its own archetypes.
    #      "biomes" limits where they spawn; shapes/behaviours are registered in
    #      monster_shapes.py / monster_ai.py. "armor" = fraction of melee damage
    #      shrugged off (combat_system reads it). ----
    "ice_bat": {
        "label": "Frost Bat", "shape": "icebat", "color": (150, 206, 240), "size": 12,
        "base_hp": 16, "hp_per_depth": 1.6, "speed": 118, "base_damage": 7, "dmg_per_depth": 0.45,
        "behavior": "swoop", "xp": 8, "gold": (8, 15),
        "drops": [("bat_wing", 0.7, (1, 2)), ("amethyst", 0.05, (1, 1))],
        "min_depth": 5, "max_depth": 9, "weight": 2.4, "biomes": ("ice",),
    },
    "snow_golem": {
        "label": "Snow Golem", "shape": "snowgolem", "color": (236, 244, 252), "size": 17,
        "base_hp": 34, "hp_per_depth": 3, "speed": 50, "base_damage": 9, "dmg_per_depth": 0.5,
        "behavior": "lob", "xp": 12, "gold": (10, 20),
        "drops": [("stone", 0.5, (1, 3)), ("iron", 0.2, (1, 1)), ("amethyst", 0.08, (1, 1))],
        "min_depth": 5, "max_depth": 9, "weight": 1.6, "biomes": ("ice",),
    },
    "magma_slime": {
        "label": "Magma Slime", "shape": "magma", "color": (236, 104, 60), "size": 17,
        "base_hp": 34, "hp_per_depth": 3, "speed": 74, "base_damage": 11, "dmg_per_depth": 0.6,
        "behavior": "hop", "xp": 13, "gold": (14, 26),
        "drops": [("slime_goo", 0.8, (1, 3)), ("iron", 0.15, (1, 1)), ("ruby", 0.06, (1, 1))],
        "min_depth": 10, "max_depth": 14, "weight": 2.2, "biomes": ("lava",),
    },
    "fire_imp": {
        "label": "Fire Imp", "shape": "imp", "color": (226, 84, 70), "size": 13,
        "base_hp": 26, "hp_per_depth": 2.5, "speed": 88, "base_damage": 9, "dmg_per_depth": 0.5,
        "behavior": "imp", "xp": 15, "gold": (16, 28),
        "drops": [("essence", 0.35, (1, 1)), ("bat_wing", 0.3, (1, 1)), ("ruby", 0.07, (1, 1))],
        "min_depth": 10, "max_depth": 14, "weight": 1.8, "biomes": ("lava",),
    },
    "crystal_golem": {
        "label": "Crystal Golem", "shape": "crystalgolem", "color": (172, 142, 232), "size": 19,
        "base_hp": 70, "hp_per_depth": 4, "speed": 48, "base_damage": 15, "dmg_per_depth": 0.7,
        "behavior": "chase", "xp": 20, "gold": (22, 36), "armor": 0.2,
        "drops": [("essence", 0.4, (1, 1)), ("gold_ore", 0.2, (1, 1)), ("emerald", 0.08, (1, 1))],
        "min_depth": 15, "max_depth": 19, "weight": 1.7, "biomes": ("crystal",),
    },
    "prism_wisp": {
        "label": "Prism Wisp", "shape": "prism", "color": (150, 230, 220), "size": 12,
        "base_hp": 32, "hp_per_depth": 2.5, "speed": 96, "base_damage": 12, "dmg_per_depth": 0.6,
        "behavior": "blink", "xp": 20, "gold": (20, 34),
        "drops": [("essence", 0.55, (1, 2)), ("emerald", 0.07, (1, 1))],
        "min_depth": 15, "max_depth": 19, "weight": 2.0, "biomes": ("crystal",),
    },
    "shadow_stalker": {
        "label": "Shadow Stalker", "shape": "stalker", "color": (92, 78, 134), "size": 16,
        "base_hp": 60, "hp_per_depth": 3.5, "speed": 70, "base_damage": 18, "dmg_per_depth": 0.7,
        "behavior": "stalk", "xp": 26, "gold": (30, 48),
        "drops": [("void_essence", 0.45, (1, 1)), ("bone", 0.4, (1, 2)), ("diamond", 0.05, (1, 1))],
        "min_depth": 20, "max_depth": 29, "weight": 2.0, "biomes": ("abyss",),
    },
    "abyss_wraith": {
        "label": "Abyss Wraith", "shape": "wraith", "color": (96, 178, 196), "size": 15,
        "base_hp": 55, "hp_per_depth": 3.5, "speed": 104, "base_damage": 16, "dmg_per_depth": 0.6,
        "behavior": "erratic", "xp": 24, "gold": (26, 44),
        "drops": [("void_essence", 0.6, (1, 2)), ("diamond", 0.04, (1, 1))],
        "min_depth": 20, "max_depth": 29, "weight": 1.6, "biomes": ("abyss",),
    },
    "ruin_guardian": {
        "label": "Ruin Guardian", "shape": "guardian", "color": (176, 166, 136), "size": 19,
        "base_hp": 110, "hp_per_depth": 4.5, "speed": 40, "base_damage": 20, "dmg_per_depth": 0.8,
        "behavior": "chase", "xp": 32, "gold": (36, 60), "armor": 0.4,
        "drops": [("stone", 0.8, (2, 4)), ("gold_ore", 0.35, (1, 2)), ("ancient_relic", 0.03, (1, 1))],
        "min_depth": 30, "max_depth": None, "weight": 1.6, "biomes": ("ruins",),
    },
    "cursed_knight": {
        "label": "Cursed Knight", "shape": "knight", "color": (88, 96, 124), "size": 16,
        "base_hp": 80, "hp_per_depth": 4, "speed": 76, "base_damage": 22, "dmg_per_depth": 0.8,
        "behavior": "lunge", "xp": 34, "gold": (38, 64), "armor": 0.15,
        "drops": [("void_essence", 0.4, (1, 2)), ("iridium_ore", 0.2, (1, 1)), ("diamond", 0.05, (1, 1))],
        "min_depth": 30, "max_depth": None, "weight": 1.8, "biomes": ("ruins",),
    },

    # ---- mine BOSSES (one per 5 floors; chosen by boss_for_depth) ----
    "slime_king": {
        "label": "Slime King", "shape": "slime", "color": (70, 184, 204), "size": 30,
        "base_hp": 160, "hp_per_depth": 14, "speed": 50, "base_damage": 16, "dmg_per_depth": 0.8,
        "behavior": "chase", "xp": 60, "gold": (120, 200), "boss": True, "group": "boss",
        "drops": [("slime_goo", 1.0, (5, 8)), ("essence", 0.8, (1, 2)), ("iridium_ore", 0.6, (1, 2)),
                  ("amethyst", 0.6, (1, 2))],
        "min_depth": 5, "max_depth": None, "weight": 1.0,
    },
    "rock_titan": {
        "label": "Rock Titan", "shape": "golem", "color": (150, 140, 120), "size": 34,
        "base_hp": 300, "hp_per_depth": 18, "speed": 40, "base_damage": 22, "dmg_per_depth": 1.0,
        "behavior": "chase", "xp": 110, "gold": (220, 360), "boss": True, "group": "boss",
        "drops": [("stone", 1.0, (8, 14)), ("iridium_ore", 0.8, (2, 4)), ("essence", 1.0, (2, 3)),
                  ("ruby", 0.6, (1, 2))],
        "min_depth": 10, "max_depth": None, "weight": 1.0,
    },
    "void_overlord": {
        "label": "Void Overlord", "shape": "spirit", "color": (112, 60, 172), "size": 30,
        "base_hp": 380, "hp_per_depth": 20, "speed": 90, "base_damage": 24, "dmg_per_depth": 1.0,
        "behavior": "erratic", "xp": 160, "gold": (320, 520), "boss": True, "group": "boss",
        "drops": [("void_essence", 1.0, (3, 6)), ("iridium_ore", 1.0, (3, 5)), ("gold_ore", 1.0, (3, 6)),
                  ("emerald", 0.6, (1, 2))],
        "min_depth": 15, "max_depth": None, "weight": 1.0,
    },
    "abyss_wyrm": {
        "label": "Abyss Wyrm", "shape": "wyrm", "color": (92, 74, 156), "size": 24,
        "base_hp": 520, "hp_per_depth": 22, "speed": 92, "base_damage": 24, "dmg_per_depth": 1.0,
        "behavior": "wyrm", "xp": 220, "gold": (420, 640), "boss": True, "group": "boss",
        "title": "Serpent of the Deep",
        "drops": [("void_essence", 1.0, (4, 7)), ("iridium_ore", 1.0, (3, 5)),
                  ("diamond", 0.8, (1, 2)), ("prismatic_shard", 0.25, (1, 1))],
        "min_depth": 20, "max_depth": None, "weight": 1.0,
    },
    "ruin_colossus": {
        "label": "Ruin Colossus", "shape": "colossus", "color": (182, 170, 142), "size": 34,
        "base_hp": 800, "hp_per_depth": 26, "speed": 34, "base_damage": 28, "dmg_per_depth": 1.1,
        "behavior": "colossus", "xp": 300, "gold": (600, 900), "boss": True, "group": "boss",
        "armor": 0.2, "title": "Warden of the Old Kingdom",
        "drops": [("ancient_relic", 1.0, (1, 2)), ("gold_ore", 1.0, (4, 7)),
                  ("diamond", 0.8, (1, 3)), ("prismatic_shard", 0.5, (1, 1))],
        "min_depth": 30, "max_depth": None, "weight": 1.0,
    },

    # ---- FOREST wildlife (overworld hunting; fixed stats, group "forest") ----
    "boar": {
        "label": "Wild Boar", "shape": "boar", "color": (150, 112, 84), "size": 16,
        "base_hp": 28, "hp_per_depth": 0, "speed": 72, "base_damage": 8, "dmg_per_depth": 0,
        "behavior": "chase", "xp": 9, "gold": (8, 16), "group": "forest",
        "drops": [("meat", 0.9, (1, 2)), ("hide", 0.5, (1, 1))],
        "min_depth": 1, "max_depth": 1, "weight": 2.4,
    },
    "deer": {
        "label": "Deer", "shape": "deer", "color": (192, 150, 110), "size": 15,
        "base_hp": 18, "hp_per_depth": 0, "speed": 124, "base_damage": 0, "dmg_per_depth": 0,
        "behavior": "flee", "xp": 6, "gold": (5, 12), "group": "forest",
        "drops": [("meat", 0.9, (1, 2)), ("hide", 0.6, (1, 1))],
        "min_depth": 1, "max_depth": 1, "weight": 2.4,
    },
    "wolf": {
        "label": "Wolf", "shape": "wolf", "color": (132, 132, 142), "size": 14,
        "base_hp": 30, "hp_per_depth": 0, "speed": 122, "base_damage": 10, "dmg_per_depth": 0,
        "behavior": "chase", "xp": 11, "gold": (10, 20), "group": "forest",
        "drops": [("meat", 0.7, (1, 1)), ("pelt", 0.6, (1, 1))],
        "min_depth": 1, "max_depth": 1, "weight": 2.0,
    },
    "bear": {
        "label": "Bear", "shape": "bear", "color": (112, 82, 60), "size": 21,
        "base_hp": 72, "hp_per_depth": 0, "speed": 56, "base_damage": 16, "dmg_per_depth": 0,
        "behavior": "chase", "xp": 18, "gold": (20, 38), "group": "forest",
        "drops": [("meat", 0.95, (2, 4)), ("pelt", 0.7, (1, 2))],
        "min_depth": 1, "max_depth": 1, "weight": 1.3,
    },
    "tiger": {
        "label": "Tiger", "shape": "tiger", "color": (222, 152, 60), "size": 18,
        "base_hp": 60, "hp_per_depth": 0, "speed": 132, "base_damage": 18, "dmg_per_depth": 0,
        "behavior": "chase", "xp": 20, "gold": (25, 45), "group": "forest",
        "drops": [("meat", 0.9, (1, 3)), ("pelt", 0.8, (1, 2))],
        "min_depth": 1, "max_depth": 1, "weight": 1.2,
    },
    "wild_man": {
        "label": "Wild Man", "shape": "wildman", "color": (152, 122, 92), "size": 15,
        "base_hp": 46, "hp_per_depth": 0, "speed": 96, "base_damage": 13, "dmg_per_depth": 0,
        "behavior": "chase", "xp": 16, "gold": (18, 36), "group": "forest",
        "drops": [("hide", 0.6, (1, 2)), ("essence", 0.2, (1, 1)), ("gold_ore", 0.1, (1, 1))],
        "min_depth": 1, "max_depth": 1, "weight": 1.5,
    },
}

# preferred draw order so deeper monsters feel rarer-but-tougher is handled by weights


def hp_for(name, depth):
    a = ARCHETYPES[name]
    return int(a["base_hp"] + a["hp_per_depth"] * max(0, depth - a["min_depth"] + 1))


# Damage tapers on deep floors so a single hit never one-shots a player (max HP
# is 100 + 5 per combat level = 150). Full per-floor growth for the first
# DMG_FULL_STEPS floors past an archetype's min_depth, DMG_TAIL_RATE of it after
# that, then a hard cap (bosses a little higher; the colossus slam is x1.4 ~ 64).
DMG_FULL_STEPS = 20
DMG_TAIL_RATE = 0.3
DMG_CAP = 40
BOSS_DMG_CAP = 46


def damage_for(name, depth):
    a = ARCHETYPES[name]
    steps = max(0, depth - a["min_depth"] + 1)
    eff = min(steps, DMG_FULL_STEPS) + DMG_TAIL_RATE * max(0, steps - DMG_FULL_STEPS)
    cap = a.get("max_damage", BOSS_DMG_CAP if a.get("boss") else DMG_CAP)
    return int(min(cap, round(a["base_damage"] + a["dmg_per_depth"] * eff)))


def is_boss(name):
    return ARCHETYPES.get(name, {}).get("boss", False)


def _weighted(names, rng):
    weights = [ARCHETYPES[n]["weight"] for n in names]
    total = sum(weights)
    r = rng.random() * total
    acc = 0.0
    for n, w in zip(names, weights):
        acc += w
        if r <= acc:
            return n
    return names[-1]


# mine depth -> biome (same table as world.build_mine / area.biome; see
# docs/UPGRADE_2026-09.md): rock 1-4, ice 5-9, lava 10-14, crystal 15-19,
# abyss 20-29, ruins 30+
BIOME_TABLE = [(30, "ruins"), (20, "abyss"), (15, "crystal"), (10, "lava"), (5, "ice"), (1, "rock")]
BIOMES = [b for _d, b in reversed(BIOME_TABLE)]


def biome_for_depth(depth):
    for d, name in BIOME_TABLE:
        if depth >= d:
            return name
    return "rock"


def eligible(depth, biome=None):
    """Mine archetypes that can spawn at ``depth``. Archetypes with a "biomes"
    tuple only spawn in those biomes (biome derived from depth when not given)."""
    biome = biome or biome_for_depth(depth)
    out = []
    for name, a in ARCHETYPES.items():
        if a.get("group", "mine") != "mine":
            continue
        bs = a.get("biomes")
        if bs and biome not in bs:
            continue
        if depth >= a["min_depth"] and (a["max_depth"] is None or depth <= a["max_depth"]):
            out.append(name)
    return out or ["green_slime"]


def spawn_name(depth, rng=random, biome=None):
    return _weighted(eligible(depth, biome), rng)


def forest_spawn_name(rng=random):
    names = [n for n, a in ARCHETYPES.items() if a.get("group") == "forest"]
    return _weighted(names, rng)


def boss_for_depth(depth):
    """Pick the toughest boss whose min_depth has been reached (used on %5 floors)."""
    best = None
    for name, a in ARCHETYPES.items():
        if a.get("group") == "boss" and depth >= a["min_depth"]:
            if best is None or a["min_depth"] > ARCHETYPES[best]["min_depth"]:
                best = name
    return best or "slime_king"


# --- slime sprite art (lives in the monster domain; pygame imported lazily so the
#     spawn/scaling helpers above stay usable in headless unit tests) ------------
_SLIME_CACHE = {}


def slime_frames(color, size=16, n=4, crown=False):
    """Procedural *cute* bouncing-blob frames for slime monsters (list of Surfaces).

    Kawaii style: squat dome body (wider than tall), big glossy highlight, large
    round eyes with a white glint, soft smile. Pass crown=True for the Slime King's
    jeweled gold crown. Scales with `size`; cached per key so we build each set once.
    """
    import math
    import pygame
    from .settings import TILE

    col = tuple(int(max(0, min(255, c))) for c in color)
    size = int(size)
    key = (col, size, n, bool(crown))
    if key in _SLIME_CACHE:
        return _SLIME_CACHE[key]

    dk = tuple(max(0, c - 40) for c in col)
    dk2 = tuple(max(0, c - 78) for c in col)
    lt = tuple(min(255, c + 72) for c in col)
    lt2 = tuple(min(255, c + 125) for c in col)
    d = max(TILE, size * 2 + 16)
    cx = d / 2
    baseline = d / 2 + size * 0.95           # ground line; base stays put while it bounces
    frames = []
    for i in range(n):
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        squash = math.sin(i / n * math.tau)  # -1..1: squash <-> stretch (gentle)
        rx = size * (1.14 + 0.11 * squash)   # always wider than tall -> squat & cute
        ry = size * (0.92 - 0.11 * squash)
        body_h = ry * 1.95
        top = baseline - body_h
        rxi = int(rx)
        rt = rxi                              # fully round top (dome)
        rb = max(2, int(rx * 0.5))            # softly round base
        # contact shadow
        pygame.draw.ellipse(s, (0, 0, 0, 70), (cx - rx * 0.95, baseline - 2, rx * 1.9, rx * 0.4))
        # dome body
        rect = pygame.Rect(int(cx - rx), int(top), rxi * 2, int(body_h))
        pygame.draw.rect(s, col, rect, border_top_left_radius=rt, border_top_right_radius=rt,
                         border_bottom_left_radius=rb, border_bottom_right_radius=rb)
        # soft darker belly pool (kept inside the body)
        pygame.draw.ellipse(s, dk, (cx - rx * 0.82, top + body_h * 0.52,
                                    rx * 1.64, body_h * 0.46))
        # thin soft outline
        pygame.draw.rect(s, dk2, rect, width=max(1, size // 11),
                         border_top_left_radius=rt, border_top_right_radius=rt,
                         border_bottom_left_radius=rb, border_bottom_right_radius=rb)
        # glossy top highlight + tiny sparkle
        hl = pygame.Rect(0, 0, int(rx * 0.78), int(ry * 0.62))
        hl.center = (int(cx - rx * 0.3), int(top + ry * 0.62))
        pygame.draw.ellipse(s, lt, hl)
        pygame.draw.circle(s, lt2, (int(cx - rx * 0.46), int(top + ry * 0.46)),
                           max(1, int(size * 0.13)))
        # big round friendly eyes with pupil + glint
        ey = int(top + body_h * 0.52 + squash)
        esp = rx * 0.36
        er = max(3, int(size * 0.23))
        pr = max(2, int(size * 0.13))
        for ex in (cx - esp, cx + esp):
            pygame.draw.circle(s, (250, 250, 252), (int(ex), ey), er)
            pygame.draw.circle(s, (44, 40, 56), (int(ex), ey + 1), pr)
            pygame.draw.circle(s, (255, 255, 255),
                               (int(ex - er * 0.32), int(ey - er * 0.32)), max(1, int(size * 0.07)))
        # gentle smile
        mw = rx * 0.5
        pygame.draw.arc(s, dk2, (cx - mw / 2, ey + er * 0.5, mw, size * 0.5),
                        3.5, 5.93, max(2, size // 9))
        # rosy cheeks
        cheek = (min(255, col[0] + 70), max(0, col[1] - 6), max(0, col[2] + 6))
        for sgn in (-1, 1):
            pygame.draw.circle(s, cheek, (int(cx + sgn * rx * 0.6), ey + er),
                               max(1, int(size * 0.11)))

        # ---- Slime King's jeweled gold crown ----
        if crown:
            gold = (255, 212, 72); gold_d = (198, 156, 38); gold_lt = (255, 244, 158)
            jewel = (226, 64, 88)
            cw = rx * 1.2
            cyb = int(top + ry * 0.16)               # crown band sits near the dome crest
            bandh = max(4, int(size * 0.34))
            left, right = cx - cw / 2, cx + cw / 2
            pts_n = 5
            step = cw / pts_n
            peak = bandh * 1.5
            poly = [(left, cyb)]
            for kk in range(pts_n):
                x0 = left + kk * step
                poly.append((x0 + step * 0.5, cyb - peak))   # spike
                poly.append((x0 + step, cyb))                # valley
            pygame.draw.polygon(s, gold, poly)
            band = pygame.Rect(int(left), cyb, int(cw), bandh)
            pygame.draw.rect(s, gold, band, border_radius=2)
            pygame.draw.rect(s, gold_d, band, 1, border_radius=2)
            pygame.draw.line(s, gold_lt, (int(left) + 1, cyb + 1), (int(right) - 1, cyb + 1), 1)
            for jx in (cx - cw * 0.28, cx, cx + cw * 0.28):  # band jewels
                pygame.draw.circle(s, jewel, (int(jx), cyb + bandh // 2), max(1, int(size * 0.1)))
            for kk in range(pts_n):                          # gold ball on each spike
                x0 = left + kk * step + step * 0.5
                pygame.draw.circle(s, gold_lt, (int(x0), int(cyb - peak)), max(1, int(size * 0.09)))

        frames.append(s)

    _SLIME_CACHE[key] = frames
    return frames


# ---- register the biome monsters' AI + art (Chat 1). Imported last so the
#      registries above exist; monster_ai is pure math, monster_shapes needs pygame.
from . import monster_ai  # noqa: E402,F401
from . import monster_shapes  # noqa: E402,F401
