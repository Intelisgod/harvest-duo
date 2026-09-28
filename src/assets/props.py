"""Interaction & decorative props: beds/bins/stalls/signposts, the full temple
set (Buddha, chedi, naga, etc.), farm decor and coop barn fittings.

Owner: shared by "World, Areas & Build" (placement) and "Temple/Farm" content
chats. To add a new prop: write a ``*_sprite()`` here and register it in the
``prop_sprite`` dispatcher at the bottom (the one shared seam in this file).
"""
import math
import pygame
from ..settings import TILE
from ._base import _cache, _surf, _dk, _lt, _shade


def bed_sprite():
    if "bed" in _cache:
        return _cache["bed"]
    s = _surf()
    pygame.draw.rect(s, (110, 74, 50), (5, 8, TILE - 10, TILE - 14), border_radius=5)
    pygame.draw.rect(s, (238, 238, 246), (8, 11, TILE - 16, 13), border_radius=3)  # pillow
    pygame.draw.rect(s, (196, 78, 88), (8, 24, TILE - 16, TILE - 34), border_radius=3)  # blanket
    pygame.draw.rect(s, (170, 60, 70), (8, 30, TILE - 16, 4))                          # fold
    _cache["bed"] = s
    return s


def bin_sprite():
    if "bin" in _cache:
        return _cache["bin"]
    s = _surf()
    pygame.draw.rect(s, (104, 72, 44), (7, 17, TILE - 14, TILE - 24), border_radius=4)
    pygame.draw.rect(s, (140, 98, 58), (5, 11, TILE - 10, 9), border_radius=3)   # open lid
    pygame.draw.line(s, (78, 54, 34), (TILE // 2, 21), (TILE // 2, TILE - 9), 2)
    pygame.draw.circle(s, (240, 205, 80), (TILE // 2, 13), 5)                    # coin hint
    pygame.draw.circle(s, (180, 150, 50), (TILE // 2, 13), 5, 1)
    _cache["bin"] = s
    return s


def stall_sprite():
    if "stall" in _cache:
        return _cache["stall"]
    h = TILE + 18
    s = _surf((TILE, h))
    pygame.draw.rect(s, (110, 80, 55), (5, 14, 5, h - 18))          # posts
    pygame.draw.rect(s, (110, 80, 55), (TILE - 10, 14, 5, h - 18))
    pygame.draw.rect(s, (150, 110, 72), (2, h - 18, TILE - 4, 16), border_radius=3)  # counter
    pygame.draw.rect(s, (190, 150, 95), (4, h - 16, TILE - 8, 6))                    # goods
    for i in range(0, TILE - 4, 12):                                # striped awning
        c = (208, 70, 70) if (i // 12) % 2 == 0 else (236, 236, 236)
        pygame.draw.rect(s, c, (2 + i, 2, 12, 16))
    pygame.draw.polygon(s, (150, 40, 40), [(2, 18), (TILE - 2, 18), (TILE - 6, 22), (6, 22)])
    _cache["stall"] = s
    return s


def signpost_sprite():
    if "sign" in _cache:
        return _cache["sign"]
    s = _surf()
    pygame.draw.rect(s, (120, 85, 55), (TILE // 2 - 3, 18, 6, TILE - 20))   # post
    pygame.draw.rect(s, (168, 126, 82), (5, 10, TILE - 10, 18), border_radius=3)  # board
    pygame.draw.rect(s, (110, 80, 52), (5, 10, TILE - 10, 18), 2, border_radius=3)
    _cache["sign"] = s
    return s


def buddha_sprite():
    if "buddha" in _cache:
        return _cache["buddha"]
    s = _surf((TILE, TILE * 2))
    ox, oy = TILE // 2, TILE * 2
    gold, gdk, glt = (228, 190, 96), (188, 150, 64), (244, 222, 150)
    # lotus pedestal
    pygame.draw.rect(s, (170, 120, 150), (6, oy - 16, TILE - 12, 12), border_radius=4)
    for i in range(5):
        pygame.draw.polygon(s, (206, 150, 180),
                            [(8 + i * 8, oy - 6), (12 + i * 8, oy - 16), (16 + i * 8, oy - 6)])
    # crossed-legs base
    pygame.draw.ellipse(s, gold, (8, oy - 34, TILE - 16, 22))
    pygame.draw.ellipse(s, gdk, (8, oy - 34, TILE - 16, 22), 2)
    # body / robe
    pygame.draw.polygon(s, gold, [(ox - 12, oy - 28), (ox + 12, oy - 28),
                                  (ox + 9, oy - 54), (ox - 9, oy - 54)])
    pygame.draw.polygon(s, gdk, [(ox - 12, oy - 28), (ox + 12, oy - 28),
                                 (ox + 9, oy - 54), (ox - 9, oy - 54)], 1)
    pygame.draw.line(s, gdk, (ox, oy - 52), (ox - 7, oy - 30), 1)         # robe fold
    # head + ushnisha (top knot) + halo
    pygame.draw.circle(s, glt, (ox, oy - 64), 18)                          # halo glow
    pygame.draw.circle(s, gold, (ox, oy - 60), 9)
    pygame.draw.circle(s, gdk, (ox, oy - 60), 9, 1)
    pygame.draw.circle(s, gold, (ox, oy - 71), 3)                          # flame finial
    pygame.draw.circle(s, (120, 86, 60), (ox - 3, oy - 61), 1)            # eyes (serene)
    pygame.draw.circle(s, (120, 86, 60), (ox + 3, oy - 61), 1)
    _cache["buddha"] = s
    return s


def incense_sprite():
    if "incense" in _cache:
        return _cache["incense"]
    s = _surf()
    pygame.draw.rect(s, (160, 96, 70), (TILE // 2 - 8, TILE - 16, 16, 10), border_radius=3)  # pot
    pygame.draw.ellipse(s, (120, 70, 50), (TILE // 2 - 8, TILE - 18, 16, 6))
    for dx in (-4, 0, 4):                                                  # sticks
        pygame.draw.line(s, (120, 80, 60), (TILE // 2 + dx, TILE - 14), (TILE // 2 + dx, TILE - 30), 1)
        pygame.draw.circle(s, (240, 120, 60), (TILE // 2 + dx, TILE - 30), 1)
    _cache["incense"] = s
    return s


def candle_sprite():
    if "candle" in _cache:
        return _cache["candle"]
    s = _surf()
    pygame.draw.rect(s, (240, 232, 210), (TILE // 2 - 4, TILE - 24, 8, 18), border_radius=2)  # candle
    pygame.draw.rect(s, (210, 200, 178), (TILE // 2 - 6, TILE - 8, 12, 5), border_radius=2)   # holder
    pygame.draw.polygon(s, (250, 200, 90), [(TILE // 2, TILE - 32), (TILE // 2 - 3, TILE - 25),
                                            (TILE // 2 + 3, TILE - 25)])                       # flame
    pygame.draw.polygon(s, (250, 240, 180), [(TILE // 2, TILE - 29), (TILE // 2 - 1, TILE - 25),
                                             (TILE // 2 + 1, TILE - 25)])
    _cache["candle"] = s
    return s


def lotus_sprite():
    if "lotus" in _cache:
        return _cache["lotus"]
    s = _surf()
    cx, cy = TILE // 2, TILE - 12
    pygame.draw.ellipse(s, (120, 170, 150), (cx - 12, cy + 2, 24, 8))      # leaf pad
    for ang in range(0, 360, 45):
        a = math.radians(ang)
        pygame.draw.polygon(s, (244, 180, 200),
                            [(cx, cy), (cx + math.cos(a) * 5 - 3, cy - 10 + math.sin(a) * 2),
                             (cx + math.cos(a) * 5 + 3, cy - 10 + math.sin(a) * 2)])
    pygame.draw.circle(s, (250, 220, 180), (cx, cy - 4), 3)                # bright centre
    _cache["lotus"] = s
    return s


def bell_sprite():
    if "bell" in _cache:
        return _cache["bell"]
    s = _surf()
    cx = TILE // 2
    pygame.draw.rect(s, (120, 90, 60), (cx - 14, TILE - 36, 28, 4))        # frame beam
    pygame.draw.rect(s, (120, 90, 60), (cx - 12, TILE - 36, 3, 8))
    pygame.draw.rect(s, (120, 90, 60), (cx + 9, TILE - 36, 3, 8))
    pygame.draw.polygon(s, (196, 150, 70), [(cx - 9, TILE - 12), (cx + 9, TILE - 12),
                                            (cx + 7, TILE - 28), (cx - 7, TILE - 28)])  # bell body
    pygame.draw.ellipse(s, (170, 126, 56), (cx - 9, TILE - 14, 18, 6))
    pygame.draw.circle(s, (150, 110, 50), (cx, TILE - 28), 3)              # crown
    _cache["bell"] = s
    return s


def temple_gate_sprite():
    if "temple_gate" in _cache:
        return _cache["temple_gate"]
    s = _surf((TILE, TILE + 16))
    h = TILE + 16
    red, rdk, gold = (190, 74, 62), (150, 52, 44), (224, 168, 78)
    pygame.draw.rect(s, red, (6, 14, 6, h - 16))                           # pillars
    pygame.draw.rect(s, red, (TILE - 12, 14, 6, h - 16))
    pygame.draw.rect(s, gold, (2, 8, TILE - 4, 8), border_radius=2)        # lintel
    pygame.draw.polygon(s, red, [(0, 8), (TILE, 8), (TILE - 6, 0), (6, 0)])  # upturned roof
    pygame.draw.polygon(s, rdk, [(0, 8), (TILE, 8), (TILE - 6, 0), (6, 0)], 1)
    _cache["temple_gate"] = s
    return s


def donation_box_sprite():
    if "donation_box" in _cache:
        return _cache["donation_box"]
    s = _surf()
    wood, wdk, gold = (150, 104, 60), (110, 76, 44), (240, 205, 90)
    pygame.draw.rect(s, wood, (8, TILE - 26, TILE - 16, 20), border_radius=3)     # box body
    pygame.draw.rect(s, wdk, (8, TILE - 26, TILE - 16, 20), 2, border_radius=3)
    pygame.draw.rect(s, wdk, (TILE // 2 - 7, TILE - 23, 14, 3), border_radius=1)   # coin slot
    pygame.draw.line(s, (90, 62, 36), (8, TILE - 16), (TILE - 8, TILE - 16), 1)    # plank seam
    pygame.draw.circle(s, gold, (TILE // 2, TILE - 30), 4)                          # coin going in
    pygame.draw.circle(s, (200, 160, 60), (TILE // 2, TILE - 30), 4, 1)
    pygame.draw.line(s, (210, 170, 70), (TILE // 2 - 6, TILE - 12), (TILE // 2 - 6, TILE - 9), 1)
    _cache["donation_box"] = s
    return s


def chedi_sprite():
    if "chedi" in _cache:
        return _cache["chedi"]
    s = _surf((TILE, TILE * 2)); cx, oy = TILE // 2, TILE * 2
    gold, gdk, glt = (236, 198, 96), (196, 158, 64), (250, 228, 150)
    pygame.draw.rect(s, gold, (cx - 16, oy - 16, 32, 14), border_radius=2)        # square base
    pygame.draw.rect(s, gdk, (cx - 16, oy - 16, 32, 14), 1, border_radius=2)
    pygame.draw.rect(s, gold, (cx - 12, oy - 26, 24, 12), border_radius=2)        # 2nd tier
    pygame.draw.polygon(s, glt, [(cx - 13, oy - 26), (cx + 13, oy - 26),          # bell dome
                                 (cx + 8, oy - 46), (cx - 8, oy - 46)])
    pygame.draw.polygon(s, gdk, [(cx - 13, oy - 26), (cx + 13, oy - 26),
                                 (cx + 8, oy - 46), (cx - 8, oy - 46)], 1)
    for i, rr in enumerate((7, 5, 3)):                                            # spire rings
        pygame.draw.circle(s, gold, (cx, oy - 48 - i * 6), rr)
    pygame.draw.line(s, glt, (cx, oy - 66), (cx, oy - 78), 2)                     # finial
    pygame.draw.circle(s, (255, 244, 196), (cx, oy - 79), 2)
    _cache["chedi"] = s
    return s


def naga_sprite():
    if "naga" in _cache:
        return _cache["naga"]
    s = _surf()
    green, gdk, gold = (96, 168, 120), (60, 120, 84), (226, 190, 96)
    pts = [(6, TILE - 6), (10, TILE - 18), (20, TILE - 22), (24, TILE - 12)]      # arching body
    pygame.draw.lines(s, green, False, pts, 5)
    pygame.draw.lines(s, gdk, False, pts, 1)
    head = (28, TILE - 12)                                                        # raised head
    pygame.draw.circle(s, green, head, 6)
    pygame.draw.circle(s, gdk, head, 6, 1)
    pygame.draw.polygon(s, gold, [(head[0] + 2, head[1] - 6), (head[0] + 7, head[1] - 12),
                                  (head[0] + 4, head[1] - 4)])                    # crest
    pygame.draw.circle(s, (40, 30, 30), (head[0] + 2, head[1] - 1), 1)           # eye
    pygame.draw.line(s, (210, 80, 80), (head[0] + 5, head[1] + 2), (head[0] + 9, head[1] + 3), 1)
    _cache["naga"] = s
    return s


def tung_sprite():
    if "tung" in _cache:
        return _cache["tung"]
    s = _surf((TILE, TILE + 20)); cx = TILE // 2
    pygame.draw.rect(s, (120, 90, 60), (cx - 14, 2, 28, 3))                        # cross bar
    for dx, col in ((-8, (208, 92, 96)), (0, (236, 206, 110)), (8, (96, 150, 200))):
        x = cx + dx
        for k in range(5):                                                        # tasselled banner
            yy = 6 + k * 11
            w = 7 - k
            pygame.draw.rect(s, col, (x - w // 2, yy, w, 9))
            pygame.draw.rect(s, _dk(col, 0.7), (x - w // 2, yy, w, 9), 1)
        pygame.draw.line(s, _dk(col, 0.7), (x, 61), (x, 67), 1)
    _cache["tung"] = s
    return s


def bodhi_sprite():
    if "bodhi" in _cache:
        return _cache["bodhi"]
    s = _surf((TILE, TILE * 2)); cx, oy = TILE // 2, TILE * 2
    pygame.draw.rect(s, (120, 92, 64), (cx - 4, oy - 30, 8, 28))                   # trunk
    pygame.draw.line(s, (100, 76, 52), (cx, oy - 24), (cx - 10, oy - 34), 2)
    pygame.draw.line(s, (100, 76, 52), (cx, oy - 24), (cx + 10, oy - 34), 2)
    for dx, dy, r in ((0, -44, 18), (-13, -36, 12), (13, -36, 12), (0, -30, 13)):  # heart-leaf canopy
        pygame.draw.circle(s, (86, 162, 96), (cx + dx, oy + dy), r)
    for dx, dy, r in ((-6, -48, 7), (8, -44, 7), (0, -52, 6)):
        pygame.draw.circle(s, (120, 196, 120), (cx + dx, oy + dy), r)
    _cache["bodhi"] = s
    return s


def chatra_sprite():
    if "chatra" in _cache:
        return _cache["chatra"]
    s = _surf((TILE, TILE + 24)); cx = TILE // 2
    gold, gdk = (236, 200, 96), (196, 158, 64)
    pygame.draw.line(s, (150, 120, 70), (cx, 18), (cx, TILE + 22), 2)              # pole
    for i, (yy, w) in enumerate(((20, 9), (28, 13), (37, 17))):                    # tiered canopy
        pygame.draw.polygon(s, gold, [(cx - w, yy + 6), (cx + w, yy + 6), (cx, yy - 4)])
        pygame.draw.polygon(s, gdk, [(cx - w, yy + 6), (cx + w, yy + 6), (cx, yy - 4)], 1)
    pygame.draw.circle(s, (250, 228, 150), (cx, 14), 2)                            # finial
    _cache["chatra"] = s
    return s


def offering_bowl_sprite():
    if "offering_bowl" in _cache:
        return _cache["offering_bowl"]
    s = _surf(); cx = TILE // 2
    pygame.draw.rect(s, (180, 140, 80), (cx - 6, TILE - 10, 12, 5), border_radius=2)   # pedestal
    pygame.draw.ellipse(s, (210, 178, 110), (cx - 10, TILE - 22, 20, 14))             # gold bowl
    pygame.draw.ellipse(s, (170, 136, 70), (cx - 10, TILE - 22, 20, 14), 1)
    pygame.draw.circle(s, (228, 96, 110), (cx - 3, TILE - 17), 3)                      # fruit
    pygame.draw.circle(s, (236, 196, 96), (cx + 3, TILE - 16), 3)
    pygame.draw.circle(s, (150, 196, 120), (cx, TILE - 20), 2)
    _cache["offering_bowl"] = s
    return s


def collector_sprite():
    if "collector" in _cache:
        return _cache["collector"]
    s = _surf((TILE, TILE + 10)); cx = TILE // 2; oy = TILE + 10
    body, dk, steel = (150, 156, 168), (104, 110, 124), (196, 202, 214)
    pygame.draw.polygon(s, steel, [(8, oy - 30), (TILE - 8, oy - 30),                  # funnel hopper
                                   (TILE - 16, oy - 16), (16, oy - 16)])
    pygame.draw.polygon(s, dk, [(8, oy - 30), (TILE - 8, oy - 30),
                                (TILE - 16, oy - 16), (16, oy - 16)], 1)
    pygame.draw.rect(s, body, (14, oy - 18, TILE - 28, 14), border_radius=2)           # collection box
    pygame.draw.rect(s, dk, (14, oy - 18, TILE - 28, 14), 1, border_radius=2)
    pygame.draw.circle(s, (250, 246, 232), (cx - 4, oy - 11), 3)                       # egg
    pygame.draw.rect(s, (244, 246, 250), (cx + 2, oy - 14, 5, 8), border_radius=1)     # milk
    pygame.draw.rect(s, (120, 170, 215), (cx + 2, oy - 14, 5, 3), border_radius=1)
    pygame.draw.rect(s, (210, 170, 70), (cx - 10, oy - 34, 20, 5), border_radius=2)    # gold rim chute
    _cache["collector"] = s
    return s


def scarecrow_sprite():
    if "scarecrow" in _cache:
        return _cache["scarecrow"]
    s = _surf((TILE, TILE + 16)); cx = TILE // 2; oy = TILE + 16
    pygame.draw.rect(s, (140, 100, 62), (cx - 2, oy - 40, 4, 38))                      # post
    pygame.draw.rect(s, (140, 100, 62), (cx - 14, oy - 30, 28, 4))                     # arms
    pygame.draw.rect(s, (180, 120, 80), (cx - 9, oy - 30, 18, 14), border_radius=3)    # shirt
    pygame.draw.circle(s, (224, 190, 120), (cx, oy - 36), 7)                           # straw head
    for a in range(0, 360, 45):
        rad = math.radians(a)
        pygame.draw.line(s, (210, 178, 96), (cx, oy - 36),
                         (cx + int(math.cos(rad) * 9), oy - 36 + int(math.sin(rad) * 9)), 1)
    pygame.draw.polygon(s, (150, 110, 70), [(cx - 9, oy - 40), (cx + 9, oy - 40), (cx, oy - 48)])  # hat
    pygame.draw.circle(s, (40, 32, 28), (cx - 3, oy - 37), 1)
    pygame.draw.circle(s, (40, 32, 28), (cx + 3, oy - 37), 1)
    _cache["scarecrow"] = s
    return s


def flowerbed_sprite():
    if "flowerbed" in _cache:
        return _cache["flowerbed"]
    s = _surf()
    pygame.draw.rect(s, (150, 110, 72), (4, TILE - 18, TILE - 8, 14), border_radius=3)  # soil bed
    pygame.draw.rect(s, (118, 84, 54), (4, TILE - 18, TILE - 8, 14), 1, border_radius=3)
    cols = [(238, 120, 140), (244, 206, 96), (170, 140, 224), (236, 150, 200)]
    spots = [(11, TILE - 14), (20, TILE - 9), (29, TILE - 14), (37, TILE - 10), (15, TILE - 6)]
    for i, (fx, fy) in enumerate(spots):
        c = cols[i % len(cols)]
        for a in range(0, 360, 72):
            rad = math.radians(a)
            pygame.draw.circle(s, c, (fx + int(math.cos(rad) * 2), fy + int(math.sin(rad) * 2)), 2)
        pygame.draw.circle(s, (255, 244, 200), (fx, fy), 1)
    _cache["flowerbed"] = s
    return s


def windmill_sprite():
    if "windmill" in _cache:
        return _cache["windmill"]
    s = _surf((TILE, TILE * 2)); cx, oy = TILE // 2, TILE * 2
    pygame.draw.polygon(s, (208, 196, 170), [(cx - 9, oy - 4), (cx + 9, oy - 4),        # tapered tower
                                             (cx + 6, oy - 40), (cx - 6, oy - 40)])
    pygame.draw.polygon(s, (150, 138, 116), [(cx - 9, oy - 4), (cx + 9, oy - 4),
                                             (cx + 6, oy - 40), (cx - 6, oy - 40)], 1)
    pygame.draw.polygon(s, (150, 80, 70), [(cx - 8, oy - 40), (cx + 8, oy - 40), (cx, oy - 50)])  # cap
    hub = (cx, oy - 42)
    for a in (0, 90, 180, 270):                                                        # 4 sail blades
        rad = math.radians(a)
        ex, ey = cx + int(math.cos(rad) * 16), (oy - 42) + int(math.sin(rad) * 16)
        pygame.draw.line(s, (120, 92, 64), hub, (ex, ey), 2)
        px, py = int(math.cos(rad + 1.57) * 4), int(math.sin(rad + 1.57) * 4)
        pygame.draw.polygon(s, (236, 232, 220), [hub, (ex, ey), (ex + px, ey + py)])
    pygame.draw.circle(s, (90, 70, 50), hub, 2)
    _cache["windmill"] = s
    return s


def phra_pratan_sprite():
    """Large principal Buddha (phra pratan) on a tiered altar -- 3 tiles wide."""
    if "phra_pratan" in _cache:
        return _cache["phra_pratan"]
    W = TILE * 3
    # surface is 4 tiles tall so the head, halo and flame finial have headroom and
    # are never clipped at the top edge (figure is bottom-anchored to oy)
    s = _surf((W, TILE * 4)); cx, oy = W // 2, TILE * 4
    gold, gdk, glt = (232, 196, 104), (190, 156, 70), (248, 228, 156)
    stone, stone2 = (210, 198, 172), (226, 214, 188)
    # tiered altar dais
    pygame.draw.rect(s, stone, (16, oy - 24, W - 32, 20), border_radius=3)
    pygame.draw.rect(s, gdk, (16, oy - 24, W - 32, 20), 1, border_radius=3)
    pygame.draw.rect(s, stone2, (30, oy - 40, W - 60, 18), border_radius=3)
    # lotus throne
    pygame.draw.rect(s, gold, (40, oy - 56, W - 80, 18), border_radius=4)
    for i in range(7):
        px = 44 + i * ((W - 88) // 6)
        pygame.draw.polygon(s, glt, [(px, oy - 40), (px + 6, oy - 56), (px + 12, oy - 40)])
    # crossed legs / lap
    pygame.draw.ellipse(s, gold, (cx - 38, oy - 76, 76, 30))
    pygame.draw.ellipse(s, gdk, (cx - 38, oy - 76, 76, 30), 1)
    pygame.draw.line(s, gdk, (cx, oy - 70), (cx, oy - 52), 1)
    # hands resting in lap (meditation mudra)
    pygame.draw.ellipse(s, glt, (cx - 14, oy - 70, 28, 12))
    # robed body
    pygame.draw.polygon(s, gold, [(cx - 30, oy - 70), (cx + 30, oy - 70),
                                  (cx + 20, oy - 118), (cx - 20, oy - 118)])
    pygame.draw.polygon(s, gdk, [(cx - 30, oy - 70), (cx + 30, oy - 70),
                                 (cx + 20, oy - 118), (cx - 20, oy - 118)], 1)
    pygame.draw.line(s, gdk, (cx - 16, oy - 110), (cx - 24, oy - 74), 1)   # robe sash
    pygame.draw.line(s, gdk, (cx + 6, oy - 116), (cx + 18, oy - 74), 1)
    # halo, head + ushnisha + flame finial
    pygame.draw.circle(s, glt, (cx, oy - 132), 30)
    pygame.draw.circle(s, gdk, (cx, oy - 132), 30, 1)
    pygame.draw.circle(s, gold, (cx, oy - 128), 17)
    pygame.draw.circle(s, gdk, (cx, oy - 128), 17, 1)
    pygame.draw.circle(s, gold, (cx, oy - 146), 6)                          # top knot
    pygame.draw.polygon(s, glt, [(cx, oy - 160), (cx - 3, oy - 150), (cx + 3, oy - 150)])  # flame
    pygame.draw.circle(s, (120, 90, 60), (cx - 6, oy - 130), 1)             # serene eyes
    pygame.draw.circle(s, (120, 90, 60), (cx + 6, oy - 130), 1)
    pygame.draw.arc(s, (150, 110, 80), (cx - 7, oy - 126, 14, 8), 3.4, 6.0, 1)  # gentle smile
    _cache["phra_pratan"] = s
    return s


def pillar_sprite():
    """Lacquered temple column with a gold base and capital."""
    if "pillar" in _cache:
        return _cache["pillar"]
    s = _surf((TILE, TILE * 2)); cx, oy = TILE // 2, TILE * 2
    red, rdk, gold = (176, 64, 56), (132, 46, 40), (224, 180, 86)
    pygame.draw.rect(s, gold, (cx - 11, oy - 8, 22, 8), border_radius=2)        # base
    pygame.draw.rect(s, red, (cx - 8, oy - 64, 16, 58), border_radius=2)        # shaft
    pygame.draw.rect(s, rdk, (cx - 8, oy - 64, 16, 58), 1, border_radius=2)
    pygame.draw.line(s, rdk, (cx, oy - 60), (cx, oy - 10), 1)
    pygame.draw.rect(s, gold, (cx - 12, oy - 72, 24, 10), border_radius=2)      # capital
    pygame.draw.polygon(s, gold, [(cx - 12, oy - 72), (cx + 12, oy - 72),       # kanok flare
                                  (cx + 7, oy - 82), (cx - 7, oy - 82)])
    pygame.draw.polygon(s, _dk(gold, 0.8), [(cx - 12, oy - 72), (cx + 12, oy - 72),
                                            (cx + 7, oy - 82), (cx - 7, oy - 82)], 1)
    _cache["pillar"] = s
    return s


def haybale_sprite():
    if "haybale" in _cache:
        return _cache["haybale"]
    s = _surf(); straw, sdk = (226, 196, 110), (196, 162, 78)
    pygame.draw.rect(s, straw, (6, TILE - 26, TILE - 12, 22), border_radius=5)
    pygame.draw.rect(s, sdk, (6, TILE - 26, TILE - 12, 22), 1, border_radius=5)
    for bx in (16, TILE - 18):                                                  # binding twine
        pygame.draw.line(s, sdk, (bx, TILE - 25), (bx, TILE - 5), 2)
    for hx in range(10, TILE - 10, 6):                                          # straw texture
        pygame.draw.line(s, (236, 214, 140), (hx, TILE - 22), (hx + 2, TILE - 9), 1)
    _cache["haybale"] = s
    return s


def trough_sprite():
    if "trough" in _cache:
        return _cache["trough"]
    s = _surf(); wood, wdk = (150, 110, 70), (112, 80, 50)
    pygame.draw.rect(s, wood, (5, TILE - 18, TILE - 10, 12), border_radius=2)
    pygame.draw.rect(s, wdk, (5, TILE - 18, TILE - 10, 12), 2, border_radius=2)
    pygame.draw.rect(s, (120, 184, 214), (9, TILE - 16, TILE - 18, 5), border_radius=1)  # water
    pygame.draw.line(s, (170, 214, 232), (12, TILE - 14), (TILE - 14, TILE - 14), 1)
    _cache["trough"] = s
    return s


# --------------------------------------------------------------------------
# Beach decor (World/Chat 5).  Reference: classic top-down beach scenes -- palms,
# striped parasol, sandcastle, starfish, scallop shells, driftwood, beach ball,
# message-in-a-bottle, surfboard and a little crab.
# --------------------------------------------------------------------------

def palm_sprite():
    """A leaning coconut palm: curved trunk, a crown of fronds and coconuts.
    Two tiles tall so it rises above the player (bottom-anchored when drawn)."""
    if "palm" in _cache:
        return _cache["palm"]
    s = _surf((TILE, TILE * 2))
    cx = TILE // 2
    trunk, trunk_d = (168, 128, 84), (132, 96, 60)
    # gently curved trunk built from short segments (base -> crown)
    seg = [(cx - 5, TILE * 2 - 2), (cx - 4, TILE + 22), (cx - 1, TILE + 6),
           (cx + 4, TILE - 4), (cx + 8, TILE - 12)]
    for i in range(len(seg) - 1):
        pygame.draw.line(s, trunk, seg[i], seg[i + 1], 7)
    for i in range(len(seg) - 1):
        pygame.draw.line(s, trunk_d, seg[i], seg[i + 1], 2)
    for i in range(len(seg) - 1):                       # ring texture up the trunk
        mx = (seg[i][0] + seg[i + 1][0]) // 2
        my = (seg[i][1] + seg[i + 1][1]) // 2
        pygame.draw.line(s, trunk_d, (mx - 3, my), (mx + 3, my), 1)
    crown = (cx + 8, TILE - 12)
    # coconuts clustered under the crown
    for dx, dy in ((-4, 2), (3, 4), (-1, 6)):
        pygame.draw.circle(s, (122, 86, 54), (crown[0] + dx, crown[1] + dy), 3)
        pygame.draw.circle(s, (150, 112, 72), (crown[0] + dx - 1, crown[1] + dy - 1), 1)
    # fronds radiating from the crown, drooping at the tips
    g, gd, gl = (78, 168, 96), (54, 132, 74), (120, 200, 120)
    fronds = [(-22, -10, -30, 4), (-12, -16, -16, -2), (2, -18, 4, -4),
              (16, -14, 26, -2), (22, -4, 32, 10), (-20, 2, -28, 16), (10, 4, 18, 18)]
    for ex, ey, tx, ty in fronds:
        mid = (crown[0] + ex, crown[1] + ey)
        tip = (crown[0] + tx, crown[1] + ty)
        pygame.draw.line(s, gd, crown, mid, 5)
        pygame.draw.line(s, g, crown, mid, 3)
        pygame.draw.line(s, g, mid, tip, 3)
        pygame.draw.line(s, gl, crown, mid, 1)
    pygame.draw.circle(s, (60, 120, 70), crown, 4)      # crown knot
    _cache["palm"] = s
    return s


def parasol_sprite():
    """A striped beach umbrella on a pole."""
    if "parasol" in _cache:
        return _cache["parasol"]
    h = TILE + 26
    s = _surf((TILE, h))
    cx = TILE // 2
    pygame.draw.line(s, (220, 220, 228), (cx, 14), (cx + 4, h - 4), 3)   # pole
    pygame.draw.line(s, (150, 150, 160), (cx, 14), (cx + 4, h - 4), 1)
    red, white = (228, 86, 84), (244, 244, 248)
    # canopy: alternating wedges of a shallow dome
    cyx, cyy, rad = cx, 16, TILE // 2 + 4
    wedges = 8
    for i in range(wedges):
        a0 = math.pi + i * math.pi / wedges
        a1 = math.pi + (i + 1) * math.pi / wedges
        col = red if i % 2 == 0 else white
        p0 = (cyx + rad * math.cos(a0), cyy + rad * math.sin(a0) * 0.55 + rad * 0.0)
        p1 = (cyx + rad * math.cos(a1), cyy + rad * math.sin(a1) * 0.55)
        pygame.draw.polygon(s, col, [(cyx, cyy), (p0[0], cyy - 2 - (rad - abs(cyx - p0[0])) * 0.2), (p1[0], cyy - 2 - (rad - abs(cyx - p1[0])) * 0.2)])
    pygame.draw.arc(s, (170, 60, 60), (cyx - rad, cyy - rad, rad * 2, rad), math.pi, 2 * math.pi, 2)
    pygame.draw.circle(s, (250, 230, 140), (cyx, cyy), 3)               # finial
    _cache["parasol"] = s
    return s


def sandcastle_sprite():
    """A little sandcastle with battlements and a pennant."""
    if "sandcastle" in _cache:
        return _cache["sandcastle"]
    s = _surf()
    sand, sdk, sl = (224, 198, 142), (196, 168, 112), (240, 220, 170)
    base_y = TILE - 6
    pygame.draw.rect(s, sand, (8, base_y - 14, TILE - 16, 14))           # main keep
    pygame.draw.rect(s, sdk, (8, base_y - 14, TILE - 16, 14), 1)
    for tx in (6, 6 + (TILE - 24)):                                      # corner towers
        pygame.draw.rect(s, sand, (tx, base_y - 22, 12, 22))
        pygame.draw.rect(s, sdk, (tx, base_y - 22, 12, 22), 1)
        for cxx in (tx, tx + 7):                                         # crenellations
            pygame.draw.rect(s, sand, (cxx, base_y - 26, 5, 5))
    pygame.draw.rect(s, _dk(sand, 0.78), (TILE // 2 - 4, base_y - 9, 8, 9))  # gate arch
    pygame.draw.line(s, (150, 120, 80), (TILE // 2, base_y - 30), (TILE // 2, base_y - 22), 1)  # flagpole
    pygame.draw.polygon(s, (228, 86, 84), [(TILE // 2, base_y - 30), (TILE // 2 + 8, base_y - 28), (TILE // 2, base_y - 26)])
    pygame.draw.line(s, sl, (10, base_y - 12), (TILE - 12, base_y - 12), 1)  # highlight
    _cache["sandcastle"] = s
    return s


def starfish_sprite():
    """A five-armed starfish resting on the sand."""
    if "starfish" in _cache:
        return _cache["starfish"]
    s = _surf()
    cx, cy, R, r = TILE // 2, TILE // 2 + 4, 13, 5
    orange, odk, dots = (240, 158, 96), (208, 120, 70), (255, 206, 150)
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    pygame.draw.polygon(s, orange, pts)
    pygame.draw.polygon(s, odk, pts, 1)
    for i in range(0, 10, 2):                                            # arm spots
        ang = -math.pi / 2 + i * math.pi / 5
        pygame.draw.circle(s, dots, (int(cx + (R - 4) * math.cos(ang)), int(cy + (R - 4) * math.sin(ang))), 1)
    pygame.draw.circle(s, dots, (cx, cy), 2)
    _cache["starfish"] = s
    return s


def seashell_sprite():
    """A ridged scallop shell."""
    if "seashell" in _cache:
        return _cache["seashell"]
    s = _surf()
    cx, by = TILE // 2, TILE // 2 + 8
    shell, sdk, sl = (246, 206, 206), (216, 158, 162), (255, 234, 234)
    pygame.draw.polygon(s, shell, [(cx, by), (cx - 13, by - 14), (cx - 8, by - 18),
                                   (cx, by - 20), (cx + 8, by - 18), (cx + 13, by - 14)])
    for dx in (-9, -4, 0, 4, 9):                                         # radiating ribs
        pygame.draw.line(s, sdk, (cx, by), (cx + dx, by - 17), 1)
    pygame.draw.polygon(s, sl, [(cx, by), (cx - 4, by - 17), (cx, by - 19)])
    pygame.draw.circle(s, sdk, (cx, by), 3)                              # hinge
    _cache["seashell"] = s
    return s


def driftwood_sprite():
    """A weathered, sun-bleached log washed up on the shore."""
    if "driftwood" in _cache:
        return _cache["driftwood"]
    s = _surf()
    y = TILE // 2 + 6
    wood, wdk, wl = (170, 156, 138), (138, 124, 108), (200, 188, 170)
    pygame.draw.rect(s, wood, (4, y - 6, TILE - 8, 12), border_radius=6)
    pygame.draw.rect(s, wdk, (4, y - 6, TILE - 8, 12), 1, border_radius=6)
    for gx in range(8, TILE - 10, 7):                                    # grain
        pygame.draw.line(s, wdk, (gx, y - 4), (gx + 4, y + 4), 1)
    pygame.draw.line(s, wl, (8, y - 3), (TILE - 12, y - 3), 1)
    pygame.draw.ellipse(s, _dk(wood, 0.82), (TILE - 13, y - 5, 8, 10))   # cut end rings
    pygame.draw.ellipse(s, wdk, (TILE - 13, y - 5, 8, 10), 1)
    pygame.draw.line(s, wood, (12, y - 5), (6, y - 12), 4)               # broken branch stub
    _cache["driftwood"] = s
    return s


def beach_ball_sprite():
    """A bright striped beach ball."""
    if "beach_ball" in _cache:
        return _cache["beach_ball"]
    s = _surf()
    cx, cy, r = TILE // 2, TILE // 2 + 4, 12
    pygame.draw.circle(s, (248, 248, 250), (cx, cy), r)
    cols = [(228, 86, 84), (244, 210, 90), (96, 168, 220), (120, 196, 130)]
    for i, col in enumerate(cols):                                       # coloured gores
        a0 = -math.pi / 2 + i * math.pi / 2
        a1 = -math.pi / 2 + (i + 1) * math.pi / 2
        pts = [(cx, cy)]
        steps = 6
        for k in range(steps + 1):
            a = a0 + (a1 - a0) * k / steps
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        if i % 2 == 0:
            pygame.draw.polygon(s, col, pts)
    pygame.draw.circle(s, (120, 130, 140), (cx, cy), r, 1)
    pygame.draw.circle(s, (255, 255, 255), (cx - 4, cy - 4), 3)          # gloss
    _cache["beach_ball"] = s
    return s


def message_bottle_sprite():
    """A corked glass bottle with a rolled note inside, lying on the sand."""
    if "message_bottle" in _cache:
        return _cache["message_bottle"]
    s = _surf()
    y = TILE // 2 + 6
    glass, gdk = (150, 200, 176, 230), (110, 162, 140)
    pygame.draw.rect(s, glass, (8, y - 7, TILE - 22, 14), border_radius=6)   # body
    pygame.draw.rect(s, gdk, (8, y - 7, TILE - 22, 14), 1, border_radius=6)
    pygame.draw.rect(s, glass, (TILE - 16, y - 4, 8, 8), border_radius=2)    # neck
    pygame.draw.rect(s, (176, 132, 84), (TILE - 9, y - 4, 5, 8), border_radius=2)  # cork
    pygame.draw.rect(s, (238, 226, 196), (14, y - 4, 12, 8), border_radius=2)  # rolled note
    pygame.draw.line(s, (200, 184, 150), (16, y), (24, y), 1)
    pygame.draw.line(s, (210, 240, 224), (11, y - 5), (11, y + 3), 1)        # glass shine
    _cache["message_bottle"] = s
    return s


def surfboard_sprite():
    """A surfboard stuck upright in the sand."""
    if "surfboard" in _cache:
        return _cache["surfboard"]
    h = TILE + 20
    s = _surf((TILE, h))
    cx = TILE // 2
    board, bdk = (248, 244, 250), (210, 206, 214)
    pts = [(cx, 4), (cx - 9, 28), (cx - 10, h - 18), (cx, h - 6),
           (cx + 10, h - 18), (cx + 9, 28)]
    pygame.draw.polygon(s, board, pts)
    pygame.draw.polygon(s, bdk, pts, 1)
    pygame.draw.line(s, (228, 86, 84), (cx, 8), (cx, h - 10), 3)          # centre stripe
    pygame.draw.line(s, (96, 168, 220), (cx - 5, 16), (cx - 5, h - 22), 2)
    pygame.draw.line(s, (96, 168, 220), (cx + 5, 16), (cx + 5, h - 22), 2)
    pygame.draw.circle(s, bdk, (cx, h - 12), 2)                            # leash plug
    _cache["surfboard"] = s
    return s


def crab_sprite():
    """A small red shore crab."""
    if "crab" in _cache:
        return _cache["crab"]
    s = _surf()
    cx, cy = TILE // 2, TILE // 2 + 5
    red, rdk = (224, 96, 84), (184, 66, 58)
    pygame.draw.ellipse(s, red, (cx - 11, cy - 6, 22, 12))                # shell
    pygame.draw.ellipse(s, rdk, (cx - 11, cy - 6, 22, 12), 1)
    for sx in (-1, 1):                                                    # legs
        for i, ly in enumerate((-2, 1, 4)):
            pygame.draw.line(s, rdk, (cx + sx * 9, cy + ly - 2),
                             (cx + sx * 15, cy + ly + 2 + i), 2)
    for sx in (-1, 1):                                                    # eyestalks
        pygame.draw.line(s, rdk, (cx + sx * 3, cy - 5), (cx + sx * 3, cy - 9), 1)
        pygame.draw.circle(s, (40, 40, 48), (cx + sx * 3, cy - 10), 2)
    for sx in (-1, 1):                                                    # claws
        pygame.draw.circle(s, red, (cx + sx * 14, cy - 4), 3)
        pygame.draw.circle(s, rdk, (cx + sx * 14, cy - 4), 3, 1)
    _cache["crab"] = s
    return s


def crab(facing=1):
    """A small *green* shore crab for the wandering beach critters.

    Core spawns these on ``area.crab_spawns`` tiles and moves them; this is the
    moving-critter art (the static decorative crab is ``crab_sprite``). The
    leading claw is drawn larger and ``facing`` (+1 right / -1 left) mirrors the
    sprite so a crab visibly turns around when it changes direction.
    """
    key = ("crab_walk", 1 if facing >= 0 else -1)
    if key in _cache:
        return _cache[key]
    s = _surf()
    cx, cy = TILE // 2, TILE // 2 + 5
    grn, gdk = (96, 184, 96), (60, 138, 66)
    pygame.draw.ellipse(s, grn, (cx - 11, cy - 6, 22, 12))                # shell
    pygame.draw.ellipse(s, gdk, (cx - 11, cy - 6, 22, 12), 1)
    pygame.draw.arc(s, gdk, (cx - 8, cy - 5, 16, 9), 3.4, 6.0, 1)         # shell ridge
    for sx in (-1, 1):                                                    # legs
        for i, ly in enumerate((-2, 1, 4)):
            pygame.draw.line(s, gdk, (cx + sx * 9, cy + ly - 2),
                             (cx + sx * 15, cy + ly + 2 + i), 2)
    for sx in (-1, 1):                                                    # eyestalks
        pygame.draw.line(s, gdk, (cx + sx * 3, cy - 5), (cx + sx * 3, cy - 9), 1)
        pygame.draw.circle(s, (40, 40, 48), (cx + sx * 3, cy - 10), 2)
    for sx in (-1, 1):                                                    # claws (lead bigger)
        r = 4 if sx > 0 else 3
        pygame.draw.circle(s, grn, (cx + sx * 14, cy - 4), r)
        pygame.draw.circle(s, gdk, (cx + sx * 14, cy - 4), r, 1)
        pygame.draw.line(s, gdk, (cx + sx * 14, cy - 4 - r),
                         (cx + sx * (14 + r), cy - 4), 1)                 # pincer notch
    if facing < 0:
        s = pygame.transform.flip(s, True, False)
    _cache[key] = s
    return s


def beach_towel_sprite():
    """A striped picnic towel laid flat on the sand (a skewed rectangle)."""
    if "beach_towel" in _cache:
        return _cache["beach_towel"]
    s = _surf()
    # four corners of a blanket seen in slight top-down perspective
    tl, tr = (10, 18), (TILE - 6, 14)
    bl, br = (6, TILE - 8), (TILE - 10, TILE - 4)
    teal, cream = (88, 184, 178), (244, 240, 226)
    pygame.draw.polygon(s, cream, [tl, tr, br, bl])
    # stripes running across the blanket
    for i in range(1, 6):
        a = (tl[0] + (bl[0] - tl[0]) * i / 6, tl[1] + (bl[1] - tl[1]) * i / 6)
        b = (tr[0] + (br[0] - tr[0]) * i / 6, tr[1] + (br[1] - tr[1]) * i / 6)
        if i % 2:
            pygame.draw.line(s, teal, a, b, 3)
    pygame.draw.polygon(s, (60, 150, 146), [tl, tr, br, bl], 1)
    _cache["beach_towel"] = s
    return s


def deck_chair_sprite():
    """A striped folding deck/lounge chair, side-on."""
    if "deck_chair" in _cache:
        return _cache["deck_chair"]
    h = TILE + 8
    s = _surf((TILE, h))
    frame, fdk = (180, 142, 96), (140, 104, 66)
    red, white = (228, 120, 96), (244, 240, 230)
    # reclined canvas (a slanted band) + a seat band
    back = [(10, h - 30), (26, h - 40), (30, h - 28), (14, h - 18)]
    seat = [(14, h - 18), (30, h - 28), (40, h - 22), (24, h - 12)]
    pygame.draw.polygon(s, white, back)
    pygame.draw.polygon(s, white, seat)
    for i, quad in enumerate((back, seat)):                  # canvas stripes
        for k in range(1, 4):
            a = (quad[0][0] + (quad[3][0] - quad[0][0]) * k / 4,
                 quad[0][1] + (quad[3][1] - quad[0][1]) * k / 4)
            b = (quad[1][0] + (quad[2][0] - quad[1][0]) * k / 4,
                 quad[1][1] + (quad[2][1] - quad[1][1]) * k / 4)
            pygame.draw.line(s, red, a, b, 2)
    pygame.draw.line(s, fdk, (10, h - 30), (8, h - 6), 3)    # back leg
    pygame.draw.line(s, frame, (30, h - 28), (34, h - 4), 3)  # front leg
    pygame.draw.line(s, frame, (24, h - 12), (40, h - 22), 2)
    _cache["deck_chair"] = s
    return s


def lifebuoy_sprite():
    """A red-and-white life ring hung on a short wooden post."""
    if "lifebuoy" in _cache:
        return _cache["lifebuoy"]
    h = TILE + 18
    s = _surf((TILE, h))
    cx = TILE // 2 - 4
    pygame.draw.rect(s, (150, 112, 72), (cx + 10, 16, 6, h - 20))         # post
    pygame.draw.rect(s, (120, 86, 54), (cx + 10, 16, 6, h - 20), 1)
    ring_c = (cx + 2, 24)
    pygame.draw.circle(s, (232, 84, 80), ring_c, 13)                      # ring
    pygame.draw.circle(s, (244, 244, 248), ring_c, 13, 0)
    pygame.draw.circle(s, (232, 84, 80), ring_c, 13, 5)
    for a in range(0, 360, 90):                                           # white bands
        x = ring_c[0] + int(11 * math.cos(math.radians(a)))
        y = ring_c[1] + int(11 * math.sin(math.radians(a)))
        pygame.draw.circle(s, (244, 244, 248), (x, y), 3)
    pygame.draw.circle(s, (0, 0, 0, 0), ring_c, 7)                        # hollow centre
    s.fill((0, 0, 0, 0), (ring_c[0] - 6, ring_c[1] - 6, 12, 12))
    _cache["lifebuoy"] = s
    return s


def bucket_sprite():
    """A child's sand bucket with a little spade poking out."""
    if "bucket" in _cache:
        return _cache["bucket"]
    s = _surf()
    bx, by = TILE // 2, TILE - 8
    red, rdk = (228, 96, 92), (188, 66, 64)
    pygame.draw.polygon(s, red, [(bx - 9, by - 14), (bx + 9, by - 14),
                                 (bx + 6, by), (bx - 6, by)])              # pail (tapered)
    pygame.draw.polygon(s, rdk, [(bx - 9, by - 14), (bx + 9, by - 14),
                                 (bx + 6, by), (bx - 6, by)], 1)
    pygame.draw.arc(s, (235, 235, 240), (bx - 9, by - 20, 18, 12), 3.3, 6.1, 2)  # handle
    pygame.draw.line(s, (110, 150, 210), (bx + 7, by - 22), (bx + 12, by - 4), 3)   # spade shaft
    pygame.draw.polygon(s, (150, 190, 230), [(bx + 10, by - 6), (bx + 16, by - 8),
                                             (bx + 14, by + 1), (bx + 9, by - 1)])  # spade blade
    _cache["bucket"] = s
    return s


def swim_ring_sprite():
    """A colourful inflatable swim ring lying on the sand."""
    if "swim_ring" in _cache:
        return _cache["swim_ring"]
    s = _surf()
    cx, cy, R = TILE // 2, TILE // 2 + 3, 13
    pink = (240, 120, 150)
    pygame.draw.circle(s, pink, (cx, cy), R)
    white = (246, 246, 250)
    for q in (1, 3):                                     # alternating white quadrants
        a0 = math.radians(q * 90); a1 = math.radians(q * 90 + 90)
        pts = [(cx, cy)]
        for t in range(6):
            a = a0 + (a1 - a0) * t / 5
            pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
        pygame.draw.polygon(s, white, pts)
    pygame.draw.circle(s, (210, 90, 120), (cx, cy), R, 1)
    pygame.draw.circle(s, (0, 0, 0, 0), (cx, cy), 5)     # transparent inner hole
    pygame.draw.circle(s, (205, 80, 110), (cx, cy), 5, 1)
    _cache["swim_ring"] = s
    return s


def sun_lounger_sprite():
    """A blue padded sun lounger / beach bed."""
    if "sun_lounger" in _cache:
        return _cache["sun_lounger"]
    h = TILE + 6
    s = _surf((TILE, h))
    blue, bdk, pillow = (96, 156, 220), (66, 120, 184), (230, 238, 248)
    pygame.draw.line(s, (180, 184, 196), (8, h - 4), (12, h - 16), 3)        # legs
    pygame.draw.line(s, (180, 184, 196), (TILE - 8, h - 4), (TILE - 12, h - 16), 3)
    pygame.draw.rect(s, blue, (6, h - 22, TILE - 12, 14), border_radius=5)   # mattress
    pygame.draw.rect(s, bdk, (6, h - 22, TILE - 12, 14), 1, border_radius=5)
    pygame.draw.polygon(s, blue, [(6, h - 22), (6, h - 34), (16, h - 30), (16, h - 18)])  # backrest
    pygame.draw.polygon(s, bdk, [(6, h - 22), (6, h - 34), (16, h - 30), (16, h - 18)], 1)
    pygame.draw.rect(s, pillow, (8, h - 31, 7, 6), border_radius=2)          # pillow
    for sx in range(13, TILE - 10, 7):                                       # seams
        pygame.draw.line(s, bdk, (sx, h - 21), (sx, h - 10), 1)
    _cache["sun_lounger"] = s
    return s


def boat_sprite():
    """A little sailboat bobbing on the water."""
    if "boat" in _cache:
        return _cache["boat"]
    h = TILE + 18
    s = _surf((TILE, h))
    cx = TILE // 2
    hull, hdk = (210, 92, 84), (170, 64, 60)
    hull_pts = [(6, h - 16), (TILE - 6, h - 16), (TILE - 12, h - 4), (12, h - 4)]
    pygame.draw.polygon(s, hull, hull_pts)
    pygame.draw.polygon(s, hdk, hull_pts, 1)
    pygame.draw.line(s, (244, 244, 248), (8, h - 14), (TILE - 8, h - 14), 2)  # trim
    pygame.draw.line(s, (140, 100, 64), (cx, h - 16), (cx, 6), 3)             # mast
    pygame.draw.polygon(s, (248, 246, 250), [(cx + 2, 8), (cx + 2, h - 20), (TILE - 8, h - 22)])  # mainsail
    pygame.draw.polygon(s, (210, 214, 224), [(cx + 2, 8), (cx + 2, h - 20), (TILE - 8, h - 22)], 1)
    pygame.draw.polygon(s, (120, 178, 226), [(cx - 2, 12), (cx - 2, h - 20), (10, h - 22)])       # jib
    pygame.draw.polygon(s, (240, 210, 90), [(cx, 6), (cx + 10, 9), (cx, 12)])  # pennant
    _cache["boat"] = s
    return s


def bush_sprite():
    """A small rounded shrub for the dunes/headland."""
    if "bush" in _cache:
        return _cache["bush"]
    s = _surf()
    g, gd, gl = (96, 176, 96), (70, 146, 78), (140, 206, 130)
    base = TILE - 8
    for (dx, dy, r) in ((-8, 0, 9), (8, 0, 9), (0, -4, 11), (0, 2, 9)):
        pygame.draw.circle(s, gd, (TILE // 2 + dx, base + dy), r)
    for (dx, dy, r) in ((-7, -1, 7), (7, -1, 7), (0, -5, 9)):
        pygame.draw.circle(s, g, (TILE // 2 + dx, base + dy), r)
    pygame.draw.circle(s, gl, (TILE // 2 - 2, base - 7), 4)
    pygame.draw.circle(s, (246, 226, 120), (TILE // 2 + 5, base - 3), 2)    # tiny flower
    _cache["bush"] = s
    return s


def _towel(name, base, stripe):
    if name in _cache:
        return _cache[name]
    s = _surf()
    tl, tr = (10, 18), (TILE - 6, 14)
    bl, br = (6, TILE - 8), (TILE - 10, TILE - 4)
    pygame.draw.polygon(s, base, [tl, tr, br, bl])
    for i in range(1, 6):
        a = (tl[0] + (bl[0] - tl[0]) * i / 6, tl[1] + (bl[1] - tl[1]) * i / 6)
        b = (tr[0] + (br[0] - tr[0]) * i / 6, tr[1] + (br[1] - tr[1]) * i / 6)
        if i % 2:
            pygame.draw.line(s, stripe, a, b, 3)
    pygame.draw.polygon(s, _dk(base, 0.8), [tl, tr, br, bl], 1)
    _cache[name] = s
    return s


def towel_pink_sprite():
    return _towel("towel_pink", (248, 200, 214), (232, 110, 150))


def towel_yellow_sprite():
    return _towel("towel_yellow", (250, 232, 160), (244, 192, 84))


def mist_gate_sprite():
    """The ruined warp gate hidden deep in the forest (-> Mist City): a cracked
    stone arch, one pillar broken, moss creeping over it, with a faint sickly
    green mist shimmering in the opening and dim neon runes.  Eerie-but-pastel,
    2 tiles tall (bottom-anchored)."""
    if "mist_gate" in _cache:
        return _cache["mist_gate"]
    h = TILE * 2
    s = _surf((TILE, h))
    stone, sdk = (152, 154, 164), (112, 114, 126)
    moss, rune = (104, 148, 100), (150, 230, 190)
    # soft mist glow swirling inside the archway (alpha layers)
    pygame.draw.ellipse(s, (140, 200, 170, 80), (8, 20, TILE - 16, h - 36))
    pygame.draw.ellipse(s, (174, 226, 196, 60), (13, 30, TILE - 26, h - 54))
    pygame.draw.ellipse(s, (200, 244, 216, 45), (17, 40, TILE - 34, h - 70))
    # left pillar (intact) and right pillar (snapped shorter)
    pygame.draw.rect(s, stone, (4, 12, 10, h - 16), border_radius=3)
    pygame.draw.rect(s, sdk, (4, 12, 10, h - 16), 1, border_radius=3)
    pygame.draw.rect(s, stone, (TILE - 14, 26, 10, h - 30), border_radius=3)
    pygame.draw.rect(s, sdk, (TILE - 14, 26, 10, h - 30), 1, border_radius=3)
    pygame.draw.polygon(s, sdk, [(TILE - 14, 26), (TILE - 8, 22), (TILE - 4, 26)])  # jagged break
    # broken lintel: only the left half still bridges the arch
    pygame.draw.rect(s, stone, (2, 6, 26, 9), border_radius=3)
    pygame.draw.rect(s, sdk, (2, 6, 26, 9), 1, border_radius=3)
    # the fallen half lies at the foot of the gate
    pygame.draw.rect(s, stone, (TILE - 24, h - 9, 16, 6), border_radius=2)
    pygame.draw.rect(s, sdk, (TILE - 24, h - 9, 16, 6), 1, border_radius=2)
    # cracks + moss reclaiming the stone
    pygame.draw.line(s, sdk, (9, 28), (12, 44), 1)
    pygame.draw.line(s, sdk, (TILE - 9, 38), (TILE - 12, 56), 1)
    for (mx, my, r) in ((6, 14, 3), (11, h - 20, 4), (TILE - 10, 30, 3),
                        (TILE - 18, h - 10, 3), (16, 8, 2)):
        pygame.draw.circle(s, moss, (mx, my), r)
        pygame.draw.circle(s, _dk(moss, 0.8), (mx, my), r, 1)
    # faint neon runes still pulsing on the intact pillar
    for ry in (32, 46, 60, 74):
        pygame.draw.line(s, rune, (7, ry), (11, ry), 1)
    pygame.draw.circle(s, rune, (9, 22), 2, 1)
    _cache["mist_gate"] = s
    return s


# Registry of every prop kind -> sprite factory. SINGLE SOURCE OF TRUTH:
# prop_sprite() dispatches from it and the gallery enumerates it, so adding a
# new prop here is all that's needed for it to render and appear everywhere.
def shore_rock_sprite():
    """A small cluster of coastal rocks + pebbles (about half the size of a mine
    boulder), sitting low in the tile so it grounds at the wet-sand/water edge.
    Grey boulder tones; the lower stones get a darker, damp base."""
    if "shore_rock" in _cache:
        return _cache["shore_rock"]
    s = _surf()
    base, dk, lt, wet = (124, 124, 136), (80, 80, 92), (158, 158, 170), (66, 70, 82)
    # 3 main stones of varying size, clustered toward the bottom of the tile
    for (cx, cy, r) in ((17, 32, 8), (28, 33, 7), (23, 30, 6), (35, 35, 4), (10, 35, 4)):
        pygame.draw.ellipse(s, (0, 0, 0, 70), (cx - r, cy + r - 3, r * 2, r))   # shadow
        pygame.draw.circle(s, dk, (cx, cy + 1), r)
        pygame.draw.circle(s, base, (cx, cy), r)
        pygame.draw.circle(s, lt, (cx - r // 3, cy - r // 3), max(1, r // 3))    # highlight
        pygame.draw.arc(s, wet, (cx - r, cy - r, r * 2, r * 2), 3.5, 6.0, 2)     # damp base
    for (px, py) in ((9, 38), (38, 39), (21, 40), (31, 39), (14, 40)):
        pygame.draw.circle(s, (112, 112, 124), (px, py), 2)                      # pebbles
    _cache["shore_rock"] = s
    return s


def shore_rock_sub_sprite():
    """Submerged version for stones sitting on a water tile: only the top ~45% of
    each rock pokes above the surface, with a white foam ring at the waterline and
    a faint blue wash where it meets the sea -- looks like rocks awash in the surf."""
    if "shore_rock_sub" in _cache:
        return _cache["shore_rock_sub"]
    s = _surf()
    base, dk, lt = (124, 124, 136), (84, 84, 96), (158, 158, 170)
    stones = ((17, 33, 8), (27, 34, 7), (22, 31, 6), (34, 36, 4), (11, 36, 4))
    for (cx, cy, r) in stones:
        cut = cy - r + int(r * 0.95)        # waterline: only the band above shows
        # foam ring + ripple at the waterline around the base
        pygame.draw.ellipse(s, (235, 245, 252, 130), (cx - r - 2, cut - 2, (r + 2) * 2, 6), 1)
        pygame.draw.ellipse(s, (255, 255, 255, 95), (cx - r, cut - 1, r * 2, 4), 1)
        # draw only the cap (clip to the band above the waterline)
        prev = s.get_clip()
        s.set_clip(pygame.Rect(cx - r - 1, cy - r - 1, 2 * r + 2, (cut - (cy - r)) + 1))
        pygame.draw.circle(s, dk, (cx, cy + 1), r)
        pygame.draw.circle(s, base, (cx, cy), r)
        pygame.draw.circle(s, lt, (cx - r // 3, cy - r // 3), max(1, r // 3))
        s.set_clip(prev)
        # faint blue wash on the wet rim where the rock enters the water
        pygame.draw.line(s, (150, 195, 225, 120), (cx - r + 1, cut - 1), (cx + r - 1, cut - 1), 2)
    _cache["shore_rock_sub"] = s
    return s


def cabana_sprite():
    """A striped beach cabana: a canvas roof on two posts with a faint back wall
    and a mat seat inside, open to the front (the sea). Built from the stall
    (posts + striped scalloped awning) and towel (striped mat) techniques."""
    if "cabana" in _cache:
        return _cache["cabana"]
    h = TILE + 18
    s = _surf((TILE, h))
    red, white = (228, 86, 84), (244, 244, 248)        # parasol palette
    frame, frame_d = (150, 118, 86), (120, 92, 64)
    # faint canvas back wall so it reads as a booth (open at the front)
    back = pygame.Surface((TILE - 12, h - 30), pygame.SRCALPHA)
    back.fill((244, 244, 248, 95))
    s.blit(back, (6, 18))
    # two posts (like the stall)
    pygame.draw.rect(s, frame, (5, 16, 5, h - 20))
    pygame.draw.rect(s, frame, (TILE - 10, 16, 5, h - 20))
    pygame.draw.rect(s, frame_d, (5, 16, 2, h - 20))
    pygame.draw.rect(s, frame_d, (TILE - 10, 16, 2, h - 20))
    # striped canvas roof across the top (red/white, like the stall awning)
    for i in range(0, TILE - 4, 12):
        c = red if (i // 12) % 2 == 0 else white
        pygame.draw.rect(s, c, (2 + i, 2, 12, 16))
    # scalloped lower edge of the roof (stall awning trim)
    pygame.draw.polygon(s, (170, 60, 60), [(2, 18), (TILE - 2, 18), (TILE - 6, 22), (6, 22)])
    # a striped mat seat inside (towel logic -- simple horizontal stripes)
    my = h - 18
    base = (250, 232, 160)
    pygame.draw.rect(s, base, (7, my, TILE - 14, 12), border_radius=2)
    for k in range(my + 2, my + 12, 4):
        pygame.draw.line(s, (244, 192, 84), (8, k), (TILE - 8, k), 2)
    pygame.draw.rect(s, _dk(base, 0.8), (7, my, TILE - 14, 12), 1, border_radius=2)
    _cache["cabana"] = s
    return s


PROPS = {"bed": bed_sprite, "bin": bin_sprite, "stall": stall_sprite,
         "sign": signpost_sprite, "buddha": buddha_sprite, "incense": incense_sprite,
         "candle": candle_sprite, "lotus": lotus_sprite, "bell": bell_sprite,
         "temple_gate": temple_gate_sprite, "donation_box": donation_box_sprite,
         "chedi": chedi_sprite, "naga": naga_sprite, "tung": tung_sprite,
         "bodhi": bodhi_sprite, "chatra": chatra_sprite, "offering_bowl": offering_bowl_sprite,
         "collector": collector_sprite, "scarecrow": scarecrow_sprite,
         "flowerbed": flowerbed_sprite, "windmill": windmill_sprite,
         "phra_pratan": phra_pratan_sprite, "pillar": pillar_sprite,
         "haybale": haybale_sprite, "trough": trough_sprite,
         "palm": palm_sprite, "parasol": parasol_sprite, "cabana": cabana_sprite,
         "shore_rock": shore_rock_sprite, "shore_rock_sub": shore_rock_sub_sprite,
         "sandcastle": sandcastle_sprite,
         "starfish": starfish_sprite, "seashell": seashell_sprite,
         "driftwood": driftwood_sprite, "beach_ball": beach_ball_sprite,
         "message_bottle": message_bottle_sprite, "surfboard": surfboard_sprite,
         "crab": crab_sprite, "beach_towel": beach_towel_sprite,
         "deck_chair": deck_chair_sprite, "lifebuoy": lifebuoy_sprite,
         "bucket": bucket_sprite, "swim_ring": swim_ring_sprite,
         "sun_lounger": sun_lounger_sprite, "boat": boat_sprite,
         "bush": bush_sprite, "towel_pink": towel_pink_sprite,
         "towel_yellow": towel_yellow_sprite,
         "mist_gate": mist_gate_sprite}


def register_prop(kind, painter):
    """Extension point: register a new prop sprite. ``painter()`` returns a
    Surface (cache it yourself if it is expensive). The gallery, world render and
    prop_sprite all read PROPS, so the new prop shows up everywhere."""
    PROPS[kind] = painter


def prop_sprite(kind):
    return PROPS.get(kind, signpost_sprite)()
