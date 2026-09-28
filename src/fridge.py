"""The Fridge: a real kitchen fridge you open, stock and eat from.

Interact with a placed Fridge in the house. The door swings open (the piece in
the room opens too), revealing a lit interior: a frosty freezer shelf on top
(fish & meat), glass shelves below, and a door full of sauces and magnets.

  Left/Right/Up/Down  move (left of the first shelf column = your bag)
  Action              move 1 item   (bag <-> fridge)
  Shift+Action        move the whole stack
  E  /  .             eat or drink the selected item right from the fridge
  Esc / B             shut the door

Only food belongs in a fridge: crops, fish, animal produce, forage snacks,
artisan goods and cooked dishes. Contents live on the piece's ``Placed.store``
(saved with the house), and the Stove cooks with whatever is inside every
fridge in the house (``HomeMixin._kitchen_count``).

Pure UI + rules; the mutations go through ``game._fridge_op`` (HomeMixin), which
the LAN host also runs for a client's fridge presses.
"""
import math
import random
import pygame

from .settings import SCREEN_W, P1_KEYS, P2_KEYS
from . import ui_kit as K

OPEN_T = 0.36          # door swing, seconds
CLOSE_T = 0.26
COLS = 5               # items per shelf
SHELVES = 4            # glass shelves under the freezer (freezer = row 0)
ROWS = SHELVES + 1

_FROZEN_EXTRA = {"meat", "clam", "sea_urchin"}
_DRINK_PREFIX = ("juice_", "wine_")
_DRINKS = {"milk", "goat_milk", "milk_tea", "honey_tea", "mead"}
_ANIMAL = {"egg", "duck_egg", "milk", "goat_milk", "meat"}
_FRUITISH_FORAGE = {"apple", "persimmon", "clam", "sea_urchin"}


# ------------------------------------------------------------------ rules
def _fish():
    try:
        from .fishing import FISH
        return FISH
    except Exception:
        return {}


def is_fridge_food(item):
    """True for things that belong in a fridge (food & drink of any kind)."""
    if not item or item.startswith("seed:"):
        return False
    from . import cooking
    from .crops import CROPS
    if item in cooking.FOODS or item in CROPS or item in _ANIMAL or item in _fish():
        return True
    if item in _DRINKS or item.startswith(_DRINK_PREFIX):
        return True
    try:
        from . import loot
        cat = loot.MATERIALS.get(item, {}).get("cat")
    except Exception:
        cat = None
    if cat == "artisan":
        return True
    if cat == "forage":
        try:
            from .forage import EDIBLE
        except Exception:
            EDIBLE = {}
        return item in EDIBLE or item in _FRUITISH_FORAGE
    return False


def is_frozen(item):
    """Goes on the freezer shelf (fish & raw meat)."""
    return item in _fish() or item in _FROZEN_EXTRA


def is_drink(item):
    return item in _DRINKS or item.startswith(_DRINK_PREFIX)


# drinks and fruit you can simply have from the fridge (energy)
_AS_IS = {"milk": 25, "goat_milk": 30, "mead": 25, "apple": 20, "persimmon": 20}


def eat_info(item):
    """(energy, health, verb) if the item can be eaten/drunk, else None."""
    from . import cooking
    if item in _AS_IS:
        return _AS_IS[item], 0, ("drink" if is_drink(item) else "eat")
    if item.startswith("juice_"):
        return 30, 5, "drink"
    if item.startswith("wine_"):
        return 20, 0, "drink"
    if item in cooking.FOODS:
        f = cooking.FOODS[item]
        drink = bool(f.get("drink", False))
        return f["energy"], f["health"], ("drink" if drink else "eat")
    try:
        from .forage import EDIBLE
    except Exception:
        EDIBLE = {}
    if item in EDIBLE:
        return EDIBLE[item], 0, "eat"
    return None


