"""Small procedural HUD icons (weather, seasons, coin, bars, buffs, faces, glows).

Owner: "UI & Rendering" chat. Everything is drawn once and cached in the shared
``_cache`` -- callers blit the returned Surface every frame for free.
Only depends on ``_base`` (package rule: submodules never import each other).
"""
import math
import pygame
from ._base import _cache

# --------------------------------------------------------------- helpers


def _s(w, h=None):
    return pygame.Surface((w, h or w), pygame.SRCALPHA)


def glow(radius, color, strength=110):
    """Soft radial glow disc (cached)."""
    key = ("hud_glow", radius, tuple(color[:3]), strength)
    if key in _cache:
        return _cache[key]
    s = _s(radius * 2)
    steps = 10
    for i in range(steps):
        r = int(radius * (1 - i / steps))
        a = int(strength * ((i + 1) / steps) ** 1.8)
        pygame.draw.circle(s, (*color[:3], min(255, a)), (radius, radius), max(1, r))
    _cache[key] = s
    return s


def soft_shadow(w, h, alpha=70):
    """Soft blurred-ish ground shadow ellipse (3 stacked rings)."""
    key = ("hud_softshadow", w, h, alpha)
    if key in _cache:
        return _cache[key]
    s = _s(w, h)
    for i, f in enumerate((1.0, 0.8, 0.6)):
        ew, eh = int(w * f), int(h * f)
        pygame.draw.ellipse(s, (0, 0, 0, int(alpha * (0.35 + 0.3 * i))),
                            ((w - ew) // 2, (h - eh) // 2, ew, eh))
    _cache[key] = s
    return s


# --------------------------------------------------------------- weather

def _sun(s, cx, cy, r, col=(255, 214, 96)):
    for k in range(8):
        a = k * math.pi / 4
        x1, y1 = cx + math.cos(a) * (r + 2), cy + math.sin(a) * (r + 2)
        x2, y2 = cx + math.cos(a) * (r + 5), cy + math.sin(a) * (r + 5)
        pygame.draw.line(s, col, (int(x1), int(y1)), (int(x2), int(y2)), 2)
    pygame.draw.circle(s, col, (cx, cy), r)
    pygame.draw.circle(s, (255, 244, 190), (cx - 2, cy - 2), max(1, r // 2))


def _cloud(s, cx, cy, col=(236, 240, 248), dark=(188, 196, 214)):
    pygame.draw.ellipse(s, dark, (cx - 11, cy - 1, 23, 10))
    pygame.draw.circle(s, col, (cx - 5, cy), 5)
    pygame.draw.circle(s, col, (cx + 2, cy - 3), 7)
    pygame.draw.circle(s, col, (cx + 8, cy + 1), 4)
    pygame.draw.rect(s, col, (cx - 10, cy, 21, 6), border_radius=3)


def weather_icon(kind, size=26):
    """sunny / rain / snow / storm / fog / windy (+ unknown -> cloud)."""
    key = ("hud_weather", kind, size)
    if key in _cache:
        return _cache[key]
    s = _s(26)
    k = (kind or "").lower()
    if k in ("sunny", "clear", ""):
        _sun(s, 13, 13, 6)
    elif k in ("rain", "rainy"):
        _cloud(s, 13, 9, (214, 222, 236), (160, 172, 196))
        for x in (7, 13, 19):
            pygame.draw.line(s, (110, 170, 236), (x, 18), (x - 2, 23), 2)
    elif k in ("snow", "snowy"):
        _cloud(s, 13, 9)
        for x, y in ((7, 19), (13, 22), (19, 19)):
            pygame.draw.circle(s, (255, 255, 255), (x, y), 2)
            pygame.draw.circle(s, (180, 206, 236), (x, y), 2, 1)
    elif k in ("storm", "thunder", "stormy"):
        _cloud(s, 13, 8, (150, 156, 178), (96, 102, 128))
        pygame.draw.polygon(s, (255, 226, 90), [(14, 13), (9, 20), (13, 20), (11, 25),
                                                (18, 17), (14, 17), (16, 13)])
    elif k in ("fog", "foggy", "mist"):
        for i, y in enumerate((8, 13, 18)):
            off = 3 if i % 2 else 0
            pygame.draw.line(s, (214, 220, 230), (4 + off, y), (22 - (3 - off), y), 3)
            pygame.draw.circle(s, (214, 220, 230), (4 + off, y), 1)
    elif k in ("wind", "windy"):
        col = (196, 226, 214)
        pygame.draw.arc(s, col, (12, 4, 10, 9), -1.6, 3.2, 2)
        pygame.draw.line(s, col, (3, 12), (17, 12), 2)
        pygame.draw.arc(s, col, (12, 14, 9, 8), -3.2, 1.6, 2)
        pygame.draw.line(s, col, (5, 16), (16, 16), 2)
        pygame.draw.line(s, col, (3, 20), (10, 20), 2)
        pygame.draw.circle(s, (126, 190, 110), (21, 21), 2)       # a drifting leaf
    else:
        _cloud(s, 13, 12)
    if size != 26:
        s = pygame.transform.smoothscale(s, (size, size))
    _cache[key] = s
    return s


# --------------------------------------------------------------- seasons

def season_icon(season, size=22):
    key = ("hud_season", season, size)
    if key in _cache:
        return _cache[key]
    s = _s(22)
    se = (season or "").lower()
    if se == "spring":                               # pink blossom
        for k in range(5):
            a = k * math.tau / 5 - math.pi / 2
            pygame.draw.circle(s, (248, 170, 200), (int(11 + math.cos(a) * 5),
                                                    int(11 + math.sin(a) * 5)), 4)
        pygame.draw.circle(s, (255, 226, 130), (11, 11), 3)
    elif se == "summer":                             # sunflower-ish sun
        _sun(s, 11, 11, 5, (255, 196, 70))
    elif se == "fall":                               # maple-ish leaf
        pts = [(11, 2), (14, 7), (19, 6), (17, 11), (20, 14), (14, 14), (11, 19),
               (8, 14), (2, 14), (5, 11), (3, 6), (8, 7)]
        pygame.draw.polygon(s, (226, 124, 58), pts)
        pygame.draw.polygon(s, (170, 78, 40), pts, 1)
        pygame.draw.line(s, (150, 72, 38), (11, 8), (11, 21), 2)
    else:                                            # snowflake
        col = (206, 232, 250)
        for k in range(3):
            a = k * math.pi / 3
            dx, dy = math.cos(a) * 9, math.sin(a) * 9
            pygame.draw.line(s, col, (int(11 - dx), int(11 - dy)), (int(11 + dx), int(11 + dy)), 2)
        pygame.draw.circle(s, (255, 255, 255), (11, 11), 2)
    if size != 22:
        s = pygame.transform.smoothscale(s, (size, size))
    _cache[key] = s
    return s


SEASON_TINT = {"spring": (132, 206, 130), "summer": (240, 196, 86),
               "fall": (226, 136, 70), "winter": (150, 196, 236)}


# --------------------------------------------------------------- stat icons

def coin_icon(size=18):
    key = ("hud_coin", size)
    if key in _cache:
        return _cache[key]
    s = _s(18)
    pygame.draw.circle(s, (176, 124, 36), (9, 10), 8)
    pygame.draw.circle(s, (246, 200, 76), (9, 9), 8)
    pygame.draw.circle(s, (255, 228, 128), (9, 9), 6)
    pygame.draw.circle(s, (214, 164, 52), (9, 9), 6, 1)
    pygame.draw.line(s, (196, 146, 40), (9, 5), (9, 13), 2)
    pygame.draw.circle(s, (255, 250, 220), (6, 6), 1)
    if size != 18:
        s = pygame.transform.smoothscale(s, (size, size))
    _cache[key] = s
    return s


def heart_icon(size=14, col=(240, 96, 120)):
    key = ("hud_heart", size, col)
    if key in _cache:
        return _cache[key]
    s = _s(14)
    pygame.draw.circle(s, col, (4, 5), 4)
    pygame.draw.circle(s, col, (10, 5), 4)
    pygame.draw.polygon(s, col, [(0, 6), (14, 6), (7, 13)])
    pygame.draw.circle(s, (255, 214, 224), (4, 4), 1)
    if size != 14:
        s = pygame.transform.smoothscale(s, (size, size))
    _cache[key] = s
    return s


def bolt_icon(size=14, col=(130, 220, 120)):
    key = ("hud_bolt", size, col)
    if key in _cache:
        return _cache[key]
    s = _s(14)
    pts = [(8, 0), (2, 8), (6, 8), (5, 14), (12, 5), (8, 5), (10, 0)]
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, tuple(int(c * 0.6) for c in col), pts, 1)
    if size != 14:
        s = pygame.transform.smoothscale(s, (size, size))
    _cache[key] = s
    return s


BUFF_COLORS = {"speed": (120, 210, 240), "luck": (120, 214, 130), "mining": (190, 160, 130),
               "fishing": (110, 170, 236), "farming": (150, 214, 100),
               "combat": (238, 108, 96), "defense": (170, 180, 206), "regen": (250, 206, 100)}


def buff_icon(kind, size=18):
    """Round badge per buff kind; unknown kinds get a sparkle star."""
    key = ("hud_buff", kind, size)
    if key in _cache:
        return _cache[key]
    s = _s(18)
    col = BUFF_COLORS.get(kind, (214, 180, 240))
    pygame.draw.circle(s, (30, 26, 40), (9, 9), 9)
    pygame.draw.circle(s, col, (9, 9), 8)
    pygame.draw.circle(s, tuple(min(255, c + 40) for c in col), (9, 9), 8, 1)
    ink = (38, 30, 44)
    if kind == "speed":                                   # boot-wing chevrons
        for x in (5, 9):
            pygame.draw.lines(s, ink, False, [(x, 5), (x + 4, 9), (x, 13)], 2)
    elif kind == "luck":                                  # clover
        for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
            pygame.draw.circle(s, (40, 110, 50), (9 + dx, 8 + dy), 2)
        pygame.draw.line(s, (40, 110, 50), (9, 10), (11, 14), 1)
    elif kind == "mining":                                # pick
        pygame.draw.arc(s, ink, (4, 4, 11, 8), 0.2, 2.9, 2)
        pygame.draw.line(s, ink, (9, 6), (9, 14), 2)
    elif kind == "fishing":                               # fish
        pygame.draw.ellipse(s, ink, (4, 7, 8, 5))
        pygame.draw.polygon(s, ink, [(12, 9), (15, 6), (15, 12)])
    elif kind == "farming":                               # sprout
        pygame.draw.line(s, ink, (9, 14), (9, 8), 2)
        pygame.draw.ellipse(s, ink, (4, 5, 6, 4))
        pygame.draw.ellipse(s, ink, (9, 4, 6, 4))
    elif kind == "combat":                                # sword
        pygame.draw.line(s, ink, (5, 13), (13, 5), 2)
        pygame.draw.line(s, ink, (5, 10), (8, 13), 2)
    elif kind == "defense":                               # shield
        pygame.draw.polygon(s, ink, [(5, 5), (13, 5), (13, 9), (9, 14), (5, 9)], 2)
    elif kind == "regen":                                 # plus
        pygame.draw.line(s, ink, (9, 5), (9, 13), 3)
        pygame.draw.line(s, ink, (5, 9), (13, 9), 3)
    else:                                                 # sparkle
        pygame.draw.line(s, ink, (9, 4), (9, 14), 1)
        pygame.draw.line(s, ink, (4, 9), (14, 9), 1)
        pygame.draw.circle(s, ink, (9, 9), 2)
    if size != 18:
        s = pygame.transform.smoothscale(s, (size, size))
    _cache[key] = s
    return s


def face_icon(frame, size=30):
    """Head crop of a character's front walk frame (cached per frame surface)."""
    key = ("hud_face", id(frame), size)
    hit = _cache.get(key)
    if hit is not None and hit[0] is frame:
        return hit[1]
    fw, fh = frame.get_size()
    w = min(32, fw)
    r = pygame.Rect((fw - w) // 2, 0, w, min(30, fh))
    head = frame.subsurface(r).copy()
    out = pygame.transform.scale(head, (size, int(size * r.h / r.w)))
    _cache[key] = (frame, out)
    return out


# --------------------------------------------------------------- day/night dial

def dial_base(r=15):
    """Half-disc day/night dial background (sky gradient + ground line)."""
    key = ("hud_dial", r)
    if key in _cache:
        return _cache[key]
    s = _s(r * 2 + 4, r + 6)
    cx, cy = r + 2, r + 2
    for i in range(r, 0, -1):
        f = i / r
        col = (int(60 + 120 * (1 - f)), int(90 + 110 * (1 - f)), int(160 + 70 * (1 - f)))
        pygame.draw.circle(s, col, (cx, cy), i, draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(s, (250, 238, 200), (cx, cy), r, 1, draw_top_left=True,
                       draw_top_right=True)
    pygame.draw.line(s, (120, 170, 100), (1, cy), (r * 2 + 3, cy), 3)
    _cache[key] = s
    return s


def moon_icon(size=10):
    key = ("hud_moon", size)
    if key in _cache:
        return _cache[key]
    s = _s(size)
    h = size // 2
    pygame.draw.circle(s, (240, 236, 210), (h, h), h)
    pygame.draw.circle(s, (0, 0, 0, 0), (h + 3, h - 2), h)
    _cache[key] = s
    return s
