"""Wardrobe / mirror: change your outfit and hair without starting a new farm.

Opened from a Wardrobe or Dresser (starts on the shirt) or a Vanity / mirror
(starts on the hair). A live preview walks in place and slowly turns around
while you flip through the options.

  Up/Down     pick a row (hairstyle, hair colour, shirt)
  Left/Right  change it
  Action      keep this look          Esc / B  put everything back
"""
import pygame

from .settings import SCREEN_W, P1_KEYS, P2_KEYS
from . import ui_kit as K

FIELDS = [("hair_style", "Hairstyle"), ("hair_color", "Hair Colour"),
          ("shirt_color", "Shirt")]
_DIRS = ("down", "right", "up", "left")


def _count(field):
    from . import assets
    return {"hair_style": len(assets.HAIR_STYLES), "hair_color": len(assets.HAIR_COLORS),
            "shirt_color": len(assets.SHIRT_COLORS), "skin": len(assets.SKIN_TONES)}[field]


class WardrobeMenu:
    def __init__(self, game, pidx, kind="wardrobe", client=False):
        self.g = game
        self.pidx = pidx
        self.kind = kind
        self.client = client
        p = game.players[pidx]
        self.before = dict(p.appearance)
        self.look = dict(p.appearance)
        for f, _ in FIELDS:
            self.look.setdefault(f, 0)
        self.row = 2 if kind == "wardrobe" else 0
        self.clock = 0.0
        self.spin = 0.0
        self._frames = None
        self._key = None

    @property
    def p(self):
        return self.g.players[self.pidx]

    def _preview_frames(self):
        from . import assets
        key = tuple(sorted((k, v) for k, v in self.look.items() if k != "name"))
        if key != self._key:
            self._key = key
            self._frames = assets.frames_for(self.look, arms=False)
        return self._frames

    def handle_key(self, key):
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self.g._wardrobe_done(self, keep=False)
            return
        if key in (P1_KEYS["action"], P2_KEYS["action"]):
            self.g._wardrobe_done(self, keep=True)
            return
        if key in (P1_KEYS["up"], P2_KEYS["up"]):
            self.row = (self.row - 1) % len(FIELDS)
        elif key in (P1_KEYS["down"], P2_KEYS["down"]):
            self.row = (self.row + 1) % len(FIELDS)
        elif key in (P1_KEYS["left"], P2_KEYS["left"], P1_KEYS["right"], P2_KEYS["right"]):
            d = -1 if key in (P1_KEYS["left"], P2_KEYS["left"]) else 1
            f = FIELDS[self.row][0]
            self.look[f] = (int(self.look.get(f, 0)) + d) % _count(f)
            self.spin = 0.0
        else:
            return
        self.g.audio.play("ui_move")

    def update(self, dt):
        self.clock += dt
        self.spin += dt

    def draw(self, surf):
        from . import assets
        K.dim(surf, 150)
        pw, ph = 720, 440
        px, py = (SCREEN_W - pw) // 2, 150
        title = "Wardrobe" if self.kind == "wardrobe" else "Mirror"
        P = K.modal(surf, (px, py, pw, ph), title, K.font(28, True))
        K.blit_text(surf, K.font(15, True), f"{self.p.name}, looking good!", K.GOLD_TXT,
                    (P.centerx, P.y + 46))
        # preview on a little round rug, turning every ~0.9 s
        stage = pygame.Rect(P.x + 40, P.y + 76, 250, 280)
        K.well(surf, stage, radius=16)
        rug = (stage.centerx - 80, stage.bottom - 70, 160, 40)
        pygame.draw.ellipse(surf, (226, 172, 190), rug)
        pygame.draw.ellipse(surf, (206, 142, 166), rug, 3)
        frames = self._preview_frames()
        d = _DIRS[int(self.spin / 0.9) % 4]
        try:
            seq = frames[d]
            fr = seq[int(self.clock * 6) % len(seq)]
        except Exception:
            fr = assets.player_sprite(self.look)
        big = pygame.transform.scale(fr, (fr.get_width() * 4, fr.get_height() * 4))
        surf.blit(big, big.get_rect(midbottom=(stage.centerx, stage.bottom - 46)))
        # option rows
        x0 = P.x + 320
        for i, (f, lab) in enumerate(FIELDS):
            r = pygame.Rect(x0, P.y + 90 + i * 76, 360, 60)
            if i == self.row:
                K.row_cursor(surf, r, self.clock)
            else:
                K.well(surf, r, radius=10)
            K.blit_text(surf, K.font(14, True), lab, K.INK_SOFT, (r.x + 22, r.y + 16), align="left")
            n = _count(f)
            idx = int(self.look.get(f, 0)) % n
            val = pygame.Rect(r.x + 60, r.y + 28, r.w - 120, 24)
            if f == "hair_style":
                K.blit_text(surf, K.font(17, True), assets.HAIR_STYLES[idx].title(), K.INK,
                            val.center)
            else:
                pal = assets.HAIR_COLORS if f == "hair_color" else assets.SHIRT_COLORS
                sw = pygame.Rect(0, 0, 120, 20)
                sw.center = val.center
                pygame.draw.rect(surf, pal[idx], sw, border_radius=8)
                pygame.draw.rect(surf, K.INK_SOFT, sw, 2, border_radius=8)
            for side in (-1, 1):                          # < > arrows
                ax = val.x - 18 if side < 0 else val.right + 18
                ay = val.centery
                pts = ([(ax + 6, ay - 8), (ax - 6, ay), (ax + 6, ay + 8)] if side < 0 else
                       [(ax - 6, ay - 8), (ax + 6, ay), (ax - 6, ay + 8)])
                pygame.draw.polygon(surf, K.WOOD if i == self.row else K.INK_FAINT, pts)
            K.blit_text(surf, K.font(12, True), f"{idx + 1}/{n}", K.INK_FAINT,
                        (r.right - 14, r.y + 16), align="right")
        K.divider(surf, P.centerx, P.bottom - 38, 200, heart=True)
        K.blit_text(surf, K.font(13, True),
                    "Up/Down pick  -  Left/Right change  -  Action keep this look  -  "
                    "Esc put it back", K.INK_SOFT, (P.centerx, P.bottom - 20))
