"""World terrain & structure sprites: water, trees, rocks,
buildings, and the boss name tag.

Owner: "World, Areas & Build" chat for content tuning; "UI & Rendering" for art.
"""
import math
import pygame
from ..settings import TILE
from ._base import _cache, _surf, _shade, _bldfont


def water_frames():
    if "water" in _cache:
        return _cache["water"]
    base = (62, 116, 188)
    hi = (110, 165, 222)
    frames = []
    for f in range(8):
        s = _surf()
        s.fill(base)
        off = f / 8 * TILE
        for row in range(0, TILE, 8):
            phase = math.sin((row + off) / TILE * math.tau)
            x = int((phase + 1) / 2 * (TILE - 16))
            pygame.draw.line(s, hi, (x, row + 3), (x + 12, row + 3), 2)
        frames.append(s)
    _cache["water"] = frames
    return frames


def tree_frames(season=None):
    """Swaying tree frames. ``season`` (Spring/Summer/Fall/Winter) picks the
    canopy: spring blossoms, summer lush green, fall orange/red/gold, winter
    bare frosted branches. ``None`` keeps the classic green tree."""
    se = (season or "").lower()
    key = ("tree", se) if se else "tree"
    if key in _cache:
        return _cache[key]
    frames = []
    for f in range(5):
        s = _surf((TILE, TILE * 2))
        cx = TILE // 2
        sway = int(math.sin(f / 5 * math.tau) * 2)
        # trunk (pastel bark)
        pygame.draw.rect(s, (150, 112, 78), (cx - 5, TILE + 22, 10, TILE - 22), border_radius=2)
        pygame.draw.rect(s, (130, 96, 66), (cx - 5, TILE + 22, 4, TILE - 22), border_radius=2)
        if se == "winter":
            # bare branches with snow caps + a few frost glints
            bark, snow = (132, 100, 74), (246, 250, 255)
            pygame.draw.line(s, bark, (cx, TILE + 24), (cx + sway, TILE - 14), 5)
            for (bx, by, ex, ey) in ((0, 10, -14, -6), (0, 4, 13, -10), (0, -4, -9, -18),
                                     (0, -8, 8, -22), (-7, 0, -17, 4), (6, -2, 17, 0)):
                x0, y0 = cx + bx + sway, TILE + by
                x1, y1 = cx + ex + sway, TILE + ey
                pygame.draw.line(s, bark, (x0, y0), (x1, y1), 3)
                pygame.draw.line(s, snow, (x0, y0 - 2), (x1, y1 - 2), 2)
                pygame.draw.circle(s, snow, (x1, y1 - 1), 2)
            pygame.draw.ellipse(s, snow, (cx - 9 + sway, TILE - 20, 18, 7))
            for gx, gy in ((cx - 12, TILE - 4), (cx + 10, TILE - 14), (cx + 2, TILE + 6)):
                pygame.draw.circle(s, (206, 232, 250), (gx + sway, gy), 1)
        else:
            if se == "fall":
                c1, c2, c3, c4 = (214, 118, 60), (232, 150, 70), (246, 190, 90), (252, 220, 140)
            elif se == "spring":
                c1, c2, c3, c4 = (124, 190, 124), (146, 206, 144), (176, 224, 170), (206, 240, 198)
            elif se == "summer":
                c1, c2, c3, c4 = (92, 164, 100), (116, 184, 118), (150, 208, 146), (186, 228, 176)
            else:
                c1, c2, c3, c4 = (108, 172, 112), (130, 192, 134), (162, 214, 162), (190, 230, 188)
            # canopy kept inside the 48px width so it never clips on the sides
            pygame.draw.circle(s, _shade(c1, 0.82), (cx + sway, TILE + 7), 18)
            pygame.draw.circle(s, c1, (cx + sway, TILE + 4), 19)
            pygame.draw.circle(s, c2, (cx - 8 + sway, TILE - 2), 14)
            pygame.draw.circle(s, c2, (cx + 9 + sway, TILE), 13)
            pygame.draw.circle(s, c3, (cx + sway, TILE - 8), 10)
            pygame.draw.circle(s, c4, (cx - 3 + sway, TILE - 11), 4)
            if se == "spring":                      # pink blossoms
                for bx, by in ((-12, -4), (8, -10), (12, 6), (-4, 8), (-9, -14), (3, -1)):
                    pygame.draw.circle(s, (250, 186, 208), (cx + bx + sway, TILE + by), 3)
                    pygame.draw.circle(s, (255, 236, 244), (cx + bx + sway, TILE + by), 1)
            elif se == "fall":                      # a few red accent leaves
                for bx, by in ((-13, 2), (11, -6), (4, 10), (-6, -12)):
                    pygame.draw.circle(s, (196, 72, 56), (cx + bx + sway, TILE + by), 3)
            elif se == "summer":                    # tiny fruit
                for bx, by in ((-9, 4), (10, -2), (2, 9)):
                    pygame.draw.circle(s, (236, 96, 90), (cx + bx + sway, TILE + by), 2)
        frames.append(s)
    _cache[key] = frames
    return frames


