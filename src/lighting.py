"""Time-of-day colour grading, vignette and soft light glows.

A single full-screen tint is interpolated across keyframes (dawn -> day -> dusk ->
night) and alpha-blended over the rendered scene. A cached vignette adds gentle
edge falloff, and at dusk/night each player carries a warm lantern glow so the
world stays readable while feeling moody. Tuned for a soft pastel mood.
"""
import pygame
from .settings import SCREEN_W, SCREEN_H

# (minute-of-day, tint RGB, alpha)  -- minutes: 360=6:00 .. 1560=26:00(=2am)
_KEYS = [
    (360,  (255, 208, 156), 64),    # 6:00  soft warm dawn haze
    (450,  (255, 240, 214), 0),     # 7:30  clear pastel day
    (1010, (255, 240, 214), 0),     # 16:50 still day
    (1110, (255, 178, 120), 56),    # 18:30 golden hour
    (1200, (150, 120, 186), 96),    # 20:00 lilac dusk
    (1320, (84, 86, 156), 140),     # 22:00 night
    (1560, (52, 56, 122), 168),     # 26:00 deep night
]


def grade(minutes):
    m = max(_KEYS[0][0], min(_KEYS[-1][0], minutes))
    for i in range(len(_KEYS) - 1):
        m0, c0, a0 = _KEYS[i]
        m1, c1, a1 = _KEYS[i + 1]
        if m0 <= m <= m1:
            t = (m - m0) / (m1 - m0) if m1 > m0 else 0.0
            col = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
            return col, a0 + (a1 - a0) * t
    return _KEYS[-1][1], _KEYS[-1][2]


# Late-night DARKENING: the scene is multiplied by a cool blue (so darks stay
# dark and lamps get contrast) and the tint overlay above is thinned out, instead
# of alpha-washing everything towards a flat lavender haze.
# (minute-of-day, multiply RGB, overlay-alpha scale)
_NIGHT_KEYS = [
    (1140, (255, 255, 255), 1.0),   # 19:00 no darkening yet
    (1200, (236, 234, 246), 0.95),  # 20:00 dusk
    (1320, (144, 156, 208), 0.62),  # 22:00 night
    (1410, (80, 96, 160), 0.42),    # 23:30 late night
    (1560, (72, 88, 150), 0.42),    # 26:00 deep night
]


