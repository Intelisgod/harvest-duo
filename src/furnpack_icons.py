"""Catalogue icons for the furniture expansion pack (see furnpack.py).

Flat icons in the house style of furniture._draw_base (front / top views,
lit + shaded tones). Authored on a 40 px tile and scaled by k = t / 40, so
they read at 40 px in Build, at 20 px/tile on 2x1 icons and at 48 px in the
gallery. furniture._draw_base calls draw_icon() for every kind in ICONS.
"""
import math

import pygame

from .furnpack import (WOOD, WOOD_LT, METAL, BRASS, GOLD, LEAF, LEAF_LT, LEAF_DK,
                       _mix, _lt, _dk, _ceramic, _star)


class _I:
    def __init__(self, s, t):
        self.s, self.k = s, t / 40.0

    def _r(self, x, y, w, h):
        k = self.k
        return pygame.Rect(round(x * k), round(y * k), max(1, round(w * k)),
                           max(1, round(h * k)))

    def rect(self, col, x, y, w, h, r=0, width=0):
        pygame.draw.rect(self.s, col, self._r(x, y, w, h), width,
                         border_radius=max(0, round(r * self.k)))

    def ell(self, col, x, y, w, h, width=0):
        pygame.draw.ellipse(self.s, col, self._r(x, y, w, h), width)

    def circ(self, col, x, y, r, width=0):
        pygame.draw.circle(self.s, col, (round(x * self.k), round(y * self.k)),
                           max(1, round(r * self.k)), width)

    def poly(self, col, pts, width=0):
        pygame.draw.polygon(self.s, col, [(x * self.k, y * self.k) for x, y in pts], width)

    def line(self, col, a, b, width=1):
        pygame.draw.line(self.s, col, (a[0] * self.k, a[1] * self.k),
                         (b[0] * self.k, b[1] * self.k), max(1, round(width * self.k)))


ICONS = {}


def _icon(*kinds):
    def deco(fn):
        for k in kinds:
            ICONS[k] = fn
        return fn
    return deco


def draw_icon(kind, s, t, color, on=True):
    """Paint `kind` onto s (its size is the footprint * t)."""
    ICONS[kind](_I(s, t), color, on)


def _ink(c):
    return _dk(c, 0.55)


@_icon("side_table")
def _i_side_table(i, c, on):
    for x in (9, 28):
        i.rect(_dk(WOOD, 0.8), x, 16, 3, 20)
    i.rect(_dk(c, 0.86), 8, 28, 24, 3)
    i.rect(c, 9, 15, 22, 6, 1)
    i.rect(_lt(c, 1.1), 9, 16, 22, 4, 1)
    i.rect(_ink(c), 9, 15, 22, 6, 1, 1)
    i.circ(BRASS, 20, 18, 1)
    i.rect(_lt(c, 1.15), 6, 11, 28, 5, 2)
    i.rect(_ink(c), 6, 11, 28, 5, 2, 1)


@_icon("writing_desk")
def _i_writing_desk(i, c, on):
    i.rect(WOOD_LT, 3, 11, 74, 5, 2)
    i.rect(_dk(WOOD_LT, 0.6), 3, 11, 74, 5, 2, 1)
    i.rect(c, 6, 16, 22, 22, 1)
    for y in (18, 25, 32):
        i.rect(_lt(c, 1.08), 8, y, 18, 5, 1)
        i.rect(_ink(c), 8, y, 18, 5, 1, 1)
        i.line(BRASS, (15, y + 2.5), (19, y + 2.5), 1)
    i.rect(_dk(c, 0.86), 28, 16, 44, 5)
    i.rect(_dk(c, 0.8), 70, 16, 4, 22)
    i.rect(_dk(c, 0.7), 30, 21, 40, 8)


@_icon("bean_bag")
def _i_bean_bag(i, c, on):
    i.ell(_dk(c, 0.8), 5, 18, 30, 19)
    i.ell(c, 6, 17, 28, 17)
    i.ell(_lt(c, 1.12), 11, 20, 18, 8)
    i.ell(_dk(c, 0.9), 9, 5, 22, 17)
    i.ell(c, 10, 5, 20, 15)
    i.ell(_lt(c, 1.2), 13, 7, 8, 5)
    i.ell(_ink(c), 5, 18, 30, 19, 1)


@_icon("floor_cushion")
def _i_floor_cushion(i, c, on):
    i.rect(_dk(c, 0.8), 5, 14, 30, 18, 7)
    i.rect(c, 5, 12, 30, 17, 7)
    i.rect(_lt(c, 1.14), 9, 14, 22, 9, 5)
    i.circ(_dk(c, 0.6), 20, 20, 2)
    for x, y in ((6, 13), (34, 13), (6, 30), (34, 30)):
        i.circ(GOLD, x, y, 2)


