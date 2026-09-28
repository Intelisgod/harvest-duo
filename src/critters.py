"""Cute, detailed animal sprites (outlined + soft-shaded + big shiny eyes),
shared by farm livestock (animals.py) and forest creatures (entities.py).

Side-view, drawn around a centre (cx, cy); `fl` is +1 facing right / -1 left;
`col` is the base body colour. The bear stands on two legs.
"""
import math
import pygame


def _lt(c, f=1.16):
    return tuple(min(255, int(v * f)) for v in c)


def _dk(c, f=0.72):
    return tuple(max(0, int(v * f)) for v in c)


def _oell(s, rect, col, w=2, ol=None):
    pygame.draw.ellipse(s, col, rect)
    pygame.draw.ellipse(s, ol or _dk(col, 0.52), rect, w)


def _ocirc(s, c, r, col, w=2, ol=None):
    pygame.draw.circle(s, col, (int(c[0]), int(c[1])), int(r))
    pygame.draw.circle(s, ol or _dk(col, 0.52), (int(c[0]), int(c[1])), int(r), w)


def _opoly(s, pts, col, w=2, ol=None):
    pygame.draw.polygon(s, col, pts)
    pygame.draw.polygon(s, ol or _dk(col, 0.52), pts, w)


def _eye(s, cx, cy, r=3, look=1):
    pygame.draw.circle(s, (255, 255, 255), (int(cx), int(cy)), r + 1)
    pygame.draw.circle(s, (32, 26, 28), (int(cx), int(cy)), r)
    pygame.draw.circle(s, (255, 255, 255), (int(cx - look), int(cy - r * 0.45)), max(1, int(r * 0.5)))
    pygame.draw.circle(s, (255, 255, 255), (int(cx + look * 0.7), int(cy + r * 0.4)), 1)


def _d_chicken(s, cx, cy, sz, fl, col=(248, 248, 246)):
    ol = (118, 120, 128); dk = _dk(col, 0.9); lt = _lt(col, 1.04); foot = (236, 152, 44)
    for lx in (-0.22, 0.24):
        fx = cx + lx * sz
        pygame.draw.line(s, foot, (fx, cy + sz * 0.72), (fx, cy + sz * 1.0), 3)
        for tt in (-0.2, 0, 0.2):
            pygame.draw.line(s, foot, (fx, cy + sz * 1.0), (fx + tt * sz + fl * 0.06 * sz, cy + sz * 1.14), 2)
    for i, a in enumerate((0.0, 0.2, 0.4)):
        _opoly(s, [(cx - fl * sz * 0.6, cy - sz * 0.1), (cx - fl * (sz * 1.32), cy - sz * (0.26 + a)),
                   (cx - fl * sz * 0.55, cy - sz * 0.45)], dk if i % 2 else col, 1, ol)
    _oell(s, (cx - sz, cy - sz * 0.85, sz * 2.0, sz * 1.7), col, 2, ol)
    pygame.draw.ellipse(s, lt, (cx - sz * 0.7, cy - sz * 0.78, sz * 1.1, sz * 0.72))
    _oell(s, (cx - sz * 0.12, cy - sz * 0.28, sz * 0.98, sz * 0.9), col, 2, ol)
    for k in range(3):
        pygame.draw.arc(s, ol, (cx - sz * 0.02 + k * sz * 0.18, cy - sz * 0.18, sz * 0.5, sz * 0.72), 1.1, 2.7, 1)
    hx, hy = cx + fl * sz * 0.55, cy - sz * 0.62
    for i in range(3):
        _ocirc(s, (hx - fl * sz * 0.2 + i * fl * sz * 0.18, hy - sz * 0.58), sz * 0.17, (226, 74, 74), 1)
    _ocirc(s, (hx, hy), sz * 0.64, col, 2, ol)
    _ocirc(s, (hx + fl * sz * 0.22, hy + sz * 0.5), sz * 0.14, (226, 74, 74), 1)
    _opoly(s, [(hx + fl * sz * 0.46, hy - sz * 0.06), (hx + fl * sz * 0.98, hy + sz * 0.06),
               (hx + fl * sz * 0.46, hy + sz * 0.22)], (242, 170, 50), 1)
    pygame.draw.line(s, (196, 128, 30), (hx + fl * sz * 0.46, hy + sz * 0.08), (hx + fl * sz * 0.92, hy + sz * 0.06), 1)
    _eye(s, hx + fl * sz * 0.1, hy - sz * 0.04, 3, look=fl)
    _eye(s, hx + fl * sz * 0.42, hy - sz * 0.04, 3, look=fl)


def _d_cow(s, cx, cy, sz, fl, col=(244, 242, 238)):
    ol = (120, 116, 116); spot = (58, 52, 54); pink = (244, 178, 188); hoof = (54, 48, 50)
    for lx in (-0.55, -0.24, 0.24, 0.55):
        x = cx + lx * sz
        _oell(s, (x - sz * 0.13, cy + sz * 0.35, sz * 0.26, sz * 0.62), col, 2, ol)
        pygame.draw.ellipse(s, hoof, (x - sz * 0.13, cy + sz * 0.86, sz * 0.26, sz * 0.16))
    pygame.draw.line(s, ol, (cx - fl * sz * 0.95, cy - sz * 0.1), (cx - fl * sz * 1.25, cy + sz * 0.55), 2)
    _ocirc(s, (cx - fl * sz * 1.25, cy + sz * 0.6), sz * 0.16, spot, 1)
    _oell(s, (cx - sz * 1.02, cy - sz * 0.62, sz * 2.0, sz * 1.3), col, 2, ol)
    pygame.draw.ellipse(s, _lt(col, 1.04), (cx - sz * 0.8, cy - sz * 0.55, sz * 1.3, sz * 0.5))
    for ox, oy, rr in ((-sz * 0.45, sz * 0.12, sz * 0.34), (sz * 0.3, -sz * 0.1, sz * 0.28), (sz * 0.0, sz * 0.4, sz * 0.22)):
        pygame.draw.ellipse(s, spot, (cx + ox - rr, cy + oy - rr * 0.75, rr * 2, rr * 1.5))
    hx, hy = cx + fl * sz * 0.78, cy - sz * 0.3
    for ex in (-0.5, 0.28):
        _opoly(s, [(hx + fl * sz * ex, hy - sz * 0.2), (hx + fl * sz * (ex - 0.18), hy - sz * 0.6),
                   (hx + fl * sz * (ex + 0.18), hy - sz * 0.32)], col, 1, ol)
    for ex in (-0.22, 0.2):
        _opoly(s, [(hx + fl * sz * ex, hy - sz * 0.42), (hx + fl * sz * (ex + fl * 0.04), hy - sz * 0.74),
                   (hx + fl * sz * (ex + 0.14), hy - sz * 0.42)], (238, 226, 198), 1)
    _ocirc(s, (hx, hy), sz * 0.62, col, 2, ol)
    # black patch on the head (sits around the back eye, like a real cow)
    pygame.draw.ellipse(s, spot, (hx - fl * sz * 0.06 - sz * 0.33, hy - sz * 0.46, sz * 0.66, sz * 0.52))
    pygame.draw.ellipse(s, spot, (hx - fl * sz * 0.44, hy - sz * 0.5, sz * 0.26, sz * 0.24))  # smaller dab near ear
    _oell(s, (hx + fl * sz * 0.05, hy + sz * 0.12, sz * 0.66, sz * 0.5), pink, 1)
    for nx in (0.2, 0.45):
        pygame.draw.circle(s, (150, 96, 104), (int(hx + fl * sz * nx), int(hy + sz * 0.32)), 2)
    _eye(s, hx + fl * sz * 0.08, hy - sz * 0.06, 3, look=fl)
    _eye(s, hx + fl * sz * 0.42, hy - sz * 0.08, 3, look=fl)


def _d_sheep(s, cx, cy, sz, fl, col=(246, 246, 250)):
    ol = (160, 160, 168); wool = col; face = (74, 68, 76); leg = (78, 72, 78)
    for lx in (-0.4, -0.14, 0.16, 0.42):
        x = cx + lx * sz
        pygame.draw.line(s, leg, (x, cy + sz * 0.42), (x, cy + sz * 0.95), 3)
        pygame.draw.line(s, (44, 40, 44), (x, cy + sz * 0.88), (x, cy + sz * 1.0), 4)
    # fluffy wool body = a cluster of soft bumps
    for bx, by, rr in ((-0.55, 0.02, 0.5), (-0.22, -0.2, 0.55), (0.2, -0.18, 0.55),
                       (0.52, 0.04, 0.46), (-0.32, 0.26, 0.42), (0.08, 0.3, 0.46),
                       (0.38, 0.26, 0.4), (0.0, 0.02, 0.6)):
        _ocirc(s, (cx + bx * sz, cy + by * sz), rr * sz, wool, 2, ol)
    hx, hy = cx + fl * sz * 0.78, cy - sz * 0.08
    for ex in (-0.32, 0.24):
        _oell(s, (hx + fl * sz * ex - sz * 0.1, hy + sz * 0.02, sz * 0.22, sz * 0.34),
              _dk(face, 0.86), 1, _dk(face, 0.6))
    _ocirc(s, (hx, hy), sz * 0.4, face, 2, _dk(face, 0.6))
    _ocirc(s, (hx - fl * sz * 0.16, hy - sz * 0.34), sz * 0.24, wool, 1, ol)   # forelock
    _eye(s, hx + fl * sz * 0.08, hy - sz * 0.02, 3, look=fl)
    _eye(s, hx + fl * sz * 0.3, hy - sz * 0.02, 3, look=fl)