def label(item_id):
    from . import cooking, loot
    if item_id.startswith("seed:"):                  # same names as the bag
        try:
            from .inventory import Inventory
            return Inventory.label(("item", item_id))
        except Exception:
            return item_id.split(":", 1)[1].replace("_", " ").title() + " Seeds"
    if item_id in cooking.FOODS:
        return cooking.FOODS[item_id]["label"]
    try:
        return loot.label(item_id)
    except Exception:
        return item_id.replace("_", " ").title()


def _order_key(item):
    """Freezer goods first, then dishes, produce, drinks -- like a real fridge."""
    from . import cooking
    if is_frozen(item):
        grp = 0
    elif item in cooking.FOODS and not is_drink(item):
        grp = 1
    elif is_drink(item):
        grp = 3
    else:
        grp = 2
    return (grp, label(item))


def sorted_contents(store):
    return sorted((k for k, q in store.items() if q > 0), key=_order_key)


def layout(store):
    """Rows of item ids as they sit in the fridge: row 0 is the freezer (fish &
    meat only), then glass shelves of COLS each. Freezer overflow and everything
    else fill the shelves; there is always at least one (maybe empty) shelf."""
    items = sorted_contents(store)
    frozen = [i for i in items if is_frozen(i)]
    rest = frozen[COLS:] + [i for i in items if not is_frozen(i)]
    rows = [frozen[:COLS]]
    for k in range(0, len(rest), COLS):
        rows.append(rest[k:k + COLS])
    if len(rows) == 1:
        rows.append([])
    return rows


# ------------------------------------------------------------------ colour helpers
def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _dk(c, f=0.7):
    return tuple(max(0, int(v * f)) for v in c)


def _lt(c, f=1.2):
    return tuple(min(255, int(v * f)) for v in c)


_BIG_ICONS = {}