@_icon("tall_plant")
def _i_tall_plant(i, c, on):
    for (x, y, a) in ((10, 14, -0.6), (29, 12, 0.6), (20, 7, 0.0), (8, 22, -1.1),
                      (32, 21, 1.1)):
        L, W = 12, 6
        d = (math.sin(a), -math.cos(a))
        n = (-d[1], d[0])
        pts = []
        for s in range(9):
            t = s / 8
            w = W * math.sin(math.pi * t) ** 0.8
            pts.append((x + d[0] * (t - 0.5) * L + n[0] * w, y + d[1] * (t - 0.5) * L + n[1] * w))
        for s in range(8, -1, -1):
            t = s / 8
            w = W * math.sin(math.pi * t) ** 0.8
            pts.append((x + d[0] * (t - 0.5) * L - n[0] * w, y + d[1] * (t - 0.5) * L - n[1] * w))
        i.line(_dk(LEAF, 0.8), (20, 28), (x - d[0] * 5, y - d[1] * 5), 1)
        i.poly(LEAF, pts)
        i.poly(LEAF_DK, pts, 1)
        i.line(LEAF_LT, (x - d[0] * 4, y - d[1] * 4), (x + d[0] * 4, y + d[1] * 4), 1)
    i.poly(c, [(13, 28), (27, 28), (25, 38), (15, 38)])
    i.rect(_lt(c, 1.12), 12, 27, 16, 3, 1)
    i.poly(_ink(c), [(13, 28), (27, 28), (25, 38), (15, 38)], 1)


@_icon("floor_vase")
def _i_floor_vase(i, c, on):
    for x, y in ((10, 5), (20, 2), (30, 6), (14, 8), (26, 9)):
        i.line((176, 150, 104), (20, 17), (x, y + 6), 1)
        i.ell((236, 222, 192), x - 3, y, 7, 10)
        i.ell((222, 202, 162), x - 1, y + 3, 4, 6)
    body = [(15, 38), (25, 38), (28, 30), (26, 24), (22, 20), (22, 17), (18, 17), (18, 20),
            (14, 24), (12, 30)]
    i.poly(c, body)
    i.poly(_ink(c), body, 1)
    i.line(_lt(c, 1.3), (13, 30), (27, 30), 1)


@_icon("grandfather_clock")
def _i_grandfather_clock(i, c, on):
    i.rect(_dk(c, 0.82), 11, 34, 18, 5)
    i.rect(c, 13, 16, 14, 18)
    i.rect((58, 44, 38), 16, 19, 8, 13)
    i.line((196, 170, 110), (20, 19), (20, 28), 1)
    i.circ(GOLD, 20, 29, 2)
    i.rect(c, 12, 4, 16, 12)
    i.circ(GOLD, 20, 10, 5)
    i.circ((250, 246, 234), 20, 10, 4)
    i.line((40, 34, 40), (20, 10), (18, 8), 1)
    i.line((40, 34, 40), (20, 10), (22, 7), 1)
    i.rect(_dk(c, 0.82), 11, 2, 18, 3)
    i.circ(GOLD, 20, 1, 1)
    i.rect(_ink(c), 12, 4, 16, 30, 0, 1)


@_icon("tv_stand")
def _i_tv_stand(i, c, on):
    i.rect(WOOD_LT, 3, 14, 74, 3, 1)
    i.rect(c, 4, 17, 72, 16, 1)
    for x0 in (6, 52):
        i.rect(_lt(c, 1.06), x0, 19, 22, 12)
        for k in range(1, 6):
            i.line(_dk(c, 0.82), (x0 + k * 3.7, 20), (x0 + k * 3.7, 30), 1)
    i.rect(_dk(c, 0.45), 30, 19, 20, 12)
    i.rect((238, 238, 242), 32, 25, 7, 5)
    for k, bc in enumerate(((208, 96, 90), (96, 140, 208), (230, 196, 92))):
        i.rect(bc, 42 + k * 2.5, 22, 2, 9)
    for x in (8, 70):
        i.rect(_dk(WOOD, 0.75), x, 33, 3, 4)


@_icon("floor_mirror")
def _i_floor_mirror(i, c, on):
    i.rect(c, 11, 3, 18, 33, 8)
    i.rect((186, 212, 226), 13, 5, 14, 29, 7)
    i.poly((214, 232, 240), [(14, 14), (22, 6), (25, 7), (14, 22)])
    i.line((248, 252, 255), (15, 18), (22, 9), 1)
    i.rect(_ink(c), 11, 3, 18, 33, 8, 1)
    i.rect(_dk(c, 0.7), 9, 36, 22, 3, 1)