def _d_duck(s, cx, cy, sz, fl, col=(250, 246, 224)):
    ol = (158, 150, 116); body = col; bill = (244, 178, 54)
    foot = (236, 152, 44); wing = _dk(col, 0.9)
    for lx in (-0.12, 0.18):
        fx = cx + lx * sz
        pygame.draw.line(s, foot, (fx, cy + sz * 0.55), (fx, cy + sz * 0.86), 3)
        _opoly(s, [(fx - sz * 0.2, cy + sz * 0.92), (fx + sz * 0.24, cy + sz * 0.92),
                   (fx, cy + sz * 0.78)], foot, 1)
    _opoly(s, [(cx - fl * sz * 0.7, cy - sz * 0.08), (cx - fl * sz * 1.18, cy - sz * 0.38),
               (cx - fl * sz * 0.6, cy - sz * 0.42)], body, 1, ol)               # tail
    _oell(s, (cx - sz * 0.88, cy - sz * 0.52, sz * 1.74, sz * 1.28), body, 2, ol)
    _oell(s, (cx - sz * 0.34, cy - sz * 0.26, sz * 0.88, sz * 0.62), wing, 1, ol)
    hx, hy = cx + fl * sz * 0.72, cy - sz * 0.72
    pygame.draw.line(s, body, (cx + fl * sz * 0.46, cy - sz * 0.2), (hx, hy), max(3, int(sz * 0.5)))
    _ocirc(s, (hx, hy), sz * 0.46, body, 2, ol)
    _opoly(s, [(hx + fl * sz * 0.2, hy - sz * 0.06), (hx + fl * sz * 0.88, hy + sz * 0.02),
               (hx + fl * sz * 0.2, hy + sz * 0.24)], bill, 1, _dk(bill, 0.7))
    _eye(s, hx + fl * sz * 0.12, hy - sz * 0.06, 2, look=fl)


def _d_goat(s, cx, cy, sz, fl, col=(224, 208, 180)):
    ol = _dk(col, 0.5); belly = _lt(col, 1.12); leg = _dk(col, 0.7); hoof = (54, 48, 50)
    horn = (214, 204, 184); beard = (240, 236, 226)
    for lx in (-0.5, -0.22, 0.24, 0.5):
        x = cx + lx * sz
        pygame.draw.line(s, leg, (x, cy + sz * 0.3), (x, cy + sz * 1.0), 4)
        pygame.draw.line(s, hoof, (x, cy + sz * 0.9), (x, cy + sz * 1.04), 5)
    _opoly(s, [(cx - fl * sz * 0.9, cy - sz * 0.3), (cx - fl * sz * 1.12, cy - sz * 0.56),
               (cx - fl * sz * 0.68, cy - sz * 0.46)], col, 1, ol)               # tail
    _oell(s, (cx - sz * 0.94, cy - sz * 0.5, sz * 1.82, sz * 1.0), col, 2, ol)
    pygame.draw.ellipse(s, belly, (cx - sz * 0.55, cy - sz * 0.08, sz * 1.0, sz * 0.4))
    hx, hy = cx + fl * sz * 0.84, cy - sz * 0.3
    _opoly(s, [(hx - fl * sz * 0.3, hy - sz * 0.08), (hx - fl * sz * 0.64, hy + sz * 0.06),
               (hx - fl * sz * 0.26, hy + sz * 0.18)], col, 1, ol)               # ear
    for ho in (0.0, 0.16):
        pygame.draw.line(s, horn, (hx + fl * sz * ho, hy - sz * 0.4),
                         (hx - fl * sz * (0.22 - ho), hy - sz * 0.84), 3)         # horns
    _ocirc(s, (hx, hy), sz * 0.5, col, 2, ol)
    _oell(s, (hx + fl * sz * 0.04, hy + sz * 0.06, sz * 0.62, sz * 0.46), belly, 1, ol)
    pygame.draw.circle(s, (90, 72, 70), (int(hx + fl * sz * 0.5), int(hy + sz * 0.22)), 2)
    _opoly(s, [(hx + fl * sz * 0.08, hy + sz * 0.42), (hx + fl * sz * 0.32, hy + sz * 0.42),
               (hx + fl * sz * 0.2, hy + sz * 0.8)], beard, 1, _dk(beard, 0.7))   # goatee
    _eye(s, hx + fl * sz * 0.12, hy - sz * 0.04, 3, look=fl)
    _eye(s, hx + fl * sz * 0.4, hy - sz * 0.04, 3, look=fl)


def _d_bear(s, cx, cy, sz, fl, col):       # BIPEDAL -- stands on two legs
    ol = _dk(col, 0.5); dk = _dk(col, 0.82); belly = _lt(col, 1.32); muz = _lt(col, 1.4)
    for lx in (-0.34, 0.34):
        _oell(s, (cx + lx * sz - sz * 0.24, cy + sz * 0.5, sz * 0.48, sz * 0.62), dk, 2, ol)
        pygame.draw.ellipse(s, _dk(col, 0.6), (cx + lx * sz - sz * 0.22, cy + sz * 0.92, sz * 0.44, sz * 0.22))
    for lx in (-0.64, 0.64):
        _oell(s, (cx + lx * sz - sz * 0.19, cy - sz * 0.22, sz * 0.38, sz * 0.78), col, 2, ol)
    _oell(s, (cx - sz * 0.62, cy - sz * 0.4, sz * 1.24, sz * 1.2), col, 2, ol)
    pygame.draw.ellipse(s, belly, (cx - sz * 0.4, cy - sz * 0.12, sz * 0.8, sz * 0.86))
    hy = cy - sz * 0.78
    for lx in (-0.52, 0.52):
        _ocirc(s, (cx + lx * sz, hy - sz * 0.5), sz * 0.28, col, 2, ol)
        pygame.draw.circle(s, muz, (int(cx + lx * sz), int(hy - sz * 0.5)), int(sz * 0.13))
    _ocirc(s, (cx, hy), sz * 0.72, col, 2, ol)
    _oell(s, (cx - sz * 0.34, hy + sz * 0.04, sz * 0.68, sz * 0.54), muz, 1)
    pygame.draw.ellipse(s, (44, 32, 30), (cx - sz * 0.13, hy + sz * 0.06, sz * 0.26, sz * 0.2))
    _eye(s, cx - sz * 0.26, hy - sz * 0.08, 3, look=fl)
    _eye(s, cx + sz * 0.26, hy - sz * 0.08, 3, look=fl)


def _d_tiger(s, cx, cy, sz, fl, col):
    ol = _dk(col, 0.45); stripe = (52, 36, 30); belly = (250, 244, 232)
    for lx in (-0.58, -0.26, 0.26, 0.55):
        _oell(s, (cx + lx * sz - sz * 0.13, cy + sz * 0.32, sz * 0.26, sz * 0.6), col, 2, ol)
    pygame.draw.line(s, col, (cx - fl * sz * 0.95, cy - sz * 0.05), (cx - fl * sz * 1.4, cy - sz * 0.5), max(3, int(sz * 0.24)))
    for tt in (0.2, 0.45, 0.7):
        p = (cx - fl * sz * (0.95 + tt * 0.45), cy - sz * (0.05 + tt * 0.45))
        pygame.draw.circle(s, stripe, (int(p[0]), int(p[1])), 2)
    _oell(s, (cx - sz * 1.0, cy - sz * 0.6, sz * 2.0, sz * 1.28), col, 2, ol)
    pygame.draw.ellipse(s, belly, (cx - sz * 0.55, cy + sz * 0.06, sz * 1.0, sz * 0.46))
    rx, ry = sz * 0.98, sz * 0.55
    for dxr in (-0.62, -0.4, -0.16, 0.08, 0.32, 0.52):
        xx = cx + dxr * sz; frac = 1 - (dxr * sz / rx) ** 2
        if frac <= 0:
            continue
        hh = ry * (frac ** 0.5) * 0.92
        pygame.draw.line(s, stripe, (xx, cy - sz * 0.5 + (ry - hh)), (xx, cy - sz * 0.5 + (ry - hh) + hh), 2)
    hx, hy = cx + fl * sz * 0.74, cy - sz * 0.22
    for ex in (-0.3, 0.32):
        _ocirc(s, (hx + fl * sz * ex, hy - sz * 0.44), sz * 0.22, col, 2, ol)
        pygame.draw.circle(s, stripe, (int(hx + fl * sz * ex), int(hy - sz * 0.44)), int(sz * 0.1))
    _ocirc(s, (hx, hy), sz * 0.6, col, 2, ol)
    pygame.draw.ellipse(s, belly, (hx - sz * 0.34, hy + sz * 0.06, sz * 0.78, sz * 0.5))
    for o in (-0.2, 0.2):
        pygame.draw.line(s, stripe, (hx + fl * sz * o, hy - sz * 0.4), (hx + fl * sz * o, hy - sz * 0.16), 2)
    pygame.draw.ellipse(s, (224, 120, 130), (hx - sz * 0.08, hy + sz * 0.14, sz * 0.18, sz * 0.13))
    _eye(s, hx - sz * 0.16, hy - sz * 0.06, 3, look=fl)
    _eye(s, hx + sz * 0.18, hy - sz * 0.06, 3, look=fl)


def _d_wolf(s, cx, cy, sz, fl, col):
    ol = _dk(col, 0.5); belly = _lt(col, 1.22); muz = _lt(col, 1.28)
    for lx in (-0.55, -0.25, 0.25, 0.52):
        _oell(s, (cx + lx * sz - sz * 0.13, cy + sz * 0.3, sz * 0.26, sz * 0.66), _dk(col, 0.86), 2, ol)
    _oell(s, (cx - fl * sz * 1.45, cy - sz * 0.45, sz * 0.66, sz * 0.8), col, 2, ol)
    pygame.draw.ellipse(s, belly, (cx - fl * sz * 1.32, cy - sz * 0.3, sz * 0.4, sz * 0.45))
    _oell(s, (cx - sz * 1.0, cy - sz * 0.58, sz * 2.0, sz * 1.18), col, 2, ol)
    pygame.draw.ellipse(s, belly, (cx - sz * 0.5, cy + sz * 0.05, sz * 1.0, sz * 0.42))
    hx, hy = cx + fl * sz * 0.82, cy - sz * 0.22
    _opoly(s, [(hx - fl * sz * 0.12, hy - sz * 0.3), (hx - fl * sz * 0.04, hy - sz * 0.92), (hx + fl * sz * 0.24, hy - sz * 0.34)], col, 1, ol)
    _opoly(s, [(hx + fl * sz * 0.22, hy - sz * 0.34), (hx + fl * sz * 0.36, hy - sz * 0.86), (hx + fl * sz * 0.54, hy - sz * 0.28)], col, 1, ol)
    _ocirc(s, (hx, hy), sz * 0.55, col, 2, ol)
    _opoly(s, [(hx + fl * sz * 0.1, hy - sz * 0.12), (hx + fl * sz * 0.72, hy + sz * 0.06),
               (hx + fl * sz * 0.1, hy + sz * 0.34)], muz, 1)
    pygame.draw.circle(s, (38, 34, 38), (int(hx + fl * sz * 0.62), int(hy + sz * 0.04)), 2)
    _eye(s, hx + fl * sz * 0.06, hy - sz * 0.04, 3, look=fl)
    _eye(s, hx + fl * sz * 0.36, hy - sz * 0.02, 3, look=fl)


