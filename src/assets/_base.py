"""Shared primitives for the procedurally-generated sprite package.

Every sprite module imports its low-level helpers, palettes and the shared
surface cache from here. Keep cross-cutting constants/helpers in this file so
the per-domain modules (chars, terrain, items, props) only depend on _base and
never on each other.
"""
import pygame
from ..settings import TILE

# One shared surface cache for the whole package: generation happens once and
# every module reads/writes the SAME dict (imported by reference).
_cache = {}

PANTS = (58, 50, 72)
SHOE = (40, 35, 46)

# customisation palettes (used by the character creator)
SKIN_TONES = [(248, 220, 190), (240, 200, 165), (224, 178, 140),
              (196, 150, 116), (162, 120, 92), (130, 95, 72)]
HAIR_COLORS = [(54, 42, 38), (92, 60, 40), (150, 96, 52), (214, 178, 96),
               (226, 228, 234), (196, 72, 60), (96, 80, 150), (210, 120, 160)]
SHIRT_COLORS = [(206, 74, 70), (74, 122, 200), (94, 172, 96), (232, 198, 86),
                (158, 100, 184), (228, 142, 172), (74, 170, 168), (150, 102, 64)]
HAIR_STYLES = ["short", "long", "ponytail", "spiky", "bun", "cap", "bald"]

# hotbar/item icon palette
IC = 28
WOOD = (140, 95, 55)
STEEL = (200, 205, 215)

# how each crop's produce is drawn, so they don't all look the same
CROP_FORM = {
    "parsnip": "root", "potato": "root", "cauliflower": "gourd", "green_bean": "pod",
    "melon": "gourd", "tomato": "fruit", "blueberry": "berry", "pepper": "fruit",
    "pumpkin": "gourd", "corn": "cob", "cranberry": "berry", "eggplant": "fruit",
    "winter_root": "root", "snow_yam": "root", "crocus": "flower", "frost_melon": "gourd",
}
FISH_LOOK = {"anchovy": (150, 160, 180), "sardine": (178, 188, 198), "carp": (150, 178, 128),
             "tuna": (84, 120, 186), "catfish": (120, 104, 80), "pufferfish": (220, 206, 120),
             # new common / uncommon
             "bluegill": (96, 150, 190), "sunfish": (224, 196, 96), "perch": (150, 170, 110),
             "bass": (108, 150, 110), "salmon": (224, 138, 120), "pike": (120, 160, 120),
             # rare
             "sturgeon": (110, 120, 130), "eel": (96, 110, 90), "rainbow_trout": (170, 150, 210),
             # legendary (warm gold)
             "crimson_bass": (208, 80, 80), "glacier_pike": (150, 210, 230),
             "the_legend": (236, 200, 96),
             # leviathan / eldritch (sickly purples & voids)
             "void_eel": (96, 60, 140), "phantom_carp": (150, 170, 200),
             "unseeing_maw": (150, 70, 150), "the_leviathan": (90, 50, 120),
             # --- sea fish (saltwater) ---
             # common: silvery schooling fish
             "herring": (186, 198, 208), "mackerel": (92, 142, 162),
             # uncommon
             "cod": (156, 158, 126), "red_snapper": (210, 92, 84),
             # rare
             "halibut": (132, 126, 114), "swordfish": (96, 124, 168),
             # legendary (sea apex)
             "coelacanth": (74, 100, 134), "golden_swordfish": (236, 200, 96),
             "abyssal_tuna": (52, 96, 120),
             # leviathan (sea eldritch)
             "kraken_spawn": (112, 60, 132), "maelstrom_ray": (60, 116, 128)}

# held-tool grip metadata (consumed by entities when rendering a carried tool)
HELD_TWO_HAND = {"hoe", "pickaxe", "axe"}
HELD_ONE_HAND = {"watering_can", "sword", "fishing_rod"}
CAN_BLUE = (70, 140, 200)
GOLD_HILT = (210, 175, 90)


def resolve_appearance(a):
    return (SKIN_TONES[a.get("skin", 0) % len(SKIN_TONES)],
            HAIR_STYLES[a.get("hair_style", 0) % len(HAIR_STYLES)],
            HAIR_COLORS[a.get("hair_color", 0) % len(HAIR_COLORS)],
            SHIRT_COLORS[a.get("shirt_color", 0) % len(SHIRT_COLORS)])


def _surf(size=None):
    if size is None:
        size = (TILE, TILE)
    return pygame.Surface(size, pygame.SRCALPHA)


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _lt(c, f=1.3):
    return tuple(min(255, int(v * f)) for v in c)


def _dk(c, f=0.7):
    return tuple(max(0, int(v * f)) for v in c)


def _ic():
    return pygame.Surface((IC, IC), pygame.SRCALPHA)


_bld_font = None


def _bldfont():
    global _bld_font
    if _bld_font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _bld_font = pygame.font.SysFont("arialroundedmtbold,arial", 15, bold=True)
    return _bld_font


def _I(p):
    return (int(p[0]), int(p[1]))


def shadow(w=26, h=10):
    key = ("shadow", w, h)
    if key in _cache:
        return _cache[key]
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (0, 0, 0, 90), (0, 0, w, h))
    _cache[key] = s
    return s