def _big_icon(item):
    s = _BIG_ICONS.get(item)
    if s is None:
        from . import assets
        try:
            ic = assets.item_icon(item)
            s = pygame.transform.scale(ic, (ic.get_width() * 3 // 2, ic.get_height() * 3 // 2))
        except Exception:
            s = pygame.Surface((42, 42), pygame.SRCALPHA)
        _BIG_ICONS[item] = s
    return s


# ------------------------------------------------------------------ menu
class FridgeMenu:
    """Two panes -- your bag (food only) | the open fridge's shelves."""

    def __init__(self, game, pidx, fridge, client=False):
        self.g = game
        self.pidx = pidx
        self._fr = fridge
        self.gx, self.gy = fridge.gx, fridge.gy
        self.client = client            # LAN client: ops are sent to the host
        self.side = 1 if fridge.store else 0
        self.sel_bag = 0
        self.sel_fr = 0
        self.phase = "opening"
        self.t = 0.0                    # phase clock
        self.clock = 0.0                # free-running (pulses, mist)
        self.msg = ("Cold and cosy. Only food & drinks go in here." if fridge.store
                    else "It's empty! Stock it with food from your bag.")
        self.mist = []                  # cold air puffs rolling out of the door
        self.light = 0.0                # interior light warm-up

    # ---- data ----
    @property
    def p(self):
        return self.g.players[self.pidx]

    @property
    def fr(self):
        """The live fridge piece (a LAN world resync replaces Placed objects)."""
        home = self.g.world.home_furniture
        if any(q is self._fr for q in home):
            return self._fr
        for q in home:
            if q.kind == "fridge" and q.gx == self.gx and q.gy == self.gy:
                self._fr = q
                return q
        return self._fr

    def bag_items(self):
        inv = self.p.inv
        if inv is None:
            return []
        return [i for i in inv.item_order if inv.count(i) > 0 and is_fridge_food(i)]

    def fridge_rows(self):
        return layout(self.fr.store)

    def fridge_items(self):
        """Flat list in layout order (sel_fr indexes this)."""
        return [it for row in self.fridge_rows() for it in row]

    def _rc(self, rows, idx):
        """(row, col) of flat index ``idx`` in ``rows``."""
        for r, row in enumerate(rows):
            if idx < len(row):
                return r, idx
            idx -= len(row)
        return 0, 0

    @staticmethod
    def _flat(rows, r, c):
        return sum(len(rows[k]) for k in range(r)) + c

    def _clamp(self):
        nb, nf = len(self.bag_items()), len(self.fridge_items())
        self.sel_bag = 0 if nb == 0 else max(0, min(self.sel_bag, nb - 1))
        self.sel_fr = 0 if nf == 0 else max(0, min(self.sel_fr, nf - 1))

    def selected(self):
        self._clamp()
        if self.side == 0:
            lst = self.bag_items()
            return lst[self.sel_bag] if lst else None
        lst = self.fridge_items()
        return lst[self.sel_fr] if lst else None

    # ---- actions ----
    def _op(self, op, item, n=1):
        ok, text = self.g._fridge_op(self.pidx, self.fr, op, item, n, client=self.client)
        if text:
            self.msg = text
        if ok:
            self._clamp()
        return ok

    def transfer(self, whole=False):
        item = self.selected()
        if item is None:
            self.msg = ("Your bag has no food to put away." if self.side == 0
                        else "The shelves are empty.")
            self.g.audio.play("ui_move")
            return
        if self.side == 0:
            n = self.p.inv.count(item) if whole else 1
            self._op("put", item, n)
        else:
            n = self.fr.store.get(item, 0) if whole else 1
            self._op("take", item, n)

    def eat(self):
        if self.side == 0:
            self.msg = "Pick something on the fridge shelves to eat it."
            self.g.audio.play("ui_move")
            return
        item = self.selected()
        if item is None:
            self.msg = "Nothing to snack on... the fridge is empty."
            self.g.audio.play("ui_move")
            return
        if eat_info(item) is None:
            from . import cooking
            if not is_fridge_food(item):
                self.msg = f"{label(item)} isn't food - take it out to use it."
            elif any(item in need for need in cooking.RECIPES.values()):
                self.msg = f"{label(item)} needs cooking first - try the Stove."
            else:
                self.msg = f"{label(item)} can't be eaten as is."
            self.g.audio.play("ui_move")
            return
        self._op("eat", item, 1)

    def close(self):
        if self.phase != "closing":
            self.phase = "closing"
            self.t = 0.0
            self.g.audio.play("fridge_close" if "fridge_close" in getattr(
                self.g.audio, "sfx", {}) else "ui_move")

    # ---- input ----
    def handle_key(self, key):
        if self.phase == "closing":
            return
        if key in (pygame.K_ESCAPE, pygame.K_b):
            self.close()
            return
        up = key in (P1_KEYS["up"], P2_KEYS["up"])
        down = key in (P1_KEYS["down"], P2_KEYS["down"])
        left = key in (P1_KEYS["left"], P2_KEYS["left"])
        right = key in (P1_KEYS["right"], P2_KEYS["right"])
        if key in (P1_KEYS["action"], P2_KEYS["action"]):
            self.transfer(bool(pygame.key.get_mods() & pygame.KMOD_SHIFT))
            return
        if key in (pygame.K_e, P1_KEYS.get("next"), P2_KEYS.get("next")):
            self.eat()
            return
        self._clamp()
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
            rows = self.fridge_rows()
            n = sum(len(row) for row in rows)
            r, c = self._rc(rows, self.sel_fr)
            if left:
                if c == 0 or n == 0:
                    self.side = 0
                else:
                    self.sel_fr -= 1
            elif right and n and c + 1 < len(rows[r]):
                self.sel_fr += 1
            elif (up or down) and n:
                step = -1 if up else 1
                r2 = r + step
                while 0 <= r2 < len(rows) and not rows[r2]:
                    r2 += step                        # skip an empty freezer row
                if not 0 <= r2 < len(rows):
                    return
                self.sel_fr = self._flat(rows, r2, min(c, len(rows[r2]) - 1))
            else:
                return
        self.g.audio.play("ui_move")

    def update(self, dt):
        self.clock += dt
        self.t += dt
        if self.phase == "opening" and self.t >= OPEN_T:
            self.phase, self.t = "open", 0.0
        if self.phase == "closing" and self.t >= CLOSE_T:
            self.g._fridge_closed(self)
            return
        if self.phase != "closing":
            self.light = min(1.0, self.light + dt * 5)
        else:
            self.light = max(0.0, self.light - dt * 6)
        # a puff of cold fog spills out along the floor as the door opens
        if self.phase != "closing" and self.clock < 1.2 and random.random() < dt * 30:
            self.mist.append([random.uniform(0.0, 1.0), random.choice((-1, 1)), 0.0,
                              random.uniform(1.0, 1.8)])
        for m in self.mist:
            m[2] += dt
        self.mist = [m for m in self.mist if m[2] < m[3]]

    # ---- door geometry ----
    def _swing(self):
        """Door angle 0 (shut) .. 1 (wide open), eased."""
        if self.phase == "opening":
            k = min(1.0, self.t / OPEN_T)
            return 1 - (1 - k) ** 3
        if self.phase == "closing":
            k = min(1.0, self.t / CLOSE_T)
            return 1 - k * k
        return 1.0

    # ---- draw ----
    def draw(self, surf):
        self._clamp()
        color = self._piece_color()
        K.dim(surf, 150)
        pw, ph = 1060, 576
        px, py = (SCREEN_W - pw) // 2, 118
        P = K.modal(surf, (px, py, pw, ph), "Fridge", K.font(28, True))
        K.blit_text(surf, K.font(14, True), f"{self.p.name} raiding the fridge",
                    K.INK_SOFT, (P.x + 190, P.y + 44))
        self._draw_bag(surf, pygame.Rect(P.x + 22, P.y + 64, 340, ph - 150))
        body = pygame.Rect(P.x + 420, P.y + 50, 400, 432)
        self._draw_fridge(surf, body, color)
        # info strip
        item = self.selected()
        info_y = P.bottom - 72
        if item:
            nm = label(item)
            ei = eat_info(item)
            extra = ""
            if ei and self.side == 1:
                e, h, verb = ei
                extra = f"   -   E: {verb} (+{e} energy" + (f", +{h} HP)" if h else ")")
            where = ("in your bag" if self.side == 0 else
                     "in the freezer" if self._rc(self.fridge_rows(), self.sel_fr)[0] == 0
                     else "on the shelf")
            qty = (self.p.inv.count(item) if self.side == 0 else self.fr.store.get(item, 0))
            txt = f"{nm}  x{qty} {where}{extra}"
            f = K.fit_font(txt, pw - 60, (16, 15, 14, 13), bold=True)
            K.blit_text(surf, f, txt, K.INK, (P.centerx, info_y))
        mf = K.fit_font(self.msg, pw - 60, (15, 14, 13, 12), bold=True)
        K.blit_text(surf, mf, self.msg, K.GOLD_TXT, (P.centerx, info_y + 22))
        K.divider(surf, P.centerx, P.bottom - 30, 170, heart=False)
        K.blit_text(surf, K.font(12, True),
                    "Arrows move  -  Action put/take 1  -  Shift+Action whole stack  -  "
                    "E / .  eat  -  Esc shut the door", K.INK_SOFT, (P.centerx, P.bottom - 15))

    def _piece_color(self):
        from . import furniture as F
        try:
            return F.PALETTE[self.fr.ci % len(F.PALETTE)][1]
        except Exception:
            return (236, 236, 240)

    def _draw_bag(self, surf, box):
        from . import assets
        active = self.side == 0
        K.well(surf, box, hot=active, radius=12)
        K.blit_text(surf, K.font(18, True), "Your Bag", K.INK if active else K.INK_SOFT,
                    (box.x + 16, box.y + 20), align="left")
        K.blit_text(surf, K.font(12, True), "food only", K.INK_FAINT,
                    (box.right - 14, box.y + 21), align="right")
        items = self.bag_items()
        pitch, vis = 38, (box.h - 52) // 38
        top = box.y + 42
        if not items:
            f = K.font(14)
            for i, ln in enumerate(("(no food in your bag)", "harvest, fish or cook",
                                    "something first!")):
                K.blit_text(surf, f, ln, K.INK_FAINT, (box.centerx, top + 50 + i * 20))
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
            try:
                ic = assets.item_icon(it)
                surf.blit(ic, (r.x + 16, r.centery - ic.get_height() // 2))
            except Exception:
                pass
            q = f"x{self.p.inv.count(it)}"
            qw = rf.size(q)[0]
            K.blit_text(surf, rf, q, K.GOLD_TXT, (r.right - 10, r.centery), align="right")
            K.blit_text(surf, rf, K.ellipsize(rf, label(it), r.w - 70 - qw),
                        K.INK if active else K.INK_SOFT, (r.x + 50, r.centery), align="left")
        if len(items) > vis:
            K.blit_text(surf, K.font(12, True), f"{start + 1}-{min(start + vis, len(items))} / "
                        f"{len(items)}", K.INK_SOFT, (box.centerx, box.bottom - 10))

    def _draw_fridge(self, surf, body, color):
        sw = self._swing()
        rim = _dk(color, 0.55)
        light = self.light
        # cast shadow + body shell
        sh = pygame.Surface((body.w + 40, 24), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (40, 26, 20, 70), sh.get_rect())
        surf.blit(sh, (body.x - 20, body.bottom - 10))
        pygame.draw.rect(surf, _dk(color, 0.82), body.inflate(6, 6), border_radius=18)
        pygame.draw.rect(surf, color, body, border_radius=16)
        pygame.draw.rect(surf, rim, body, 3, border_radius=16)
        # interior cavity
        inner = body.inflate(-26, -26)
        cav = _mix((150, 160, 172), (226, 240, 248), light)
        pygame.draw.rect(surf, _dk(cav, 0.86), inner, border_radius=10)
        pygame.draw.rect(surf, cav, inner.inflate(-8, -8), border_radius=8)
        # interior light: a soft glow from the bulb at the top
        if light > 0:
            gl = pygame.Surface(inner.size, pygame.SRCALPHA)
            for r_, a in ((inner.w * 0.7, 30), (inner.w * 0.45, 40), (inner.w * 0.25, 50)):
                pygame.draw.ellipse(gl, (255, 255, 240, int(a * light)),
                                    (inner.w / 2 - r_, -r_ * 0.5, r_ * 2, r_ * 1.2))
            surf.blit(gl, inner.topleft)
            pygame.draw.rect(surf, _mix((200, 200, 190), (255, 250, 214), light),
                             (inner.centerx - 18, inner.y + 5, 36, 7), border_radius=3)
        # freezer row (row 0) + glass shelves
        row_h = (inner.h - 16) // ROWS
        rows_y = [inner.y + 12 + r * row_h for r in range(ROWS)]
        frz = pygame.Rect(inner.x + 6, rows_y[0], inner.w - 12, row_h - 6)
        pygame.draw.rect(surf, _mix((170, 196, 214), (206, 232, 246), light), frz,
                         border_radius=6)
        for i in range(7):                                  # frost speckles
            fx = frz.x + 10 + (i * 53) % (frz.w - 20)
            fy = frz.y + 6 + (i * 17) % (frz.h - 12)
            pygame.draw.circle(surf, (248, 252, 255), (fx, fy), 2)
        lab = pygame.transform.rotate(K.font(10, True).render("FREEZER", True,
                                                               _dk(color, 0.5)), 90)
        surf.blit(lab, lab.get_rect(center=(body.x + 7, frz.centery)))
        for r in range(1, ROWS):                            # glass shelf lips
            y = rows_y[r] + row_h - 8
            pygame.draw.line(surf, (190, 214, 226), (inner.x + 6, y), (inner.right - 6, y), 4)
            pygame.draw.line(surf, (246, 252, 255), (inner.x + 6, y - 2),
                             (inner.right - 6, y - 2), 1)
        # contents: the freezer row stays put, the shelves scroll by row
        rows = self.fridge_rows()
        n = sum(len(row) for row in rows)
        sel_r, _c = self._rc(rows, self.sel_fr)
        nshelf = len(rows) - 1
        top = 0
        if nshelf > SHELVES:
            top = max(0, min(max(0, sel_r - 1) - SHELVES // 2, nshelf - SHELVES))
        col_w = (inner.w - 12) // COLS
        active = self.side == 1
        slots = []                                   # (flat index, item, screen row, col)
        i = 0
        for r, row in enumerate(rows):
            for c, it in enumerate(row):
                vr = 0 if r == 0 else r - top
                if r == 0 or 1 <= vr <= SHELVES:
                    slots.append((i, it, vr, c))
                i += 1
        for i, it, r, c in slots:
            cx = inner.x + 6 + c * col_w + col_w // 2
            cy = rows_y[r] + row_h // 2 - 4
            if i == self.sel_fr and self.phase != "opening":
                pulse = 0.5 + 0.5 * math.sin(self.clock * 5)
                cr = pygame.Rect(0, 0, col_w - 6, row_h - 10)
                cr.center = (cx, cy + 1)
                if active:
                    pygame.draw.rect(surf, (252, 236, 180), cr, border_radius=8)
                    pygame.draw.rect(surf, _mix(K.GOLD_RIM, (240, 192, 104), pulse), cr, 3,
                                     border_radius=8)
                else:
                    pygame.draw.rect(surf, (200, 214, 224), cr, 2, border_radius=8)
            ic = _big_icon(it)
            bob = 0
            if i == self.sel_fr and active:
                bob = int(round(math.sin(self.clock * 6) * 1.5))
            surf.blit(ic, ic.get_rect(center=(cx, cy - 2 + bob)))
            q = self.fr.store.get(it, 0)
            if q > 1:
                t = K.font(12, True).render(str(q), True, (255, 255, 255))
                b = pygame.Rect(0, 0, t.get_width() + 8, 16)
                b.bottomright = (cx + col_w // 2 - 4, cy + row_h // 2 - 6)
                pygame.draw.rect(surf, (96, 120, 150), b, border_radius=7)
                surf.blit(t, t.get_rect(center=b.center))
        if n == 0 and self.phase != "opening":
            K.blit_text(surf, K.font(15, True), "(empty shelves)", (120, 140, 156),
                        (inner.centerx, rows_y[2] + row_h // 2))
        if nshelf > SHELVES:
            K.blit_text(surf, K.font(11, True), f"shelves {top + 1}-{top + SHELVES} / {nshelf}",
                        (110, 130, 150), (inner.x + 10, inner.bottom - 8), align="left")
        # cold fog rolling out along the floor
        ms = pygame.Surface((body.w + 200, 60), pygame.SRCALPHA)
        for (u, d, age, life) in self.mist:
            k = age / life
            mx = int(100 + u * body.w + d * age * 70)
            my = int(34 + k * 10)
            rr = int(10 + k * 16)
            a = int(46 * (1 - k))
            if a > 2:
                pygame.draw.ellipse(ms, (240, 248, 255, a), (mx - rr * 1.4, my - rr * 0.5,
                                                             rr * 2.8, rr))
        surf.blit(ms, (body.x - 100, body.bottom - 38))
        # the door (hinged on the right edge)
        self._draw_door(surf, body, color, sw)

    def _draw_door(self, surf, body, color, sw):
        ang = sw * math.radians(112)
        W = body.w + 4
        hx = body.right + 2
        top, bot = body.y - 2, body.bottom + 2
        ex = hx - W * math.cos(ang)                     # free edge x
        persp = 0.10 * math.sin(ang)                    # free edge grows toward the viewer
        etop = top - (bot - top) * persp * 0.35
        ebot = bot + (bot - top) * persp * 0.35
        quad = [(hx, top), (ex, etop), (ex, ebot), (hx, bot)]
        if abs(ex - hx) < 2:
            return
        rim = _dk(color, 0.55)

        def pt(u, v):                                   # u: 0 hinge .. 1 free edge
            x = hx + (ex - hx) * u
            ytop = top + (etop - top) * u
            ybot = bot + (ebot - bot) * u
            return (int(x), int(ytop + (ybot - ytop) * v))
        if math.cos(ang) > 0:                           # we still see the OUTSIDE
            pygame.draw.polygon(surf, _lt(color, 1.04), quad)
            pygame.draw.polygon(surf, rim, quad, 3)
            pygame.draw.line(surf, rim, pt(0, 0.23), pt(1, 0.23), 3)   # freezer seam
            pygame.draw.line(surf, (190, 196, 206), pt(0.88, 0.30), pt(0.88, 0.52), 6)
            pygame.draw.line(surf, (190, 196, 206), pt(0.88, 0.06), pt(0.88, 0.17), 6)
            return
        # swung open: the INSIDE of the door with its bins
        inner = _mix(_dk(color, 0.9), (234, 240, 244), 0.55)
        pygame.draw.polygon(surf, _dk(color, 0.8), quad)
        liner = [pt(0.08, 0.03), pt(0.92, 0.03), pt(0.92, 0.97), pt(0.08, 0.97)]
        pygame.draw.polygon(surf, inner, liner)
        pygame.draw.polygon(surf, _dk(color, 0.5), quad, 3)
        wide = abs(ex - hx)
        if wide < 40:
            return
        # three door bins with bottles & jars
        bottles = [[(206, 64, 60), (238, 196, 70), (120, 180, 220)],
                   [(240, 240, 236), (150, 96, 60), (230, 130, 150)],
                   [(110, 170, 90), (246, 204, 110), (200, 90, 90)]]
        for b, v in enumerate((0.36, 0.62, 0.88)):
            a0, a1 = pt(0.12, v), pt(0.88, v)
            for k, col in enumerate(bottles[b]):
                bp = pt(0.22 + k * 0.28, v)
                bh = 30 if (b + k) % 2 == 0 else 22
                bw = max(6, int(wide * 0.12))
                pygame.draw.rect(surf, col, (bp[0] - bw // 2, bp[1] - bh, bw, bh),
                                 border_radius=3)
                pygame.draw.rect(surf, _dk(col, 0.6), (bp[0] - bw // 2, bp[1] - bh, bw, bh),
                                 1, border_radius=3)
                pygame.draw.rect(surf, (250, 250, 250), (bp[0] - bw // 2 + 2, bp[1] - bh + 6,
                                                         max(2, bw // 3), bh // 3))
            lip = [pt(0.10, v - 0.035), pt(0.90, v - 0.035), a1, a0]
            pygame.draw.polygon(surf, (214, 234, 244), lip)
            pygame.draw.polygon(surf, (170, 196, 210), lip, 2)
        # sticky note + heart magnet at the top of the door
        n0 = pt(0.2, 0.08)
        nw = max(20, int(wide * 0.42))
        note = pygame.Rect(n0[0], n0[1], nw, 34)
        pygame.draw.rect(surf, (252, 236, 140), note, border_radius=2)
        pygame.draw.line(surf, (200, 170, 90), (note.x + 5, note.y + 14),
                         (note.right - 5, note.y + 14), 1)
        pygame.draw.line(surf, (200, 170, 90), (note.x + 5, note.y + 22),
                         (note.right - 8, note.y + 22), 1)
        hx0, hy0 = note.centerx, note.y + 2
        pygame.draw.circle(surf, (230, 90, 120), (hx0 - 3, hy0), 4)
        pygame.draw.circle(surf, (230, 90, 120), (hx0 + 3, hy0), 4)
        pygame.draw.polygon(surf, (230, 90, 120), [(hx0 - 7, hy0 + 1), (hx0 + 7, hy0 + 1),
                                                   (hx0, hy0 + 8)])