def _d_boar(s, cx, cy, sz, fl, col):
    ol = _dk(col, 0.5); dk = _dk(col, 0.7); lt = _lt(col, 1.14)
    for lx in (-0.5, -0.25, 0.25, 0.5):
        _oell(s, (cx + lx * sz - sz * 0.12, cy + sz * 0.34, sz * 0.24, sz * 0.5), dk, 2, ol)
    for i in range(7):
        t = i / 6.0; mx = cx - sz * 0.6 + t * sz * 1.3; my = cy - sz * 0.4 - math.sin(t * 3.14) * sz * 0.12
        pygame.draw.line(s, dk, (mx, my), (mx - fl * 2, my - sz * 0.34), 2)
    _oell(s, (cx - sz * 0.98, cy - sz * 0.42, sz * 1.7, sz * 1.05), col, 2, ol)
    pygame.draw.ellipse(s, lt, (cx - sz * 0.6, cy - sz * 0.34, sz * 0.9, sz * 0.34))
    for gx, gy in ((-0.5, 0.15), (-0.2, 0.25), (0.05, 0.05), (0.25, 0.3)):
        pygame.draw.circle(s, lt, (int(cx + gx * sz), int(cy + gy * sz)), 1)
    hx, hy = cx + fl * sz * 0.7, cy - sz * 0.05
    _opoly(s, [(hx - fl * sz * 0.1, hy - sz * 0.32), (hx, hy - sz * 0.66), (hx + fl * sz * 0.16, hy - sz * 0.3)], dk, 1, ol)
    _ocirc(s, (hx, hy), sz * 0.52, col, 2, ol)
    snout = [(hx + fl * sz * 0.2, hy - sz * 0.2), (hx + fl * sz * 0.72, hy + sz * 0.02),
             (hx + fl * sz * 0.72, hy + sz * 0.3), (hx + fl * sz * 0.2, hy + sz * 0.32)]
    _opoly(s, snout, _lt(col, 1.1), 1, ol)
    for ny in (0.06, 0.2):
        pygame.draw.circle(s, (44, 32, 30), (int(hx + fl * sz * 0.66), int(hy + ny * sz)), 1)
    pygame.draw.lines(s, (246, 242, 228), False, [(hx + fl * sz * 0.4, hy + sz * 0.34), (hx + fl * sz * 0.52, hy + sz * 0.12),
                                                  (hx + fl * sz * 0.46, hy - sz * 0.04)], 2)
    _eye(s, hx + fl * sz * 0.16, hy - sz * 0.14, 2, look=fl)


def _d_deer(s, cx, cy, sz, fl, col):       # cute fawn
    ol = _dk(col, 0.55); belly = (246, 238, 226); muz = (250, 244, 234)
    leg = _dk(col, 0.78); hoof = (52, 42, 40)
    for lx in (-0.5, -0.22, 0.24, 0.5):
        x = cx + lx * sz
        pygame.draw.line(s, leg, (x, cy + sz * 0.28), (x, cy + sz * 1.05), 4)
        pygame.draw.line(s, hoof, (x, cy + sz * 0.98), (x, cy + sz * 1.08), 5)
    _oell(s, (cx - sz * 0.9, cy - sz * 0.42, sz * 1.8, sz * 0.95), col, 2, ol)
    pygame.draw.ellipse(s, _lt(col, 1.08), (cx - sz * 0.66, cy - sz * 0.38, sz * 1.1, sz * 0.36))
    pygame.draw.ellipse(s, belly, (cx - sz * 0.5, cy + sz * 0.12, sz * 1.0, sz * 0.34))
    for ox, oy in ((-0.42, -0.12), (-0.12, -0.18), (0.18, -0.1), (-0.28, 0.05), (0.04, 0.04)):
        pygame.draw.circle(s, (250, 246, 238), (int(cx + ox * sz), int(cy + oy * sz)), 2)
    nx0, ny0 = cx + fl * sz * 0.62, cy - sz * 0.2
    nx1, ny1 = cx + fl * sz * 0.95, cy - sz * 0.74
    _opoly(s, [(nx0 - fl * sz * 0.16, ny0), (nx0 + fl * sz * 0.18, ny0 + sz * 0.2),
               (nx1 + fl * sz * 0.18, ny1 + sz * 0.18), (nx1 - fl * sz * 0.16, ny1)], col, 2, ol)
    hx, hy = nx1 + fl * sz * 0.08, ny1 - sz * 0.02
    _opoly(s, [(hx - fl * sz * 0.2, hy - sz * 0.1), (hx - fl * sz * 0.5, hy - sz * 0.4), (hx - fl * sz * 0.06, hy - sz * 0.3)], col, 1, ol)
    pygame.draw.polygon(s, (236, 200, 196), [(hx - fl * sz * 0.22, hy - sz * 0.12), (hx - fl * sz * 0.42, hy - sz * 0.34), (hx - fl * sz * 0.1, hy - sz * 0.28)])
    _opoly(s, [(hx + fl * sz * 0.08, hy - sz * 0.2), (hx + fl * sz * 0.34, hy - sz * 0.5), (hx + fl * sz * 0.3, hy - sz * 0.08)], col, 1, ol)
    ac = (170, 138, 92)
    for off in (0.0, 0.16):
        bx0, by0 = hx - fl * sz * 0.02 + fl * off * sz, hy - sz * 0.28
        bx1, by1 = bx0 + fl * sz * 0.14, by0 - sz * 0.5
        pygame.draw.line(s, ac, (bx0, by0), (bx1, by1), 3)
        pygame.draw.line(s, ac, (bx0 + fl * sz * 0.06, by0 - sz * 0.24), (bx0 + fl * sz * 0.3, by0 - sz * 0.3), 3)
        pygame.draw.line(s, ac, (bx1, by1), (bx1 + fl * sz * 0.18, by1 - sz * 0.06), 3)
    _ocirc(s, (hx, hy), sz * 0.42, col, 2, ol)
    pygame.draw.ellipse(s, muz, (hx + fl * sz * 0.06, hy + sz * 0.04, sz * 0.5, sz * 0.42))
    pygame.draw.ellipse(s, (54, 42, 40), (hx + fl * sz * 0.42, hy + sz * 0.1, sz * 0.18, sz * 0.16))
    _eye(s, hx + fl * sz * 0.12, hy - sz * 0.04, 3, look=fl)


def _d_wildman(s, cx, cy, sz, fl, col=(150, 122, 92)):
    fur = col if col else (150, 122, 92); ol = _dk(fur, 0.55); dk = _dk(fur, 0.78)
    face = _lt(fur, 1.25)
    for lx in (-0.28, 0.28):
        _oell(s, (cx + lx * sz - sz * 0.16, cy + sz * 0.45, sz * 0.32, sz * 0.55), dk, 2, ol)
    _oell(s, (cx - sz * 0.5, cy - sz * 0.35, sz * 1.0, sz * 1.05), fur, 2, ol)
    for ang in range(0, 360, 30):
        a = math.radians(ang)
        pygame.draw.line(s, dk, (cx + math.cos(a) * sz * 0.48, cy + 0.1 * sz + math.sin(a) * sz * 0.5),
                         (cx + math.cos(a) * sz * 0.62, cy + 0.1 * sz + math.sin(a) * sz * 0.64), 2)
    for lx in (-0.55, 0.55):
        _oell(s, (cx + lx * sz - sz * 0.14, cy - sz * 0.1, sz * 0.28, sz * 0.55), fur, 2, ol)
    _ocirc(s, (cx, cy - sz * 0.55), sz * 0.5, fur, 2, ol)
    pygame.draw.ellipse(s, face, (cx - sz * 0.32, cy - sz * 0.6, sz * 0.64, sz * 0.6))
    for hx2 in range(-5, 6, 3):
        pygame.draw.line(s, dk, (cx + hx2 * sz * 0.08, cy - sz * 0.95), (cx + hx2 * sz * 0.08, cy - sz * 1.12), 2)
    _eye(s, cx - sz * 0.16, cy - sz * 0.52, 3, look=fl)
    _eye(s, cx + sz * 0.16, cy - sz * 0.52, 3, look=fl)
    pygame.draw.ellipse(s, (60, 46, 44), (cx - sz * 0.06, cy - sz * 0.42, sz * 0.12, sz * 0.1))
    pygame.draw.line(s, (120, 90, 60), (cx + sz * 0.55, cy + sz * 0.0), (cx + sz * 0.85, cy - sz * 0.5), 5)
    _ocirc(s, (cx + sz * 0.85, cy - sz * 0.5), sz * 0.18, (134, 100, 66), 2)


def _render(fn, s, cx, cy, sz, fl, col):
    """Draw the animal facing RIGHT into a temp surface, then mirror it for
    left-facing so both directions look identical (no asymmetric face bugs)."""
    p = int(sz * 2.4) + 4
    tmp = pygame.Surface((p * 2, p * 2), pygame.SRCALPHA)
    fn(tmp, p, p, sz, 1, col)
    if fl < 0:
        tmp = pygame.transform.flip(tmp, True, False)
    s.blit(tmp, (int(cx - p), int(cy - p)))


def chicken(s, cx, cy, sz, fl, col=(248, 248, 246)):
    _render(_d_chicken, s, cx, cy, sz, fl, col)


def cow(s, cx, cy, sz, fl, col=(244, 242, 238)):
    _render(_d_cow, s, cx, cy, sz, fl, col)


def wildman(s, cx, cy, sz, fl, col=(150, 122, 92)):
    _render(_d_wildman, s, cx, cy, sz, fl, col)


_BEASTS = {"bear": _d_bear, "wolf": _d_wolf, "boar": _d_boar, "tiger": _d_tiger, "deer": _d_deer}


def draw_beast(s, cx, cy, sz, fl, shape, col):
    _render(_BEASTS.get(shape, _d_bear), s, cx, cy, sz, fl, col)


