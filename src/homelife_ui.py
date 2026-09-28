"""Home Life screens: the Aquarium menu and the Cat Tower card.

Pure UI (parchment ``ui_kit`` style); every mutation goes through the game
(``HomeLifeMixin._aqua_op`` / ``_cat_card_*``), which the LAN host also runs for
a client's presses.

Aquarium   Left/Right/Up/Down move (left of the first slot = your bag)
           Action  put a fish in / scoop it back out, or Feed
           F / E   feed the fish        Esc / B  close
Cat Tower  Up/Down pick, Action choose; Rename: type, Enter to keep, Esc cancel
"""
import math
import random

import pygame

from .settings import SCREEN_W, SCREEN_H, P1_KEYS, P2_KEYS
from . import ui_kit as K
from . import homelife as L


def _label(item):
    try:
        from .fridge import label
        return label(item)
    except Exception:
        return item.replace("_", " ").title()


def _is_fish(item):
    try:
        from .fishing import FISH
        return item in FISH
    except Exception:
        return False


def _keyset(key, name):
    return key in (P1_KEYS.get(name), P2_KEYS.get(name))


_ICONS = {}


def _icon(item, scale=1.0, flip=False):
    k = (item, scale, flip)
    s = _ICONS.get(k)
    if s is None:
        try:
            from . import assets
            ic = assets.item_icon(item)
        except Exception:
            ic = pygame.Surface((28, 28), pygame.SRCALPHA)
            pygame.draw.ellipse(ic, L.fish_color(item), (4, 9, 20, 10))
        if scale != 1.0:
            ic = pygame.transform.scale(ic, (int(ic.get_width() * scale),
                                             int(ic.get_height() * scale)))
        if flip:
            ic = pygame.transform.flip(ic, True, False)
        s = _ICONS[k] = ic
    return s


_WATER = {}


def _water(w, h):
    s = _WATER.get((w, h))
    if s is None:
        s = pygame.Surface((w, h))
        top, bot = (120, 196, 226), (40, 96, 150)
        for y in range(h):
            k = y / max(1, h - 1)
            pygame.draw.line(s, tuple(int(top[i] + (bot[i] - top[i]) * k) for i in range(3)),
                             (0, y), (w, y))
        _WATER[(w, h)] = s
    return s


