"""Shared camera that follows the midpoint of both players, clamped to the area."""
from .settings import TILE, SCREEN_W, SCREEN_H


class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0

    def update(self, players, area):
        mx = sum(p.x for p in players) / len(players)
        my = sum(p.y for p in players) / len(players)
        tx = mx - SCREEN_W / 2
        ty = my - SCREEN_H / 2
        # clamp to map bounds; a map smaller than the screen (e.g. the Temple)
        # is centred instead of pinned to the top-left corner
        mw, mh = area.w * TILE, area.h * TILE
        if mw < SCREEN_W:
            tx = (mw - SCREEN_W) / 2
        else:
            tx = min(max(0, tx), mw - SCREEN_W)
        if mh < SCREEN_H:
            ty = (mh - SCREEN_H) / 2
        else:
            ty = min(max(0, ty), mh - SCREEN_H)
        # smooth follow
        self.x += (tx - self.x) * 0.12
        self.y += (ty - self.y) * 0.12