# registry-driven farm livestock: animals.py picks the sprite by `shape`
_FARM = {"chicken": _d_chicken, "cow": _d_cow,
         "sheep": _d_sheep, "duck": _d_duck, "goat": _d_goat}


def farm_animal(s, cx, cy, sz, fl, shape, col=None):
    fn = _FARM.get(shape, _d_chicken)
    if col is None:
        col = fn.__defaults__[-1]          # each _d_* has its colour as last default
    _render(fn, s, cx, cy, sz, fl, col)


# =============================================================================
#  AMBIENT WILDLIFE (Fishing & Foraging, 2026-09 upgrade)
#  Butterflies (spring/summer days), fireflies (summer/fall nights, with glows),
#  birds that peck the grass and take off when a farmer comes close, fish that
#  leap out of the water, frogs hopping by the shore in the rain, ducks paddling
#  the ponds, dragonflies over the water's edge and bunnies (white in winter)
#  that bolt when you get near.
#  Purely cosmetic: no collision, no gameplay effect, never saved. Driven by
#  systems/forage_system.py (ForageMixin) through the hook bus. All sprites are
#  drawn once and cached; per-frame work is a few dozen tiny blits.
# =============================================================================
import random as _rnd
from .settings import TILE as _TILE, SCREEN_W as _SW, SCREEN_H as _SH

_WC = {}                                  # wildlife sprite cache

_BUTTERFLY_AREAS = ("farm", "forest", "meadow", "town")
_FIREFLY_AREAS = ("forest", "meadow", "farm")
_BIRD_AREAS = ("farm", "town", "forest", "meadow", "beach")
_FROG_AREAS = ("farm", "forest", "town", "meadow")
_JUMP_AREAS = ("farm", "town", "forest", "meadow", "beach")
_DUCK_AREAS = ("farm", "town", "forest", "meadow")
_RABBIT_AREAS = ("farm", "forest", "meadow")
_WET = ("rain", "storm")
_BF_COLS = [((250, 196, 110), (214, 120, 60)), ((170, 206, 250), (90, 130, 210)),
            ((250, 250, 240), (200, 190, 150)), ((246, 168, 206), (196, 96, 150)),
            ((200, 240, 150), (120, 170, 80))]


class WildCtx:
    """What the wildlife needs from the game each frame (built by ForageMixin)."""
    __slots__ = ("area", "minutes", "season", "weather", "players", "cam", "parts", "audio")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


# ------------------------------------------------------------------ sprites
def _butterfly(ci, frame):
    """14x11 butterfly; frame 0 = wings open, 1 = half, 2 = closed."""
    key = ("bf", ci, frame)
    if key not in _WC:
        wing, edge = _BF_COLS[ci % len(_BF_COLS)]
        s = pygame.Surface((14, 11), pygame.SRCALPHA)
        span = (6, 4, 2)[frame]
        for side in (-1, 1):
            x = 7 - span - 1 if side < 0 else 8
            pygame.draw.ellipse(s, wing, (x, 1, span + 1, 6))            # fore wing
            pygame.draw.ellipse(s, edge, (x, 1, span + 1, 6), 1)
            hx = 7 - max(2, span - 1) if side < 0 else 8
            pygame.draw.ellipse(s, _lt(wing, 1.06), (hx, 6, max(2, span - 1), 4))   # hind wing
            pygame.draw.ellipse(s, edge, (hx, 6, max(2, span - 1), 4), 1)
        pygame.draw.line(s, (60, 48, 56), (7, 2), (7, 9), 2)          # body
        pygame.draw.line(s, (60, 48, 56), (7, 2), (5, 0), 1)          # antennae
        pygame.draw.line(s, (60, 48, 56), (8, 2), (10, 0), 1)
        _WC[key] = _up(s, 1.5)
    return _WC[key]


def _up(s, f):
    """Scale a freshly drawn critter up a notch (cached by the callers)."""
    return pygame.transform.smoothscale(s, (int(s.get_width() * f), int(s.get_height() * f)))


def _firefly(level):
    """Glowing dot, brightness level 1..5 baked into alpha."""
    key = ("ff", level)
    if key not in _WC:
        b = level / 5.0
        s = pygame.Surface((22, 22), pygame.SRCALPHA)
        pygame.draw.circle(s, (200, 250, 120, int(34 * b)), (11, 11), 11)
        pygame.draw.circle(s, (214, 252, 140, int(70 * b)), (11, 11), 7)
        pygame.draw.circle(s, (236, 255, 170, int(150 * b)), (11, 11), 4)
        pygame.draw.circle(s, (255, 255, 220, int(255 * b)), (11, 11), 2)
        _WC[key] = s
    return _WC[key]


def _bird(kind, pose, fl):
    """kind "sparrow" | "gull"; pose "stand" | "peck" | "up" | "down"."""
    key = ("bird", kind, pose, fl)
    if key in _WC:
        return _WC[key]
    if fl < 0:
        _WC[key] = pygame.transform.flip(_bird(kind, pose, 1), True, False)
        return _WC[key]
    if kind == "gull":
        body, wing, cap, belly, beak = ((246, 246, 250), (170, 178, 196), (246, 246, 250),
                                        (255, 255, 255), (246, 196, 70))
    else:
        body, wing, cap, belly, beak = ((170, 124, 88), (128, 90, 62), (110, 78, 60),
                                        (232, 212, 180), (240, 180, 70))
    s = pygame.Surface((18, 16), pygame.SRCALPHA)
    ol = _dk(body, 0.55)
    if pose in ("up", "down"):
        by = 8
        pygame.draw.polygon(s, body, [(4, by), (0, by - 2), (0, by + 2)])      # tail
        pygame.draw.ellipse(s, body, (4, by - 2, 10, 6))
        pygame.draw.ellipse(s, ol, (4, by - 2, 10, 6), 1)
        if pose == "up":
            wpts = [(6, by), (4, 1), (11, by - 1)]
        else:
            wpts = [(6, by + 1), (3, by + 7), (11, by + 1)]
        pygame.draw.polygon(s, wing, wpts)
        pygame.draw.polygon(s, _dk(wing), wpts, 1)
        pygame.draw.circle(s, cap, (14, by - 1), 3)
        pygame.draw.polygon(s, beak, [(16, by - 2), (18, by - 1), (16, by)])
        pygame.draw.circle(s, (30, 26, 30), (15, by - 2), 1)
    else:
        peck = pose == "peck"
        pygame.draw.line(s, (200, 130, 60), (8, 12), (8, 15), 1)          # legs
        pygame.draw.line(s, (200, 130, 60), (10, 12), (10, 15), 1)
        pygame.draw.polygon(s, _dk(body, 0.8), [(4, 9), (0, 6), (1, 10)])  # tail
        pygame.draw.ellipse(s, body, (3, 5, 11, 8))
        pygame.draw.ellipse(s, belly, (6, 8, 7, 4))
        pygame.draw.ellipse(s, ol, (3, 5, 11, 8), 1)
        pygame.draw.ellipse(s, wing, (4, 6, 7, 4))
        hx, hy = (14, 10) if peck else (13, 5)
        pygame.draw.circle(s, cap, (hx, hy), 3)
        pygame.draw.circle(s, ol, (hx, hy), 3, 1)
        pygame.draw.polygon(s, beak, [(hx + 2, hy - 1), (hx + 5, hy + (2 if peck else 0)), (hx + 2, hy + 1)])
        pygame.draw.circle(s, (30, 26, 30), (hx + 1, hy - 1), 1)
    s = _up(s, 1.4)
    _WC[key] = s
    return s


def _frog(pose, fl):
    key = ("frog", pose, fl)
    if key in _WC:
        return _WC[key]
    if fl < 0:
        _WC[key] = pygame.transform.flip(_frog(pose, 1), True, False)
        return _WC[key]
    g, gd, belly = (110, 186, 96), (60, 120, 60), (206, 232, 160)
    s = pygame.Surface((18, 14), pygame.SRCALPHA)
    if pose == "hop":
        pygame.draw.line(s, gd, (4, 9), (0, 13), 2)                      # stretched legs
        pygame.draw.line(s, gd, (6, 10), (2, 13), 2)
        pygame.draw.ellipse(s, g, (3, 3, 12, 7))
        pygame.draw.ellipse(s, gd, (3, 3, 12, 7), 1)
        pygame.draw.line(s, gd, (13, 8), (16, 12), 2)
    else:
        pygame.draw.ellipse(s, gd, (1, 8, 7, 5))                         # haunch
        pygame.draw.ellipse(s, g, (3, 4, 12, 9))
        pygame.draw.ellipse(s, belly, (8, 8, 6, 4))
        pygame.draw.ellipse(s, gd, (3, 4, 12, 9), 1)
        pygame.draw.line(s, gd, (12, 11), (14, 13), 2)
    for ex in (10, 13):                                                  # eye bumps
        pygame.draw.circle(s, g, (ex, 4), 2)
        pygame.draw.circle(s, (250, 250, 240), (ex, 4), 1)
    pygame.draw.circle(s, (20, 20, 20), (13, 4), 1)
    s = _up(s, 1.45)
    _WC[key] = s
    return s


def _jumpfish(ang, fl):
    """Small silvery fish, ang in (-1 nose up, 0 level, 1 nose down)."""
    key = ("jf", ang, fl)
    if key in _WC:
        return _WC[key]
    s = pygame.Surface((14, 8), pygame.SRCALPHA)
    col = (176, 200, 220)
    pygame.draw.polygon(s, _dk(col, 0.8), [(3, 4), (0, 1), (0, 7)])
    pygame.draw.ellipse(s, col, (2, 1, 11, 6))
    pygame.draw.ellipse(s, (236, 244, 250), (4, 4, 8, 2))
    pygame.draw.circle(s, (30, 30, 40), (10, 3), 1)
    s = _up(s, 1.4)
    if ang:
        s = pygame.transform.rotate(s, -35 * ang)
    if fl < 0:
        s = pygame.transform.flip(s, True, False)
    _WC[key] = s
    return s


