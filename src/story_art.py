"""Procedural art for the Story domain (Chat 4): the restoration board and the
golden statue props, festival eggs, story item icons, big heart-event portraits
and small UI hearts. Everything is cached -- call freely every frame.

Registered with the shared registries on import of ``register_all()`` (called
from systems/story_system.py at import time).
"""
import math
import pygame
from .settings import TILE

_C = {}


def _s(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _lt(c, f=1.25):
    return tuple(min(255, int(v * f)) for v in c[:3])


def _dk(c, f=0.72):
    return tuple(int(v * f) for v in c[:3])


# ---------------------------------------------------------------- props
def restoration_board():
    """A charming wooden notice board: two posts, a little roof, pinned
    parchments with bundle doodles and a small golden emblem on top."""
    if "board" in _C:
        return _C["board"]
    w, h = TILE, int(TILE * 1.6)
    s = _s(w, h)
    wood, wdk, wlt = (150, 102, 62), (104, 70, 44), (186, 138, 90)
    base = h - 2
    # posts
    for px in (6, w - 12):
        pygame.draw.rect(s, wdk, (px, 30, 6, base - 30), border_radius=2)
        pygame.draw.rect(s, wood, (px + 1, 30, 3, base - 32))
    # little shingled roof
    pygame.draw.polygon(s, (170, 84, 70), [(0, 22), (w // 2, 9), (w, 22)])
    pygame.draw.polygon(s, (126, 58, 50), [(0, 22), (w // 2, 9), (w, 22)], 2)
    for i in range(4):
        pygame.draw.line(s, (196, 108, 88), (6 + i * 10, 20 - i * 2 + (3 if i > 1 else 0)),
                         (12 + i * 10, 20 - i * 2 + (3 if i > 1 else 0)), 1)
    # board
    pygame.draw.rect(s, wood, (3, 22, w - 6, 36), border_radius=3)
    pygame.draw.rect(s, wdk, (3, 22, w - 6, 36), 2, border_radius=3)
    pygame.draw.line(s, wlt, (6, 25), (w - 7, 25), 1)
    # pinned parchments (slightly rotated rectangles)
    papers = [((8, 28, 12, 13), (248, 240, 214), (120, 180, 90)),
              ((22, 27, 11, 12), (244, 232, 196), (90, 150, 210)),
              ((34, 29, 9, 11), (250, 244, 222), (220, 150, 80)),
              ((12, 43, 13, 11), (246, 236, 206), (180, 120, 200)),
              ((28, 42, 12, 12), (248, 238, 210), (230, 110, 120))]
    for (x, y, pw, ph), paper, doodle in papers:
        pygame.draw.rect(s, paper, (x, y, pw, ph))
        pygame.draw.rect(s, _dk(paper, 0.8), (x, y, pw, ph), 1)
        pygame.draw.circle(s, doodle, (x + pw // 2, y + ph // 2 + 1), 3)
        pygame.draw.line(s, _dk(paper, 0.7), (x + 2, y + ph - 3), (x + pw - 3, y + ph - 3), 1)
        pygame.draw.circle(s, (220, 70, 70), (x + pw // 2, y + 1), 1)       # pin
    # golden emblem on the roof peak (a little star-flower)
    cx, cy = w // 2, 10
    pygame.draw.circle(s, (150, 110, 40), (cx, cy), 6)
    pygame.draw.circle(s, (250, 210, 90), (cx, cy), 5)
    for a in range(5):
        ang = a * math.tau / 5 - math.pi / 2
        pygame.draw.circle(s, (255, 236, 150), (int(cx + math.cos(ang) * 3),
                                                int(cy + math.sin(ang) * 3)), 1)
    pygame.draw.circle(s, (255, 250, 220), (cx - 1, cy - 1), 1)
    _C["board"] = s
    return s


def golden_statue():
    """Grand prize: a gleaming golden statue of two farmers lifting a heart
    together, on a two-step marble plinth with a little plaque."""
    if "statue" in _C:
        return _C["statue"]
    w, h = TILE, int(TILE * 2.3)
    s = _s(w, h)
    gold, gdk, glt, gxx = (236, 196, 92), (170, 126, 44), (255, 238, 170), (206, 160, 64)
    stone, sdk, slt = (214, 208, 222), (150, 144, 164), (240, 238, 246)
    cx = w // 2
    # plinth: wide base + narrower top step
    pygame.draw.rect(s, sdk, (1, h - 14, w - 2, 13), border_radius=3)
    pygame.draw.rect(s, stone, (2, h - 15, w - 4, 10), border_radius=3)
    pygame.draw.line(s, slt, (4, h - 14), (w - 5, h - 14), 1)
    pygame.draw.rect(s, sdk, (6, h - 26, w - 12, 13), border_radius=2)
    pygame.draw.rect(s, stone, (7, h - 27, w - 14, 10), border_radius=2)
    pygame.draw.line(s, slt, (8, h - 26), (w - 9, h - 26), 1)
    pygame.draw.rect(s, gdk, (cx - 8, h - 24, 16, 5), border_radius=1)      # plaque
    pygame.draw.line(s, glt, (cx - 6, h - 22), (cx + 5, h - 22), 1)
    foot = h - 27
    for side in (-1, 1):
        fx = cx + side * 10
        # legs
        pygame.draw.rect(s, gdk, (fx - 5, foot - 12, 4, 12))
        pygame.draw.rect(s, gdk, (fx + 1, foot - 12, 4, 12))
        # body (tunic)
        pygame.draw.rect(s, gold, (fx - 7, foot - 30, 14, 20), border_radius=5)
        pygame.draw.rect(s, gdk, (fx - 7, foot - 30, 14, 20), 1, border_radius=5)
        pygame.draw.line(s, glt, (fx - 4 * side, foot - 27), (fx - 4 * side, foot - 14), 2)
        # inner arm raised towards the heart, outer arm resting
        pygame.draw.line(s, gold, (fx - side * 5, foot - 27), (cx - side * 4, foot - 50), 4)
        pygame.draw.line(s, gdk, (fx + side * 6, foot - 26), (fx + side * 8, foot - 14), 3)
        # head + hair tuft (one ponytail, one short cut)
        hy = foot - 37
        pygame.draw.circle(s, gold, (fx, hy), 7)
        pygame.draw.circle(s, gdk, (fx, hy), 7, 1)
        if side < 0:
            pygame.draw.ellipse(s, gxx, (fx - 11, hy - 4, 5, 10))
        else:
            pygame.draw.rect(s, gxx, (fx - 6, hy - 7, 12, 4), border_radius=2)
        pygame.draw.circle(s, glt, (fx - 2, hy - 2), 2)
    # the heart they lift together
    hx, hy = cx, foot - 56
    pygame.draw.circle(s, (228, 92, 116), (hx - 5, hy), 6)
    pygame.draw.circle(s, (228, 92, 116), (hx + 5, hy), 6)
    pygame.draw.polygon(s, (228, 92, 116), [(hx - 11, hy + 2), (hx + 11, hy + 2), (hx, hy + 14)])
    pygame.draw.circle(s, (255, 196, 206), (hx - 6, hy - 2), 2)
    pygame.draw.circle(s, glt, (hx, hy - 9), 1)
    _C["statue"] = s
    return s


# ------------------------------------------------- restoration decor props
def _cached(key, fn):
    if key not in _C:
        _C[key] = fn()
    return _C[key]


def planter():
    def mk():
        s = _s(TILE, TILE)
        wood, wdk = (156, 106, 64), (110, 72, 44)
        pygame.draw.rect(s, wdk, (4, 26, TILE - 8, 18), border_radius=3)
        pygame.draw.rect(s, wood, (5, 26, TILE - 10, 15), border_radius=3)
        for x in (12, 24, 36):
            pygame.draw.line(s, wdk, (x, 28), (x, 40), 1)
        pygame.draw.ellipse(s, (96, 70, 50), (7, 22, TILE - 14, 9))          # soil
        cols = [(246, 150, 180), (255, 220, 110), (170, 150, 240), (255, 170, 120),
                (150, 210, 250)]
        for i, x in enumerate(range(10, TILE - 8, 7)):
            h = 8 + (i * 5) % 7
            pygame.draw.line(s, (86, 150, 80), (x, 26), (x, 26 - h), 2)
            pygame.draw.circle(s, (100, 170, 90), (x + 2, 26 - h // 2), 2)
            c = cols[i % len(cols)]
            pygame.draw.circle(s, c, (x, 24 - h), 3)
            pygame.draw.circle(s, (255, 250, 230), (x, 24 - h), 1)
        return s
    return _cached("planter", mk)


def fruit_cart():
    def mk():
        w, h = TILE, int(TILE * 1.5)
        s = _s(w, h)
        base = h - 4
        pygame.draw.circle(s, (90, 64, 44), (12, base - 4), 6)                 # wheel
        pygame.draw.circle(s, (160, 120, 80), (12, base - 4), 3)
        pygame.draw.rect(s, (150, 100, 60), (4, base - 22, w - 8, 14), border_radius=2)
        pygame.draw.rect(s, (110, 72, 44), (4, base - 22, w - 8, 14), 2, border_radius=2)
        fr = [(230, 70, 70), (250, 190, 70), (120, 200, 100), (90, 100, 210), (240, 130, 60)]
        for i in range(7):
            pygame.draw.circle(s, fr[i % 5], (9 + i * 5, base - 24 - (i % 2) * 2), 4)
        for x in (6, w - 8):
            pygame.draw.line(s, (110, 72, 44), (x, base - 22), (x, 16), 2)
        for i in range(6):                                                      # canopy
            c = (240, 120, 130) if i % 2 == 0 else (255, 246, 236)
            pygame.draw.polygon(s, c, [(2 + i * 7, 18), (9 + i * 7, 18), (9 + i * 7, 10),
                                       (2 + i * 7, 12)])
        pygame.draw.line(s, (200, 90, 100), (2, 18), (w - 3, 18), 2)
        return s
    return _cached("fruit_cart", mk)


def lamp_post():
    def mk():
        w, h = TILE, int(TILE * 1.8)
        s = _s(w, h)
        cx, base = w // 2, h - 3
        pygame.draw.ellipse(s, (0, 0, 0, 50), (cx - 10, base - 5, 20, 6))
        pygame.draw.rect(s, (60, 60, 74), (cx - 6, base - 8, 12, 7), border_radius=2)
        pygame.draw.rect(s, (70, 70, 86), (cx - 2, 22, 4, base - 28))
        pygame.draw.line(s, (110, 110, 130), (cx - 1, 24), (cx - 1, base - 10), 1)
        pygame.draw.polygon(s, (60, 60, 74), [(cx - 9, 12), (cx + 9, 12), (cx + 6, 6),
                                              (cx - 6, 6)])
        pygame.draw.rect(s, (255, 226, 150), (cx - 7, 12, 14, 12), border_radius=2)
        pygame.draw.rect(s, (255, 248, 210), (cx - 3, 14, 6, 8), border_radius=2)
        pygame.draw.rect(s, (60, 60, 74), (cx - 8, 12, 16, 12), 2, border_radius=2)
        pygame.draw.circle(s, (60, 60, 74), (cx, 4), 3)
        return s
    return _cached("lamp_post", mk)


def bird_bath():
    def mk():
        w, h = TILE, int(TILE * 1.2)
        s = _s(w, h)
        cx, base = w // 2, h - 3
        stone, sdk = (200, 198, 210), (150, 146, 164)
        pygame.draw.rect(s, sdk, (cx - 10, base - 7, 20, 7), border_radius=2)
        pygame.draw.rect(s, stone, (cx - 5, base - 28, 10, 22))
        pygame.draw.ellipse(s, sdk, (cx - 18, base - 38, 36, 14))
        pygame.draw.ellipse(s, stone, (cx - 17, base - 39, 34, 11))
        pygame.draw.ellipse(s, (150, 200, 240), (cx - 13, base - 37, 26, 7))
        pygame.draw.line(s, (230, 246, 255), (cx - 8, base - 35), (cx - 2, base - 35), 1)
        bx, by = cx + 9, base - 44                                             # tiny bird
        pygame.draw.ellipse(s, (240, 170, 110), (bx - 5, by - 3, 10, 7))
        pygame.draw.circle(s, (240, 170, 110), (bx + 4, by - 4), 3)
        pygame.draw.polygon(s, (250, 210, 90), [(bx + 7, by - 4), (bx + 10, by - 3),
                                                (bx + 7, by - 2)])
        pygame.draw.circle(s, (40, 30, 40), (bx + 5, by - 5), 1)
        return s
    return _cached("bird_bath", mk)


def picnic_table():
    def mk():
        s = _s(TILE, TILE)
        wood, wdk = (170, 118, 72), (120, 80, 50)
        pygame.draw.rect(s, wdk, (8, 34, 5, 11))
        pygame.draw.rect(s, wdk, (TILE - 13, 34, 5, 11))
        pygame.draw.rect(s, wood, (2, 38, TILE - 4, 4), border_radius=1)       # bench
        pygame.draw.rect(s, wdk, (4, 18, TILE - 8, 17), border_radius=3)
        for i in range(5):                                                      # gingham
            for j in range(3):
                c = (236, 110, 120) if (i + j) % 2 == 0 else (255, 244, 240)
                pygame.draw.rect(s, c, (5 + i * 8, 18 + j * 5, 8, 5))
        pygame.draw.circle(s, (250, 220, 150), (16, 20), 4)                     # pie
        pygame.draw.circle(s, (220, 140, 80), (16, 20), 2)
        pygame.draw.rect(s, (160, 210, 240), (29, 15, 5, 7), border_radius=1)   # cup
        return s
    return _cached("picnic_table", mk)


def heart_arch():
    def mk():
        w, h = TILE * 2, TILE * 2
        s = _s(w, h)
        post, pdk = (236, 226, 214), (180, 166, 150)
        for x in (6, w - 14):
            pygame.draw.rect(s, pdk, (x, 30, 8, h - 32), border_radius=2)
            pygame.draw.rect(s, post, (x + 1, 30, 5, h - 34))
        pygame.draw.arc(s, pdk, (6, 6, w - 12, 60), 0.0, math.pi, 7)
        pygame.draw.arc(s, post, (7, 7, w - 14, 58), 0.05, math.pi - 0.05, 4)
        cols = [(246, 150, 180), (255, 220, 120), (200, 170, 250), (255, 190, 150)]
        for i in range(15):                                                     # vines
            a = math.pi * i / 14
            x = w / 2 + math.cos(a) * (w / 2 - 10)
            y = 36 - math.sin(a) * 29
            pygame.draw.circle(s, (110, 170, 100), (int(x), int(y)), 4)
            pygame.draw.circle(s, cols[i % 4], (int(x) + 1, int(y) - 1), 2)
        hx, hy = w // 2, 12
        pygame.draw.circle(s, (232, 90, 120), (hx - 5, hy), 6)
        pygame.draw.circle(s, (232, 90, 120), (hx + 5, hy), 6)
        pygame.draw.polygon(s, (232, 90, 120), [(hx - 11, hy + 2), (hx + 11, hy + 2),
                                                (hx, hy + 14)])
        pygame.draw.circle(s, (255, 200, 214), (hx - 6, hy - 2), 2)
        return s
    return _cached("heart_arch", mk)


def fish_rack():
    def mk():
        w, h = TILE, int(TILE * 1.4)
        s = _s(w, h)
        wood, wdk = (150, 110, 74), (104, 74, 50)
        base = h - 3
        for x in (5, w - 9):
            pygame.draw.rect(s, wdk, (x, 14, 4, base - 14))
        pygame.draw.rect(s, wood, (2, 12, w - 4, 4), border_radius=1)
        pygame.draw.line(s, wdk, (4, 30), (w - 5, 30), 1)
        fish = [(170, 186, 200), (200, 150, 110), (150, 170, 130), (180, 190, 210)]
        for i in range(4):
            fx = 10 + i * 9
            pygame.draw.line(s, (90, 70, 60), (fx, 16), (fx, 19), 1)
            pygame.draw.ellipse(s, fish[i], (fx - 3, 19, 7, 13))
            pygame.draw.polygon(s, fish[i], [(fx, 31), (fx - 3, 35), (fx + 3, 35)])
        pygame.draw.ellipse(s, (120, 160, 200), (8, base - 9, 16, 8))           # bucket
        pygame.draw.ellipse(s, (90, 130, 170), (8, base - 9, 16, 8), 1)
        return s
    return _cached("fish_rack", mk)


DECOR_PAINTERS = {"restore_planter": planter, "restore_fruitcart": fruit_cart,
                  "restore_lamp": lamp_post, "restore_birdbath": bird_bath,
                  "restore_picnic": picnic_table, "restore_heart_arch": heart_arch,
                  "restore_fishrack": fish_rack}


# ------------------------------------------------- villager work props
def easel():
    def mk():
        w, h = 40, 60
        s = _s(w, h)
        wood, wdk = (170, 120, 76), (116, 80, 50)
        pygame.draw.line(s, wdk, (20, 6), (6, h - 2), 3)                  # tripod
        pygame.draw.line(s, wdk, (20, 6), (34, h - 2), 3)
        pygame.draw.line(s, wood, (20, 6), (20, h - 8), 2)
        pygame.draw.rect(s, (250, 246, 236), (5, 10, 30, 24))               # canvas
        pygame.draw.rect(s, wdk, (5, 10, 30, 24), 1)
        pygame.draw.rect(s, (160, 210, 240), (6, 11, 28, 10))               # sky
        pygame.draw.rect(s, (130, 196, 110), (6, 21, 28, 12))               # meadow
        pygame.draw.circle(s, (255, 214, 120), (27, 15), 3)                 # sun
        for i, c in enumerate([(246, 150, 180), (250, 220, 110), (190, 160, 240)]):
            pygame.draw.circle(s, c, (10 + i * 7, 26 + (i % 2) * 2), 2)
        pygame.draw.rect(s, wood, (4, 34, 32, 3))                           # ledge
        pygame.draw.ellipse(s, (236, 222, 200), (22, 38, 14, 8))            # palette
        for i, c in enumerate([(230, 80, 90), (90, 140, 230), (250, 210, 80)]):
            pygame.draw.circle(s, c, (25 + i * 3, 41), 1)
        return s
    return _cached("easel", mk)


def anvil():
    def mk():
        w, h = 44, 36
        s = _s(w, h)
        iron, idk, ilt = (96, 98, 112), (60, 62, 74), (150, 154, 170)
        pygame.draw.rect(s, (120, 84, 54), (12, 22, 20, 12), border_radius=2)   # stump
        pygame.draw.rect(s, (90, 62, 40), (12, 22, 20, 12), 1, border_radius=2)
        pygame.draw.rect(s, idk, (16, 14, 12, 9))
        pygame.draw.polygon(s, iron, [(4, 6), (38, 6), (40, 9), (30, 14), (14, 14), (8, 10)])
        pygame.draw.polygon(s, idk, [(4, 6), (38, 6), (40, 9), (30, 14), (14, 14), (8, 10)], 1)
        pygame.draw.line(s, ilt, (8, 7), (36, 7), 1)
        pygame.draw.line(s, (130, 90, 60), (30, 2), (40, 12), 2)            # hammer
        pygame.draw.rect(s, idk, (27, 0, 7, 4))
        return s
    return _cached("anvil", mk)


def cafe_sign():
    def mk():
        w, h = 36, 48
        s = _s(w, h)
        wood, wdk = (150, 104, 64), (104, 70, 44)
        pygame.draw.line(s, wdk, (8, 6), (2, h - 2), 3)
        pygame.draw.line(s, wdk, (28, 6), (34, h - 2), 3)
        pygame.draw.rect(s, (54, 58, 62), (5, 6, 26, 30), border_radius=3)   # chalkboard
        pygame.draw.rect(s, wood, (5, 6, 26, 30), 2, border_radius=3)
        pygame.draw.line(s, (250, 250, 240), (9, 12), (27, 12), 1)
        pygame.draw.circle(s, (250, 190, 200), (13, 22), 4)                  # cake doodle
        pygame.draw.rect(s, (250, 240, 220), (18, 19, 8, 6))
        pygame.draw.line(s, (250, 250, 240), (9, 31), (22, 31), 1)
        pygame.draw.circle(s, (255, 120, 140), (26, 31), 2)
        return s
    return _cached("cafe_sign", mk)


def tackle():
    def mk():
        w, h = 40, 30
        s = _s(w, h)
        pygame.draw.rect(s, (70, 130, 150), (2, 14, 18, 12), border_radius=2)   # tackle box
        pygame.draw.rect(s, (40, 90, 110), (2, 14, 18, 12), 1, border_radius=2)
        pygame.draw.line(s, (220, 220, 230), (6, 13), (16, 13), 2)
        pygame.draw.polygon(s, (150, 150, 162), [(24, 12), (36, 12), (34, 27), (26, 27)])
        pygame.draw.ellipse(s, (90, 150, 200), (24, 9, 12, 6))                  # bucket water
        pygame.draw.polygon(s, (220, 150, 110), [(28, 10), (33, 8), (33, 12)])  # a tail!
        pygame.draw.arc(s, (120, 120, 130), (23, 2, 14, 16), 0.3, 2.8, 1)
        return s
    return _cached("tackle", mk)


VILLAGER_PROPS = {"Luna": easel, "Kai": anvil, "Fah": cafe_sign, "Somchai": tackle}


def umbrella(col):
    """A little pastel umbrella villagers carry on rainy days (dome + scallops)."""
    key = ("umb", col)
    if key in _C:
        return _C[key]
    w, h = 44, 40
    s = _s(w, h)
    c = _lt(col, 1.15)
    cd = _dk(c, 0.8)
    cx, cy, r = w // 2, 18, 19
    pygame.draw.line(s, (90, 70, 60), (cx, cy), (cx, h - 4), 2)          # handle
    pygame.draw.arc(s, (90, 70, 60), (cx - 6, h - 9, 7, 8), 3.3, 6.2, 2)
    pygame.draw.circle(s, cd, (cx, cy), r, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(s, c, (cx, cy + 1), r - 2, draw_top_left=True, draw_top_right=True)
    for i in range(5):                                                   # scalloped hem
        x = cx - r + 4 + i * ((2 * r - 8) // 4)
        pygame.draw.circle(s, cd, (x, cy), 4, draw_bottom_left=True, draw_bottom_right=True)
    for dx in (-10, 0, 10):                                              # ribs
        pygame.draw.line(s, cd, (cx, cy - r + 2), (cx + dx, cy), 1)
    pygame.draw.circle(s, (255, 255, 255), (cx - 8, cy - 9), 2)
    pygame.draw.circle(s, (90, 70, 60), (cx, cy - r), 2)
    _C[key] = s
    return s


# ------------------------------------------------- heart-event backdrops
SCENE_OF = {"Fah": "cafe", "Somchai": "pier", "Kai": "forge", "Luna": "meadow",
            "Mira": "garden", "Tomas": "sea", "Elya": "shop", "Luang Por": "temple"}


def scene(kind, bg, w=400, h=330):
    """A soft, cached vignette behind the heart-event portrait: a hint of the
    villager's favourite place (cafe, pier, forge, meadow, garden, sea, seed
    shop, temple) in the event's pastel colour."""
    key = ("scene", kind, bg, w, h)
    if key in _C:
        return _C[key]
    s = _s(w, h)
    sky = _lt(bg, 1.12)
    pygame.draw.rect(s, sky + (255,), (0, 0, w, h), border_radius=18)
    hz = int(h * 0.68)                                             # horizon line
    ground = _dk(bg, 0.82)
    if kind in ("pier", "sea"):
        sea = (120, 170, 214)
        pygame.draw.rect(s, sea, (0, hz - 30, w, h - hz + 30))
        for i in range(8):
            y = hz - 20 + i * 12
            pygame.draw.line(s, _lt(sea, 1.18), (20 + (i * 37) % 90, y), (70 + (i * 37) % 90, y), 2)
            pygame.draw.line(s, _lt(sea, 1.18), (220 + (i * 53) % 110, y + 5),
                             (260 + (i * 53) % 110, y + 5), 2)
        pygame.draw.circle(s, (255, 236, 190), (w - 80, hz - 60), 34)   # low sun
        if kind == "pier":
            wood, wdk = (170, 124, 82), (120, 84, 54)
            pygame.draw.polygon(s, wood, [(40, h), (w - 40, h), (w - 110, hz + 6), (110, hz + 6)])
            for i in range(9):
                y = hz + 10 + i * 12
                pygame.draw.line(s, wdk, (110 - i * 8, y), (w - 110 + i * 8, y), 1)
            for x in (96, w - 96):
                pygame.draw.rect(s, wdk, (x - 4, hz - 26, 8, 40))
        else:
            pygame.draw.polygon(s, (240, 240, 250), [(90, hz - 40), (120, hz - 40), (105, hz - 90)])
            pygame.draw.polygon(s, (150, 96, 70), [(80, hz - 38), (135, hz - 38), (125, hz - 28),
                                                   (90, hz - 28)])
            pygame.draw.rect(s, (230, 214, 170), (0, hz + 30, w, h - hz - 30))   # beach
    elif kind == "cafe":
        pygame.draw.rect(s, (236, 214, 190), (0, 0, w, hz))
        for i in range(0, w, 40):                                   # wallpaper stripes
            pygame.draw.rect(s, (246, 226, 206), (i, 0, 20, hz))
        pygame.draw.rect(s, (160, 110, 76), (0, hz, w, h - hz))     # counter
        pygame.draw.rect(s, (196, 144, 100), (0, hz, w, 10))
        for x, c in ((60, (250, 190, 200)), (w - 90, (250, 226, 150))):  # cakes
            pygame.draw.rect(s, (255, 250, 240), (x, hz - 28, 44, 28), border_radius=5)
            pygame.draw.rect(s, c, (x, hz - 30, 44, 10), border_radius=5)
            pygame.draw.circle(s, (230, 70, 90), (x + 22, hz - 34), 4)
        pygame.draw.rect(s, (255, 250, 240), (w - 150, hz - 18, 16, 18), border_radius=3)  # cup
        pygame.draw.arc(s, (255, 250, 240), (w - 138, hz - 14, 10, 10), -1.6, 1.6, 2)
        pygame.draw.rect(s, (120, 170, 200), (w // 2 - 60, 30, 120, 80), border_radius=8)  # window
        pygame.draw.line(s, (255, 250, 240), (w // 2, 30), (w // 2, 110), 3)
    elif kind == "forge":
        pygame.draw.rect(s, (120, 96, 90), (0, 0, w, hz))
        for y in range(0, hz, 22):                                  # brick rows
            for x in range((y // 22) % 2 * 20, w, 40):
                pygame.draw.rect(s, (136, 108, 100), (x + 2, y + 2, 36, 18), border_radius=2)
        pygame.draw.rect(s, (90, 70, 66), (w - 150, hz - 110, 120, 110), border_radius=10)
        pygame.draw.ellipse(s, (255, 150, 60), (w - 130, hz - 60, 80, 50))     # fire
        pygame.draw.ellipse(s, (255, 220, 120), (w - 112, hz - 48, 44, 30))
        pygame.draw.rect(s, (96, 80, 72), (0, hz, w, h - hz))
        pygame.draw.polygon(s, (80, 82, 96), [(40, hz - 20), (130, hz - 20), (120, hz - 8),
                                              (60, hz - 8)])        # anvil
    elif kind in ("meadow", "garden"):
        pygame.draw.circle(s, (255, 244, 200), (w - 90, 70), 36)
        pygame.draw.ellipse(s, (170, 214, 150), (-60, hz - 50, w // 2 + 120, 120))  # hills
        pygame.draw.ellipse(s, (150, 204, 140), (w // 3, hz - 36, w, 110))
        pygame.draw.rect(s, (140, 196, 126), (0, hz, w, h - hz))
        cols = [(246, 150, 180), (255, 220, 110), (190, 160, 240), (255, 170, 120),
                (150, 210, 250)]
        for i in range(34):
            x = (i * 53) % (w - 20) + 10
            y = hz + 8 + (i * 29) % (h - hz - 16)
            pygame.draw.circle(s, cols[i % 5], (x, y), 3)
            pygame.draw.circle(s, (255, 250, 230), (x, y), 1)
        if kind == "garden":
            pygame.draw.rect(s, (156, 106, 64), (20, hz - 26, 110, 26), border_radius=4)
            for i in range(6):
                pygame.draw.circle(s, cols[i % 5], (32 + i * 17, hz - 30), 6)
    elif kind == "shop":
        pygame.draw.rect(s, (214, 196, 160), (0, 0, w, hz))
        for row in range(3):                                        # seed shelves
            y = 40 + row * 60
            pygame.draw.rect(s, (150, 104, 66), (20, y + 36, w - 40, 8))
            for i in range(9):
                c = [(236, 150, 120), (150, 200, 120), (240, 210, 110), (170, 150, 220)][(i + row) % 4]
                pygame.draw.rect(s, c, (30 + i * 40, y + 8, 26, 28), border_radius=3)
                pygame.draw.rect(s, (255, 250, 236), (34 + i * 40, y + 14, 18, 8))
        pygame.draw.rect(s, (170, 124, 82), (0, hz, w, h - hz))
    else:                                                           # temple
        pygame.draw.rect(s, (196, 80, 66), (0, 0, w, hz))
        for x in (40, w - 70):                                      # pillars
            pygame.draw.rect(s, (236, 190, 96), (x, 0, 30, hz))
            pygame.draw.rect(s, (200, 150, 70), (x, 0, 30, hz), 2)
        pygame.draw.rect(s, (160, 60, 56), (0, hz, w, h - hz))
        for x in (110, w - 130):                                    # candles
            pygame.draw.rect(s, (255, 246, 220), (x, hz - 40, 14, 40))
            pygame.draw.ellipse(s, (255, 190, 80), (x + 2, hz - 60, 10, 20))
            pygame.draw.ellipse(s, (255, 240, 170), (x + 4, hz - 54, 6, 12))
    # soft vignette edge so it melts into the card
    edge = _s(w, h)
    for i in range(10):
        pygame.draw.rect(edge, bg + (int(18 * (10 - i)),), (i * 2, i * 2, w - i * 4, h - i * 4),
                         3, border_radius=18)
    s.blit(edge, (0, 0))
    mask = _s(w, h)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=18)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    _C[key] = s
    return s


# ---------------------------------------------------------------- eggs
EGG_COLORS = [(246, 170, 190), (160, 206, 246), (186, 230, 160), (250, 222, 140),
              (206, 176, 240)]


def egg_sprite(ci, golden=False):
    key = ("egg", ci, golden)
    if key in _C:
        return _C[key]
    s = _s(22, 26)
    base = (250, 206, 80) if golden else EGG_COLORS[ci % len(EGG_COLORS)]
    pygame.draw.ellipse(s, (0, 0, 0, 50), (3, 20, 16, 5))                  # shadow
    pygame.draw.ellipse(s, _dk(base, 0.78), (3, 2, 16, 21))
    pygame.draw.ellipse(s, base, (4, 2, 14, 19))
    stripe = (255, 250, 236) if not golden else (255, 244, 190)
    pygame.draw.line(s, stripe, (5, 10), (16, 10), 2)
    pygame.draw.line(s, _dk(base, 0.85), (6, 14), (15, 14), 1)
    for i in range(3):                                                       # dots
        pygame.draw.circle(s, stripe, (7 + i * 4, 6 + (i % 2)), 1)
    pygame.draw.circle(s, (255, 255, 255), (8, 5), 2)                        # gloss
    if golden:
        pygame.draw.ellipse(s, (160, 110, 30), (3, 2, 16, 21), 1)
    _C[key] = s
    return s


# ---------------------------------------------------------------- icons
def paint_golden_egg(surf):
    w, h = surf.get_size()
    pygame.draw.ellipse(surf, (160, 110, 30), (w // 2 - 8, 3, 16, 22))
    pygame.draw.ellipse(surf, (250, 206, 80), (w // 2 - 7, 3, 14, 20))
    pygame.draw.line(surf, (255, 244, 190), (w // 2 - 6, 12), (w // 2 + 6, 12), 2)
    pygame.draw.circle(surf, (255, 255, 240), (w // 2 - 3, 7), 2)
    pygame.draw.line(surf, (255, 250, 210), (w - 6, 3), (w - 6, 9), 1)
    pygame.draw.line(surf, (255, 250, 210), (w - 9, 6), (w - 3, 6), 1)


def paint_twin_locket(surf):
    w, h = surf.get_size()
    pygame.draw.arc(surf, (210, 170, 80), (w // 2 - 7, 1, 14, 14), 0.2, 2.9, 1)   # chain
    cx, cy = w // 2, 16
    for dx, col in ((-4, (236, 190, 90)), (4, (250, 214, 120))):
        pygame.draw.circle(surf, col, (cx + dx - 3, cy - 2), 4)
        pygame.draw.circle(surf, col, (cx + dx + 1, cy - 2), 4)
        pygame.draw.polygon(surf, col, [(cx + dx - 7, cy - 1), (cx + dx + 5, cy - 1),
                                        (cx + dx - 1, cy + 7)])
    pygame.draw.circle(surf, (240, 110, 130), (cx, cy), 2)
    pygame.draw.circle(surf, (255, 250, 230), (cx - 6, cy - 4), 1)


# ---------------------------------------------------------------- UI bits
def heart_icon(size=12, full=True):
    key = ("heart", size, full)
    if key in _C:
        return _C[key]
    s = _s(size, size)
    col = (236, 96, 128) if full else (96, 84, 110)
    r = max(2, size // 4)
    pygame.draw.circle(s, col, (r + 1, r + 1), r)
    pygame.draw.circle(s, col, (size - r - 1, r + 1), r)
    pygame.draw.polygon(s, col, [(1, r + 2), (size - 1, r + 2), (size // 2, size - 1)])
    if full:
        pygame.draw.circle(s, (255, 190, 206), (r, r), max(1, r // 2))
    _C[key] = s
    return s


def portrait(frames, name, scale=4):
    """Big nearest-neighbour portrait from an NPC's front walk frame."""
    key = ("portrait", name, scale)
    if key in _C:
        return _C[key]
    fr = frames["down"][0]
    w, h = fr.get_size()
    big = pygame.transform.scale(fr, (w * scale, h * scale))
    _C[key] = big
    return big


def gradient(size, top, bottom):
    key = ("grad", size, top, bottom)
    if key in _C:
        return _C[key]
    w, h = size
    s = pygame.Surface((w, h))
    for y in range(0, h, 4):
        t = y / max(1, h - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        pygame.draw.rect(s, c, (0, y, w, 4))
    _C[key] = s
    return s


def rounded_gradient(size, top, bottom, radius=16):
    key = ("rgrad", size, top, bottom, radius)
    if key in _C:
        return _C[key]
    w, h = size
    panel = pygame.Surface((w, h), pygame.SRCALPHA)
    panel.blit(gradient(size, top, bottom), (0, 0))
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=radius)
    panel.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    _C[key] = panel
    return panel


def glow(radius, col):
    """Soft radial glow (cached); set_alpha() on the shared surface per use."""
    key = ("glow", radius, col)
    if key in _C:
        return _C[key]
    s = _s(radius * 2, radius * 2)
    for i in range(radius, 0, -2):
        a = int(90 * (1 - i / radius) ** 1.6) + 4
        pygame.draw.circle(s, col + (a,), (radius, radius), i)
    _C[key] = s
    return s


def dim(alpha=150, col=(14, 10, 24)):
    key = ("dim", alpha, col)
    if key in _C:
        return _C[key]
    from .settings import SCREEN_W, SCREEN_H
    s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    s.fill(col + (alpha,))
    _C[key] = s
    return s


def name_tag(font, text):
    key = ("tag", text)
    if key in _C:
        return _C[key]
    t = font.render(text, True, (255, 250, 245))
    s = _s(t.get_width() + 12, t.get_height() + 4)
    pygame.draw.rect(s, (54, 42, 70, 200), s.get_rect(), border_radius=6)
    s.blit(t, (6, 2))
    _C[key] = s
    return s


_REGISTERED = [False]


def register_all():
    """Hook the story props / items into the shared registries (idempotent)."""
    if _REGISTERED[0]:
        return
    _REGISTERED[0] = True
    from . import loot
    try:
        from . import assets
    except Exception:
        assets = None
    if "golden_egg" not in loot.MATERIALS:
        loot.register_item("golden_egg", "Golden Egg", 350, (250, 206, 80), "trophy")
    if "twin_locket" not in loot.MATERIALS:
        loot.register_item("twin_locket", "Twin Heart Locket", 500, (240, 150, 160), "relic")
    if assets is not None:
        try:
            assets.register_prop("restoration_board", restoration_board)
            assets.register_prop("golden_statue", golden_statue)
            for k, fn in DECOR_PAINTERS.items():
                assets.register_prop(k, fn)
            assets.register_item_icon("golden_egg", paint_golden_egg)
            assets.register_item_icon("twin_locket", paint_twin_locket)
        except Exception:
            pass