@_icon("shoe_rack")
def _i_shoe_rack(i, c, on):
    for x in (6, 32):
        i.rect(_dk(c, 0.85), x, 8, 3, 30)
    for y in (8, 22, 35):
        i.rect(c, 5, y, 30, 3, 1)
    for x, col in ((10, (244, 244, 248)), (21, (150, 96, 60))):
        i.rect(col, x, 16, 9, 6, 2)
        i.rect(_dk(col, 0.7), x, 16, 9, 6, 2, 1)
    for x, col in ((10, (236, 150, 176)), (21, (90, 120, 190))):
        i.rect(col, x, 30, 9, 5, 2)
        i.rect(_dk(col, 0.7), x, 30, 9, 5, 2, 1)


@_icon("laundry_basket")
def _i_laundry_basket(i, c, on):
    wick = (206, 170, 116)
    i.ell(c, 10, 8, 12, 9)
    i.ell((244, 244, 248), 18, 7, 12, 8)
    i.ell(_lt(c, 1.25), 14, 5, 10, 7)
    i.poly(wick, [(8, 13), (32, 13), (29, 37), (11, 37)])
    for y in (19, 25, 31):
        i.line(_dk(wick, 0.72), (9, y), (31, y), 1)
    for x in (14, 20, 26):
        i.line(_dk(wick, 0.8), (x, 14), (x, 36), 1)
    i.rect(_lt(wick, 1.1), 7, 12, 26, 3, 1)
    i.poly(_dk(wick, 0.55), [(8, 13), (32, 13), (29, 37), (11, 37)], 1)


@_icon("teddy_giant", "teddy_bear")
def _i_teddy(i, c, on):
    fur = (196, 146, 100)
    i.circ(fur, 11, 7, 4)
    i.circ(fur, 29, 7, 4)
    i.ell(fur, 9, 19, 22, 18)
    i.ell(_lt(fur, 1.15), 14, 24, 12, 10)
    i.circ(fur, 20, 13, 9)
    i.ell((238, 216, 186), 15, 14, 10, 7)
    i.circ((50, 36, 34), 20, 15, 1.5)
    i.circ((36, 28, 30), 16, 11, 1.2)
    i.circ((36, 28, 30), 24, 11, 1.2)
    i.poly(c, [(20, 22), (14, 19), (14, 25)])
    i.poly(c, [(20, 22), (26, 19), (26, 25)])
    i.ell(fur, 7, 31, 10, 8)
    i.ell(fur, 23, 31, 10, 8)
    i.circ((238, 206, 176), 12, 35, 2.5)
    i.circ((238, 206, 176), 28, 35, 2.5)


@_icon("coffee_machine")
def _i_coffee_machine(i, c, on):
    i.rect(c, 6, 22, 28, 16, 1)
    i.line(_dk(c, 0.6), (20, 23), (20, 37), 1)
    i.rect(WOOD_LT, 5, 20, 30, 3, 1)
    i.rect((200, 202, 210), 9, 6, 18, 14, 1)
    i.rect((74, 76, 84), 8, 4, 20, 3, 1)
    i.rect((60, 62, 70), 10, 8, 16, 4)
    i.circ((120, 236, 140) if on else (150, 60, 60), 23, 10, 1)
    i.circ((246, 244, 236), 14, 10, 1.5)
    i.rect((44, 42, 46), 15, 13, 6, 2)
    i.rect((246, 244, 240), 16, 16, 5, 4, 1)
    if on:
        i.line((230, 232, 238), (30, 14), (31, 4), 1)


@_icon("bar_cart")
def _i_bar_cart(i, c, on):
    for x in (7, 31):
        i.rect(BRASS, x, 8, 2, 28)
    i.rect(BRASS, 5, 4, 2, 8)
    i.line(BRASS, (6, 4), (10, 4), 2)
    i.rect(c, 5, 11, 30, 3, 1)
    i.rect(c, 5, 29, 30, 3, 1)
    for x, col, h in ((11, (52, 110, 70), 14), (17, (196, 130, 60), 10),
                      (23, (186, 60, 84), 13), (28, (226, 236, 240), 6)):
        i.rect(col, x, 29 - h, 4, h, 1)
        i.rect(col, x + 1, 29 - h - 3, 2, 3)
    for x in (8, 32):
        i.circ((50, 48, 54), x, 37, 2)


@_icon("spice_rack")
def _i_spice_rack(i, c, on):
    i.rect(_dk(c, 0.78), 6, 5, 28, 31, 1)
    spices = [(196, 70, 50), (232, 184, 60), (98, 150, 80), (70, 58, 50)]
    for row, y in enumerate((8, 22)):
        for k in range(4):
            x = 8 + k * 6.3
            i.rect((226, 236, 240), x, y, 5, 10, 1)
            i.rect(spices[(k + row) % 4], x + 0.5, y + 3, 4, 6)
            i.rect(_dk(c, 0.7), x, y - 1, 5, 2)
        i.rect(c, 5, y + 10, 30, 3, 1)
    i.rect(_ink(c), 6, 5, 28, 31, 1, 1)