def night_mult(minutes):
    """(multiply colour, overlay alpha scale) for the clock time."""
    if minutes <= _NIGHT_KEYS[0][0]:
        return None, 1.0
    m = min(_NIGHT_KEYS[-1][0], minutes)
    for i in range(len(_NIGHT_KEYS) - 1):
        m0, c0, a0 = _NIGHT_KEYS[i]
        m1, c1, a1 = _NIGHT_KEYS[i + 1]
        if m0 <= m <= m1:
            t = (m - m0) / (m1 - m0)
            return (tuple(int(c0[k] + (c1[k] - c0[k]) * t) // 4 * 4 for k in range(3)),
                    a0 + (a1 - a0) * t)
    return _NIGHT_KEYS[-1][1], _NIGHT_KEYS[-1][2]


_cache = {}

# Weather grading (Core weather_system sets it each frame): None or
# ((r, g, b), alpha) -- a storm darkens the sky, fog washes it pale. Only applied
# to outdoor areas (see _OUTDOOR); the renderer's apply() call is unchanged.
_WEATHER_TINT = None
_OUTDOOR = ("farm", "town", "forest", "beach", "meadow")


def set_weather_tint(tint):
    global _WEATHER_TINT
    _WEATHER_TINT = tint


def _overlay(col, alpha):
    """ONE reusable full-screen tint surface, refilled only when the tint
    changes -- no 1280x720 SRCALPHA allocation per frame (and no big cache)."""
    rgba = (int(col[0]), int(col[1]), int(col[2]), max(0, min(255, int(alpha))))
    s = _cache.get("ov")
    if s is None:
        s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        _cache["ov"] = s
        _cache["ov_rgba"] = None
    if _cache.get("ov_rgba") != rgba:
        s.fill(rgba)
        _cache["ov_rgba"] = rgba
    return s


def _vignette():
    if "vig" not in _cache:
        small = pygame.Surface((160, 90), pygame.SRCALPHA)
        cx, cy = 80, 45
        maxd = (cx * cx + cy * cy) ** 0.5
        for y in range(90):
            for x in range(160):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / maxd
                a = int(max(0.0, (d - 0.55)) * 150)
                small.set_at((x, y), (18, 16, 30, min(120, a)))
        _cache["vig"] = pygame.transform.smoothscale(small, (SCREEN_W, SCREEN_H))
    return _cache["vig"]


def _radial(radius, color):
    """Soft additive glow sprite: falloff is baked into the RGB channels so it can
    be blitted with BLEND_RGBA_ADD (which ignores the alpha channel)."""
    key = ("rad", radius, color)
    if key not in _cache:
        n = 64
        small = pygame.Surface((n, n), pygame.SRCALPHA)
        c = n / 2
        for y in range(n):
            for x in range(n):
                d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5 / c
                v = max(0.0, 1.0 - d) * 0.85       # gentle linear falloff (no hot centre)
                small.set_at((x, y), (int(color[0] * v), int(color[1] * v),
                                      int(color[2] * v), 255))
        _cache[key] = pygame.transform.smoothscale(small, (radius * 2, radius * 2))
    return _cache[key]


def apply(screen, minutes, area_name, players, cam, lights=()):
    """Grade the already-rendered scene. Returns the night intensity (0..1).

    ``lights``: extra light sources gathered from ``_lights_*`` hooks, each a
    ``(world_x, world_y, radius_px, (r, g, b))`` tuple. They glow additively once
    it's dusk (or always underground), scaled by how dark it is."""
    mult = None
    if area_name == "mine":
        col, alpha = (46, 52, 78), 104          # constant cool cave gloom
    else:
        col, alpha = grade(minutes)
        if area_name == "home":
            alpha *= 0.55                        # cosier indoors
    # night intensity follows the CLOCK only -- a dark storm sky must not turn
    # daytime into "night" for lanterns / fireflies / NPC schedules
    night = min(1.0, float(alpha) / 150.0)
    if area_name != "mine":
        mult, ascale = night_mult(minutes)
        alpha *= ascale
        if mult and area_name == "home":         # indoors: only half as dark
            mult = tuple((v + 255) // 2 // 4 * 4 for v in mult)
    if area_name != "mine":
        wt = _WEATHER_TINT
        if wt and area_name in _OUTDOOR and wt[1] > 0:
            wcol, wa = wt
            # at night a grey rain / fog sky must not LIGHTEN the scene: pull the
            # weather colour towards the night tint so it only adds gloom
            nk = min(1.0, night)
            wcol = tuple(wcol[k] + (col[k] - wcol[k]) * nk for k in range(3))
            tot = alpha + wa
            col = tuple(int((col[k] * alpha + wcol[k] * wa) / tot) for k in range(3))
            alpha = min(200.0, max(alpha, wa) + min(alpha, wa) * 0.35)
    alpha = float(alpha)

    # darken first (multiply), then the hue tint, THEN the light pools on top so
    # lamps, lanterns and fireflies really glow at night instead of being graded
    # down with everything else
    if mult and mult != (255, 255, 255):
        screen.fill(mult, special_flags=pygame.BLEND_RGB_MULT)
    if alpha > 1:
        screen.blit(_overlay((int(col[0]), int(col[1]), int(col[2])), alpha), (0, 0))

    # warm lantern glow under each player (dusk/night or in the mine)
    if night > 0.15 or area_name == "mine":
        scale = min(0.25, 0.08 + night * 0.18)    # subtle — keeps the character readable
        scale = round(scale * 32) / 32            # quantised: _radial caches per colour
        warm = (int(255 * scale), int(210 * scale), int(140 * scale))
        glow = _radial(120, warm)
        for p in players:
            screen.blit(glow, (int(p.x - cam.x - 120), int(p.y - cam.y - 120)),
                        special_flags=pygame.BLEND_RGBA_ADD)

    if lights and (night > 0.12 or area_name == "mine"):
        k = 0.36 if area_name == "mine" else min(1.0, 0.25 + night) * 0.44
        k = round(k * 24) / 24                    # quantised: _radial caches per colour
        for (lx, ly, rad, lcol) in lights:
            rad = max(16, int(rad) // 16 * 16)    # quantised radius, same reason
            c = tuple(int(v * k) // 8 * 8 for v in lcol[:3])
            screen.blit(_radial(rad, c), (int(lx - cam.x - rad), int(ly - cam.y - rad)),
                        special_flags=pygame.BLEND_RGBA_ADD)

    screen.blit(_vignette(), (0, 0))
    return night