# ======================================================================= aquarium
class AquariumMenu:
    """Two panes -- your bag (fish only) | the glass tank with 6 slots + Feed."""

    def __init__(self, game, pidx, tank, client=False):
        self.g = game
        self.pidx = pidx
        self._tank = tank
        self.gx, self.gy = tank.gx, tank.gy
        self.client = client
        self.side = 0 if self.bag_items() else 1
        self.sel_bag = 0
        self.sel_slot = 0
        self.clock = 0.0
        self.feed_t = None                   # seconds since Feed (menu tank)
        self.splash = []                     # [x, y, age] ripples where a fish dropped in
        self.closing = 0.0
        n = len(self.fish())
        self.msg = (f"{n} fish swimming. Feed them, or add a new friend." if n else
                    "An empty tank! Only fish from your bag can move in.")

    # ---- data ----
    @property
    def p(self):
        return self.g.players[self.pidx]

    @property
    def tank(self):
        home = self.g.world.home_furniture
        if any(q is self._tank for q in home):
            return self._tank
        for q in home:
            if q.kind == "aquarium" and q.gx == self.gx and q.gy == self.gy:
                self._tank = q
                return q
        return self._tank

    def fish(self):
        t = self.tank
        return [f for f in sorted(t.store) for _ in range(max(0, int(t.store[f])))][:L.TANK_CAP]

    def bag_items(self):
        inv = self.p.inv
        if inv is None:
            return []
        return [i for i in inv.item_order if inv.count(i) > 0 and _is_fish(i)]

    def _clamp(self):
        nb = len(self.bag_items())
        self.sel_bag = 0 if nb == 0 else max(0, min(self.sel_bag, nb - 1))
        self.sel_slot = max(0, min(self.sel_slot, L.TANK_CAP))

    # ---- actions ----
    def _op(self, op, item=""):
        ok, text = self.g._aqua_op(self.pidx, self.tank, op, item, client=self.client)
        if text:
            self.msg = text
        self._clamp()
        return ok

    def activate(self):
        self._clamp()
        if self.side == 0:
            items = self.bag_items()
            if not items:
                self.msg = "No fish in your bag - go fishing first!"
                self.g.audio.play("ui_move")
                return
            if self._op("put", items[self.sel_bag]):
                self.splash.append([random.uniform(0.3, 0.7), 0.0])
                self.sel_slot = min(len(self.fish()) - 1, L.TANK_CAP - 1)
            return
        if self.sel_slot >= L.TANK_CAP:
            self.feed()
            return
        fish = self.fish()
        if self.sel_slot < len(fish):
            self._op("take", fish[self.sel_slot])
        else:
            self.msg = "An empty spot - pick a fish from your bag (Left) to add one."
            self.g.audio.play("ui_move")

    def feed(self):
        if self._op("feed"):
            self.feed_t = 0.0

    def close(self):
        if not self.closing:
            self.closing = 0.01
            self.g.audio.play("ui_move")

    # ---- input ----
    def handle_event(self, e):
        if e.type == pygame.KEYDOWN:
            self.handle_key(e.key)

    def handle_key(self, key):
        if self.closing:
            return
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self.close()
            return
        if _keyset(key, "action"):
            self.activate()
            return
        if key in (pygame.K_f, pygame.K_e) or _keyset(key, "next"):
            self.feed()
            return
        self._clamp()
        up, down = _keyset(key, "up"), _keyset(key, "down")
        left, right = _keyset(key, "left"), _keyset(key, "right")
        if self.side == 0:
            n = len(self.bag_items())
            if up and n:
                self.sel_bag = (self.sel_bag - 1) % n
            elif down and n:
                self.sel_bag = (self.sel_bag + 1) % n
            elif right:
                self.side = 1
            else:
                return
        else:
            if left:
                if self.sel_slot == 0:
                    self.side = 0
                else:
                    self.sel_slot -= 1
            elif right and self.sel_slot < L.TANK_CAP:
                self.sel_slot += 1
            elif down:
                self.sel_slot = L.TANK_CAP
            elif up and self.sel_slot == L.TANK_CAP:
                self.sel_slot = max(0, len(self.fish()) - 1)
            else:
                return
        self.g.audio.play("ui_move")

    def update(self, dt):
        self.clock += dt
        if self.feed_t is not None:
            self.feed_t += dt
            if self.feed_t > 9.5:
                self.feed_t = None
        for s in self.splash:
            s[1] += dt
        self.splash = [s for s in self.splash if s[1] < 1.0]
        if self.closing:
            self.closing += dt
            if self.closing > 0.12:
                self.g._aqua_closed(self)

    # ---- draw ----
    def draw(self, surf):
        self._clamp()
        K.dim(surf, 150)
        pw, ph = 1060, 590
        px, py = (SCREEN_W - pw) // 2, 90
        P = K.modal(surf, (px, py, pw, ph), "Aquarium", K.font(28, True))
        K.blit_text(surf, K.font(14, True), f"{self.p.name} at the fish tank",
                    K.INK_SOFT, (P.x + 200, P.y + 44))
        self._draw_bag(surf, pygame.Rect(P.x + 22, P.y + 64, 300, ph - 150))
        tank = pygame.Rect(P.x + 352, P.y + 60, 680, 318)
        fishpos = self._draw_tank(surf, tank)
        self._draw_slots(surf, pygame.Rect(tank.x, tank.bottom + 16, tank.w, 70), fishpos)
        info_y = P.bottom - 70
        fish = self.fish()
        if self.side == 0 and self.bag_items():
            it = self.bag_items()[self.sel_bag]
            txt = f"{_label(it)}  x{self.p.inv.count(it)} in your bag  -  Action: put it in the tank"
        elif self.side == 1 and self.sel_slot < len(fish):
            it = fish[self.sel_slot]
            txt = f"{_label(it)} ({self._tier(it)})  -  Action: scoop it back into your bag"
        elif self.side == 1 and self.sel_slot >= L.TANK_CAP:
            txt = "Feed: a pinch of flakes (free) - the fish rush up to eat"
        else:
            txt = f"{len(fish)} / {L.TANK_CAP} fish"
        f = K.fit_font(txt, pw - 60, (16, 15, 14, 13), bold=True)
        K.blit_text(surf, f, txt, K.INK, (P.centerx, info_y))
        mf = K.fit_font(self.msg, pw - 60, (15, 14, 13, 12), bold=True)
        K.blit_text(surf, mf, self.msg, K.GOLD_TXT, (P.centerx, info_y + 22))
        K.divider(surf, P.centerx, P.bottom - 30, 170, heart=True)
        K.blit_text(surf, K.font(12, True),
                    "Arrows move  -  Action put / take  -  F feed  -  Esc close",
                    K.INK_SOFT, (P.centerx, P.bottom - 15))

    @staticmethod
    def _tier(item):
        try:
            from .fishing import tier_of
            return tier_of(item)
        except Exception:
            return "fish"

    def _draw_bag(self, surf, box):
        active = self.side == 0
        K.well(surf, box, hot=active, radius=12)
        K.blit_text(surf, K.font(18, True), "Your Bag", K.INK if active else K.INK_SOFT,
                    (box.x + 16, box.y + 20), align="left")
        K.blit_text(surf, K.font(12, True), "fish only", K.INK_FAINT,
                    (box.right - 14, box.y + 21), align="right")
        items = self.bag_items()
        pitch, vis = 38, (box.h - 52) // 38
        top = box.y + 42
        if not items:
            for i, ln in enumerate(("(no fish in your bag)", "cast a line at the pond,",
                                    "then bring them home!")):
                K.blit_text(surf, K.font(14), ln, K.INK_FAINT, (box.centerx, top + 50 + i * 20))
            return
        start = 0
        if len(items) > vis:
            start = max(0, min(self.sel_bag - vis // 2, len(items) - vis))
        rf = K.font(15, True)
        for vi, it in enumerate(items[start:start + vis]):
            i = start + vi
            r = pygame.Rect(box.x + 8, top + vi * pitch, box.w - 16, 34)
            if i == self.sel_bag:
                if active:
                    K.row_cursor(surf, r, self.clock)
                else:
                    pygame.draw.rect(surf, (234, 214, 180), r, border_radius=10)
            ic = _icon(it)
            surf.blit(ic, (r.x + 16, r.centery - ic.get_height() // 2))
            q = f"x{self.p.inv.count(it)}"
            qw = rf.size(q)[0]
            K.blit_text(surf, rf, q, K.GOLD_TXT, (r.right - 10, r.centery), align="right")
            K.blit_text(surf, rf, K.ellipsize(rf, _label(it), r.w - 70 - qw),
                        K.INK if active else K.INK_SOFT, (r.x + 50, r.centery), align="left")

    def _feed_k(self):
        return L.feed_curve(self.feed_t)

    def _draw_tank(self, surf, box):
        """A big front view of the tank; returns {slot index: fish screen pos}."""
        t = self.clock
        # wooden stand + glass frame
        pygame.draw.rect(surf, (118, 82, 56), (box.x - 8, box.bottom - 6, box.w + 16, 22),
                         border_radius=6)
        pygame.draw.rect(surf, (92, 62, 44), (box.x - 8, box.bottom - 6, box.w + 16, 22), 2,
                         border_radius=6)
        pygame.draw.rect(surf, (60, 62, 70), box.inflate(12, 12), border_radius=10)
        inner = box.copy()
        clip0 = surf.get_clip()
        surf.set_clip(inner.clip(clip0) if clip0 else inner)   # everything stays in the glass
        surf.blit(_water(inner.w, inner.h), inner.topleft)
        wl = inner.y + 26                               # waterline
        pygame.draw.rect(surf, (196, 230, 244), (inner.x, inner.y, inner.w, wl - inner.y))
        for x in range(inner.x, inner.right, 4):        # gentle surface ripple
            yy = wl + math.sin(t * 2.2 + x * 0.05) * 1.6
            pygame.draw.line(surf, (226, 246, 252), (x, yy), (x + 3, yy), 2)
        # light rays
        rays = pygame.Surface(inner.size, pygame.SRCALPHA)
        for i in range(4):
            x0 = 80 + i * 170 + math.sin(t * 0.4 + i) * 20
            pygame.draw.polygon(rays, (255, 255, 240, 22),
                                [(x0, 26), (x0 + 40, 26), (x0 - 40, inner.h), (x0 - 110, inner.h)])
        surf.blit(rays, inner.topleft)
        # sand + pebbles
        sand = pygame.Rect(inner.x, inner.bottom - 40, inner.w, 40)
        pygame.draw.ellipse(surf, (214, 190, 138), sand.inflate(60, 30).move(0, 16))
        pygame.draw.rect(surf, (214, 190, 138), (inner.x, inner.bottom - 22, inner.w, 22))
        rnd = random.Random(7)
        for _ in range(26):
            x = rnd.randint(inner.x + 6, inner.right - 10)
            y = rnd.randint(inner.bottom - 20, inner.bottom - 6)
            c = rnd.choice(((176, 150, 120), (150, 160, 170), (196, 120, 110), (236, 222, 190)))
            pygame.draw.ellipse(surf, c, (x, y, rnd.randint(5, 9), rnd.randint(3, 5)))
        # plants + a little castle rock
        for bx, n, h in ((inner.x + 60, 4, 150), (inner.right - 120, 3, 120),
                         (inner.x + 300, 2, 80)):
            for j in range(n):
                pts = []
                for i in range(9):
                    k = i / 8
                    sw = math.sin(t * 1.5 + j + k * 3) * 10 * k
                    pts.append((bx + j * 12 + sw, inner.bottom - 12 - k * (h - j * 14)))
                pygame.draw.lines(surf, (48, 118, 76), False, pts, 7)
                pygame.draw.lines(surf, (104, 184, 110), False, pts, 3)
        ck = pygame.Rect(inner.right - 230, inner.bottom - 86, 70, 70)
        pygame.draw.rect(surf, (150, 146, 160), ck, border_radius=6)
        pygame.draw.rect(surf, (120, 116, 132), ck, 3, border_radius=6)
        for i in range(3):
            pygame.draw.rect(surf, (150, 146, 160), (ck.x + i * 26, ck.y - 12, 16, 14))
        pygame.draw.ellipse(surf, (54, 60, 80), (ck.centerx - 11, ck.bottom - 32, 22, 32))
        # bubbles from an air stone by the castle
        stone = (inner.right - 262, inner.bottom - 20)
        pygame.draw.ellipse(surf, (110, 116, 128), (stone[0] - 9, stone[1] - 5, 18, 9))
        for i in range(7):
            k = ((t * 0.35) + i / 7) % 1.0
            x = stone[0] + math.sin(t * 3 + i * 2) * 5 * k
            y = stone[1] - 6 - k * (inner.h - 60)
            pygame.draw.circle(surf, (226, 244, 250), (int(x), int(y)), 2 + int(k * 4), 1)
        for s in self.splash:                           # plop! rings at the surface
            x = inner.x + s[0] * inner.w
            r = int(6 + s[1] * 40)
            pygame.draw.ellipse(surf, (240, 250, 255), (x - r, wl - r // 4, 2 * r, r // 2), 2)
        # flakes
        fk = self._feed_k()
        if self.feed_t is not None and self.feed_t < 6.5:
            rnd = random.Random(3)
            for i in range(24):
                fx = inner.centerx + rnd.uniform(-160, 160)
                fy = wl + self.feed_t * rnd.uniform(18, 40)
                if fy < inner.bottom - 20 and self.feed_t < 4.5 + i * 0.08:
                    pygame.draw.rect(surf, (236, 170, 90), (fx + math.sin(t * 3 + i) * 3, fy, 3, 2))
        # the fish (icons twice size, facing where they swim)
        pos = {}
        fish = self.fish()
        for k, fid in enumerate(fish):
            w, p1, p2, p3, r2, zc = L._fish_params(fid, k, (self.gx, self.gy))
            ax, ay = inner.w * 0.38, (inner.h - 90) * 0.34
            cx, cy = inner.centerx, inner.y + 30 + (inner.h - 90) * 0.5 + zc * 4
            x = cx + ax * math.sin(w * t + p1)
            y = cy + ay * math.sin(w * r2 * t * 1.3 + p2)
            dx = ax * w * math.cos(w * t + p1)
            if fk > 0:
                tx = inner.centerx + math.cos(k * 1.9 + t * 1.3) * 90
                x += (tx - x) * fk * 0.8
                y += (wl + 24 - y) * fk
                dx = -math.sin(k * 1.9 + t * 1.3) if fk > 0.5 else dx
            wig = math.sin(t * (6 + 5 * fk) + k) * 2
            ic = _icon(fid, 2.0, flip=dx > 0)
            r = ic.get_rect(center=(int(x), int(y + wig * 0.5)))
            surf.blit(ic, r)
            pos[k] = r
        # selection ring on the chosen fish
        if self.side == 1 and self.sel_slot in pos:
            r = pos[self.sel_slot]
            pulse = 0.5 + 0.5 * math.sin(t * 5)
            pygame.draw.ellipse(surf, (255, 236, 160), r.inflate(10 + pulse * 4, 6 + pulse * 3), 2)
            nm = _label(fish[self.sel_slot])
            tag = K.outlined(K.font(13, True), nm, (255, 250, 236))
            surf.blit(tag, tag.get_rect(midbottom=(r.centerx, r.y - 2)))
        surf.set_clip(clip0)
        # glass sheen + frame
        pygame.draw.line(surf, (236, 250, 255), (inner.x + 16, inner.y + 34),
                         (inner.x + 16, inner.bottom - 30), 2)
        pygame.draw.line(surf, (236, 250, 255), (inner.x + 24, inner.y + 34),
                         (inner.x + 24, inner.y + 80), 1)
        pygame.draw.rect(surf, (72, 74, 84), box.inflate(12, 12), 6, border_radius=10)
        pygame.draw.rect(surf, (60, 62, 70), (box.x - 10, box.y - 14, box.w + 20, 12),
                         border_radius=4)                # lid
        if not fish:
            K.blit_text(surf, K.font(18, True), "(an empty tank)", (220, 240, 250),
                        (inner.centerx, inner.centery - 10))
        return pos

    def _draw_slots(self, surf, row, fishpos):
        fish = self.fish()
        n = L.TANK_CAP
        sw, gap = 70, 12
        feed_w = 150
        total = n * sw + (n - 1) * gap + 24 + feed_w
        x = row.centerx - total // 2
        active = self.side == 1
        for i in range(n):
            r = pygame.Rect(x + i * (sw + gap), row.y, sw, 60)
            hot = active and self.sel_slot == i
            K.well(surf, r, hot=hot, radius=10)
            if i < len(fish):
                ic = _icon(fish[i], 1.5)
                bob = int(math.sin(self.clock * 6) * 1.5) if hot else 0
                surf.blit(ic, ic.get_rect(center=(r.centerx, r.centery + bob)))
            else:
                K.blit_text(surf, K.font(20, True), "+", K.INK_FAINT, r.center)
        fr = pygame.Rect(x + n * (sw + gap) + 12, row.y + 6, feed_w, 48)
        K.button(surf, fr, "Feed (F)", selected=active and self.sel_slot >= n,
                 fnt=K.font(18, True))


# ======================================================================= cat card
class CatTowerCard:
    """The cat's little card: portrait, name, affection; call or rename."""

    OPTS = ("call", "rename", "close")

    def __init__(self, game, pidx, client=False):
        self.g = game
        self.pidx = pidx
        self.client = client
        self.sel = 0
        self.clock = 0.0
        self.naming = None                   # text being typed, or None
        self.msg = ""

    @property
    def name(self):
        return self.g.cat_name

    def handle_event(self, e):
        if e.type != pygame.KEYDOWN:
            return
        if self.naming is not None:
            self._type(e)
            return
        key = e.key
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self.g._cat_card_closed(self)
            self.g.audio.play("ui_move")
        elif _keyset(key, "up"):
            self.sel = (self.sel - 1) % len(self.OPTS)
            self.g.audio.play("ui_move")
        elif _keyset(key, "down") or key == pygame.K_TAB:
            self.sel = (self.sel + 1) % len(self.OPTS)
            self.g.audio.play("ui_move")
        elif _keyset(key, "action"):
            self.choose()

    def choose(self):
        opt = self.OPTS[self.sel]
        if opt == "call":
            self.g._cat_card_call(self)
            self.g._cat_card_closed(self)
        elif opt == "rename":
            self.naming = ""
            self.g.audio.play("ui_select")
        else:
            self.g._cat_card_closed(self)
            self.g.audio.play("ui_move")

    def _type(self, e):
        if e.key == pygame.K_ESCAPE:
            self.naming = None
            self.g.audio.play("ui_move")
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.naming.strip():
                self.g._cat_card_rename(self, self.naming)
                self.msg = f"Hello, {self.name}!"
            self.naming = None
        elif e.key == pygame.K_BACKSPACE:
            self.naming = self.naming[:-1]
        else:
            ch = getattr(e, "unicode", "") or ""
            if len(ch) == 1 and (ch.isalnum() or ch in " -'") and len(self.naming) < 12:
                self.naming += ch

    def update(self, dt):
        self.clock += dt

    def _mood(self):
        c = self.g.cat
        if c is None:
            return "is out of sight", "sit"
        pose = getattr(c, "pose", "sit")
        q = None
        try:
            from . import furniture as F
            if c.z > 1:
                q = next((o for o in self.g.world.home_furniture
                          if F.CAT[o.kind]["layer"] == "ground" and (int(c.x), int(c.y)) in o.cells()),
                         None)
        except Exception:
            q = None
        where = {"cat_tower": "up on the tower", "sofa": "on the sofa", "armchair": "in the armchair",
                 "bed": "at the foot of the bed"}.get(q.kind if q else "", "")
        if pose == "sleep":
            return f"is napping {where or 'in a sunny spot'}", "sleep"
        if pose == "walk":
            return "is padding around the room", "sit"
        if pose == "groom":
            return "is grooming a paw", "groom"
        if pose == "happy":
            return "is purring away", "happy"
        return f"is sitting {where or 'politely'}", "sit"

    def draw(self, surf):
        K.dim(surf, 150)
        pw, ph = 640, 400
        px, py = (SCREEN_W - pw) // 2, (SCREEN_H - ph) // 2
        P = K.modal(surf, (px, py, pw, ph), "Cat Tower", K.font(26, True))
        mood, pose = self._mood()
        # portrait
        pr = pygame.Rect(P.x + 30, P.y + 58, 220, 230)
        K.well(surf, pr, radius=14)
        pygame.draw.ellipse(surf, (230, 206, 170), (pr.x + 30, pr.bottom - 52, pr.w - 60, 30))
        fr = int(self.clock * (0.7 if pose == "sleep" else 1.6)) % L.FRAMES.get(pose, 1)
        img = L.cat_portrait(pose, fr, 5)
        surf.blit(img, img.get_rect(midbottom=(pr.centerx, pr.bottom - 26 + 20)))
        # name + affection
        x = pr.right + 28
        name = self.naming if self.naming is not None else self.name
        if self.naming is not None:
            box = pygame.Rect(x - 6, P.y + 60, 330, 44)
            K.well(surf, box, hot=True, radius=8)
            caret = "_" if int(self.clock * 2) % 2 == 0 else " "
            K.blit_text(surf, K.font(28, True), name + caret, K.INK, (x + 6, box.centery),
                        align="left")
        else:
            K.blit_text(surf, K.font(32, True), name, K.INK, (x, P.y + 82), align="left")
        K.blit_text(surf, K.font(15, True), f"{name if name else 'The cat'} {mood}.",
                    K.INK_SOFT, (x, P.y + 122), align="left")
        love = int(getattr(self.g, "cat_love", 0))
        K.blit_text(surf, K.font(14, True), "Affection", K.SPROUT, (x, P.y + 152), align="left")
        full = love / 10.0
        def heart(hx, hy, col):
            for dx in (-4, 4):
                pygame.draw.circle(surf, col, (hx + dx, hy - 2), 6)
            pygame.draw.polygon(surf, col, [(hx - 10, hy), (hx + 10, hy), (hx, hy + 10)])
        clip0 = surf.get_clip()
        for i in range(10):
            hx, hy = x + 8 + i * 30, P.y + 180
            k = max(0.0, min(1.0, full - i))
            heart(hx, hy, (238, 214, 204))
            if k > 0:                               # filled up to the affection level
                surf.set_clip(pygame.Rect(hx - 11, hy - 10, int(22 * k), 22).clip(clip0))
                heart(hx, hy, K.HEART)
                surf.set_clip(clip0)
        K.blit_text(surf, K.font(13, True), f"{love} / 100", K.INK_SOFT, (x + 300, P.y + 152),
                    align="right")
        pets = list(getattr(self.g, "_cat_pets", [0, 0]))
        if getattr(self.g, "_cat_day", None) != self.g._today():
            pets = [0, 0]
        who = "  -  ".join(f"{p.name}: {pets[i] if i < len(pets) else 0}"
                           for i, p in enumerate(self.g.players))
        K.blit_text(surf, K.font(13, True), f"Pets today  {who}", K.INK_SOFT, (x, P.y + 208),
                    align="left")
        # options
        labels = {"call": f"Call {self.name} for pets", "rename": "Rename", "close": "Close"}
        for i, o in enumerate(self.OPTS):
            r = pygame.Rect(x - 4, P.y + 232 + i * 44, 330, 38)
            K.button(surf, r, labels[o], selected=(i == self.sel and self.naming is None),
                     fnt=K.font(17, True))
        hint = ("Type a name  -  Enter keep  -  Esc cancel" if self.naming is not None else
                self.msg or "Up/Down choose  -  Action select  -  Esc close")
        K.blit_text(surf, K.font(12, True), hint, K.INK_SOFT, (P.centerx, P.bottom - 16))