@_icon("bathtub")
def _i_bathtub(i, c, on):
    i.rect(c, 6, 14, 68, 18, 9)
    i.rect(_dk(c, 0.82), 6, 22, 68, 10, 9)
    i.rect((242, 244, 248), 4, 11, 72, 6, 3)
    if on:
        i.rect((150, 202, 230), 8, 12, 64, 3, 1)
        for x in (18, 26, 34, 44, 52, 60):
            i.circ((250, 252, 255), x, 11, 3)
        i.circ((250, 214, 70), 58, 9, 2)
    for x in (12, 64):
        i.rect(GOLD, x, 31, 4, 5, 1)
    i.line(METAL, (9, 11), (9, 4), 2)
    i.line(METAL, (9, 4), (14, 4), 2)
    i.rect(_ink(c), 6, 14, 68, 18, 9, 1)


@_icon("bath_sink")
def _i_bath_sink(i, c, on):
    cer = _ceramic(c)
    i.poly(cer, [(17, 38), (23, 38), (22, 22), (18, 22)])
    i.rect(_dk(cer, 0.8), 14, 36, 12, 3, 1)
    i.ell(cer, 6, 14, 28, 11)
    i.ell(_dk(cer, 0.86), 9, 14, 22, 6)
    i.ell(_dk(cer, 0.55), 6, 14, 28, 11, 1)
    i.line(METAL, (20, 14), (20, 7), 2)
    i.line(METAL, (20, 7), (24, 7), 2)
    i.circ((220, 90, 90), 15, 11, 1.5)
    i.circ((90, 140, 220), 25, 11, 1.5)


@_icon("toilet")
def _i_toilet(i, c, on):
    cer = (244, 244, 248)
    i.rect(cer, 10, 4, 20, 14, 2)
    i.rect(cer, 9, 3, 22, 3, 1)
    i.rect(_dk(cer, 0.6), 10, 4, 20, 14, 2, 1)
    i.poly(cer, [(14, 36), (26, 36), (24, 30), (16, 30)])
    i.ell(cer, 8, 19, 24, 13)
    i.ell(c, 8, 17, 24, 9)
    i.ell(_lt(c, 1.2), 11, 18, 18, 5)
    i.ell(_dk(cer, 0.6), 8, 19, 24, 13, 1)
    i.line(METAL, (12, 8), (15, 8), 2)


@_icon("shower_booth")
def _i_shower_booth(i, c, on):
    tile = _mix(c, (250, 250, 252), 0.62)
    i.rect(tile, 6, 3, 28, 33)
    for y in range(7, 36, 5):
        i.line(_dk(tile, 0.82), (6, y), (34, y), 1)
    for x in (13, 20, 27):
        i.line(_dk(tile, 0.82), (x, 3), (x, 36), 1)
    i.line(METAL, (20, 3), (20, 8), 2)
    i.ell(METAL, 16, 7, 8, 3)
    if on:
        for x in (17, 19, 21, 23):
            i.line((150, 196, 230), (x, 10), (x - 1 + (x - 20) * 0.6, 34), 1)
    i.rect((238, 240, 244), 4, 35, 32, 4, 1)
    i.rect((170, 206, 226), 6, 3, 28, 32, 0, 1)


@_icon("bath_mat")
def _i_bath_mat(i, c, on):
    i.rect(_dk(c, 0.86), 5, 12, 70, 18, 8)
    i.rect(c, 5, 11, 70, 17, 8)
    i.rect(_lt(c, 1.12), 11, 14, 58, 11, 6)
    for x in range(14, 68, 6):
        for y in (17, 22):
            i.circ(_lt(c, 1.28), x, y, 1)
    for x in range(8, 74, 4):
        i.line(_dk(c, 0.7), (x, 28), (x, 31), 1)


@_icon("towel_rack")
def _i_towel_rack(i, c, on):
    metal = (196, 200, 208)
    i.rect(metal, 6, 10, 3, 5)
    i.rect(metal, 31, 10, 3, 5)
    i.rect(_lt(metal, 1.05), 5, 11, 30, 3, 1)
    i.rect(c, 10, 12, 20, 22, 1)
    i.rect(_lt(c, 1.1), 10, 11, 20, 4, 1)
    stripe = _lt(c, 1.35) if sum(c) < 600 else _dk(c, 0.8)
    for y in (27, 30):
        i.rect(stripe, 10, y, 20, 1.5)
    for x in range(11, 30, 3):
        i.line(_dk(c, 0.8), (x, 34), (x, 37), 1)


@_icon("lantern")
def _i_lantern(i, c, on):
    frame = (70, 66, 74)
    i.circ(frame, 20, 4, 3, 1)
    i.poly(frame, [(20, 6), (29, 12), (11, 12)])
    i.rect(frame, 12, 12, 16, 22, 1)
    i.rect((255, 212, 130) if on else (78, 88, 100), 14, 14, 12, 18)
    if on:
        i.rect((255, 236, 180), 16, 18, 8, 13)
    i.line(frame, (20, 14), (20, 32), 1)
    i.rect((240, 232, 214), 18, 25, 4, 6)
    if on:
        i.circ((255, 170, 70), 20, 23, 1.5)
    i.rect(frame, 11, 34, 18, 3, 1)


