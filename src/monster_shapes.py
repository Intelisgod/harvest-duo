"""Procedural art for the biome monsters + deep bosses (Chat 1).

Registered into ``monsters.SHAPE_PAINTERS``; entities.Monster calls
``painter(mon, surf, cx, cy)`` with the screen-space centre. Painters also draw
the monster's telegraphs (aim lines, slam rings) and projectiles
(``mon.shots``, world space -> screen via the (mon.x - cx) offset).

Style: cosy pastel pixel look -- soft outlines, big friendly eyes, one bright
highlight. Every alpha / glow surface is cached (no per-frame Surface builds
except tiny, bounded ones).
"""
import math
import colorsys
import pygame

from . import monsters as M
from .settings import TILE

_GLOW = {}
_RING = {}
_DISC = {}


def _lt(c, k=40):
    return tuple(min(255, int(v) + k) for v in c[:3])


def _dk(c, k=40):
    return tuple(max(0, int(v) - k) for v in c[:3])


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _capped(cache, limit=192):
    if len(cache) > limit:          # bounded memory even with animated keys
        cache.clear()


def glow(r, color, strength=90):
    """Cached soft radial glow, premultiplied on black (blit with BLEND_RGB_ADD)."""
    r = max(2, int(r) // 2 * 2)
    strength = int(strength) // 10 * 10
    key = (r, tuple(color[:3]), strength)
    s = _GLOW.get(key)
    if s is None:
        _capped(_GLOW)
        s = pygame.Surface((r * 2, r * 2))
        s.fill((0, 0, 0))
        for i in range(6, 0, -1):
            rr = max(1, int(r * i / 6))
            k = strength / 255.0 * (1 - i / 7.0) * 0.8
            pygame.draw.circle(s, (int(color[0] * k), int(color[1] * k), int(color[2] * k)), (r, r), rr)
        _GLOW[key] = s
    return s


def _blit_glow(surf, x, y, r, color, strength=90):
    g = glow(r, color, strength)
    surf.blit(g, (int(x - g.get_width() / 2), int(y - g.get_height() / 2)),
              special_flags=pygame.BLEND_RGB_ADD)


def ring_surface(r, color, alpha=200, width=3):
    r = max(4, int(r) // 4 * 4)
    alpha = int(alpha) // 20 * 20
    key = (r, tuple(color[:3]), alpha, width)
    s = _RING.get(key)
    if s is None:
        _capped(_RING, 96)
        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (color[0], color[1], color[2], alpha),
                            (2, 2 + r // 3, r * 2, int(r * 1.34)), width)
        _RING[key] = s
    return s


def disc_surface(r, color, alpha=70):
    r = max(4, int(r) // 6 * 6)
    alpha = int(alpha) // 15 * 15
    key = (r, tuple(color[:3]), alpha)
    s = _DISC.get(key)
    if s is None:
        _capped(_DISC, 96)
        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (color[0], color[1], color[2], alpha),
                            (2, 2 + r // 3, r * 2, int(r * 1.34)))
        _DISC[key] = s
    return s


def _ai(mon):
    return mon.__dict__.get("ai") or {}


def _eyes(surf, x, y, sp, r, white=(252, 252, 255), pupil=(40, 36, 52), glint=True):
    for ex in (x - sp, x + sp):
        pygame.draw.circle(surf, white, (int(ex), int(y)), r)
        pygame.draw.circle(surf, pupil, (int(ex), int(y + 1)), max(1, r - 1))
        if glint:
            pygame.draw.circle(surf, (255, 255, 255), (int(ex - r * 0.35), int(y - r * 0.35)),
                               max(1, r // 3))


def draw_shots(mon, surf, cx, cy):
    shots = mon.__dict__.get("shots")
    if not shots:
        return
    ox, oy = mon.x - cx, mon.y - cy
    for s in shots:
        x, y = s["x"] - ox, s["y"] - oy
        r = s["r"]
        if s["kind"] == "void":
            core, rim = (236, 214, 255), (150, 92, 220)
        elif s["kind"] == "snow":
            core, rim = (255, 255, 255), (170, 214, 245)
        else:
            core, rim = (255, 240, 170), (255, 128, 50)
        n = math.hypot(s["vx"], s["vy"]) or 1
        tx, ty = -s["vx"] / n, -s["vy"] / n
        for k in (3, 2, 1):                                  # little comet tail
            pygame.draw.circle(surf, _dk(rim, 10 * k),
                               (int(x + tx * r * 0.9 * k), int(y + ty * r * 0.9 * k)),
                               max(1, int(r * (1 - k * 0.22))))
        _blit_glow(surf, x, y, r * 2.6, rim, 110)
        pygame.draw.circle(surf, rim, (int(x), int(y)), r)
        pygame.draw.circle(surf, core, (int(x - r * 0.2), int(y - r * 0.2)), max(2, int(r * 0.55)))


def _aim_line(surf, cx, cy, aim, length, prog, color=(255, 70, 90)):
    """Telegraph: dotted line in the locked charge direction, filling up."""
    ax, ay = aim
    n = 9
    for i in range(n):
        f = (i + 1) / n
        if f > prog + 0.12:
            break
        x = cx + ax * length * f
        y = cy + ay * length * f + 6
        r = 2 if i % 2 else 3
        pygame.draw.circle(surf, color, (int(x), int(y)), r)
    ex, ey = cx + ax * length, cy + ay * length + 6
    if prog > 0.5:
        pygame.draw.circle(surf, color, (int(ex), int(ey)), 6, 2)


# ================================================================ painters
def paint_icebat(mon, surf, cx, cy):
    col = mon.color
    st = _ai(mon)
    diving = st.get("mode") == "dive"
    flap = -3 if diving else math.sin(mon.anim_t * 1.8) * 5
    span = 11 if diving else 16
    wing = _mix(col, (255, 255, 255), 0.25)
    edge = _dk(col, 70)
    for sgn in (-1, 1):
        pts = [(cx + sgn * 3, cy - 2), (cx + sgn * span, cy - 9 - flap),
               (cx + sgn * (span - 2), cy - 2 - flap * 0.5), (cx + sgn * (span - 1), cy + 3 - flap * 0.3),
               (cx + sgn * (span - 6), cy + 2), (cx + sgn * 6, cy + 6)]
        pygame.draw.polygon(surf, wing, pts)
        pygame.draw.polygon(surf, edge, pts, 1)
        pygame.draw.line(surf, _lt(col, 60), (cx + sgn * 4, cy - 1), (cx + sgn * (span - 1), cy - 8 - flap), 1)
        pygame.draw.circle(surf, (255, 255, 255), (int(cx + sgn * span), int(cy - 9 - flap)), 2)
    body = (104, 150, 204)
    pygame.draw.circle(surf, body, (int(cx), int(cy)), 8)
    pygame.draw.ellipse(surf, (232, 244, 255), (cx - 5, cy - 1, 10, 8))
    for sgn in (-1, 1):                                     # ears
        pygame.draw.polygon(surf, body, [(cx + sgn * 2, cy - 6), (cx + sgn * 6, cy - 12), (cx + sgn * 7, cy - 4)])
        pygame.draw.polygon(surf, (190, 220, 245), [(cx + sgn * 4, cy - 6), (cx + sgn * 6, cy - 10), (cx + sgn * 6, cy - 5)])
    if st.get("mode") == "tell":                            # about to dive: eyes flare
        _blit_glow(surf, cx, cy - 2, 12, (160, 240, 255), 170)
    pygame.draw.circle(surf, (180, 250, 255), (int(cx - 3), int(cy - 2)), 2)
    pygame.draw.circle(surf, (180, 250, 255), (int(cx + 3), int(cy - 2)), 2)
    pygame.draw.circle(surf, (20, 40, 70), (int(cx - 3), int(cy - 2)), 1)
    pygame.draw.circle(surf, (20, 40, 70), (int(cx + 3), int(cy - 2)), 1)
    pygame.draw.line(surf, (255, 255, 255), (cx - 2, cy + 2), (cx - 2, cy + 4), 1)
    pygame.draw.line(surf, (255, 255, 255), (cx + 2, cy + 2), (cx + 2, cy + 4), 1)


def paint_snowgolem(mon, surf, cx, cy):
    s = mon.size
    bob = math.sin(mon.anim_t * 0.9) * 1.2
    snow = mon.color
    shade = (196, 216, 238)
    line = (150, 176, 206)
    fl = -1 if mon.facing_left else 1
    balls = [(0, s * 0.42, s * 0.78), (0, -s * 0.42 + bob * 0.5, s * 0.58), (0, -s * 1.08 + bob, s * 0.44)]
    # twig arms (behind the middle ball)
    my = cy - s * 0.42 + bob * 0.5
    wave = math.sin(mon.anim_t * 1.3) * 3
    ch = _ai(mon).get("charge", 0.0)
    for sgn in (-1, 1):
        x0, y0 = cx + sgn * s * 0.5, my
        if ch > 0:                              # telegraph: both arms up, snowball overhead
            x1, y1 = cx + sgn * s * 0.45, my - s * 1.55
        else:
            x1, y1 = cx + sgn * s * 1.15, my - s * 0.35 + (wave if sgn > 0 else -wave)
        pygame.draw.line(surf, (122, 88, 58), (x0, y0), (x1, y1), 3)
        pygame.draw.line(surf, (122, 88, 58), (x1, y1), (x1 + sgn * 4, y1 - 4), 2)
        pygame.draw.line(surf, (122, 88, 58), (x1 - sgn * 3, y1 + 1), (x1 - sgn * 1, y1 - 5), 2)
    for ox, oy, r in balls:
        x, y, r = int(cx + ox), int(cy + oy), int(r)
        pygame.draw.circle(surf, snow, (x, y), r)
        pygame.draw.circle(surf, shade, (x + r // 4, y + r // 4), int(r * 0.78))
        pygame.draw.circle(surf, snow, (x - r // 6, y - r // 6), int(r * 0.8))
        pygame.draw.circle(surf, line, (x, y), r, 1)
    # buttons (coal)
    for k in range(2):
        pygame.draw.circle(surf, (58, 56, 70), (int(cx), int(cy + s * 0.2 + k * s * 0.35)), 2)
    # cosy scarf
    hy = cy - s * 1.08 + bob
    sc = (126, 172, 236)
    pygame.draw.rect(surf, sc, (cx - s * 0.5, hy + s * 0.3, s * 1.0, 5), border_radius=2)
    pygame.draw.rect(surf, _dk(sc, 40), (cx - fl * s * 0.2 - 2, hy + s * 0.34, 5, 10), border_radius=2)
    # face: coal eyes, carrot nose, rosy cheeks
    for sgn in (-1, 1):
        pygame.draw.circle(surf, (44, 42, 56), (int(cx + sgn * s * 0.17 + fl * 1), int(hy - 1)), 2)
        pygame.draw.circle(surf, (255, 170, 186), (int(cx + sgn * s * 0.28 + fl), int(hy + 4)), 2)
    pygame.draw.polygon(surf, (246, 140, 60), [(cx + fl * 1, hy + 1), (cx + fl * 1, hy + 4),
                                               (cx + fl * (s * 0.55), hy + 3)])
    # ice-crystal hat
    pygame.draw.polygon(surf, (170, 220, 250), [(cx - 5, hy - s * 0.36), (cx, hy - s * 0.36 - 9),
                                                (cx + 5, hy - s * 0.36)])
    pygame.draw.line(surf, (255, 255, 255), (cx - 1, hy - s * 0.36 - 6), (cx - 3, hy - s * 0.36 - 1), 1)
    if ch > 0:
        grow = 1.0 - ch / 0.7
        r = 3 + int(grow * 4)
        bx, by = cx, my - s * 1.7
        pygame.draw.circle(surf, (170, 200, 230), (int(bx), int(by + 1)), r)
        pygame.draw.circle(surf, (255, 255, 255), (int(bx), int(by)), r)
        pygame.draw.circle(surf, (214, 234, 250), (int(bx + r * 0.3), int(by + r * 0.3)), max(1, r // 2))
    draw_shots(mon, surf, cx, cy)


def paint_magma(mon, surf, cx, cy):
    frames = M.slime_frames(mon.color, mon.size)
    fr = frames[int(mon.anim_t) % len(frames)]
    w, h = fr.get_width(), fr.get_height()
    _blit_glow(surf, cx, cy + mon.size * 0.3, mon.size * 2.4, (255, 110, 40), 70)
    surf.blit(fr, (cx - w / 2, cy - h / 2))
    s = mon.size
    top = cy - h / 2 + h / 2 + s * 0.95 - s * 1.8         # approx dome top
    crust = (112, 62, 52)
    for ox, oy, rw, rh in ((-0.62, 0.3, 0.34, 0.16), (0.22, 0.06, 0.44, 0.17), (-0.2, 0.02, 0.26, 0.12)):
        pygame.draw.ellipse(surf, crust, (cx + ox * s, top + oy * s, rw * s, rh * s))
    t = mon.anim_t
    for k, (ox, oy) in enumerate(((-0.46, 0.4), (0.55, 0.3), (0.0, 0.12))):
        on = 0.5 + 0.5 * math.sin(t * 1.5 + k * 2)
        pygame.draw.circle(surf, _mix((255, 150, 60), (255, 236, 150), on),
                           (int(cx + ox * s), int(top + oy * s + 2)), 2)


def paint_imp(mon, surf, cx, cy):
    st = _ai(mon)
    col = mon.color
    dk = _dk(col, 60)
    lt = _lt(col, 50)
    fl = -1 if mon.facing_left else 1
    hov = math.sin(mon.anim_t * 1.2) * 3
    y = cy - 4 + hov
    flap = math.sin(mon.anim_t * 2.4) * 4
    for sgn in (-1, 1):                                        # leathery wings
        pts = [(cx + sgn * 4, y - 2), (cx + sgn * 16, y - 10 - flap), (cx + sgn * 13, y - 2),
               (cx + sgn * 15, y + 3 - flap * 0.4), (cx + sgn * 6, y + 4)]
        pygame.draw.polygon(surf, (132, 44, 58), pts)
        pygame.draw.polygon(surf, (92, 26, 40), pts, 1)
    # tail with an arrow tip
    tx = cx - fl * 9
    pygame.draw.line(surf, dk, (cx - fl * 3, y + 7), (tx, y + 11), 2)
    pygame.draw.line(surf, dk, (tx, y + 11), (tx - fl * 3, y + 5), 2)
    pygame.draw.polygon(surf, dk, [(tx - fl * 3, y + 2), (tx - fl * 6, y + 6), (tx - fl * 1, y + 6)])
    # body + belly
    pygame.draw.ellipse(surf, col, (cx - 8, y - 6, 16, 17))
    pygame.draw.ellipse(surf, (255, 190, 150), (cx - 5, y + 1, 10, 8))
    pygame.draw.ellipse(surf, dk, (cx - 8, y - 6, 16, 17), 1)
    # head
    hy = y - 9
    pygame.draw.circle(surf, col, (int(cx), int(hy)), 7)
    pygame.draw.circle(surf, lt, (int(cx - 2), int(hy - 3)), 2)
    for sgn in (-1, 1):                                        # horns
        pygame.draw.polygon(surf, (250, 226, 180), [(cx + sgn * 3, hy - 5), (cx + sgn * 8, hy - 12),
                                                    (cx + sgn * 6, hy - 4)])
        pygame.draw.circle(surf, (255, 230, 90), (int(cx + sgn * 3 + fl), int(hy)), 2)
        pygame.draw.circle(surf, (60, 20, 20), (int(cx + sgn * 3 + fl), int(hy)), 1)
    pygame.draw.arc(surf, (90, 20, 30), (cx - 3 + fl, hy + 1, 6, 4), 3.4, 6.0, 1)
    # fireball in hand (telegraph: grows while charging)
    ch = st.get("charge", 0.0)
    hx, hy2 = cx + fl * 10, y - 8
    pygame.draw.line(surf, col, (cx + fl * 5, y - 2), (hx, hy2 + 2), 3)
    if ch > 0:
        prog = 1.0 - ch / 0.65
        r = 3 + int(prog * 5)
        _blit_glow(surf, hx, hy2, r * 3.2, (255, 130, 40), 130)
        pygame.draw.circle(surf, (255, 140, 50), (int(hx), int(hy2)), r)
        pygame.draw.circle(surf, (255, 240, 170), (int(hx), int(hy2)), max(1, r - 3))
    else:
        pygame.draw.circle(surf, (255, 150, 60), (int(hx), int(hy2)), 2)
    draw_shots(mon, surf, cx, cy)


def paint_crystalgolem(mon, surf, cx, cy):
    s = mon.size
    col = mon.color
    lt, lt2, dk = _lt(col, 45), _lt(col, 90), _dk(col, 55)
    bob = math.sin(mon.anim_t * 0.8) * 1.2
    y = cy + bob
    # legs
    for sgn in (-1, 1):
        pygame.draw.polygon(surf, dk, [(cx + sgn * s * 0.2, y + s * 0.3), (cx + sgn * s * 0.55, y + s * 0.3),
                                       (cx + sgn * s * 0.5, y + s * 0.95), (cx + sgn * s * 0.2, y + s * 0.95)])
    # torso: a faceted gem
    top, mid, bot = y - s * 0.75, y - s * 0.05, y + s * 0.45
    L, R = cx - s * 0.72, cx + s * 0.72
    pygame.draw.polygon(surf, col, [(cx - s * 0.42, top), (cx + s * 0.42, top), (R, mid), (cx + s * 0.4, bot),
                                    (cx - s * 0.4, bot), (L, mid)])
    pygame.draw.polygon(surf, lt, [(cx - s * 0.42, top), (cx, top), (cx - s * 0.2, mid), (L, mid)])
    pygame.draw.polygon(surf, lt2, [(cx - s * 0.3, top + 2), (cx - s * 0.08, top + 2), (cx - s * 0.26, mid - s * 0.2)])
    pygame.draw.polygon(surf, dk, [(cx + s * 0.2, mid), (R, mid), (cx + s * 0.4, bot), (cx + s * 0.05, bot)])
    pygame.draw.polygon(surf, _dk(col, 85), [(cx - s * 0.42, top), (cx + s * 0.42, top), (R, mid), (cx + s * 0.4, bot),
                                             (cx - s * 0.4, bot), (L, mid)], 1)
    # shoulder crystals + arms
    swing = math.sin(mon.anim_t * 0.8) * 3
    for sgn in (-1, 1):
        sx = cx + sgn * s * 0.78
        pygame.draw.polygon(surf, lt, [(sx - 4, y - s * 0.55), (sx + sgn * 3, y - s * 1.15), (sx + 5, y - s * 0.5)])
        pygame.draw.polygon(surf, dk, [(sx + sgn * 3, y - s * 1.15), (sx + 5, y - s * 0.5), (sx + sgn * 1, y - s * 0.52)])
        ax = sx + sgn * s * 0.18
        pygame.draw.polygon(surf, col, [(ax - 4, y - s * 0.35), (ax + 4, y - s * 0.35),
                                        (ax + sgn * 2 + 5, y + s * 0.35 + swing * sgn), (ax + sgn * 2 - 5, y + s * 0.35 + swing * sgn)])
        pygame.draw.polygon(surf, lt2, [(ax + sgn * 2 - 2, y + s * 0.35 + swing * sgn), (ax + sgn * 2 + 2, y + s * 0.35 + swing * sgn),
                                        (ax + sgn * 2, y + s * 0.62 + swing * sgn)])
    # head gem + glowing eyes
    hy = top - s * 0.18
    pygame.draw.polygon(surf, lt, [(cx - s * 0.3, hy), (cx, hy - s * 0.32), (cx + s * 0.3, hy), (cx, hy + s * 0.22)])
    pygame.draw.polygon(surf, dk, [(cx, hy - s * 0.32), (cx + s * 0.3, hy), (cx, hy + s * 0.22)])
    for sgn in (-1, 1):
        _blit_glow(surf, cx + sgn * s * 0.2, y - s * 0.35, 6, (120, 255, 240), 80)
        pygame.draw.circle(surf, (210, 255, 250), (int(cx + sgn * s * 0.2), int(y - s * 0.35)), 2)
    # glint
    if int(mon.anim_t * 0.7) % 3 == 0:
        gx, gy = cx - s * 0.35, top + 4
        pygame.draw.line(surf, (255, 255, 255), (gx - 3, gy), (gx + 3, gy), 1)
        pygame.draw.line(surf, (255, 255, 255), (gx, gy - 3), (gx, gy + 3), 1)


def paint_prism(mon, surf, cx, cy):
    st = _ai(mon)
    s = mon.size
    t = mon.anim_t
    bob = math.sin(t * 0.9) * 3
    y = cy - 4 + bob
    bl = st.get("blink", 0.0)
    scale = 1.0
    if bl > 0:                                  # telegraph: shrink + flicker
        prog = 1.0 - bl / 0.5
        scale = 1.0 - 0.55 * prog
        if int(prog * 12) % 2:
            _blit_glow(surf, cx, y, s * 1.8, (200, 250, 245), 90)
            return
    hue = int((t * 0.05) % 1.0 * 24) / 24.0          # quantised: bounded glow cache
    rim = tuple(int(v * 255) for v in colorsys.hsv_to_rgb(hue, 0.45, 1.0))
    _blit_glow(surf, cx, y, s * 2.2 * scale, rim, 55)
    w, h = s * 0.85 * scale, s * 1.25 * scale
    col = mon.color
    top, bot = (cx, y - h), (cx, y + h)
    left, right = (cx - w, y), (cx + w, y)
    pygame.draw.polygon(surf, _lt(col, 40), [top, left, (cx, y)])
    pygame.draw.polygon(surf, col, [top, right, (cx, y)])
    pygame.draw.polygon(surf, _dk(col, 30), [bot, left, (cx, y)])
    pygame.draw.polygon(surf, _dk(col, 70), [bot, right, (cx, y)])
    pygame.draw.polygon(surf, rim, [top, right, bot, left], 1)
    pygame.draw.line(surf, (255, 255, 255), (cx - w * 0.5, y - h * 0.3), (cx - w * 0.15, y - h * 0.75), 1)
    # tiny eyes on the prism face
    pygame.draw.circle(surf, (40, 60, 80), (int(cx - 3 * scale), int(y - 1)), max(1, int(2 * scale)))
    pygame.draw.circle(surf, (40, 60, 80), (int(cx + 3 * scale), int(y - 1)), max(1, int(2 * scale)))
    # orbiting rainbow motes
    for k in range(3):
        a = t * 0.9 + k * math.tau / 3
        mc = tuple(int(v * 255) for v in colorsys.hsv_to_rgb((hue + k / 3) % 1.0, 0.55, 1.0))
        pygame.draw.circle(surf, mc, (int(cx + math.cos(a) * s * 1.3), int(y + math.sin(a) * s * 0.5)), 2)


def paint_stalker(mon, surf, cx, cy):
    st = _ai(mon)
    s = mon.size
    mode = st.get("mode")
    col = mon.color
    dk = _dk(col, 40)
    aim = st.get("aim")
    fl = (-1 if aim[0] < 0 else 1) if (aim and mode in ("windup", "charge")) else (-1 if mon.facing_left else 1)
    t = mon.anim_t
    crouch = 3 if mode == "windup" else 0
    if mode == "windup" and aim:
        prog = 1.0 - max(0.0, st.get("t", 0)) / 0.75
        _aim_line(surf, cx, cy, aim, TILE * 3.2, prog)
    if mode == "charge":                        # after-images
        for k in (2, 1):
            ox = -fl * k * 9
            pygame.draw.ellipse(surf, _mix(col, (30, 26, 40), 0.3 * k),
                                (cx + ox - s, cy - s * 0.35, s * 2, s * 0.9))
    # shadow wisps rising off the back
    for k in range(3):
        ph = (t * 0.6 + k * 0.33) % 1.0
        wx = cx - fl * (s * 0.5) + (k - 1) * 5
        wy = cy - s * 0.4 - ph * 12
        pygame.draw.circle(surf, _mix(dk, (20, 16, 30), ph), (int(wx), int(wy)), max(1, int(4 * (1 - ph))))
    by = cy + crouch
    # legs
    step = math.sin(t * 1.6) * 3 if mode not in ("windup", "rest") else 0
    for lx, ph in ((-0.55, 1), (-0.25, -1), (0.3, 1), (0.6, -1)):
        pygame.draw.line(surf, dk, (cx + lx * s, by + s * 0.2), (cx + lx * s + step * ph * 0.5, by + s * 0.75), 3)
    # tail
    pygame.draw.lines(surf, col, False, [(cx - fl * s * 0.9, by - 2), (cx - fl * s * 1.3, by - s * 0.5 + math.sin(t) * 2),
                                         (cx - fl * s * 1.45, by - s * 0.9)], 3)
    # body
    pygame.draw.ellipse(surf, col, (cx - s, by - s * 0.4, s * 2, s * 0.85))
    pygame.draw.ellipse(surf, _lt(col, 22), (cx - s * 0.7, by - s * 0.38, s * 1.3, s * 0.3))
    # head + ears
    hx, hy = cx + fl * s * 0.9, by - s * 0.35
    pygame.draw.circle(surf, col, (int(hx), int(hy)), int(s * 0.48))
    for off in (-0.25, 0.2):
        pygame.draw.polygon(surf, col, [(hx + fl * s * off - 3, hy - s * 0.3), (hx + fl * s * off, hy - s * 0.85),
                                        (hx + fl * s * off + 3, hy - s * 0.3)])
    eye = (255, 80, 110) if mode in ("windup", "charge") else (230, 120, 255)
    if mode == "windup":
        _blit_glow(surf, hx + fl * 4, hy - 1, 12, (255, 60, 90), 150)
    pygame.draw.line(surf, eye, (hx + fl * 1, hy - 2), (hx + fl * 5, hy - 1), 2)
    pygame.draw.line(surf, eye, (hx + fl * 6, hy - 2), (hx + fl * 9, hy - 1), 2)


def paint_guardian(mon, surf, cx, cy):
    s = mon.size
    col = mon.color
    lt, dk, dk2 = _lt(col, 30), _dk(col, 40), _dk(col, 80)
    moss = (122, 164, 98)
    fl = -1 if mon.facing_left else 1
    step = math.sin(mon.anim_t * 0.7)
    y = cy + abs(step) * 1.2
    # legs (heavy blocks)
    for sgn in (-1, 1):
        lift = step * sgn * 2
        pygame.draw.rect(surf, dk, (cx + sgn * s * 0.45 - 5, y + s * 0.35 - lift, 10, s * 0.6), border_radius=2)
    # torso
    body = pygame.Rect(0, 0, int(s * 1.5), int(s * 1.2))
    body.center = (int(cx), int(y - s * 0.05))
    pygame.draw.rect(surf, col, body, border_radius=6)
    pygame.draw.rect(surf, lt, (body.x + 3, body.y + 3, body.w // 2 - 3, body.h // 3), border_radius=3)
    pygame.draw.rect(surf, dk2, body, 1, border_radius=6)
    pygame.draw.line(surf, dk, (body.x + 4, body.centery + 3), (body.right - 5, body.centery + 1), 1)   # crack
    pygame.draw.circle(surf, moss, (body.x + 5, body.bottom - 5), 4)
    pygame.draw.circle(surf, _lt(moss, 30), (body.x + 8, body.bottom - 3), 3)
    # glowing rune
    pygame.draw.circle(surf, (120, 230, 220), body.center, 3)
    _blit_glow(surf, body.centerx, body.centery, 10, (80, 220, 200), 90)
    # pauldrons
    for sgn in (-1, 1):
        pygame.draw.circle(surf, lt, (int(cx + sgn * s * 0.78), int(y - s * 0.5)), int(s * 0.32))
        pygame.draw.circle(surf, dk2, (int(cx + sgn * s * 0.78), int(y - s * 0.5)), int(s * 0.32), 1)
    # helmet with visor glow
    hy = y - s * 0.95
    helm = pygame.Rect(0, 0, int(s * 0.9), int(s * 0.75))
    helm.center = (int(cx), int(hy))
    pygame.draw.rect(surf, col, helm, border_top_left_radius=8, border_top_right_radius=8, border_radius=3)
    pygame.draw.rect(surf, dk2, helm, 1, border_top_left_radius=8, border_top_right_radius=8, border_radius=3)
    pygame.draw.rect(surf, (30, 36, 44), (helm.x + 3, helm.centery - 2, helm.w - 6, 4))
    pygame.draw.line(surf, (140, 255, 240), (helm.x + 5 + (2 if fl > 0 else 0), helm.centery),
                     (helm.right - 5 + (0 if fl > 0 else -2), helm.centery), 2)
    # tower shield in front
    sx = cx + fl * s * 0.62
    sh = pygame.Rect(0, 0, int(s * 0.62), int(s * 1.25))
    sh.center = (int(sx), int(y + 1))
    pygame.draw.rect(surf, (150, 128, 96), sh, border_radius=4)
    pygame.draw.rect(surf, (96, 80, 60), sh, 2, border_radius=4)
    pygame.draw.line(surf, (214, 190, 120), (sh.centerx, sh.y + 4), (sh.centerx, sh.bottom - 4), 2)
    pygame.draw.line(surf, (214, 190, 120), (sh.x + 3, sh.y + sh.h // 3), (sh.right - 3, sh.y + sh.h // 3), 2)


def paint_knight(mon, surf, cx, cy):
    st = _ai(mon)
    s = mon.size
    col = mon.color
    lt, dk = _lt(col, 40), _dk(col, 40)
    mode = st.get("mode")
    aim = st.get("aim")
    fl = (-1 if aim[0] < 0 else 1) if (aim and mode in ("raise", "lunge")) else (-1 if mon.facing_left else 1)
    bob = math.sin(mon.anim_t * 1.1) * 1.0
    y = cy + bob
    # tattered cape
    cape = (82, 44, 104)
    pygame.draw.polygon(surf, cape, [(cx - 6, y - s * 0.55), (cx + 6, y - s * 0.55),
                                     (cx - fl * 10 + 4, y + s * 0.75), (cx - fl * 7, y + s * 0.6),
                                     (cx - fl * 12, y + s * 0.8)])
    # legs
    for sgn in (-1, 1):
        pygame.draw.rect(surf, dk, (cx + sgn * 4 - 3, y + s * 0.3, 6, s * 0.6), border_radius=2)
    # torso armour
    pygame.draw.rect(surf, col, (cx - s * 0.5, y - s * 0.5, s, s * 0.9), border_radius=4)
    pygame.draw.rect(surf, lt, (cx - s * 0.4, y - s * 0.45, s * 0.35, s * 0.3), border_radius=2)
    pygame.draw.rect(surf, _dk(col, 70), (cx - s * 0.5, y - s * 0.5, s, s * 0.9), 1, border_radius=4)
    pygame.draw.rect(surf, (150, 120, 70), (cx - s * 0.5, y + s * 0.2, s, 3))           # belt
    # helmet + plume
    hy = y - s * 0.85
    pygame.draw.circle(surf, col, (int(cx), int(hy)), int(s * 0.42))
    pygame.draw.circle(surf, _dk(col, 70), (int(cx), int(hy)), int(s * 0.42), 1)
    pygame.draw.rect(surf, (24, 26, 34), (cx - s * 0.3, hy - 1, s * 0.6, 4))
    pygame.draw.circle(surf, (140, 255, 150), (int(cx + fl * 2 - 2), int(hy + 1)), 1)
    pygame.draw.circle(surf, (140, 255, 150), (int(cx + fl * 2 + 2), int(hy + 1)), 1)
    plume = (176, 92, 210)
    for k in range(4):
        pygame.draw.circle(surf, _mix(plume, (230, 170, 255), k / 4),
                           (int(cx - fl * k * 3), int(hy - s * 0.42 - (3 - abs(k - 1.5)) * 1.5)), 3)
    # sword arm: raised during the telegraph, thrust during the lunge
    shx, shy = cx + fl * s * 0.5, y - s * 0.3
    if mode == "raise":
        tip = (shx + fl * 4, shy - s * 1.35)
        _blit_glow(surf, tip[0], tip[1], 12, (200, 120, 255), 150)
    elif mode == "lunge":
        tip = (shx + fl * s * 1.5, shy + 2)
    else:
        tip = (shx + fl * s * 0.7, shy - s * 0.9)
    pygame.draw.line(surf, (70, 64, 80), (shx, shy), (shx + (tip[0] - shx) * 0.2, shy + (tip[1] - shy) * 0.2), 3)
    pygame.draw.line(surf, (214, 220, 236), (shx + (tip[0] - shx) * 0.2, shy + (tip[1] - shy) * 0.2), tip, 3)
    pygame.draw.line(surf, (255, 255, 255), (shx + (tip[0] - shx) * 0.3, shy + (tip[1] - shy) * 0.3), tip, 1)
    pygame.draw.circle(surf, (190, 150, 80), (int(shx), int(shy)), 3)


def paint_wraith(mon, surf, cx, cy):
    """Abyss Wraith: a hooded spectral cloak with a tattered hem and lantern eyes."""
    s = mon.size
    col = mon.color
    t = mon.anim_t
    bob = math.sin(t * 0.8) * 3
    y = cy - 4 + bob
    fl = -1 if mon.facing_left else 1
    _blit_glow(surf, cx, y, s * 2.2, col, 70)
    cloak, dk, lt = _dk(col, 70), _dk(col, 105), _lt(col, 30)
    # tattered hem (zig-zag that ripples)
    hem = []
    n = 6
    for i in range(n + 1):
        x = cx - s * 0.8 + i * (s * 1.6 / n)
        yy = y + s * 0.9 + (5 if i % 2 else 0) + math.sin(t * 1.5 + i) * 2
        hem.append((x, yy))
    body = [(cx, y - s * 1.05), (cx + s * 0.62, y - s * 0.55), (cx + s * 0.85, y + s * 0.5)] +         hem[::-1] + [(cx - s * 0.85, y + s * 0.5), (cx - s * 0.62, y - s * 0.55)]
    pygame.draw.polygon(surf, cloak, body)
    pygame.draw.polygon(surf, lt, [(cx - s * 0.1, y - s * 1.0), (cx - s * 0.55, y - s * 0.5),
                                   (cx - s * 0.7, y + s * 0.4), (cx - s * 0.45, y + s * 0.3)])
    pygame.draw.polygon(surf, dk, body, 1)
    # wispy arms reaching forward
    for k, off in enumerate((-0.1, 0.25)):
        ax = cx + fl * s * 0.55
        ay = y + s * off
        pygame.draw.line(surf, cloak, (ax, ay), (ax + fl * s * 0.55, ay + 3 + math.sin(t * 2 + k) * 3), 3)
    # hood opening + lantern eyes
    pygame.draw.ellipse(surf, (20, 22, 36), (cx - s * 0.42 + fl * 2, y - s * 0.75, s * 0.84, s * 0.62))
    eye = (190, 255, 250)
    for sgn in (-1, 1):
        ex, ey = cx + fl * 2 + sgn * s * 0.17, y - s * 0.46
        _blit_glow(surf, ex, ey, 7, (120, 240, 230), 150)
        pygame.draw.circle(surf, eye, (int(ex), int(ey)), 2)
    # drifting motes
    for k in range(3):
        ph = (t * 0.25 + k / 3) % 1.0
        pygame.draw.circle(surf, lt, (int(cx + math.sin(k * 2.1 + t) * s * 0.7), int(y + s - ph * s * 2.2)),
                           max(1, int(2 * (1 - ph))))


# ---------------------------------------------------------------- bosses
def paint_wyrm(mon, surf, cx, cy):
    from . import monster_ai as AI
    st = _ai(mon)
    s = mon.size
    col = mon.color
    lt, dk = _lt(col, 45), _dk(col, 45)
    belly = (206, 180, 236)
    ox, oy = mon.x - cx, mon.y - cy
    trail = st.get("trail") or []
    pts = []
    for i in range(1, AI.WYRM_SEGMENTS + 1):
        j = i * AI.WYRM_GAP
        if j < len(trail):
            pts.append((trail[j][0] - ox, trail[j][1] - oy))
        else:                                            # gallery / fresh spawn: a lazy S-curve
            pts.append((cx - i * s * 0.62, cy + math.sin(i * 0.9 + mon.anim_t * 0.3) * s * 0.35))
    n = len(pts)
    for i in range(n - 1, -1, -1):                       # tail first, head last
        x, y = pts[i]
        r = int(s * (0.78 - 0.45 * i / n))
        pygame.draw.circle(surf, dk, (int(x), int(y + 2)), r)
        pygame.draw.circle(surf, col if i % 2 else _mix(col, lt, 0.4), (int(x), int(y)), r)
        pygame.draw.circle(surf, belly, (int(x), int(y + r * 0.45)), max(2, int(r * 0.45)))
        pygame.draw.polygon(surf, (236, 214, 255), [(x - 3, y - r + 2), (x, y - r - 5), (x + 3, y - r + 2)])
        pygame.draw.circle(surf, _dk(col, 80), (int(x), int(y)), r, 1)
    # tail fin
    if pts:
        tx, ty = pts[-1]
        pygame.draw.polygon(surf, lt, [(tx - 2, ty), (tx - s * 0.7, ty - s * 0.5), (tx - s * 0.5, ty + s * 0.4)])
    mode = st.get("mode")
    aim = st.get("aim") or (1.0, 0.0)
    if mode == "coil":
        prog = 1.0 - max(0.0, st.get("t", 0)) / 0.8
        _aim_line(surf, cx, cy, aim, TILE * 4.5, prog, (190, 110, 255))
    # head
    if mode in ("coil", "charge"):
        fl = -1 if aim[0] < 0 else 1
    else:
        fl = st.get("face") or (-1 if mon.facing_left else 1)
    hr = int(s * 0.95)
    pygame.draw.circle(surf, dk, (int(cx), int(cy + 3)), hr)
    pygame.draw.circle(surf, col, (int(cx), int(cy)), hr)
    pygame.draw.circle(surf, lt, (int(cx - hr * 0.3), int(cy - hr * 0.35)), int(hr * 0.35))
    for sgn in (-1, 1):                                  # swept-back horns
        pygame.draw.polygon(surf, (236, 222, 250), [(cx - fl * hr * 0.1 + sgn * 5, cy - hr * 0.7),
                                                    (cx - fl * hr * 1.1 + sgn * 4, cy - hr * 1.45),
                                                    (cx - fl * hr * 0.35 + sgn * 6, cy - hr * 0.55)])
    gape = mode == "gape"
    mx = cx + fl * hr * 0.55
    if gape:
        prog = 1.0 - max(0.0, st.get("t", 0)) / 0.7
        _blit_glow(surf, mx + fl * 6, cy + 4, 16 + prog * 14, (200, 120, 255), 160)
        pygame.draw.ellipse(surf, (40, 10, 50), (mx - 8, cy, 16, 8 + prog * 6))
        pygame.draw.circle(surf, (236, 200, 255), (int(mx + fl * 2), int(cy + 4 + prog * 2)), 2 + int(prog * 3))
    else:
        pygame.draw.arc(surf, _dk(col, 90), (mx - 8, cy - 1, 16, 9), 3.5, 5.9, 2)
    ex = cx + fl * hr * 0.25
    ey = cy - hr * 0.25
    mad = st.get("phase2")
    ecol = (255, 90, 120) if mad else (255, 220, 110)
    _blit_glow(surf, ex, ey, 12, ecol, 140)
    pygame.draw.ellipse(surf, ecol, (ex - 4, ey - 3, 8, 6))
    pygame.draw.line(surf, (30, 10, 20), (ex, ey - 2), (ex, ey + 2), 2)
    draw_shots(mon, surf, cx, cy)


def paint_colossus(mon, surf, cx, cy):
    from . import monster_ai as AI
    st = _ai(mon)
    s = mon.size
    col = mon.color
    lt, dk, dk2 = _lt(col, 28), _dk(col, 38), _dk(col, 80)
    moss = (118, 160, 96)
    mad = st.get("phase2")
    rune = (255, 120, 90) if mad else (110, 236, 220)
    mode = st.get("mode")
    # ground telegraph: a ring + filling disc you can walk out of
    if mode == "windup":
        R = AI.colossus_radius(mon)
        prog = st.get("prog", 0.0)
        gy = cy + s * 0.55
        warn = (255, 90, 80)
        rs = ring_surface(R, warn, 210, 3)
        surf.blit(rs, (cx - rs.get_width() / 2, gy - rs.get_height() / 2))
        ds = disc_surface(max(6, R * prog), warn, 60 + int(60 * prog))
        surf.blit(ds, (cx - ds.get_width() / 2, gy - ds.get_height() / 2))
    wave = st.get("wave")
    if wave is not None:
        R = AI.colossus_radius(mon) * (1.0 + wave * 1.6)
        rs = ring_surface(R, (255, 236, 200), max(20, int(220 * (1 - wave / 0.8))), 4)
        surf.blit(rs, (cx - rs.get_width() / 2, cy + s * 0.55 - rs.get_height() / 2))
    raise_k = 0.0
    if mode == "windup":
        raise_k = min(1.0, st.get("prog", 0.0) * 1.6)
    elif mode == "recover":
        raise_k = -0.25
    step = math.sin(mon.anim_t * 0.55) if mode == "walk" else 0.0
    y = cy + abs(step) * 1.5
    # legs
    for sgn in (-1, 1):
        lift = step * sgn * 3
        pygame.draw.rect(surf, dk, (cx + sgn * s * 0.42 - s * 0.2, y + s * 0.3 - lift, s * 0.4, s * 0.6), border_radius=3)
        pygame.draw.rect(surf, dk2, (cx + sgn * s * 0.42 - s * 0.2, y + s * 0.3 - lift, s * 0.4, s * 0.6), 1, border_radius=3)
    # torso block
    body = pygame.Rect(0, 0, int(s * 1.55), int(s * 1.15))
    body.center = (int(cx), int(y - s * 0.12))
    pygame.draw.rect(surf, col, body, border_radius=7)
    pygame.draw.rect(surf, lt, (body.x + 4, body.y + 4, body.w // 2, body.h // 4), border_radius=4)
    pygame.draw.rect(surf, dk2, body, 2, border_radius=7)
    # glowing runes + cracks
    pulse = 0.5 + 0.5 * math.sin(mon.anim_t * (1.2 if not mad else 2.4))
    _blit_glow(surf, body.centerx, body.centery, 26 + pulse * 8, rune, 70 + int(40 * pulse))
    pygame.draw.circle(surf, rune, body.center, 6, 2)
    for a in range(4):
        ang = a * math.pi / 2 + 0.4
        pygame.draw.line(surf, rune, (body.centerx + math.cos(ang) * 9, body.centery + math.sin(ang) * 9),
                         (body.centerx + math.cos(ang) * 15, body.centery + math.sin(ang) * 15), 2)
    pygame.draw.line(surf, dk2, (body.x + 6, body.y + body.h * 0.7), (body.x + 16, body.y + body.h * 0.55), 1)
    pygame.draw.circle(surf, moss, (body.right - 7, body.y + 6), 5)
    pygame.draw.circle(surf, _lt(moss, 30), (body.right - 11, body.y + 4), 3)
    # head
    head = pygame.Rect(0, 0, int(s * 0.8), int(s * 0.62))
    head.midbottom = (int(cx), body.y + 3)
    pygame.draw.rect(surf, col, head, border_radius=5)
    pygame.draw.rect(surf, dk2, head, 2, border_radius=5)
    pygame.draw.rect(surf, lt, (head.x + 3, head.y + 3, head.w - 10, 4), border_radius=2)
    _blit_glow(surf, head.centerx, head.centery + 2, 12, rune, 170)
    pygame.draw.ellipse(surf, rune, (head.centerx - 6, head.centery - 1, 12, 6))
    pygame.draw.ellipse(surf, (255, 255, 255), (head.centerx - 2, head.centery, 4, 3))
    # arms + fists (raised over the head in the wind-up)
    for sgn in (-1, 1):
        shx, shy = cx + sgn * s * 0.85, body.y + 8
        if raise_k > 0:
            fx = cx + sgn * s * (0.85 - 0.45 * raise_k)
            fy = shy - s * 0.95 * raise_k
        else:
            fx = cx + sgn * s * 1.0
            fy = shy + s * 0.75 - raise_k * s * 0.3
        pygame.draw.line(surf, dk, (shx, shy), (fx, fy), int(s * 0.3))
        pygame.draw.circle(surf, lt, (int(shx), int(shy)), int(s * 0.28))
        pygame.draw.circle(surf, dk2, (int(shx), int(shy)), int(s * 0.28), 1)
        pygame.draw.circle(surf, col, (int(fx), int(fy)), int(s * 0.34))
        pygame.draw.circle(surf, lt, (int(fx - 3), int(fy - 3)), int(s * 0.12))
        pygame.draw.circle(surf, dk2, (int(fx), int(fy)), int(s * 0.34), 2)


M.SHAPE_PAINTERS.update({
    "icebat": paint_icebat, "snowgolem": paint_snowgolem, "magma": paint_magma,
    "imp": paint_imp, "crystalgolem": paint_crystalgolem, "prism": paint_prism,
    "stalker": paint_stalker, "guardian": paint_guardian, "knight": paint_knight,
    "wraith": paint_wraith,
    "wyrm": paint_wyrm, "colossus": paint_colossus,
})