def tree_sprite(season=None):
    return tree_frames(season)[0]


def tilled_tile(wet=False, season=None):
    """Worked soil tile with furrows (dry = warm tan, wet = dark and glossy)."""
    key = ("tilled", bool(wet))
    if key in _cache:
        return _cache[key]
    s = _surf()
    base = (122, 92, 68) if wet else (158, 118, 86)
    rim = _shade(base, 0.78)
    pygame.draw.rect(s, rim, (2, 3, TILE - 4, TILE - 4), border_radius=5)
    pygame.draw.rect(s, base, (3, 3, TILE - 6, TILE - 7), border_radius=4)
    for i, y in enumerate(range(8, TILE - 6, 8)):
        pygame.draw.line(s, _shade(base, 0.72), (7, y + 2), (TILE - 8, y + 2), 2)
        pygame.draw.line(s, _shade(base, 1.14), (7, y), (TILE - 8, y), 1)
        for x in range(9 + (i % 2) * 5, TILE - 10, 11):              # soil clods
            pygame.draw.circle(s, _shade(base, 0.86), (x, y + 4), 1)
    if wet:
        for x, y in ((12, 11), (30, 23), (20, 35)):
            pygame.draw.line(s, (170, 150, 140), (x, y), (x + 4, y), 1)   # damp sheen
    _cache[key] = s
    return s


def shore_foam(mask, phase):
    """Foam lip on a water tile along the sides touching land.
    mask bits: 1 = land above, 2 = right, 4 = below, 8 = left."""
    key = ("foam", mask, phase)
    if key in _cache:
        return _cache[key]
    s = _surf()
    a = 150 + int(60 * math.sin(phase / 4 * math.tau))
    foam = (250, 252, 255, a)
    wave = (226, 240, 250, 120)
    off = int(2 * math.sin(phase / 4 * math.tau))
    if mask & 1:
        pygame.draw.rect(s, wave, (0, 0, TILE, 7 + off))
        for x in range(0, TILE, 8):
            pygame.draw.circle(s, foam, (x + 4, 3 + off), 3)
    if mask & 4:
        pygame.draw.rect(s, wave, (0, TILE - 7 - off, TILE, 7 + off))
        for x in range(0, TILE, 8):
            pygame.draw.circle(s, foam, (x + 4, TILE - 4 - off), 3)
    if mask & 8:
        pygame.draw.rect(s, wave, (0, 0, 7 + off, TILE))
        for y in range(0, TILE, 8):
            pygame.draw.circle(s, foam, (3 + off, y + 4), 3)
    if mask & 2:
        pygame.draw.rect(s, wave, (TILE - 7 - off, 0, 7 + off, TILE))
        for y in range(0, TILE, 8):
            pygame.draw.circle(s, foam, (TILE - 4 - off, y + 4), 3)
    _cache[key] = s
    return s


