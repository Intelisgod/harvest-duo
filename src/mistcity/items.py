"""Mist City boss trophies — registered through the shared item/icon registries.

Owner: Chat 7 (Mist City). Imported by mist_system at load time. Sell prices sit
just above the 400g quest-pool cap on purpose, so the board never asks for a
boss-only item as a "fetch 3x" errand.
"""
import pygame
from .. import loot

ITEMS = {
    # id: (label, sell, colour, cat)
    "cursed_gear": ("Cursed Gear", 450, (170, 120, 196), "relic"),
    "city_key": ("City Key", 420, (232, 196, 110), "relic"),
}

for _iid, (_lab, _sell, _col, _cat) in ITEMS.items():
    loot.register_item(_iid, _lab, _sell, _col, _cat)


def paint_cursed_gear(s):
    """28x28: a bronze cog wreathed in violet mist with a glowing mint eye."""
    cx, cy = 14, 14
    import math
    pygame.draw.circle(s, (170, 120, 196, 90), (cx, cy), 13)
    for k in range(8):
        a = k * math.pi / 4
        pygame.draw.circle(s, (150, 112, 80), (cx + int(9 * math.cos(a)), cy + int(9 * math.sin(a))), 3)
    pygame.draw.circle(s, (190, 146, 98), (cx, cy), 8)
    pygame.draw.circle(s, (118, 84, 60), (cx, cy), 8, 2)
    pygame.draw.circle(s, (40, 32, 50), (cx, cy), 4)
    pygame.draw.circle(s, (140, 235, 190), (cx, cy), 2)
    pygame.draw.line(s, (220, 190, 240), (6, 5), (9, 8), 1)
    pygame.draw.line(s, (220, 190, 240), (22, 21), (19, 18), 1)


def paint_city_key(s):
    """28x28: an ornate old brass key with a tiny clock-face bow."""
    pygame.draw.line(s, (176, 140, 70), (12, 14), (24, 14), 4)
    pygame.draw.rect(s, (176, 140, 70), (19, 15, 3, 6))
    pygame.draw.rect(s, (176, 140, 70), (23, 15, 2, 5))
    pygame.draw.line(s, (246, 222, 150), (13, 13), (23, 13), 1)
    pygame.draw.circle(s, (232, 196, 110), (8, 14), 7)
    pygame.draw.circle(s, (150, 116, 60), (8, 14), 7, 2)
    pygame.draw.circle(s, (246, 240, 222), (8, 14), 4)
    pygame.draw.line(s, (90, 80, 100), (8, 14), (8, 11), 1)
    pygame.draw.line(s, (90, 80, 100), (8, 14), (10, 15), 1)


try:
    from ..assets import register_item_icon
    register_item_icon("cursed_gear", paint_cursed_gear)
    register_item_icon("city_key", paint_city_key)
except Exception:          # assets unavailable (tools / headless import order) -> label-only
    pass