@_icon("dollhouse")
def _i_dollhouse(i, c, on):
    wall = (244, 232, 218)
    i.rect(WOOD, 5, 35, 30, 3, 1)
    i.rect(wall, 8, 17, 24, 18)
    i.rect((240, 200, 214), 10, 19, 20, 7)
    i.rect((200, 228, 206), 10, 27, 9, 7)
    i.rect((206, 220, 240), 21, 27, 9, 7)
    i.rect(c, 12, 22, 7, 3)
    i.rect((220, 110, 110), 22, 30, 7, 4)
    i.poly(c, [(20, 4), (35, 18), (5, 18)])
    i.poly(_ink(c), [(20, 4), (35, 18), (5, 18)], 1)
    i.circ((150, 196, 226), 20, 13, 2)
    i.rect(_dk(wall, 0.6), 8, 17, 24, 18, 0, 1)


@_icon("guitar_stand")
def _i_guitar_stand(i, c, on):
    i.line((60, 58, 66), (12, 38), (20, 22), 1)
    i.line((60, 58, 66), (28, 38), (20, 22), 1)
    i.circ(_dk(c, 0.7), 20, 30, 8)
    i.circ(_dk(c, 0.7), 20, 20, 6)
    i.circ(c, 20, 30, 6.5)
    i.circ(c, 20, 20, 4.8)
    i.circ((40, 30, 26), 20, 22, 2)
    i.rect((132, 90, 56), 19, 3, 3, 15)
    i.rect((70, 48, 34), 18, 1, 5, 4)
    i.line((238, 232, 214), (20.5, 5), (20.5, 33), 1)
    i.rect((60, 40, 30), 17, 32, 7, 2)


@_icon("christmas_tree")
def _i_christmas_tree(i, c, on):
    green, dk = (52, 128, 76), (34, 94, 58)
    for top, bot, w in ((4, 16, 9), (11, 25, 13), (18, 33, 17)):
        i.poly(green, [(20, top), (20 + w, bot), (20 - w, bot)])
        i.poly(dk, [(20, top), (20 + w, bot), (20 - w, bot)], 1)
    i.rect(c, 15, 33, 10, 6, 1)
    i.rect(GOLD, 15, 35, 10, 1.5)
    for x, y, col in ((16, 14, (220, 70, 80)), (24, 21, (90, 140, 230)), (14, 28, (240, 196, 80)),
                      (26, 30, (236, 130, 190)), (20, 24, (220, 70, 80))):
        i.circ(col, x, y, 1.5)
    if on:
        for x, y in ((22, 12), (17, 20), (27, 26), (12, 31), (20, 30)):
            i.circ((255, 240, 170), x, y, 1)
    i.poly(GOLD, _star((20, 4), 4.5))


@_icon("string_lights")
def _i_string_lights(i, c, on):
    def y_at(x):
        return 14 + 7 * math.sin(math.pi * (((x - 3) / 17.5) % 1.0))
    pts = [(x, y_at(x)) for x in range(3, 39)]
    for a, b in zip(pts, pts[1:]):
        i.line((70, 74, 66), a, b, 1)
    warm = (255, 226, 150)
    for k, x in enumerate((7, 12, 17, 24, 29, 34)):
        y = y_at(x) + 3
        col = (c, warm)[k % 2]
        if on:
            i.circ(_lt(col, 1.3), x, y + 1, 3.5)
        i.ell(_lt(col, 1.2) if on else _mix(col, (120, 120, 126), 0.55), x - 2, y - 1, 4, 6)


@_icon("wall_calendar")
def _i_wall_calendar(i, c, on):
    i.line((150, 146, 150), (20, 2), (12, 7), 1)
    i.line((150, 146, 150), (20, 2), (28, 7), 1)
    i.rect((250, 248, 242), 9, 7, 22, 30, 1)
    i.rect(_lt(c, 1.3), 11, 9, 18, 10)
    i.poly(_mix(c, (90, 160, 100), 0.4), [(11, 19), (11, 15), (17, 13), (23, 16), (29, 14),
                                          (29, 19)])
    i.rect(c, 11, 20, 18, 2)
    for r in range(4):
        for k in range(6):
            i.rect((150, 146, 156), 12 + k * 3, 24 + r * 3, 1.5, 1.5)
    i.circ((226, 70, 96), 22.5, 27.5, 2, 1)
    i.rect((180, 176, 170), 9, 7, 22, 30, 1, 1)