def rock_sprite(ore=None, tint=None):
    """Breakable mine boulder. ``tint`` (an RGB tuple, e.g. the biome colour) gently
    blends the stone toward that hue so ice/lava/crystal depths feel different —
    the rock still reads as rock, just cooler/warmer/violet."""
    key = ("rock", ore, tint)
    if key in _cache:
        return _cache[key]

    def mix(c, f):
        return c if not tint else tuple(int(c[i] + (tint[i] - c[i]) * f) for i in range(3))

    s = _surf()
    shadow = mix((70, 70, 82), 0.55)
    base = mix((122, 122, 134), 0.42)
    hi = mix((150, 150, 162), 0.40)
    pygame.draw.circle(s, shadow, (TILE // 2, TILE // 2 + 4), 19)
    pygame.draw.circle(s, base, (TILE // 2, TILE // 2), 17)
    pygame.draw.circle(s, hi, (TILE // 2 - 5, TILE // 2 - 5), 6)
    if tint:
        # a faint biome-coloured rim + sheen so the hue clearly belongs to the rock
        pygame.draw.circle(s, mix((150, 150, 162), 0.75), (TILE // 2, TILE // 2), 17, 2)
        pygame.draw.circle(s, mix((180, 180, 190), 0.9), (TILE // 2 + 4, TILE // 2 + 3), 2)
    glint = {"copper": (205, 120, 70), "iron": (210, 205, 205), "gold": (240, 205, 80)}
    if ore in glint:
        for p in [(18, 20), (30, 28), (24, 14)]:
            pygame.draw.circle(s, glint[ore], p, 4)
            pygame.draw.circle(s, (255, 255, 255), (p[0] - 1, p[1] - 1), 1)
    _cache[key] = s
    return s


def building_sprite(w, h, wall, roof, label=None):
    """Cute storybook building: pitched roof + eaves, striped awning & sign for a
    shop (or chimney for a home), framed flower-box windows and an arched door."""
    key = ("bld", w, h, wall, roof, label)
    if key in _cache:
        return _cache[key]
    s = _surf((w, h))
    wdk, wlt = _shade(wall, 0.80), _shade(wall, 1.12)
    rdk, rlt = _shade(roof, 0.78), _shade(roof, 1.18)
    is_home = (label or "").strip().lower() in ("home", "house", "")
    roof_h = int(h * 0.40)

    pygame.draw.ellipse(s, (0, 0, 0, 45), (12, h - 11, w - 24, 11))     # ground shadow
    # ---- body ----
    body_top = roof_h - 4
    pygame.draw.rect(s, wall, (6, body_top, w - 12, h - body_top - 4), border_radius=7)
    pygame.draw.rect(s, wlt, (10, body_top + 4, w - 20, 4), border_radius=2)
    pygame.draw.rect(s, wdk, (6, h - 14, w - 12, 10), border_radius=6)  # foundation
    pygame.draw.rect(s, _shade(wall, 0.6), (6, body_top, w - 12, h - body_top - 4),
                     2, border_radius=7)
    # ---- roof (trapezoid with eaves + scallops + ridge highlight) ----
    pygame.draw.polygon(s, roof, [(2, roof_h), (w * 0.22, 4), (w * 0.78, 4), (w - 2, roof_h)])
    pygame.draw.line(s, rlt, (int(w * 0.22) + 3, 7), (int(w * 0.78) - 3, 7), 2)
    pygame.draw.polygon(s, rdk, [(2, roof_h), (w * 0.22, 4), (w * 0.78, 4), (w - 2, roof_h)], 2)
    for i in range(6, w - 4, 16):
        pygame.draw.circle(s, rlt, (i + 8, roof_h), 6)
    pygame.draw.circle(s, (248, 150, 170), (w // 2, 13), 3)             # heart on the gable
    pygame.draw.circle(s, (248, 150, 170), (w // 2 + 6, 13), 3)
    pygame.draw.polygon(s, (248, 150, 170), [(w // 2 - 3, 15), (w // 2 + 9, 15), (w // 2 + 3, 22)])
    # ---- chimney (home only) ----
    if is_home:
        pygame.draw.rect(s, wdk, (int(w * 0.70), 6, 14, roof_h - 2), border_radius=2)
        pygame.draw.rect(s, _shade(wall, 0.5), (int(w * 0.70) - 1, 4, 16, 5), border_radius=2)
    # ---- shop awning + hanging sign ----
    if not is_home:
        ay, ax, aw = body_top + 2, 14, w - 28
        stripe = max(12, aw // 7)
        for i in range(ax, ax + aw, stripe):
            col = roof if ((i - ax) // stripe) % 2 == 0 else (250, 250, 250)
            pygame.draw.rect(s, col, (i, ay, min(stripe, ax + aw - i), 15))
        for i in range(ax, ax + aw, stripe):
            pygame.draw.polygon(s, rdk, [(i, ay + 15), (i + stripe // 2, ay + 21),
                                         (min(i + stripe, ax + aw), ay + 15)])
        sb_w, sb_h = min(int(w * 0.52), 150), 24
        sbx, sby = (w - sb_w) // 2, roof_h - 6
        pygame.draw.line(s, (150, 110, 70), (sbx + 8, sby), (sbx + 8, roof_h - 14), 2)
        pygame.draw.line(s, (150, 110, 70), (sbx + sb_w - 8, sby), (sbx + sb_w - 8, roof_h - 14), 2)
        pygame.draw.rect(s, (250, 236, 196), (sbx, sby, sb_w, sb_h), border_radius=6)
        pygame.draw.rect(s, (198, 150, 96), (sbx, sby, sb_w, sb_h), 2, border_radius=6)
        if label:
            t = _bldfont().render(label.upper(), True, (158, 100, 60))
            s.blit(t, (sbx + (sb_w - t.get_width()) // 2, sby + (sb_h - t.get_height()) // 2))
    # ---- arched door ----
    dw, dh = 28, 38
    dx, dy = w // 2 - dw // 2, h - 4 - dh
    pygame.draw.rect(s, _shade(roof, 0.7), (dx - 2, dy - 2, dw + 4, dh + 2),
                     border_top_left_radius=12, border_top_right_radius=12)
    pygame.draw.rect(s, (126, 86, 56), (dx, dy, dw, dh),
                     border_top_left_radius=11, border_top_right_radius=11)
    pygame.draw.rect(s, (152, 106, 70), (dx + 3, dy + 5, dw - 6, dh - 7),
                     border_top_left_radius=8, border_top_right_radius=8)
    pygame.draw.circle(s, (240, 214, 120), (dx + dw - 7, dy + dh // 2 + 2), 2)
    pygame.draw.ellipse(s, _shade(roof, 1.12), (dx - 7, h - 8, dw + 14, 6))   # welcome mat
    # ---- framed flower-box windows ----
    for wx in (int(w * 0.13), int(w * 0.87) - 28):
        wy = h - 6 - 30
        pygame.draw.rect(s, (236, 244, 250), (wx, wy, 28, 26), border_radius=3)
        pygame.draw.rect(s, (158, 208, 236), (wx + 3, wy + 3, 22, 20), border_radius=2)
        pygame.draw.polygon(s, (206, 230, 248), [(wx + 3, wy + 18), (wx + 3, wy + 9), (wx + 16, wy + 21)])
        pygame.draw.line(s, (236, 244, 250), (wx + 14, wy + 3), (wx + 14, wy + 23), 2)
        pygame.draw.line(s, (236, 244, 250), (wx + 3, wy + 13), (wx + 25, wy + 13), 2)
        pygame.draw.rect(s, _shade(wall, 0.55), (wx, wy, 28, 26), 2, border_radius=3)
        pygame.draw.rect(s, (150, 104, 68), (wx - 2, wy + 23, 32, 7), border_radius=2)   # box
        for fx in (wx + 5, wx + 14, wx + 23):
            pygame.draw.circle(s, (246, 150, 180), (fx, wy + 23), 2)
            pygame.draw.circle(s, (250, 224, 120), (fx, wy + 23), 1)
    _cache[key] = s
    return s


_boss_font = None
# combat_system installs a (weak) callable returning the name the screen boss
# bar is showing right now (or None): that boss's in-world tag steps aside
BOSS_TAG_HIDDEN = None
_NO_TAG = []


def _tag_hidden():
    f = BOSS_TAG_HIDDEN
    if f is None:
        return None
    try:
        f = f()                      # weakref.WeakMethod -> bound method (or None)
        return f() if f is not None else None
    except Exception:
        return None


def boss_on_screen_bar(text):
    """True while the screen boss bar shows the boss named ``text`` (its
    in-world name tag and HP bar step aside meanwhile)."""
    return BOSS_TAG_HIDDEN is not None and text == _tag_hidden()


def boss_label(text):
    """Cached gold name tag drawn above boss monsters: outlined so it reads on
    ice, snow and pale stone alike.  The tag is blitted with its top 16 px above
    the boss's HP bar, so the outlined text is trimmed into a 16 px strip
    (never overlapping the bar)."""
    if boss_on_screen_bar(text):
        if not _NO_TAG:
            _NO_TAG.append(pygame.Surface((1, 1), pygame.SRCALPHA))
        return _NO_TAG[0]
    key = ("boss", text)
    if key in _cache:
        return _cache[key]
    global _boss_font
    if _boss_font is None:
        if not pygame.font.get_init():
            pygame.font.init()
        _boss_font = pygame.font.SysFont("consolas", 13, bold=True)
    from .. import ui_kit
    ol = ui_kit.outlined(_boss_font, text, (255, 220, 120), (40, 24, 30), 2)
    surf = pygame.Surface((ol.get_width(), 16), pygame.SRCALPHA)
    surf.blit(ol, (0, -ol.get_bounding_rect().top))    # same baseline for every name
    _cache[key] = surf
    return surf


def crop_sprite(stage, color=(120, 180, 90), dead=False):
    """Growing-crop foliage on a tilled tile (48x48, feet at the bottom).
    stage 0 = sprout, 1 = young, 2 = budding, 3 = full (the renderer adds the
    produce icon on top when ready). ``color`` tints the buds."""
    key = ("crop", int(stage), tuple(color), bool(dead))
    if key in _cache:
        return _cache[key]
    s = _surf()
    cx, by = TILE // 2, TILE - 6
    if dead:
        stem = (140, 112, 74)
        pygame.draw.line(s, stem, (cx, by), (cx + 2, by - 12), 2)
        pygame.draw.line(s, stem, (cx + 2, by - 12), (cx + 8, by - 8), 2)
        pygame.draw.ellipse(s, (166, 136, 90), (cx - 9, by - 7, 9, 5))
        pygame.draw.ellipse(s, (150, 120, 80), (cx + 5, by - 9, 8, 5))
        _cache[key] = s
        return s
    leaf, leaf_dk, leaf_lt = (112, 184, 96), (78, 142, 70), (160, 216, 134)
    stem = (82, 136, 70)
    pygame.draw.ellipse(s, (0, 0, 0, 40), (cx - 10, by - 2, 20, 6))          # contact shadow
    if stage <= 0:
        pygame.draw.line(s, stem, (cx, by), (cx, by - 8), 2)
        pygame.draw.ellipse(s, leaf, (cx - 7, by - 12, 7, 5))
        pygame.draw.ellipse(s, leaf_lt, (cx, by - 13, 7, 5))
    elif stage == 1:
        pygame.draw.line(s, stem, (cx, by), (cx, by - 16), 2)
        for (dx, dy, w, h, c) in ((-10, -10, 10, 6, leaf_dk), (1, -12, 10, 6, leaf),
                                  (-8, -18, 9, 6, leaf), (0, -20, 9, 6, leaf_lt)):
            pygame.draw.ellipse(s, c, (cx + dx, by + dy, w, h))
    else:
        pygame.draw.line(s, stem, (cx, by), (cx, by - 18), 3)
        for (dx, dy, w, h, c) in ((-14, -9, 13, 8, leaf_dk), (2, -10, 13, 8, leaf_dk),
                                  (-12, -17, 12, 8, leaf), (1, -18, 12, 8, leaf),
                                  (-6, -24, 12, 8, leaf_lt)):
            pygame.draw.ellipse(s, c, (cx + dx, by + dy, w, h))
            pygame.draw.line(s, _shade(c, 0.8), (cx + dx + 2, by + dy + h // 2),
                             (cx + dx + w - 3, by + dy + h // 2), 1)
        if stage == 2:                                                    # little buds
            bud = _shade(color, 0.85)
            for bx, byy in ((-7, -16), (6, -14), (0, -22)):
                pygame.draw.circle(s, bud, (cx + bx, by + byy), 2)
    _cache[key] = s
    return s