def _duck(kind, pose, fl):
    """Swimming duck on the water: kind "drake" | "hen" | "duckling";
    pose "swim" | "dip" (tail up, head under)."""
    key = ("duck", kind, pose, fl)
    if key in _WC:
        return _WC[key]
    if fl < 0:
        _WC[key] = pygame.transform.flip(_duck(kind, pose, 1), True, False)
        return _WC[key]
    s = pygame.Surface((22, 16), pygame.SRCALPHA)
    if kind == "drake":
        body, head, chest, bill = (196, 186, 170), (60, 138, 92), (136, 90, 70), (242, 196, 70)
    elif kind == "hen":
        body, head, chest, bill = (170, 128, 88), (150, 110, 76), (186, 144, 102), (226, 150, 70)
    else:
        body, head, chest, bill = (246, 222, 110), (250, 230, 120), (246, 214, 100), (236, 160, 60)
    ol = _dk(body, 0.55)
    if pose == "dip":
        pygame.draw.ellipse(s, body, (5, 7, 12, 7))
        pygame.draw.ellipse(s, ol, (5, 7, 12, 7), 1)
        pygame.draw.polygon(s, _dk(body, 0.8), [(6, 9), (3, 3), (9, 8)])      # tail up
    else:
        pygame.draw.polygon(s, _dk(body, 0.8), [(3, 9), (0, 6), (4, 11)])     # tail
        pygame.draw.ellipse(s, body, (2, 6, 15, 8))
        pygame.draw.ellipse(s, chest, (10, 7, 7, 6))
        pygame.draw.ellipse(s, ol, (2, 6, 15, 8), 1)
        pygame.draw.ellipse(s, _dk(body, 0.85), (5, 7, 7, 3))                  # folded wing
        small = kind == "duckling"
        hx, hy, hr = (15, 5, 3) if not small else (14, 6, 3)
        pygame.draw.circle(s, head, (hx, hy), hr)
        pygame.draw.circle(s, _dk(head, 0.6), (hx, hy), hr, 1)
        if kind == "drake":
            pygame.draw.line(s, (250, 250, 250), (hx - 2, hy + 3), (hx + 2, hy + 3), 1)   # white collar
        pygame.draw.polygon(s, bill, [(hx + 2, hy), (hx + 6, hy + 1), (hx + 2, hy + 2)])
        pygame.draw.circle(s, (24, 22, 26), (hx + 1, hy - 1), 1)
    pygame.draw.line(s, (214, 238, 255, 170), (2, 13), (19, 13), 1)          # waterline
    s = _up(s, 1.35)
    _WC[key] = s
    return s


def _dragonfly(ci, frame, fl):
    """Slim dragonfly (wings flicker between 2 frames)."""
    key = ("dfly", ci, frame, fl)
    if key in _WC:
        return _WC[key]
    if fl < 0:
        _WC[key] = pygame.transform.flip(_dragonfly(ci, frame, 1), True, False)
        return _WC[key]
    body = ((70, 176, 196), (226, 110, 90), (120, 190, 110))[ci % 3]
    s = pygame.Surface((18, 12), pygame.SRCALPHA)
    wing = (226, 244, 255, 150)
    if frame == 0:
        wings = [(8, 5, 6, 3), (8, 2, 5, 3), (4, 5, 6, 3), (4, 2, 5, 3)]
    else:
        wings = [(8, 6, 6, 2), (8, 3, 5, 2), (4, 6, 6, 2), (4, 3, 5, 2)]
    for (x, y, w, h) in wings:
        pygame.draw.ellipse(s, wing, (x, y, w, h))
    pygame.draw.line(s, _dk(body, 0.7), (1, 6), (12, 6), 3)                     # abdomen
    pygame.draw.line(s, body, (1, 6), (12, 6), 1)
    pygame.draw.circle(s, body, (13, 6), 2)                                      # thorax
    pygame.draw.circle(s, _dk(body, 0.5), (15, 5), 2)                            # big eyes
    _WC[key] = _up(s, 1.3)
    return _WC[key]


def _rabbit(white, pose, fl):
    """Wild bunny: brown, or snowy white in winter; pose "sit" | "hop"."""
    key = ("rab", white, pose, fl)
    if key in _WC:
        return _WC[key]
    if fl < 0:
        _WC[key] = pygame.transform.flip(_rabbit(white, pose, 1), True, False)
        return _WC[key]
    fur = (244, 244, 250) if white else (176, 140, 108)
    ol = _dk(fur, 0.6)
    s = pygame.Surface((20, 18), pygame.SRCALPHA)
    if pose == "hop":
        pygame.draw.ellipse(s, fur, (2, 7, 13, 7))                             # stretched body
        pygame.draw.ellipse(s, ol, (2, 7, 13, 7), 1)
        pygame.draw.line(s, ol, (3, 12), (0, 15), 2)                            # kicking legs
        hx, hy = 15, 7
    else:
        pygame.draw.ellipse(s, fur, (3, 7, 12, 10))                            # round body
        pygame.draw.ellipse(s, ol, (3, 7, 12, 10), 1)
        pygame.draw.ellipse(s, _lt(fur, 1.05), (9, 13, 6, 4))                  # paws
        hx, hy = 14, 8
    pygame.draw.circle(s, (255, 255, 255), (3, 10), 2)                          # cotton tail
    for ex in (-2, 1):                                                          # long ears
        pygame.draw.ellipse(s, fur, (hx + ex - 1, hy - 8, 3, 8))
        pygame.draw.ellipse(s, ol, (hx + ex - 1, hy - 8, 3, 8), 1)
    pygame.draw.circle(s, fur, (hx, hy), 4)
    pygame.draw.circle(s, ol, (hx, hy), 4, 1)
    pygame.draw.circle(s, (30, 24, 28), (hx + 1, hy - 1), 1)
    pygame.draw.circle(s, (236, 150, 160), (hx + 4, hy + 1), 1)                 # pink nose
    s = _up(s, 1.3)
    _WC[key] = s
    return s