@_icon("memory_board")
def _i_memory_board(i, c, on):
    i.rect(c, 3, 6, 34, 28, 2)
    i.rect((198, 152, 100), 6, 9, 28, 22)
    for x, y, bg in ((8, 11, (240, 170, 190)), (21, 12, (150, 200, 236)),
                     (13, 20, (170, 214, 170))):
        i.rect((250, 250, 248), x, y, 10, 10)
        i.rect(bg, x + 1, y + 1, 8, 7)
        i.circ((220, 64, 64), x + 5, y, 1)
    i.rect((250, 232, 120), 25, 23, 7, 7)


@_icon("hanging_plant")
def _i_hanging_plant(i, c, on):
    i.rect((96, 90, 96), 18, 2, 4, 3)
    for x in (13, 27):
        i.line((226, 214, 190), (20, 4), (x, 16), 1)
    for x, L in ((10, 18), (15, 22), (24, 20), (30, 15)):
        for k in range(L // 4):
            i.ell((84, 164, 92) if k % 2 else (62, 136, 76), x - 2 + (k % 2) * 2, 20 + k * 4, 5, 4)
    i.poly(c, [(11, 15), (29, 15), (26, 24), (14, 24)])
    i.rect(_lt(c, 1.15), 10, 14, 20, 3, 1)
    i.circ(LEAF, 16, 12, 4)
    i.circ(LEAF_LT, 22, 11, 4)
    i.circ(LEAF, 26, 13, 3)


@_icon("laptop")
def _i_laptop(i, c, on):
    body = _mix(c, (214, 216, 224), 0.55)
    i.rect(body, 9, 8, 22, 17, 2)
    i.rect((132, 188, 236) if on else (40, 42, 52), 11, 10, 18, 13)
    if on:
        i.poly((120, 190, 110), [(11, 23), (11, 19), (17, 17), (23, 19), (29, 18), (29, 23)])
        i.circ((236, 110, 140), 23, 14, 1.5)
    i.poly(body, [(6, 32), (34, 32), (31, 25), (9, 25)])
    i.poly(_dk(body, 0.6), [(6, 32), (34, 32), (31, 25), (9, 25)], 1)
    i.rect((58, 60, 68), 11, 26, 18, 3)


@_icon("alarm_clock")
def _i_alarm_clock(i, c, on):
    i.circ(GOLD, 12, 11, 4)
    i.circ(GOLD, 28, 11, 4)
    i.line(_dk(c, 0.6), (13, 30), (10, 35), 2)
    i.line(_dk(c, 0.6), (27, 30), (30, 35), 2)
    i.circ(c, 20, 22, 11)
    i.circ((250, 248, 240), 20, 22, 8)
    i.line((40, 36, 44), (20, 22), (20, 16), 2)
    i.line((40, 36, 44), (20, 22), (24, 22), 1)
    i.circ(_ink(c), 20, 22, 11, 1)


@_icon("teapot_set")
def _i_teapot_set(i, c, on):
    i.ell(WOOD_LT, 3, 30, 34, 7)
    i.poly(c, [(25, 21), (32, 13), (33, 15), (26, 25)])
    i.circ(_dk(c, 0.7), 9, 21, 4, 2)
    i.ell(c, 8, 13, 18, 16)
    i.ell(_lt(c, 1.15), 11, 15, 8, 6)
    i.ell(_ink(c), 8, 13, 18, 16, 1)
    i.rect(_lt(c, 1.1), 14, 10, 6, 3, 1)
    i.circ(_lt(c, 1.1), 17, 9, 1.5)
    i.rect((248, 248, 250), 27, 26, 7, 5, 2)
    i.line(c, (27, 27), (34, 27), 1)


@_icon("snow_globe")
def _i_snow_globe(i, c, on):
    i.poly(_dk(c, 0.9), [(10, 37), (30, 37), (27, 29), (13, 29)])
    i.circ((214, 236, 248), 20, 18, 12)
    i.ell((250, 250, 252), 10, 22, 20, 6)
    i.rect((214, 96, 90), 15, 18, 6, 5)
    i.poly((250, 250, 252), [(14, 18), (18, 14), (22, 18)])
    i.poly((60, 140, 90), [(24, 24), (28, 24), (26, 16)])
    for x, y in ((12, 12), (25, 10), (19, 8), (28, 16)):
        i.circ((255, 255, 255), x, y, 1)
    i.circ((170, 200, 216), 20, 18, 12, 1)


@_icon("hourglass")
def _i_hourglass(i, c, on):
    wood = _dk(WOOD_LT, 0.9)
    sand = _mix(c, (236, 206, 130), 0.55)
    i.rect(wood, 9, 4, 22, 3, 1)
    i.rect(wood, 9, 33, 22, 3, 1)
    i.line(wood, (11, 7), (11, 33), 2)
    i.line(wood, (29, 7), (29, 33), 2)
    i.poly((220, 236, 244), [(14, 7), (26, 7), (21, 20), (26, 33), (14, 33), (19, 20)])
    i.poly(sand, [(16, 12), (24, 12), (21, 19), (19, 19)])
    i.poly(sand, [(14, 33), (26, 33), (22, 27), (18, 27)])
    i.line(sand, (20, 20), (20, 27), 1)


@_icon("succulent")
def _i_succulent(i, c, on):
    i.poly(c, [(12, 26), (28, 26), (26, 36), (14, 36)])
    i.rect(_lt(c, 1.12), 11, 25, 18, 3, 1)
    for a in range(8):
        ang = a * math.pi / 4
        x, y = 20 + math.cos(ang) * 8, 19 + math.sin(ang) * 4
        i.ell((150, 196, 164), x - 3, y - 3, 7, 6)
        i.circ((232, 140, 164), x + math.cos(ang) * 3, y + math.sin(ang) * 2, 1)
    i.ell((170, 210, 176), 16, 14, 8, 7)


@_icon("jewelry_box")
def _i_jewelry_box(i, c, on):
    i.rect(c, 8, 5, 24, 13, 2)
    i.rect((200, 222, 234), 11, 7, 18, 9)
    i.rect(GOLD, 11, 7, 18, 9, 0, 1)
    i.rect((160, 44, 70), 8, 18, 24, 4)
    i.circ((250, 248, 244), 14, 19, 1.5)
    i.circ((250, 248, 244), 17, 20, 1.5)
    i.circ(GOLD, 25, 19, 2, 1)
    i.rect(c, 7, 21, 26, 13, 2)
    i.rect(_ink(c), 7, 21, 26, 13, 2, 1)
    i.rect(GOLD, 19, 23, 3, 4)


@_icon("perfume_set")
def _i_perfume_set(i, c, on):
    i.ell(GOLD, 3, 31, 34, 7)
    i.ell((214, 230, 238), 5, 32, 30, 5)
    tint = _mix(c, (250, 250, 255), 0.35)
    i.rect(tint, 7, 13, 9, 20, 2)
    i.rect(GOLD, 9, 9, 5, 4)
    i.circ((236, 150, 176), 23, 26, 6)
    i.rect(GOLD, 22, 17, 2, 4)
    i.circ((214, 90, 120), 31, 18, 2)
    i.rect((250, 214, 120), 28, 27, 6, 6, 1)
    i.rect((60, 50, 60), 30, 24, 2, 3)


@_icon("radio")
def _i_radio(i, c, on):
    i.line(METAL, (28, 12), (35, 2), 1)
    i.line((70, 56, 44), (12, 12), (14, 8), 2)
    i.line((70, 56, 44), (14, 8), (26, 8), 2)
    i.line((70, 56, 44), (26, 8), (28, 12), 2)
    i.rect(c, 5, 12, 30, 22, 4)
    i.rect((230, 214, 180), 8, 16, 13, 15, 1)
    for y in (19, 22, 25, 28):
        i.line((170, 150, 116), (9, y), (20, y), 1)
    i.rect((255, 222, 140) if on else (236, 226, 200), 23, 16, 9, 7)
    i.line((200, 60, 60), (27, 16), (27, 23), 1)
    i.circ((240, 236, 226), 25, 28, 2)
    i.circ((240, 236, 226), 31, 28, 2)
    i.rect(_ink(c), 5, 12, 30, 22, 4, 1)


@_icon("lava_lamp")
def _i_lava_lamp(i, c, on):
    liq = _lt(c, 1.25) if on else _dk(c, 0.75)
    i.poly((170, 174, 186), [(12, 38), (28, 38), (24, 29), (16, 29)])
    i.poly(liq, [(16, 29), (24, 29), (26, 18), (23, 7), (17, 7), (14, 18)])
    for x, y, r in ((19, 12, 2.5), (21, 20, 3), (18, 26, 2)):
        i.circ(_mix(_lt(c, 1.5), (255, 230, 150), 0.4) if on else _dk(c, 0.95), x, y, r)
    i.poly((170, 174, 186), [(17, 7), (23, 7), (21, 2), (19, 2)])


@_icon("cake_stand")
def _i_cake_stand(i, c, on):
    frost = _mix(c, (255, 255, 255), 0.45)
    i.ell((238, 240, 244), 12, 35, 16, 4)
    i.rect((238, 240, 244), 18, 28, 4, 8)
    i.ell((246, 246, 250), 5, 26, 30, 5)
    i.rect(frost, 9, 13, 22, 14, 2)
    i.rect((250, 240, 220), 9, 19, 22, 2)
    i.ell(_lt(frost, 1.06), 9, 10, 22, 7)
    for x in (13, 18, 23, 28):
        i.circ((214, 50, 64), x, 12, 2)
    i.line((250, 230, 140), (20, 11), (20, 5), 2)
    i.circ((255, 190, 90), 20, 3, 1.5)


@_icon("board_game")
def _i_board_game(i, c, on):
    i.poly((246, 238, 220), [(20, 8), (38, 20), (20, 32), (2, 20)])
    for pts, col in (([(20, 8), (26, 12), (20, 16), (14, 12)], (220, 80, 80)),
                     ([(32, 16), (38, 20), (32, 24), (26, 20)], (80, 130, 220)),
                     ([(20, 24), (26, 28), (20, 32), (14, 28)], (240, 196, 80)),
                     ([(8, 16), (14, 20), (8, 24), (2, 20)], (96, 180, 110))):
        i.poly(col, pts)
    i.poly(c, [(20, 17), (24, 20), (20, 23), (16, 20)])
    i.poly((170, 150, 120), [(20, 8), (38, 20), (20, 32), (2, 20)], 1)
    i.circ((200, 60, 60), 12, 15, 2)
    i.circ((70, 110, 210), 27, 23, 2)
    i.rect((250, 250, 252), 28, 8, 5, 5, 1)
    i.circ((40, 40, 50), 30.5, 10.5, 0.8)


@_icon("trophy")
def _i_trophy(i, c, on):
    i.rect((70, 50, 40), 12, 32, 16, 6, 1)
    i.rect(GOLD, 16, 34, 8, 2)
    i.rect(GOLD, 18, 24, 4, 8)
    i.circ(_dk(GOLD, 0.7), 9, 11, 4, 2)
    i.circ(_dk(GOLD, 0.7), 31, 11, 4, 2)
    i.poly(GOLD, [(10, 6), (30, 6), (27, 20), (13, 20)])
    i.ell(_lt(GOLD, 1.1), 10, 4, 20, 5)
    i.poly((255, 248, 210), _star((20, 12.5), 4))
    i.poly(_dk(GOLD, 0.6), [(10, 6), (30, 6), (27, 20), (13, 20)], 1)


@_icon("music_box")
def _i_music_box(i, c, on):
    i.rect(WOOD_LT, 7, 5, 26, 13, 2)
    i.rect((206, 226, 236), 10, 7, 20, 9)
    i.rect(c, 7, 18, 26, 4)
    i.poly((250, 190, 210), [(16, 17), (24, 17), (20, 11)])
    i.circ((250, 226, 214), 20, 9, 1.5)
    i.rect(WOOD_LT, 6, 21, 28, 13, 2)
    i.rect(_dk(WOOD_LT, 0.6), 6, 21, 28, 13, 2, 1)
    i.circ((240, 150, 170), 11, 28, 1.5)
    i.circ((240, 150, 170), 29, 28, 1.5)
    i.line(METAL, (34, 27), (37, 27), 1)
    i.circ(METAL, 37, 27, 2, 1)


@_icon("bonsai")
def _i_bonsai(i, c, on):
    i.line((96, 66, 44), (19, 28), (16, 21), 3)
    i.line((96, 66, 44), (16, 21), (22, 14), 3)
    i.line((96, 66, 44), (18, 19), (9, 16), 2)
    for x, y, w, h in ((16, 6, 16, 8), (4, 11, 12, 7), (20, 14, 12, 6)):
        i.ell((52, 118, 70), x, y, w, h)
        i.ell((86, 158, 96), x + 2, y + 1, w - 6, h - 4)
    i.rect(c, 6, 28, 28, 7, 2)
    i.rect(_lt(c, 1.12), 5, 27, 30, 3, 1)


@_icon("fish_bowl")
def _i_fish_bowl(i, c, on):
    i.circ((226, 240, 248), 20, 22, 14)
    i.poly((150, 206, 236), [(20 + 14 * math.cos(a), 22 + 14 * math.sin(a))
                             for a in (k * math.pi / 16 for k in range(-3, 20))])
    i.circ((190, 220, 236), 20, 22, 14, 1)
    i.ell((214, 236, 246), 12, 7, 16, 4, 1)
    i.ell((246, 140, 50), 15, 21, 9, 6)
    i.poly((250, 170, 80), [(15, 24), (10, 20), (10, 27)])
    i.circ((30, 30, 36), 21, 23, 1)
    for x, col in ((13, (236, 120, 120)), (18, (240, 220, 140)), (24, (140, 190, 240))):
        i.circ(col, x, 33, 1.5)
    i.line((80, 170, 100), (28, 34), (29, 26), 1)


@_icon("dish_rack")
def _i_dish_rack(i, c, on):
    i.rect((176, 180, 190), 4, 30, 32, 4, 1)
    for k in range(5):
        col = (250, 250, 252) if k % 2 == 0 else _mix(c, (255, 255, 255), 0.3)
        x = 8 + k * 6
        i.ell(col, x - 3, 12, 7, 20)
        i.ell(_dk(col, 0.6), x - 3, 12, 7, 20, 1)
    for x in (5, 35):
        i.line((200, 204, 212), (x, 20), (x, 30), 1)
