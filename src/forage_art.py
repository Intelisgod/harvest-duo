"""Procedural art for forageables + the fishing treasure chest.

Owner: Fishing & Foraging (Chat 3). Pastel pixel style matching
``assets/items.py`` (28x28 icons, flat fills + a darker outline + a lit
highlight). Everything is drawn once and cached. Registered as item icons from
``systems/forage_system.py`` (this module never imports ``assets``).
"""
import math
import pygame

IC = 28
_cache = {}


def _lt(c, f=1.25):
    return tuple(min(255, int(v * f)) for v in c)


def _dk(c, f=0.66):
    return tuple(max(0, int(v * f)) for v in c)


def _poly(s, col, pts, w=1, ol=None):
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, ol or _dk(col), pts, w)


def _circ(s, col, c, r, ol=None):
    pygame.draw.circle(s, col, c, r)
    pygame.draw.circle(s, ol or _dk(col), c, r, 1)


def _leaf(s, x, y, ang, ln=8, wd=3, col=(104, 176, 92)):
    """A little pointed leaf from (x, y) in direction ``ang`` (radians)."""
    ca, sa = math.cos(ang), math.sin(ang)
    tip = (x + ca * ln, y + sa * ln)
    mid = (x + ca * ln * 0.5, y + sa * ln * 0.5)
    l = (mid[0] - sa * wd, mid[1] + ca * wd)
    r = (mid[0] + sa * wd, mid[1] - ca * wd)
    _poly(s, col, [(x, y), l, tip, r])
    pygame.draw.line(s, _dk(col, 0.8), (x, y), tip, 1)