def _shadow(w):
    key = ("sh", w)
    if key not in _WC:
        s = pygame.Surface((w, max(3, w // 3)), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (20, 30, 20, 60), s.get_rect())
        _WC[key] = s
    return _WC[key]


# ------------------------------------------------------------------ manager
class Wildlife:
    """All ambient critters of the current area. ``enter`` on every warp,
    ``update`` each frame, then ``sprites`` (y-sorted, ground level),
    ``draw_above`` (airborne) and ``lights`` (firefly glows)."""

    def __init__(self):
        self.area_name = None
        self.grass, self.water, self.shore = [], [], []
        self._clear()

    def _clear(self):
        self.bf, self.ff, self.birds, self.frogs, self.jumps = [], [], [], [], []
        self.ducks, self.dfly, self.rabbits = [], [], []
        self._think = 0.0
        self._jump_t = _rnd.uniform(1.5, 4.0)
        self._bird_cd = 0.0
        self.t = 0.0

    def count(self):
        return (len(self.bf) + len(self.ff) + len(self.birds) + len(self.frogs)
                + len(self.jumps) + len(self.ducks) + len(self.dfly) + len(self.rabbits))

    # ---- area scan ----
    def enter(self, ctx):
        self._clear()
        area = ctx.area
        self.area_name = getattr(area, "name", None)
        self.grass, self.water, self.shore = [], [], []
        if self.area_name not in _BIRD_AREAS:
            return                                   # indoors / mine: nothing lives here
        ground = (".", ",", "n", "N") if self.area_name == "beach" else None
        not_ground = ("P", "W", "S", "#", "F", "d", "T", "m", "@", "k", "K", "i", "l", "c")
        for gy in range(1, area.h - 1):
            row = area.grid[gy]
            for gx in range(1, area.w - 1):
                t = row[gx]
                if t == "W":
                    if all(area.tile(gx + dx, gy + dy) == "W"
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        self.water.append((gx, gy))
                    continue
                if (ground and t not in ground) or (not ground and t in not_ground):
                    continue
                if area.is_solid(gx, gy):
                    continue
                self.grass.append((gx, gy))
                if any(area.tile(gx + dx, gy + dy) == "W"
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.shore.append((gx, gy))
        self._populate(ctx, instant=True)

    # ---- population targets ----
    def _targets(self, ctx):
        a, m, s = self.area_name, ctx.minutes or 0, ctx.season
        wet = ctx.weather in _WET
        day = 390 <= m < 1110
        night = m >= 1170 or m < 300
        bf = ff = birds = frogs = 0
        if a in _BUTTERFLY_AREAS and day and s in ("Spring", "Summer") and not wet:
            bf = {"meadow": 8, "town": 3}.get(a, 5)
        if a in _FIREFLY_AREAS and night and s in ("Summer", "Fall") and not wet:
            ff = {"meadow": 16, "forest": 12}.get(a, 7)
        if a in _BIRD_AREAS and 360 <= m < 1140 and not wet and self.grass:
            birds = 3 if a in ("town", "beach") else 4
            if s == "Winter":
                birds -= 1
        if wet and a in _FROG_AREAS and self.shore:
            frogs = 3
        return bf, ff, birds, frogs

    def _duck_target(self, ctx):
        """A pair of ducks paddles on the ponds by day (+ a duckling in spring)."""
        m, s = ctx.minutes or 0, ctx.season
        if self.area_name in _DUCK_AREAS and 390 <= m < 1140 and s != "Winter" and len(self.water) >= 6:
            return 3 if s == "Spring" else 2
        return 0

    def _populate_ducks(self, ctx, instant):
        want = self._duck_target(ctx)
        if len(self.ducks) >= want:
            if len(self.ducks) > want:                   # evening: one paddles off (out of view)
                x0, y0, x1, y1 = self._view(ctx, 40)
                for d in self.ducks:
                    if not (x0 < d["x"] < x1 and y0 < d["y"] < y1):
                        self.ducks.remove(d)
                        break
            return
        # the flock swims together: newcomers join the leader, else start anywhere
        lead = self.ducks[0] if self.ducks else None
        if lead is None:
            x0, y0, x1, y1 = self._view(ctx, 40)
            pool = self.water if instant else [t for t in self.water
                                               if not (x0 < t[0] * _TILE < x1 and y0 < t[1] * _TILE < y1)]
            if not pool:
                return
            gx, gy = _rnd.choice(pool)
            x, y = gx * _TILE + _TILE / 2, gy * _TILE + _TILE / 2
        else:
            x, y = lead["x"] - 20, lead["y"] + 6
        kinds = ("drake", "hen", "duckling")
        self.ducks.append({"x": x, "y": y, "a": _rnd.uniform(0, 6.28), "spd": _rnd.uniform(9, 14),
                           "t": _rnd.uniform(1.5, 4.0), "dip": 0.0, "wake": _rnd.uniform(0, 0.7),
                           "kind": kinds[min(len(self.ducks), 2)], "ph": _rnd.uniform(0, 6.28)})

    def _view(self, ctx, margin=0):
        """World rect the players can see. Centred on the players (the camera
        follows their midpoint) so it is right even on the frame of a warp,
        before the camera has caught up."""
        ps = ctx.players or ()
        if ps:
            cx = sum(p.x for p in ps) / len(ps)
            cy = sum(p.y for p in ps) / len(ps)
        else:
            cx, cy = ctx.cam.x + _SW / 2, ctx.cam.y + _SH / 2
        return (cx - _SW / 2 - margin, cy - _SH / 2 - margin,
                cx + _SW / 2 + margin, cy + _SH / 2 + margin)

    def _tile_in_view(self, tiles, ctx, margin=_TILE, avoid=0, tries=14):
        if not tiles:
            return None
        x0, y0, x1, y1 = self._view(ctx, margin)
        for _ in range(tries):
            gx, gy = _rnd.choice(tiles)
            wx, wy = gx * _TILE + _TILE / 2, gy * _TILE + _TILE / 2
            if not (x0 <= wx <= x1 and y0 <= wy <= y1):
                continue
            if avoid and any(abs(p.x - wx) + abs(p.y - wy) < avoid for p in ctx.players):
                continue
            return wx, wy
        return None

    def _populate(self, ctx, instant=False):
        bf, ff, birds, frogs = self._targets(ctx)
        # butterflies drift in from the edge of the view (instant: already here)
        live = [b for b in self.bf if not b["leave"]]
        for _ in range(max(0, bf - len(live)) if instant else min(1, bf - len(live))):
            pos = self._tile_in_view(self.grass, ctx, margin=0 if instant else _TILE * 2)
            if pos:
                x, y = pos
                a = _rnd.uniform(0, 6.28)
                if not instant:                              # start just off-screen
                    side = _rnd.choice((-1, 1))
                    vx0, _vy0, vx1, _vy1 = self._view(ctx)
                    x = vx0 - 20 if side > 0 else vx1 + 20
                    a = 0.0 if side > 0 else math.pi
                self.bf.append({"x": x, "y": y, "h": 18.0, "a": a,
                                "spd": _rnd.uniform(24, 38), "ph": _rnd.uniform(0, 6.28),
                                "ci": _rnd.randrange(len(_BF_COLS)), "turn": 0.0, "da": 0.0,
                                "leave": False, "rest": 0.0})
        if len(live) > bf:
            live[0]["leave"] = True
        # fireflies blink into being anywhere in view
        lit = [f for f in self.ff if not f["leave"]]
        n = (ff - len(lit)) if instant else min(2, ff - len(lit))
        for _ in range(max(0, n)):
            pos = self._tile_in_view(self.grass, ctx, margin=_TILE * 2)
            if pos:
                self.ff.append({"x": pos[0] + _rnd.uniform(-20, 20), "y": pos[1] + _rnd.uniform(-20, 20),
                                "h": _rnd.uniform(10, 34), "vx": _rnd.uniform(-10, 10),
                                "vy": _rnd.uniform(-6, 6), "ph": _rnd.uniform(0, 6.28),
                                "sp": _rnd.uniform(1.6, 3.0), "leave": False,
                                "life": 1.0 if instant else 0.0})
        if len(lit) > ff:
            lit[0]["leave"] = True
        # birds: already pecking when you arrive, later they fly in and land
        ground = [b for b in self.birds if b["state"] != "fly"]
        for _ in range(max(0, birds - len(ground)) if instant else 1):
            if len(ground) >= birds or (not instant and self._bird_cd > 0):
                break
            pos = self._tile_in_view(self.grass, ctx, margin=0, avoid=_TILE * 5)
            if not pos:
                break
            self._bird_cd = _rnd.uniform(3.0, 7.0)
            fl = _rnd.choice((-1, 1))
            b = {"x": pos[0] + _rnd.uniform(-12, 12), "y": pos[1] + _rnd.uniform(-8, 8), "h": 0.0,
                 "vx": 0.0, "vh": 0.0, "state": "peck", "fl": fl, "t": _rnd.uniform(0.2, 0.8),
                 "pose": "stand", "hops": _rnd.randint(2, 5), "scare": -1.0,
                 "kind": "gull" if self.area_name == "beach" else "sparrow"}
            if not instant:                                  # glide down to land
                b.update(state="land", h=150.0, tx=b["x"], x=b["x"] - fl * 180, vx=fl * 120.0)
            self.birds.append(b)
            ground.append(b)
        # evening / rain: grounded birds fly off one by one
        grounded = [b for b in self.birds if b["state"] in ("peck", "hop")]
        if not instant and len(grounded) > birds:
            self._takeoff(grounded[0], None, ctx)
        # rain stopped: frogs plop back into the water
        sitting = [f for f in self.frogs if f["state"] == "sit"]
        if not instant and len(self.frogs) > frogs and sitting:
            f = sitting[0]
            self._frog_hop(f, ctx, dive=True)
            if not f.get("dive"):
                self.frogs.remove(f)
        for _ in range(3 if instant else 1):
            self._populate_ducks(ctx, instant)
        # dragonflies zip over the water's edge on warm, dry days
        m = ctx.minutes or 0
        want = 3 if (self.area_name in _DUCK_AREAS and 480 <= m < 1080 and self.shore
                     and ctx.season in ("Spring", "Summer") and ctx.weather not in _WET) else 0
        if len(self.dfly) < want:
            pos = self._tile_in_view(self.shore, ctx, margin=_TILE * 2)
            if pos:
                self.dfly.append({"x": pos[0], "y": pos[1], "hx": pos[0], "hy": pos[1], "h": 22.0,
                                  "t": _rnd.uniform(0.3, 1.2), "tx": pos[0], "ty": pos[1],
                                  "ci": _rnd.randrange(3), "fl": 1, "dash": False})
        elif len(self.dfly) > want:
            self.dfly.pop(0)
        # bunnies nibble in the grass (snow-white in winter)
        want = 0
        if self.area_name in _RABBIT_AREAS and 360 <= m < 1140 and ctx.weather not in _WET:
            want = 3 if self.area_name in ("forest", "meadow") else 1
        calm = [r for r in self.rabbits if r["state"] != "flee"]
        for _ in range(want - len(calm) if instant else (1 if _rnd.random() < 0.25 else 0)):
            if len(calm) >= want:
                break
            pos = self._tile_in_view(self.grass, ctx, margin=0, avoid=_TILE * 5)
            if pos:
                r = {"x": pos[0], "y": pos[1], "state": "sit", "t": _rnd.uniform(0.5, 3.0),
                     "fl": _rnd.choice((-1, 1)), "k": 0.0, "x0": 0.0, "y0": 0.0,
                     "x1": 0.0, "y1": 0.0, "white": ctx.season == "Winter", "left": 0}
                self.rabbits.append(r)
                calm.append(r)
        if len(calm) > want and calm:
            calm[0]["state"] = "flee"
            calm[0]["left"] = 6
        # frogs appear by the water when it rains
        if len(self.frogs) < frogs:
            pos = self._tile_in_view(self.shore, ctx, margin=_TILE, avoid=_TILE * 3)
            if pos:
                self.frogs.append({"x": pos[0], "y": pos[1] + 6, "state": "sit",
                                   "t": _rnd.uniform(0.8, 3.0), "fl": _rnd.choice((-1, 1)),
                                   "k": 0.0, "x0": 0, "y0": 0, "x1": 0, "y1": 0, "dive": False})

    # ---- per-frame ----
    def update(self, dt, ctx):
        if ctx.area is None:
            return
        if getattr(ctx.area, "name", None) != self.area_name:
            self.enter(ctx)
        if self.area_name not in _BIRD_AREAS:
            return
        self.t += dt
        self._bird_cd -= dt
        self._think -= dt
        if self._think <= 0:
            self._think = 0.9
            self._populate(ctx)
        x0, y0, x1, y1 = self._view(ctx, 260)
        # critters left far behind (players walked off) are recycled so the
        # population re-forms around the players
        far = 520
        self.ff = [f for f in self.ff if x0 - far < f["x"] < x1 + far and y0 - far < f["y"] < y1 + far]
        self.birds = [b for b in self.birds
                      if b["state"] == "fly" or (x0 - far < b["x"] < x1 + far and y0 - far < b["y"] < y1 + far)]
        self.frogs = [f for f in self.frogs if x0 - far < f["x"] < x1 + far and y0 - far < f["y"] < y1 + far]
        self.dfly = [d for d in self.dfly if x0 - far < d["x"] < x1 + far and y0 - far < d["y"] < y1 + far]
        self.rabbits = [r for r in self.rabbits
                        if x0 - far < r["x"] < x1 + far and y0 - far < r["y"] < y1 + far]
        self._update_butterflies(dt, ctx, x0, y0, x1, y1)
        self._update_fireflies(dt)
        self._update_birds(dt, ctx, x0, x1)
        self._update_frogs(dt, ctx)
        self._update_jumps(dt, ctx)
        self._update_ducks(dt, ctx, x0, y0, x1, y1)
        self._update_dragonflies(dt)
        self._update_rabbits(dt, ctx, x0, y0, x1, y1)

    def _update_rabbits(self, dt, ctx, x0, y0, x1, y1):
        area = ctx.area
        keep = []
        for r in self.rabbits:
            if r["state"] == "hop":
                r["k"] += dt / (0.2 if r["left"] else 0.3)
                if r["k"] < 1.0:
                    keep.append(r)
                    continue
                r["x"], r["y"] = r["x1"], r["y1"]
                if r["left"] > 0:                              # fleeing: bound after bound
                    r["left"] -= 1
                    if r["left"] <= 0 or not (x0 < r["x"] < x1 and y0 < r["y"] < y1):
                        continue                               # gone into the bushes
                    self._rabbit_hop(r, area, flee=True)
                else:
                    r.update(state="sit", t=_rnd.uniform(1.0, 4.0), k=0.0)
                keep.append(r)
                continue
            if r["state"] == "flee":                           # told to leave (evening / rain)
                self._rabbit_hop(r, area, flee=True)
                keep.append(r)
                continue
            near = None
            for p in ctx.players:
                d = abs(p.x - r["x"]) + abs(p.y - r["y"])
                if d < _TILE * 2.4 and (near is None or d < near[0]):
                    near = (d, p)
            if near:
                r["left"] = 6
                r["away"] = 1 if r["x"] >= near[1].x else -1
                self._rabbit_hop(r, area, flee=True)
            else:
                r["t"] -= dt
                if r["t"] <= 0:
                    self._rabbit_hop(r, area)
            keep.append(r)
        self.rabbits = keep

    def _rabbit_hop(self, r, area, flee=False):
        if flee:
            away = r.get("away", r["fl"])
            opts = [(away * _TILE * 1.4, _rnd.uniform(-0.5, 0.5) * _TILE),
                    (away * _TILE * 1.1, _rnd.choice((-1, 1)) * _TILE)]
        else:
            opts = [(_rnd.uniform(-1, 1) * _TILE * 0.8, _rnd.uniform(-0.6, 0.6) * _TILE) for _ in range(3)]
        for dx, dy in opts:
            nx, ny = r["x"] + dx, r["y"] + dy
            gx, gy = int(nx // _TILE), int(ny // _TILE)
            if not area.is_solid(gx, gy) and area.tile(gx, gy) != "W":
                r.update(state="hop", k=0.0, x0=r["x"], y0=r["y"], x1=nx, y1=ny,
                         fl=1 if dx >= 0 else -1)
                return
        if flee:
            r["left"] = 1                                      # cornered: vanish on the next bound
            r.update(state="hop", k=0.0, x0=r["x"], y0=r["y"], x1=r["x"], y1=r["y"])
        else:
            r["t"] = _rnd.uniform(1.0, 3.0)

    def _update_dragonflies(self, dt):
        for d in self.dfly:
            if d["dash"]:                                   # a quick straight zip
                dx, dy = d["tx"] - d["x"], d["ty"] - d["y"]
                dist = math.hypot(dx, dy)
                step = 190 * dt
                if dist <= step:
                    d["x"], d["y"], d["dash"] = d["tx"], d["ty"], False
                    d["t"] = _rnd.uniform(0.4, 1.6)
                else:
                    d["x"] += dx / dist * step
                    d["y"] += dy / dist * step
            else:                                           # hover with a tiny jitter
                d["t"] -= dt
                d["x"] += _rnd.uniform(-8, 8) * dt
                d["y"] += _rnd.uniform(-6, 6) * dt
                if d["t"] <= 0:
                    d["tx"] = d["hx"] + _rnd.uniform(-_TILE * 2.5, _TILE * 2.5)
                    d["ty"] = d["hy"] + _rnd.uniform(-_TILE * 1.5, _TILE * 1.5)
                    d["fl"] = 1 if d["tx"] >= d["x"] else -1
                    d["dash"] = True
            d["h"] = 20 + math.sin(self.t * 3 + d["hx"]) * 3

    def _update_ducks(self, dt, ctx, x0, y0, x1, y1):
        area = ctx.area
        lead = None
        for d in self.ducks:
            if d["dip"] > 0:                               # bottoms up!
                d["dip"] -= dt
                lead = lead or d
                continue
            d["t"] -= dt
            if lead is None:                                # the leader wanders the pond
                if d["t"] <= 0:
                    d["t"] = _rnd.uniform(1.5, 4.0)
                    d["a"] += _rnd.uniform(-0.9, 0.9)
                    if _rnd.random() < 0.12:
                        d["dip"] = 0.9
                        if ctx.parts and x0 < d["x"] < x1 and y0 < d["y"] < y1:
                            ctx.parts.ripple(d["x"], d["y"] + 4)
                ahead = (d["x"] + math.cos(d["a"]) * 26, d["y"] + math.sin(d["a"]) * 22)
                if area.tile(int(ahead[0] // _TILE), int(ahead[1] // _TILE)) != "W":
                    d["a"] += math.pi * _rnd.uniform(0.6, 1.0)      # bump the bank: turn
                else:
                    d["x"] += math.cos(d["a"]) * d["spd"] * dt
                    d["y"] += math.sin(d["a"]) * d["spd"] * dt * 0.7
                lead = d
            else:                                           # the others follow in a line
                tx = lead["x"] - math.cos(lead["a"]) * 22
                ty = lead["y"] - math.sin(lead["a"]) * 14 + 4
                dx, dy = tx - d["x"], ty - d["y"]
                dist = math.hypot(dx, dy)
                if dist > 3:
                    step = min(dist, (d["spd"] + 6) * dt)
                    nx, ny = d["x"] + dx / dist * step, d["y"] + dy / dist * step
                    if area.tile(int(nx // _TILE), int(ny // _TILE)) == "W":
                        d["x"], d["y"] = nx, ny
                    d["a"] = math.atan2(dy, dx)
                lead = d
            d["wake"] -= dt
            if d["wake"] <= 0:
                d["wake"] = 0.8
                if ctx.parts and x0 < d["x"] < x1 and y0 < d["y"] < y1:
                    ctx.parts.ripple(d["x"] - math.cos(d["a"]) * 8, d["y"] + 5)

    def _update_butterflies(self, dt, ctx, x0, y0, x1, y1):
        aw, ah = ctx.area.w * _TILE, ctx.area.h * _TILE
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        keep = []
        for b in self.bf:
            b["turn"] -= dt
            if b["rest"] > 0:                               # perched on a flower, wings flexing
                b["rest"] -= dt
                b["h"] = max(4.0, b["h"] - 40 * dt)
                keep.append(b)
                continue
            if b["turn"] <= 0:
                b["turn"] = _rnd.uniform(0.4, 1.3)
                b["da"] = _rnd.uniform(-1.8, 1.8)
                if not b["leave"] and _rnd.random() < 0.07:
                    b["rest"] = _rnd.uniform(1.0, 2.5)
            b["a"] += b["da"] * dt
            if not b["leave"]:                              # stay near the action
                far = (abs(b["x"] - cx) > (x1 - x0) / 2 - 260 or abs(b["y"] - cy) > (y1 - y0) / 2 - 260
                       or not (_TILE < b["x"] < aw - _TILE and _TILE < b["y"] < ah - _TILE))
                if far:
                    want = math.atan2(cy - b["y"], cx - b["x"])
                    diff = math.atan2(math.sin(want - b["a"]), math.cos(want - b["a"]))
                    b["a"] += diff * min(1.0, dt * 2.5)
            b["x"] += math.cos(b["a"]) * b["spd"] * dt
            b["y"] += math.sin(b["a"]) * b["spd"] * dt * 0.7
            want_h = 18 + math.sin(self.t * 1.7 + b["ph"]) * 7
            b["h"] += (want_h - b["h"]) * min(1.0, dt * 4)
            if b["leave"] and not (x0 < b["x"] < x1 and y0 < b["y"] < y1):
                continue
            keep.append(b)
        self.bf = keep

    def _update_fireflies(self, dt):
        keep = []
        for f in self.ff:
            f["life"] += dt
            f["vx"] = max(-14, min(14, f["vx"] + _rnd.uniform(-20, 20) * dt))
            f["vy"] = max(-10, min(10, f["vy"] + _rnd.uniform(-14, 14) * dt))
            f["x"] += f["vx"] * dt
            f["y"] += f["vy"] * dt
            f["h"] = max(6.0, min(40.0, f["h"] + math.sin(self.t + f["ph"]) * dt * 6))
            if f["leave"] and self._ff_level(f) == 0:
                continue
            keep.append(f)
        self.ff = keep

    def _update_birds(self, dt, ctx, x0, x1):
        keep = []
        for b in self.birds:
            st = b["state"]
            if st in ("peck", "hop"):
                near = None
                for p in ctx.players:
                    d = abs(p.x - b["x"]) + abs(p.y - b["y"])
                    if d < _TILE * 2.6 and (near is None or d < near[0]):
                        near = (d, p)
                if b["scare"] > 0:
                    b["scare"] = max(0.0, b["scare"] - dt)
                if near or b["scare"] == 0.0:
                    self._takeoff(b, near[1] if near else None, ctx)
                    for o in self.birds:                    # the flock startles a beat later
                        if (o is not b and o["state"] in ("peck", "hop") and o["scare"] < 0
                                and abs(o["x"] - b["x"]) + abs(o["y"] - b["y"]) < _TILE * 4):
                            o["scare"] = _rnd.uniform(0.08, 0.35)
                    keep.append(b)
                    continue
            if st == "peck":
                b["t"] -= dt
                if b["t"] <= 0:
                    b["pose"] = "peck" if b["pose"] == "stand" else "stand"
                    b["t"] = _rnd.uniform(0.12, 0.3) if b["pose"] == "peck" else _rnd.uniform(0.3, 1.1)
                    if b["pose"] == "stand":
                        b["hops"] -= 1
                        if b["hops"] <= 0:
                            b["hops"] = _rnd.randint(2, 5)
                            if _rnd.random() < 0.35:
                                b["fl"] = -b["fl"]
                            b.update(state="hop", k=0.0, hx=b["x"], dx=b["fl"] * _rnd.uniform(6, 14))
            elif st == "hop":
                b["k"] += dt / 0.22
                k = min(1.0, b["k"])
                b["x"] = b["hx"] + b["dx"] * k
                b["h"] = math.sin(k * math.pi) * 4
                if k >= 1.0:
                    b.update(state="peck", h=0.0, pose="stand", t=_rnd.uniform(0.3, 0.9))
            elif st == "land":
                b["x"] += b["vx"] * dt
                b["h"] = max(0.0, b["h"] - 100 * dt)
                b["pose"] = "up" if int(self.t * 12) % 2 else "down"
                arrived = (b["vx"] > 0 and b["x"] >= b["tx"]) or (b["vx"] < 0 and b["x"] <= b["tx"])
                if b["h"] <= 0 or arrived:
                    b.update(state="peck", h=0.0, pose="stand", t=_rnd.uniform(0.3, 0.9), x=b["tx"])
            else:                                           # flying away
                b["x"] += b["vx"] * dt
                b["h"] += b["vh"] * dt
                b["vh"] += 25 * dt
                b["pose"] = "up" if int(self.t * 14 + b["y"]) % 2 else "down"
                if b["h"] > 320 or not (x0 < b["x"] < x1):
                    continue
            keep.append(b)
        self.birds = keep

    def _update_frogs(self, dt, ctx):
        keep = []
        for f in self.frogs:
            if f["state"] == "sit":
                f["t"] -= dt
                scared = any(abs(p.x - f["x"]) + abs(p.y - f["y"]) < _TILE * 1.7 for p in ctx.players)
                if scared or f["t"] <= 0:
                    self._frog_hop(f, ctx, dive=scared)
            else:
                f["k"] += dt / 0.36
                if f["k"] >= 1.0:
                    f["x"], f["y"] = f["x1"], f["y1"]
                    if f["dive"]:
                        if ctx.parts:
                            ctx.parts.ripple(f["x"], f["y"])
                            ctx.parts.splash(f["x"], f["y"], n=4)
                        continue
                    f.update(state="sit", t=_rnd.uniform(1.2, 3.5), k=0.0)
            keep.append(f)
        self.frogs = keep

    def _update_jumps(self, dt, ctx):
        self._jump_t -= dt
        if self._jump_t <= 0:
            self._jump_t = _rnd.uniform(2.5, 6.0)
            pos = self._tile_in_view(self.water, ctx, margin=-_TILE) if self.area_name in _JUMP_AREAS else None
            if pos:
                x, y = pos[0] + _rnd.uniform(-10, 10), pos[1] + _rnd.uniform(-8, 8)
                fl = _rnd.choice((-1, 1))
                self.jumps.append({"x": x, "y": y, "dx": fl * _rnd.uniform(14, 26), "k": 0.0,
                                   "fl": fl, "hi": _rnd.uniform(12, 20)})
                if ctx.parts:
                    ctx.parts.ripple(x, y)
                    ctx.parts.splash(x, y, n=3)
        keep = []
        for j in self.jumps:
            j["k"] += dt / 0.75
            if j["k"] >= 1.0:
                if ctx.parts:
                    ctx.parts.ripple(j["x"] + j["dx"], j["y"])
                    ctx.parts.splash(j["x"] + j["dx"], j["y"], n=4)
                continue
            keep.append(j)
        self.jumps = keep

    def _takeoff(self, b, p, ctx):
        away = 1 if (p is None or b["x"] >= p.x) else -1
        b.update(state="fly", fl=away, vx=away * _rnd.uniform(120, 170), vh=_rnd.uniform(70, 110),
                 pose="up", scare=-1.0)
        if ctx.parts:
            ctx.parts.dust(b["x"], b["y"] + 4, n=3, color=(190, 180, 150))
        if ctx.audio:
            ctx.audio.play("flutter")                        # no-op until Core adds it

    def _frog_hop(self, f, ctx, dive=False):
        area = ctx.area
        gx, gy = int(f["x"] // _TILE), int(f["y"] // _TILE)
        target = None
        if dive:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if area.tile(gx + dx, gy + dy) == "W":
                    target = ((gx + dx) * _TILE + _TILE / 2, (gy + dy) * _TILE + _TILE / 2)
                    break
        if target is None:
            dive = False
            near = [t for t in self.shore
                    if abs(t[0] - gx) <= 2 and abs(t[1] - gy) <= 2 and t != (gx, gy)]
            if not near:
                f["t"] = _rnd.uniform(1.5, 3.0)
                return
            tx, ty = _rnd.choice(near)
            target = (tx * _TILE + _TILE / 2 + _rnd.uniform(-8, 8), ty * _TILE + _TILE / 2 + 6)
        f.update(state="hop", k=0.0, x0=f["x"], y0=f["y"], x1=target[0], y1=target[1], dive=dive,
                 fl=1 if target[0] >= f["x"] else -1)

    def _ff_level(self, f):
        v = (math.sin(self.t * f["sp"] + f["ph"]) + 0.45) / 1.45     # lit ~2/3 of the time
        if f["life"] < 1.0:
            v *= f["life"]
        return max(0, min(5, int(v * 6)))

    # ---- drawing ----
    def sprites(self, cam):
        """Ground-level critters for the shared y-sort: (baseline, surf, pos)."""
        out = []
        vx0, vy0 = cam.x - 40, cam.y - 60
        vx1, vy1 = cam.x + _SW + 40, cam.y + _SH + 60
        for b in self.bf:
            if not (vx0 < b["x"] < vx1 and vy0 < b["y"] < vy1):
                continue
            if b["rest"] > 0:
                fr = 0 if int(self.t * 2 + b["ph"]) % 3 else 2
            else:
                fr = (0, 1, 2, 1)[int(self.t * 16 + b["ph"] * 3) % 4]
            spr = _butterfly(b["ci"], fr)
            out.append((b["y"], _shadow(8), (b["x"] - 4 - cam.x, b["y"] - cam.y)))
            out.append((b["y"] + 0.1, spr, (b["x"] - spr.get_width() / 2 - cam.x,
                                             b["y"] - b["h"] - spr.get_height() / 2 - cam.y)))
        for b in self.birds:
            if b["state"] in ("fly", "land") and b["h"] > 8:
                continue
            if not (vx0 < b["x"] < vx1 and vy0 < b["y"] < vy1):
                continue
            spr = _bird(b["kind"], b["pose"] if b["state"] != "hop" else "stand", b["fl"])
            out.append((b["y"], _shadow(16), (b["x"] - 8 - cam.x, b["y"] - 2 - cam.y)))
            out.append((b["y"] + 0.1, spr, (b["x"] - spr.get_width() / 2 - cam.x,
                                            b["y"] - spr.get_height() - b["h"] - cam.y)))
        for f in self.frogs:
            if f["state"] == "hop":
                k = min(1.0, f["k"])
                x = f["x0"] + (f["x1"] - f["x0"]) * k
                y = f["y0"] + (f["y1"] - f["y0"]) * k
                h = math.sin(k * math.pi) * 12
                pose = "hop"
            else:
                x, y, h, pose = f["x"], f["y"], 0.0, "sit"
            if not (vx0 < x < vx1 and vy0 < y < vy1):
                continue
            spr = _frog(pose, f["fl"])
            out.append((y, _shadow(16), (x - 8 - cam.x, y - 3 - cam.y)))
            out.append((y + 0.1, spr, (x - spr.get_width() / 2 - cam.x,
                                       y - spr.get_height() - h - cam.y)))
        for r in self.rabbits:
            if r["state"] == "hop":
                k = min(1.0, r["k"])
                x = r["x0"] + (r["x1"] - r["x0"]) * k
                y = r["y0"] + (r["y1"] - r["y0"]) * k
                h = math.sin(k * math.pi) * (10 if r["left"] else 6)
                pose = "hop"
            else:
                x, y, h = r["x"], r["y"], 0.0
                pose = "sit"
            if not (vx0 < x < vx1 and vy0 < y < vy1):
                continue
            spr = _rabbit(r["white"], pose, r["fl"])
            out.append((y, _shadow(16), (x - 8 - cam.x, y - 3 - cam.y)))
            out.append((y + 0.1, spr, (x - spr.get_width() / 2 - cam.x, y - spr.get_height() - h - cam.y)))
        for d in self.dfly:
            if not (vx0 < d["x"] < vx1 and vy0 < d["y"] < vy1):
                continue
            spr = _dragonfly(d["ci"], int(self.t * 30) % 2, d["fl"])
            out.append((d["y"], _shadow(6), (d["x"] - 3 - cam.x, d["y"] - cam.y)))
            out.append((d["y"] + 0.1, spr, (d["x"] - spr.get_width() / 2 - cam.x,
                                            d["y"] - d["h"] - spr.get_height() / 2 - cam.y)))
        for d in self.ducks:
            if not (vx0 < d["x"] < vx1 and vy0 < d["y"] < vy1):
                continue
            fl = 1 if math.cos(d["a"]) >= 0 else -1
            spr = _duck(d["kind"], "dip" if d["dip"] > 0 else "swim", fl)
            bob = math.sin(self.t * 2.2 + d["ph"]) * 1.2
            out.append((d["y"] - _TILE * 0.5, spr, (d["x"] - spr.get_width() / 2 - cam.x,
                                                     d["y"] - spr.get_height() + 6 + bob - cam.y)))
        for j in self.jumps:
            k = j["k"]
            x = j["x"] + j["dx"] * k
            y = j["y"] - math.sin(k * math.pi) * j["hi"]
            ang = -1 if k < 0.35 else (1 if k > 0.65 else 0)
            spr = _jumpfish(ang, j["fl"])
            out.append((j["y"] - _TILE, spr,
                        (x - spr.get_width() / 2 - cam.x, y - spr.get_height() / 2 - cam.y)))
        return out

    def draw_above(self, screen, cam):
        """Airborne things drawn over trees and roofs: flying birds."""
        for b in self.birds:
            if b["state"] in ("fly", "land") and b["h"] > 8:
                spr = _bird(b["kind"], b["pose"], b["fl"])
                screen.blit(spr, (int(b["x"] - spr.get_width() / 2 - cam.x),
                                  int(b["y"] - spr.get_height() - b["h"] - cam.y)))

    def draw_fireflies(self, screen, cam, top=0, bottom=_SH, fade=1.0):
        """Fireflies glow OVER the night grading (called from a _draw_hud_ hook),
        so they twinkle brightly in the dark instead of being tinted away.
        ``top``/``bottom`` keep them off the HUD bars."""
        if not self.ff or fade <= 0.05:
            return
        for f in self.ff:
            lv = self._ff_level(f)
            if fade < 1.0:
                lv = int(lv * fade)
            if not lv:
                continue
            sx, sy = int(f["x"] - cam.x), int(f["y"] - f["h"] - cam.y)
            if top < sy < bottom and -12 < sx < _SW + 12:
                screen.blit(_firefly(lv), (sx - 11, sy - 11))

    def lights(self):
        """Firefly glows for the _lights_* hook (only the brightly-lit ones)."""
        out = []
        for f in self.ff:
            if self._ff_level(f) >= 3:
                out.append((f["x"], f["y"] - f["h"], 32, (190, 240, 120)))
        return out
