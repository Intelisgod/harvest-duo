"""Global constants and configuration for Harvest Duo."""

# ---- Display ----
TILE = 48                      # pixel size of one tile
SCREEN_W = 1280
SCREEN_H = 720
FPS = 60
TITLE = "Harvest Duo - Co-op Farm (Stardew-style)"

# ---- Colors (soft pastel scheme) ----
BLACK = (0, 0, 0)
WHITE = (250, 248, 252)
DARK = (44, 40, 58)
UI_BG = (54, 48, 68)
UI_BORDER = (120, 106, 144)
GOLD = (246, 214, 124)
GREEN = (132, 200, 130)
RED = (230, 124, 128)
BLUE = (138, 182, 226)

# Tile palette (pastel: mint grass, cream paths, powder-blue water, soft slate stone)
COL_GRASS = (160, 206, 150)
COL_GRASS2 = (146, 196, 138)
COL_DIRT = (200, 172, 132)
COL_TILLED = (158, 118, 86)
COL_TILLED_WET = (122, 92, 68)
COL_PATH = (222, 202, 162)
COL_WATER = (150, 206, 226)
COL_WATER2 = (174, 220, 236)
COL_STONE = (192, 194, 208)
COL_STONE_DARK = (150, 150, 170)
COL_WALL = (180, 154, 132)
COL_FLOOR = (218, 198, 168)
COL_SAND = (236, 218, 168)      # warm beach sand
COL_SAND2 = (224, 204, 150)     # damp sand near the tideline

# ---- Time ----
# Real seconds per in-game 10-minute step
SECONDS_PER_STEP = 1.4
DAY_START_MIN = 6 * 60          # 06:00
DAY_END_MIN = 26 * 60           # 02:00 next day -> forced sleep
DAYS_PER_SEASON = 28
SEASONS = ["Spring", "Summer", "Fall", "Winter"]

# ---- Player ----
PLAYER_SPEED = 200              # px / sec
MAX_ENERGY = 270
MAX_HEALTH = 100
TOOL_ENERGY = 2                 # energy per tool swing

# ---- Areas ----
AREA_FARM = "farm"
AREA_TOWN = "town"
AREA_MINE = "mine"
AREA_HOME = "home"
AREA_FOREST = "forest"
AREA_TEMPLE = "temple"
AREA_COOP = "coop"
AREA_BEACH = "beach"
AREA_MEADOW = "meadow"     # flower meadow / lookout (World chat, 2026-09 upgrade)
AREA_MIST = "mistcity"   # Mist City side-scroller mode (src/mistcity/, Chat 7)

# ---- Controls ----
# Player 1: WASD + Space, tool cycle Q/E
# Player 2: Arrows + Return, tool cycle , / .
import pygame

P1_KEYS = {
    "up": pygame.K_w, "down": pygame.K_s, "left": pygame.K_a, "right": pygame.K_d,
    "action": pygame.K_SPACE, "prev": pygame.K_q, "next": pygame.K_e,
    "emote": pygame.K_f,
}
P2_KEYS = {
    "up": pygame.K_UP, "down": pygame.K_DOWN, "left": pygame.K_LEFT, "right": pygame.K_RIGHT,
    "action": pygame.K_RETURN, "prev": pygame.K_COMMA, "next": pygame.K_PERIOD,
    "emote": pygame.K_SLASH,
}

# single-purpose hotkeys -- single source of truth (TASK_no_hardcode): the
# on_keydown handler AND any "Press X" label must read these, never a literal.
BUILD_KEY = pygame.K_b          # enter Build mode (inside the house)
JOURNAL_KEY = pygame.K_j        # open the Journal (tabs contributed by every domain)

# pristine copies so the Settings screen can restore defaults after rebinding
DEFAULT_P1_KEYS = dict(P1_KEYS)
DEFAULT_P2_KEYS = dict(P2_KEYS)
# order + labels shown in the controls screen
KEY_ACTIONS = [("up", "Up"), ("down", "Down"), ("left", "Left"), ("right", "Right"),
               ("action", "Use"), ("prev", "Prev Tool"), ("next", "Next Tool"),
               ("emote", "Emote")]
# NOTE: older settings.json files have no "emote" binding -- SaveMixin._apply_settings
# MERGES saved codes into these dicts (never replaces them), so the defaults above
# survive. Code reading an optional action should still use K.get("emote").