# ------------------------------------------------------------------ spring
def _p_wild_leek(s):
    for dx, top in ((-4, 3), (0, 1), (4, 4)):
        _poly(s, (116, 190, 96), [(14 + dx // 2, 18), (12 + dx, top), (15 + dx, top + 2)])
    pygame.draw.ellipse(s, (246, 244, 226), (9, 16, 10, 8))
    pygame.draw.ellipse(s, (196, 196, 170), (9, 16, 10, 8), 1)
    pygame.draw.line(s, (255, 255, 250), (11, 18), (12, 21), 1)
    for rx in (11, 14, 17):
        pygame.draw.line(s, (206, 186, 150), (14, 23), (rx, 26), 1)


def _p_daffodil(s):
    pygame.draw.line(s, (96, 164, 84), (14, 26), (14, 14), 2)
    _leaf(s, 14, 25, -2.2, 8, 2)
    cx, cy = 14, 11
    for i in range(6):
        a = i * math.pi / 3
        _circ(s, (252, 230, 110), (int(cx + math.cos(a) * 5), int(cy + math.sin(a) * 5)), 4,
              (214, 180, 60))
    _circ(s, (246, 150, 56), (cx, cy), 4, (200, 110, 40))
    pygame.draw.circle(s, (255, 200, 120), (cx - 1, cy - 1), 1)


def _p_morel(s):
    pygame.draw.rect(s, (238, 226, 200), (11, 17, 6, 8), border_radius=2)
    pygame.draw.rect(s, (190, 176, 150), (11, 17, 6, 8), 1, border_radius=2)
    cap = [(14, 2), (20, 9), (20, 16), (17, 19), (11, 19), (8, 16), (8, 9)]
    _poly(s, (186, 146, 100), cap)
    for (x, y) in ((11, 9), (15, 8), (12, 13), (16, 12), (14, 16), (10, 16), (18, 15), (14, 5)):
        pygame.draw.ellipse(s, (120, 88, 60), (x - 1, y - 1, 3, 3))
    pygame.draw.line(s, (220, 190, 150), (12, 5), (10, 10), 1)


def _p_dandelion(s):
    pygame.draw.line(s, (96, 164, 84), (14, 26), (14, 14), 2)
    for ang in (-2.6, -0.5):
        _leaf(s, 14, 24, ang, 9, 3)
    cx, cy = 14, 10
    for i in range(12):
        a = i * math.pi / 6
        pygame.draw.circle(s, (240, 184, 40), (int(cx + math.cos(a) * 6), int(cy + math.sin(a) * 6)), 2)
    _circ(s, (252, 214, 70), (cx, cy), 5, (224, 170, 40))
    pygame.draw.circle(s, (255, 240, 150), (cx - 2, cy - 2), 2)


# ------------------------------------------------------------------ summer
def _p_spice_berry(s):
    pygame.draw.line(s, (100, 130, 70), (14, 3), (14, 9), 2)
    _leaf(s, 14, 6, -0.4, 8, 3)
    _leaf(s, 14, 6, -2.7, 7, 3)
    for (x, y) in ((10, 14), (18, 14), (14, 20)):
        _circ(s, (224, 76, 64), (x, y), 5, (160, 44, 40))
        pygame.draw.circle(s, (255, 170, 150), (x - 2, y - 2), 1)


def _p_sweet_pea(s):
    pygame.draw.arc(s, (110, 180, 100), (4, 14, 10, 10), 0.5, 4.5, 1)      # tendril
    pygame.draw.line(s, (96, 164, 84), (14, 26), (14, 15), 2)
    _leaf(s, 14, 22, -0.6, 7, 2)
    _poly(s, (236, 150, 206), [(8, 8), (14, 3), (20, 8), (19, 14), (14, 16), (9, 14)])
    _poly(s, (246, 196, 230), [(11, 9), (14, 6), (17, 9), (16, 13), (12, 13)])
    pygame.draw.circle(s, (206, 96, 170), (14, 12), 2)


def _p_wild_grape(s):
    pygame.draw.line(s, (120, 90, 60), (14, 2), (14, 7), 2)
    _leaf(s, 14, 5, -0.3, 9, 4, (110, 170, 90))
    for (x, y) in ((9, 10), (14, 10), (19, 10), (11, 15), (17, 15), (14, 20), (9, 15), (19, 15)):
        if (x, y) in ((9, 15), (19, 15)):
            continue
        _circ(s, (136, 96, 186), (x, y), 4, (90, 60, 130))
        pygame.draw.circle(s, (200, 176, 236), (x - 1, y - 1), 1)


# ------------------------------------------------------------------ fall
def _p_blackberry(s):
    _leaf(s, 14, 8, -0.5, 9, 3)
    _leaf(s, 14, 8, -2.6, 9, 3)
    pygame.draw.ellipse(s, (40, 22, 52), (7, 8, 14, 16))
    for (x, y) in ((10, 11), (14, 10), (18, 11), (9, 15), (13, 14), (17, 15), (11, 19), (15, 19), (13, 22)):
        _circ(s, (70, 38, 92), (x, y), 3, (34, 18, 44))
        pygame.draw.circle(s, (160, 128, 196), (x - 1, y - 1), 1)


def _p_chanterelle(s):
    pygame.draw.polygon(s, (230, 160, 70), [(11, 13), (17, 13), (16, 25), (12, 25)])
    pygame.draw.polygon(s, (190, 120, 50), [(11, 13), (17, 13), (16, 25), (12, 25)], 1)
    cap = [(3, 9), (7, 6), (12, 7), (16, 5), (21, 7), (25, 6), (23, 11), (17, 15), (11, 15)]
    _poly(s, (244, 180, 78), cap, 1, (196, 124, 46))
    for x in (9, 13, 17, 21):
        pygame.draw.line(s, (214, 140, 56), (x, 9), (14, 14), 1)
    pygame.draw.line(s, (255, 222, 150), (7, 8), (12, 8), 1)


def _p_hazelnut(s):
    _leaf(s, 14, 8, -0.8, 9, 4, (120, 170, 90))
    _leaf(s, 14, 8, -2.4, 9, 4, (120, 170, 90))
    pygame.draw.ellipse(s, (180, 126, 76), (7, 9, 14, 15))
    pygame.draw.ellipse(s, (120, 80, 48), (7, 9, 14, 15), 1)
    pygame.draw.ellipse(s, (232, 206, 160), (9, 18, 10, 6))                # pale base
    pygame.draw.line(s, (220, 170, 120), (10, 12), (11, 16), 2)
    pygame.draw.line(s, (130, 90, 56), (14, 9), (14, 6), 2)


def _p_wild_plum(s):
    pygame.draw.line(s, (110, 80, 50), (14, 3), (15, 8), 2)
    _leaf(s, 15, 5, -0.2, 9, 3)
    _circ(s, (156, 84, 156), (14, 16), 9, (100, 48, 104))
    pygame.draw.arc(s, (120, 60, 124), (9, 8, 10, 16), 4.2, 5.4, 1)       # crease
    pygame.draw.circle(s, (214, 170, 222), (10, 12), 2)
    pygame.draw.circle(s, (236, 210, 240), (10, 12), 1)


# ------------------------------------------------------------------ winter
def _p_crystal_fruit(s):
    body = [(14, 3), (22, 10), (20, 22), (14, 26), (8, 22), (6, 10)]
    _poly(s, (170, 222, 246), body, 1, (96, 150, 200))
    _poly(s, (214, 242, 255), [(14, 3), (14, 26), (8, 22), (6, 10)], 1, (130, 186, 226))
    pygame.draw.line(s, (130, 186, 226), (6, 10), (22, 10), 1)
    pygame.draw.line(s, (255, 255, 255), (9, 8), (11, 6), 1)
    for (x, y) in ((22, 4), (5, 20)):
        pygame.draw.line(s, (255, 255, 255), (x - 2, y), (x + 2, y), 1)
        pygame.draw.line(s, (255, 255, 255), (x, y - 2), (x, y + 2), 1)


def _holly_leaf(s, cx, cy, flip):
    pts = []
    for i in range(7):
        t = i / 6.0
        x = cx + flip * (t * 12)
        y = cy - math.sin(t * math.pi) * 5 - (2 if i % 2 else 0)
        pts.append((x, y))
    for i in range(6, -1, -1):
        t = i / 6.0
        x = cx + flip * (t * 12)
        y = cy + math.sin(t * math.pi) * 5 + (2 if i % 2 else 0)
        pts.append((x, y))
    _poly(s, (64, 146, 82), pts, 1, (36, 96, 52))
    pygame.draw.line(s, (120, 190, 120), (cx, cy), (cx + flip * 11, cy), 1)


def _p_holly(s):
    _holly_leaf(s, 13, 11, -1)
    _holly_leaf(s, 15, 14, 1)
    for (x, y) in ((12, 16), (16, 18), (11, 20)):
        _circ(s, (220, 60, 64), (x, y), 3, (150, 30, 40))
        pygame.draw.circle(s, (255, 170, 170), (x - 1, y - 1), 1)


def _p_snow_mushroom(s):
    pygame.draw.rect(s, (236, 232, 222), (11, 14, 6, 11), border_radius=2)
    pygame.draw.rect(s, (190, 184, 176), (11, 14, 6, 11), 1, border_radius=2)
    pygame.draw.ellipse(s, (226, 232, 248), (3, 4, 22, 14))
    pygame.draw.ellipse(s, (150, 164, 196), (3, 4, 22, 14), 1)
    pygame.draw.ellipse(s, (255, 255, 255), (6, 4, 16, 6))                  # snow cap
    for (x, y) in ((9, 12), (19, 11), (14, 9)):
        pygame.draw.circle(s, (170, 196, 236), (x, y), 2)


# ------------------------------------------------------------------ beach
def _p_clam(s):
    body = [(3, 18), (6, 9), (14, 5), (22, 9), (25, 18), (14, 22)]
    _poly(s, (214, 192, 170), body, 1, (150, 128, 108))
    for i, col in enumerate(((196, 170, 146), (226, 206, 186))):
        pygame.draw.arc(s, col, (5 + i * 2, 8 + i * 3, 18 - i * 4, 18 - i * 4), 0.1, 3.0, 1)
    pygame.draw.ellipse(s, (240, 226, 210), (8, 18, 12, 5))
    pygame.draw.ellipse(s, (150, 128, 108), (8, 18, 12, 5), 1)
    pygame.draw.line(s, (255, 246, 236), (9, 10), (12, 8), 1)


def _p_coral(s):
    col, dk = (250, 132, 122), (196, 84, 86)
    pygame.draw.line(s, dk, (14, 26), (14, 14), 5)
    pygame.draw.line(s, col, (14, 26), (14, 14), 3)
    for (a, b) in (((14, 18), (7, 10)), ((7, 10), (5, 4)), ((7, 10), (10, 5)),
                   ((14, 15), (21, 8)), ((21, 8), (19, 3)), ((21, 8), (24, 5)), ((14, 14), (14, 6))):
        pygame.draw.line(s, dk, a, b, 4)
        pygame.draw.line(s, col, a, b, 2)
    for (x, y) in ((5, 4), (10, 5), (19, 3), (24, 5), (14, 6)):
        pygame.draw.circle(s, (255, 190, 176), (x, y), 2)


def _p_sea_urchin(s):
    cx, cy = 14, 15
    for i in range(16):
        a = i * math.pi / 8
        pygame.draw.line(s, (70, 44, 100), (cx, cy), (int(cx + math.cos(a) * 12), int(cy + math.sin(a) * 11)), 1)
    _circ(s, (104, 70, 140), (cx, cy), 7, (60, 36, 86))
    for i in range(8):
        a = i * math.pi / 4 + 0.2
        pygame.draw.circle(s, (150, 116, 190), (int(cx + math.cos(a) * 4), int(cy + math.sin(a) * 4)), 1)
    pygame.draw.circle(s, (190, 160, 220), (cx - 2, cy - 3), 2)


def _p_nautilus_shell(s):
    _circ(s, (242, 212, 182), (14, 15), 10, (170, 130, 100))
    for i in range(5):                              # tiger stripes
        a = -2.4 + i * 0.5
        pygame.draw.line(s, (196, 120, 76), (int(14 + math.cos(a) * 5), int(15 + math.sin(a) * 5)),
                         (int(14 + math.cos(a) * 10), int(15 + math.sin(a) * 10)), 2)
    pts = []
    for i in range(30):                             # the spiral
        a = i * 0.36
        r = 1 + i * 0.26
        pts.append((14 + math.cos(a) * r + 2, 15 + math.sin(a) * r))
    pygame.draw.lines(s, (150, 100, 70), False, pts, 1)
    pygame.draw.circle(s, (255, 240, 224), (10, 10), 2)


def _p_rainbow_shell(s):
    cx, by = 14, 25
    ribs = [(236, 110, 120), (246, 170, 100), (246, 222, 110), (140, 210, 140),
            (120, 180, 236), (176, 140, 226)]
    outline = [(cx, by), (cx - 12, by - 12), (cx - 8, by - 19), (cx, by - 21), (cx + 8, by - 19), (cx + 12, by - 12)]
    pygame.draw.polygon(s, (250, 236, 246), outline)
    for i, col in enumerate(ribs):
        t = -1 + i * 0.4
        pygame.draw.polygon(s, col, [(cx, by), (cx + t * 12 - 2, by - 17 + abs(t) * 4),
                                     (cx + t * 12 + 3, by - 18 + abs(t) * 4)])
    pygame.draw.polygon(s, (190, 150, 190), outline, 1)
    pygame.draw.circle(s, (220, 190, 220), (cx, by - 1), 3)
    pygame.draw.circle(s, (255, 255, 255), (cx - 5, by - 16), 1)


PAINTERS = {
    "wild_leek": _p_wild_leek, "daffodil": _p_daffodil, "morel": _p_morel,
    "dandelion": _p_dandelion, "spice_berry": _p_spice_berry, "sweet_pea": _p_sweet_pea,
    "wild_grape": _p_wild_grape, "blackberry": _p_blackberry, "chanterelle": _p_chanterelle,
    "hazelnut": _p_hazelnut, "wild_plum": _p_wild_plum, "crystal_fruit": _p_crystal_fruit,
    "holly": _p_holly, "snow_mushroom": _p_snow_mushroom, "clam": _p_clam, "coral": _p_coral,
    "sea_urchin": _p_sea_urchin, "nautilus_shell": _p_nautilus_shell,
    "rainbow_shell": _p_rainbow_shell,
}


def icon(item_id):
    """Cached 28x28 icon (used for world sprites; the hotbar goes via assets)."""
    key = ("icon", item_id)
    if key not in _cache:
        s = pygame.Surface((IC, IC), pygame.SRCALPHA)
        PAINTERS.get(item_id, _p_clam)(s)
        _cache[key] = s
    return _cache[key]


def world_icon(item_id):
    """The icon as it lies in the world: a touch bigger with a soft cream rim so
    it reads against grass and sand (cached)."""
    key = ("wicon", item_id)
    if key not in _cache:
        base = pygame.transform.smoothscale(icon(item_id), (32, 32))
        s = pygame.Surface((36, 36), pygame.SRCALPHA)
        mask = pygame.mask.from_surface(base, 60)
        rim = mask.to_surface(setcolor=(255, 250, 226, 190), unsetcolor=(0, 0, 0, 0))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (1, -1), (-1, 1)):
            s.blit(rim, (2 + dx, 2 + dy))
        s.blit(base, (2, 2))
        _cache[key] = s
    return _cache[key]


def ground_shadow():
    if "shadow" not in _cache:
        s = pygame.Surface((22, 7), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (20, 30, 20, 70), (0, 0, 22, 7))
        _cache["shadow"] = s
    return _cache["shadow"]


def glint(size=9):
    """A little 4-point sparkle star."""
    key = ("glint", size)
    if key not in _cache:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size // 2
        pygame.draw.line(s, (255, 255, 240), (c, 0), (c, size - 1), 1)
        pygame.draw.line(s, (255, 255, 240), (0, c), (size - 1, c), 1)
        pygame.draw.circle(s, (255, 255, 255), (c, c), 1)
        pygame.draw.line(s, (255, 250, 200, 150), (c - 2, c - 2), (c + 2, c + 2), 1)
        pygame.draw.line(s, (255, 250, 200, 150), (c - 2, c + 2), (c + 2, c - 2), 1)
        _cache[key] = s
    return _cache[key]


def silhouette(surf, key):
    """Dark 'not yet discovered' silhouette of an icon (cached under ``key``)."""
    k = ("sil", key)
    if k not in _cache:
        sil = surf.copy()
        sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
        sil.fill((78, 72, 102, 0), special_flags=pygame.BLEND_RGBA_ADD)
        _cache[k] = sil
    return _cache[k]


# ------------------------------------------------------------ treasure chest
def chest(opened=False):
    """A little wooden sea-chest (32x28) with gold trim; lid up when opened."""
    key = ("chest", bool(opened))
    if key in _cache:
        return _cache[key]
    s = pygame.Surface((32, 30), pygame.SRCALPHA)
    wood, wdk, trim = (168, 110, 64), (112, 70, 40), (244, 204, 96)
    if opened:
        # lid swung back (we see its dark underside) -- drawn BEHIND the body
        lid = [(4, 14), (28, 14), (30, 3), (2, 3)]
        pygame.draw.polygon(s, (104, 64, 38), lid)
        pygame.draw.polygon(s, wdk, lid, 2)
        pygame.draw.line(s, trim, (3, 4), (29, 4), 2)
        pygame.draw.polygon(s, (255, 236, 150), [(7, 13), (25, 13), (23, 8), (9, 8)])   # glow
    # body
    pygame.draw.rect(s, wood, (3, 14, 26, 14), border_radius=3)
    pygame.draw.rect(s, wdk, (3, 14, 26, 14), 2, border_radius=3)
    for y in (19, 23):
        pygame.draw.line(s, wdk, (5, y), (26, y), 1)
    pygame.draw.rect(s, trim, (3, 14, 4, 14))
    pygame.draw.rect(s, trim, (25, 14, 4, 14))
    if opened:
        # heaped treasure spilling over the rim
        pygame.draw.ellipse(s, (60, 36, 24), (6, 12, 20, 5))                   # dark mouth
        for (x, y, c) in ((9, 13, (255, 214, 90)), (13, 12, (255, 226, 120)), (17, 12, (150, 220, 255)),
                          (21, 13, (255, 214, 90)), (15, 14, (236, 130, 200)), (11, 14, (255, 200, 80))):
            pygame.draw.circle(s, c, (x, y), 2)
            pygame.draw.circle(s, (255, 255, 240), (x - 1, y - 1), 1)
        pygame.draw.rect(s, trim, (13, 16, 6, 5), border_radius=1)           # hanging lock plate
        pygame.draw.rect(s, _dk(trim), (13, 16, 6, 5), 1, border_radius=1)
    else:
        lid = [(3, 15), (29, 15), (27, 7), (22, 5), (10, 5), (5, 7)]
        pygame.draw.polygon(s, _lt(wood, 1.08), lid)
        pygame.draw.polygon(s, wdk, lid, 2)
        pygame.draw.line(s, trim, (4, 13), (28, 13), 2)
        pygame.draw.rect(s, trim, (13, 11, 6, 7), border_radius=1)          # lock plate
        pygame.draw.rect(s, _dk(trim), (13, 11, 6, 7), 1, border_radius=1)
        pygame.draw.circle(s, wdk, (16, 14), 1)
        pygame.draw.line(s, (220, 170, 120), (9, 8), (16, 7), 1)
    _cache[key] = s
    return s
