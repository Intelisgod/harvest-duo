"""Co-op features: emotes, partner gifting, day report + lifetime stats.

Owner: Core (Chat 0). See docs/ARCHITECTURE.md (ownership map) and
src/systems/hooks.py (the hook API this mixin plugs into: define methods named
``_on_reset_*``, ``_on_update_*``, ``_interact_late_*``, ``_on_save_*`` ... and they
are called automatically -- no edits to game.py / save_system / actions_system).
Rules: no ``__init__``; initialise state in an ``_on_reset_*`` hook.

Features
--------
* EMOTES -- P1 ``F`` / P2 ``/`` (rebindable: ``P?_KEYS["emote"]``). A fresh press
  pops a heart bubble; pressing again while it shows cycles the wheel
  (heart, happy, note, wave, !, ?, zzz, sparkle). Both farmers showing a heart
  within ``LOVE_WINDOW`` s while standing close -> "Love boost!" (60 s cooldown).
* PARTNER GIFTING -- face your partner (within ~1.2 tiles) holding an item and
  press action: one of it is handed over (``partner_gift`` event).
* STATS -- today + lifetime counters fed by the shared events; after sleeping a
  cosy "End of Day" card (custom state ``day_report``) and a journal "Stats" tab.
"""
import math
import random

import pygame

from ..settings import (TILE, SCREEN_W, SCREEN_H, MAX_ENERGY, WHITE, GOLD,
                        P1_KEYS, P2_KEYS, AREA_HOME, SEASONS, DAYS_PER_SEASON,
                        JOURNAL_KEY)
from .. import loot, weather
from .. import ui_kit as K

EMOTES = ("heart", "happy", "note", "wave", "exclaim", "question", "zzz", "sparkle")
EMOTE_DUR = 2.2          # seconds a bubble stays up
LOVE_WINDOW = 1.5        # both hearts within this many seconds -> Love boost
LOVE_COOLDOWN = 60.0
LOVE_RANGE = TILE * 3.5  # "near each other"
LOVE_ENERGY = 15
GIFT_REACH = TILE * 1.2  # partner must stand this close in front of you

# per-player counters: key -> (label, fallback icon)
STAT_ROWS = [
    ("crops", "Crops harvested", "parsnip"),
    ("planted", "Seeds planted", "seed:parsnip"),
    ("animal", "Animal goods", "egg"),
    ("fish", "Fish caught", None),
    ("forage", "Forage found", "wood"),
    ("monsters", "Monsters defeated", "@sword"),
    ("rocks", "Rocks broken", "stone"),
    ("trees", "Trees chopped", "wood"),
    ("cooked", "Meals cooked", None),
    ("crafted", "Things crafted", "@hoe"),
    ("gifts", "Gifts to villagers", "@heart"),
    ("partner_gifts", "Gifts to each other", "@heart"),
    ("emotes", "Emotes shared", "@bubble"),
    ("gold_sales", "Gold from sales", "@coin"),
]
STAT_KEYS = [k for k, _l, _i in STAT_ROWS]
_ROW = {k: (l, i) for k, l, i in STAT_ROWS}
# event -> (stat key, data field holding the amount or None for +1, icon field)
_EVENT_STAT = {
    "harvest": ("crops", "qty", "item"),
    "crop_planted": ("planted", None, None),
    "animal_product": ("animal", None, "item"),
    "fish_caught": ("fish", None, "fish"),
    "foraged": ("forage", None, "item"),
    "monster_killed": ("monsters", None, None),
    "rock_broken": ("rocks", None, None),
    "tree_chopped": ("trees", None, None),
    "cooked": ("cooked", None, "food"),
    "crafted": ("crafted", None, "what"),
    "gift_given": ("gifts", None, "item"),
    "partner_gift": ("partner_gifts", None, "item"),
    "emote": ("emotes", None, None),
    "item_sold": ("gold_sales", "gold", None),
}

_SEASON_COL = {"Spring": (238, 170, 196), "Summer": (150, 206, 130),
               "Fall": (236, 164, 104), "Winter": (150, 188, 232)}

_SPR = {}                                        # cached bubble / icon sprites

# End-of-Day card geometry (card-local px)
_DR_W, _DR_H = 760, 492
_DR_RIB = 28                                     # headroom above the card for the ribbon title
_DR_SHIFT = 28                                   # content sits this much higher than the old layout
_DR_DIV = 476                                    # x of the table | right-column divider
_DR_HUD_CLEAR = 132                              # card top: its ribbon clears both hotbar rows


# ------------------------------------------------------------------ sprites
def _font(size, bold=True):
    key = ("font", size, bold)
    f = _SPR.get(key)
    if f is None:
        try:
            f = pygame.font.SysFont("consolas", size, bold=bold)
        except Exception:
            f = pygame.font.Font(None, size + 6)
        _SPR[key] = f
    return f


def _heart(surf, cx, cy, r, color):
    try:
        from ..particles import _draw_heart
        _draw_heart(surf, cx, cy, r, color)
    except Exception:
        pygame.draw.circle(surf, color, (cx, cy), r)


def _star(surf, cx, cy, r, color, inner=0.45, points=5):
    pts = []
    for i in range(points * 2):
        ang = -math.pi / 2 + i * math.pi / points
        rad = r if i % 2 == 0 else r * inner
        pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
    pygame.draw.polygon(surf, color, pts)


def emote_icon(kind, s, cx, cy):
    """Paint an emote glyph centred at (cx, cy) on ``s`` (~16px tall)."""
    if kind == "heart":
        _heart(s, cx, cy + 1, 7, (238, 92, 128))
        pygame.draw.circle(s, (255, 196, 210), (cx - 4, cy - 2), 2)
    elif kind == "happy":
        pygame.draw.circle(s, (255, 214, 92), (cx, cy), 8)
        pygame.draw.circle(s, (196, 140, 50), (cx, cy), 8, 1)
        pygame.draw.circle(s, (90, 60, 50), (cx - 3, cy - 2), 1)
        pygame.draw.circle(s, (90, 60, 50), (cx + 3, cy - 2), 1)
        pygame.draw.arc(s, (90, 60, 50), (cx - 5, cy - 4, 10, 9), math.pi * 1.1,
                        math.pi * 1.9, 2)
        pygame.draw.circle(s, (250, 160, 150), (cx - 5, cy + 2), 1)
        pygame.draw.circle(s, (250, 160, 150), (cx + 5, cy + 2), 1)
    elif kind == "note":
        col = (122, 108, 214)
        pygame.draw.ellipse(s, col, (cx - 7, cy + 2, 7, 6))
        pygame.draw.line(s, col, (cx - 1, cy + 4), (cx - 1, cy - 7), 2)
        pygame.draw.polygon(s, col, [(cx - 1, cy - 8), (cx + 6, cy - 5), (cx + 6, cy - 2),
                                     (cx - 1, cy - 4)])
    elif kind == "wave":
        skin, ink = (250, 208, 172), (150, 98, 82)
        pygame.draw.rect(s, skin, (cx - 4, cy - 1, 9, 8), border_radius=3)
        for i, h in enumerate((6, 8, 8, 6)):
            pygame.draw.line(s, skin, (cx - 3 + i * 2, cy), (cx - 3 + i * 2, cy - h), 2)
        pygame.draw.line(s, skin, (cx - 4, cy + 3), (cx - 7, cy), 2)
        pygame.draw.rect(s, ink, (cx - 4, cy - 1, 9, 8), 1, border_radius=3)
        pygame.draw.arc(s, (140, 180, 230), (cx + 4, cy - 9, 8, 10), -0.9, 0.9, 1)
        pygame.draw.arc(s, (140, 180, 230), (cx - 12, cy - 9, 8, 10), math.pi - 0.9,
                        math.pi + 0.9, 1)
    elif kind == "exclaim":
        pygame.draw.rect(s, (228, 86, 86), (cx - 2, cy - 8, 5, 11), border_radius=2)
        pygame.draw.circle(s, (228, 86, 86), (cx, cy + 6), 2)
    elif kind == "question":
        t = _font(19).render("?", True, (92, 142, 226))
        s.blit(t, (cx - t.get_width() // 2, cy - t.get_height() // 2))
    elif kind == "zzz":
        col = (136, 146, 222)
        for i, (sz, dx, dy) in enumerate(((10, -7, 3), (13, -1, -1), (16, 5, -6))):
            t = _font(sz).render("z", True, col)
            s.blit(t, (cx + dx - t.get_width() // 2, cy + dy - t.get_height() // 2))
    else:  # sparkle
        _star(s, cx - 1, cy + 1, 8, (250, 206, 80), inner=0.3, points=4)
        _star(s, cx + 6, cy - 5, 4, (255, 236, 160), inner=0.3, points=4)
        pygame.draw.circle(s, (255, 250, 220), (cx - 1, cy + 1), 2)


def _bubble(kind):
    """Cached speech-bubble sprite (34x36) for an emote."""
    key = ("bubble", kind)
    s = _SPR.get(key)
    if s is None:
        s = pygame.Surface((34, 36), pygame.SRCALPHA)
        edge = (96, 74, 92)
        pygame.draw.rect(s, (0, 0, 0, 40), (3, 4, 30, 26), border_radius=10)   # soft shadow
        pygame.draw.polygon(s, edge, [(12, 26), (22, 26), (16, 34)])
        pygame.draw.rect(s, edge, (1, 1, 31, 27), border_radius=10)
        pygame.draw.rect(s, (255, 252, 244), (3, 3, 27, 23), border_radius=9)
        pygame.draw.polygon(s, (255, 252, 244), [(13, 25), (20, 25), (16, 31)])
        pygame.draw.line(s, (255, 255, 255), (8, 5), (22, 5), 1)                # glossy rim
        emote_icon(kind, s, 16, 14)
        _SPR[key] = s
    return s


def _bubble_scaled(kind, scale):
    q = max(3, min(13, int(round(scale * 10))))          # 0.3 .. 1.3 in 0.1 steps
    key = ("bubble_s", kind, q)
    s = _SPR.get(key)
    if s is None:
        b = _bubble(kind)
        s = pygame.transform.scale(b, (max(1, b.get_width() * q // 10),
                                       max(1, b.get_height() * q // 10)))
        _SPR[key] = s
    return s


def _misc_icon(name):
    """28x28 icons for stats without an item (heart, coin, bubble)."""
    key = ("icon", name)
    s = _SPR.get(key)
    if s is None:
        s = pygame.Surface((28, 28), pygame.SRCALPHA)
        if name == "heart":
            _heart(s, 14, 14, 9, (238, 96, 132))
            pygame.draw.circle(s, (255, 200, 214), (9, 10), 2)
        elif name == "coin":
            pygame.draw.circle(s, (176, 128, 40), (14, 15), 10)
            pygame.draw.circle(s, (246, 204, 92), (14, 14), 9)
            pygame.draw.circle(s, (255, 236, 160), (11, 11), 3)
            pygame.draw.line(s, (196, 146, 50), (14, 9), (14, 19), 2)
        elif name == "bubble":
            b = pygame.transform.scale(_bubble("heart"), (25, 26))
            s.blit(b, (2, 1))
        elif name == "star":
            _star(s, 14, 15, 12, (250, 206, 80))
            _star(s, 14, 15, 6, (255, 238, 170))
        _SPR[key] = s
    return s


def _stat_icon(key, item=None):
    """Icon surface for a stat row: the most recent item for that stat when
    known (so the harvest row shows *your* crop), else a sensible default."""
    try:
        from .. import assets
        if item:
            return assets.item_icon(item)
        fb = _ROW.get(key, ("", None))[1]
        if key == "fish" and fb is None:
            from ..fishing import FISH
            fb = next(iter(FISH))
        if key == "cooked" and fb is None:
            from ..cooking import FOODS
            fb = next(iter(FOODS))
        if fb and fb.startswith("@"):
            nm = fb[1:]
            if nm in ("sword", "hoe", "pickaxe"):
                return assets.tool_icon(nm)
            return _misc_icon(nm)
        if fb:
            return assets.item_icon(fb)
    except Exception:
        pass
    return _misc_icon("star")


def _item_label(item):
    try:
        from ..cooking import FOODS
        if item in FOODS:
            return FOODS[item].get("label", item)
    except Exception:
        pass
    if item.startswith("seed:"):
        return item.split(":", 1)[1].replace("_", " ").title() + " Seeds"
    try:
        return loot.label(item)
    except Exception:
        return item.replace("_", " ").title()


def _blank_today():
    return {"n": {k: [0, 0] for k in STAT_KEYS}, "deepest": 0, "love": 0, "icons": {}}


class CoopMixin:
    """Co-op features: emotes, partner gifting, day report + lifetime stats."""

    # ================================================================ state
    def _on_reset_coop(self):
        self.emotes = [None, None]          # per player: [kind, age] or None
        self._emote_wheel = [0, 0]
        self._emote_cycled = [-99.0, -99.0]  # clock of each player's last wheel step
        self._heart_at = [-99.0, -99.0]     # coop clock when each last showed a heart
        self._coop_clock = 0.0
        self._love_cd = 0.0
        self._pgift_bonus = set()           # players who got today's first-gift glow
        self.stats_today = _blank_today()
        self.stats_life = {}
        self._day_gold0 = self.gold
        t = self.time
        self._stats_date = [t.day, t.season_idx, t.year]
        self.day_report = None              # pending report (built at dawn)
        self._dr = None                     # the report currently on screen
        self._dr_cache = {}
        self.coop_tips = set()              # one-time co-op tips already shown (saved)
        self._tip_t = 0.0
        self._idle_t = [0.0, 0.0]           # seconds each player stood still (auto zzz)

    # ================================================================ emotes
    def _on_keydown_coop_emote(self, key):
        # never swallow a key the players ALSO bound to a real action (old custom
        # bindings may already use F or /): the action wins, no emote
        for K in (P1_KEYS, P2_KEYS):
            if any(a != "emote" and c == key for a, c in K.items()):
                return False
        hit = False
        for idx, K in ((0, P1_KEYS), (1, P2_KEYS)):
            code = K.get("emote")
            if code is not None and key == code:
                self._emote_press(idx)
                hit = True
        return hit

    def _emote_press(self, idx):
        """Show / cycle player ``idx``'s emote bubble (also called for the LAN
        client's P2 via net_system)."""
        cur = self.emotes[idx]
        if cur is not None and cur[1] < EMOTE_DUR - 0.25:
            self._emote_wheel[idx] = (self._emote_wheel[idx] + 1) % len(EMOTES)
            self._emote_cycled[idx] = self._coop_clock
        else:
            self._emote_wheel[idx] = 0                       # fresh press = heart
        kind = EMOTES[self._emote_wheel[idx]]
        self.emotes[idx] = [kind, 0.0]
        p = self.players[idx]
        if kind in ("heart", "happy", "wave", "sparkle", "exclaim") and hasattr(p, "hop"):
            p.hop(0.3)
        sfx = "emote_" + kind
        self.audio.play(sfx if sfx in getattr(self.audio, "sfx", {}) else "emote")
        self.emit("emote", p=p, kind=kind)
        if kind == "heart":
            self._heart_at[idx] = self._coop_clock
            self._raw_fx(self.parts.heart_float, *self._fx(p.x, p.y, 44))
            self._try_love_boost()
        elif kind == "sparkle":
            f = getattr(self.parts, "star_burst", None)
            if f:
                self._raw_fx(f, *self._fx(p.x, p.y, 50), (255, 226, 130), n=5)
        elif kind == "note":
            self._raw_fx(self.parts.sparkle, *self._fx(p.x, p.y, 50), n=4, color=(170, 160, 240))

    def _fx(self, wx, wy, lift=0):
        """Where to spawn particles / popups for a world point ``lift`` px above
        the ground. Particles are drawn top-down (world - cam), but the home is
        an ISO room: project there and hand back the matching 'world' point."""
        if self.world.current != AREA_HOME:
            return wx, wy - lift
        try:
            from .. import homeiso
            ox, oy = homeiso.origin(self.world.area)
            sx, sy = homeiso.proj(ox, oy, wx / TILE, wy / TILE)
            return sx + self.cam.x, sy - lift * 1.5 + self.cam.y
        except Exception:
            return wx, wy - lift

    def _raw_fx(self, fn, *a, **k):
        """Spawn particles at coordinates ``_fx`` already projected: bypass the
        home's automatic spawn projection for this call."""
        lst = self.parts.items
        old = getattr(lst, "xform", None)
        try:
            if old is not None:
                lst.xform = None
            fn(*a, **k)
        finally:
            if old is not None:
                lst.xform = old

    def _try_love_boost(self):
        a, b = self.players[0], self.players[1]
        both = (abs(self._heart_at[0] - self._heart_at[1]) <= LOVE_WINDOW
                and all(e is not None and e[0] == "heart" for e in self.emotes))
        near = math.hypot(a.x - b.x, a.y - b.y) <= LOVE_RANGE
        if not (both and near):
            return
        if self._love_cd > 0:
            self._raw_fx(self.parts.heart_float, *self._fx((a.x + b.x) / 2, (a.y + b.y) / 2, 40))
            return
        self._love_cd = LOVE_COOLDOWN
        self._heart_at = [-99.0, -99.0]
        mx, my = self._fx((a.x + b.x) / 2, (a.y + b.y) / 2, 30)
        self._raw_fx(self.parts.heart_burst, mx, my, n=22)
        ring = getattr(self.parts, "ring", None)
        if ring:
            self._raw_fx(ring, mx, my, (255, 170, 200), radius=14)
        for p in self.players:
            if hasattr(p, "hop"):
                p.hop(0.42)
            p.energy = min(MAX_ENERGY, p.energy + LOVE_ENERGY)
            if hasattr(p, "add_buff"):
                p.add_buff("regen", 30, 0.3, "Love")
        self._popup(mx, my - 20, "Love boost!", (255, 150, 185))
        self.audio.play("bell")
        self.add_shake(2)
        self.ui.log(f"Love boost! +{LOVE_ENERGY} energy for you both <3")
        t = getattr(self, "toast", None)
        if t:
            t("Love boost!", f"+{LOVE_ENERGY} energy each - warm and fuzzy",
              icon=_misc_icon("heart"), color=(255, 150, 185))
        self.stats_today["love"] = self.stats_today.get("love", 0) + 1
        self.emit("love_boost", players=list(self.players))
        n = self.stats_life.get("love", 0)
        if n in (10, 25, 50, 100, 250, 500) and t:
            t(f"{n} Love boosts!", "You two are the sweetest farmers in the valley",
              icon=_misc_icon("heart"), color=(255, 150, 185))

    def _on_update_coop(self, dt):
        self._coop_clock += dt
        for p in self.players:
            if getattr(p, "hop_t", 0) > 0:
                p.hop_t = max(0.0, p.hop_t - dt)
        if self._love_cd > 0:
            self._love_cd = max(0.0, self._love_cd - dt)
        for i, e in enumerate(self.emotes):
            if e is not None:
                e[1] += dt
                if e[1] >= EMOTE_DUR:
                    self.emotes[i] = None
        # sleepy farmers: standing still late at night nods off into a "zzz"
        late = self.time.minutes >= 24 * 60
        for i, p in enumerate(self.players):
            still = not getattr(p, "moving", False)
            self._idle_t[i] = self._idle_t[i] + dt if (still and late) else 0.0
            if self._idle_t[i] >= 9.0:
                self._idle_t[i] = -30.0          # at most every ~40 s
                if self.emotes[i] is None:
                    self.emotes[i] = ["zzz", 0.0]
        self._coop_tips_tick(dt)

    def _coop_tips_tick(self, dt):
        """One-time friendly tips (rebind-proof key names), a few seconds apart."""
        self._tip_t += dt
        if self._tip_t < 6.0 or getattr(self, "net_mode", None) == "client":
            return
        from ..ui import key_label
        k1, k2 = P1_KEYS.get("emote"), P2_KEYS.get("emote")
        a1, a2 = key_label(P1_KEYS["action"]), key_label(P2_KEYS["action"])
        # the core loop first: a couple who pressed Start never saw How to Play
        tips = [("loop", f"Tip: hoe the grass, plant seeds, then water - press "
                         f"{a1} / {a2} with the tool selected."),
                ("journal", f"Tip: press {key_label(JOURNAL_KEY)} for the Journal - "
                            f"controls & farmer's tips."),
                ("bed", "Tip: sleep in your bed (in the house) to end the day "
                        "- before 2 AM for full energy.")]
        if k1 is not None and k2 is not None:
            tips.append(("emote", f"Tip: emote with {key_label(k1)} (P1) or "
                                  f"{key_label(k2)} (P2). Both send hearts = Love boost!"))
        tips.append(("gift", f"Tip: face your partner holding an item and press "
                             f"{key_label(P1_KEYS['action'])} / {key_label(P2_KEYS['action'])}"
                             " to give it."))
        for key, text in tips:
            if key not in self.coop_tips:
                self.coop_tips.add(key)
                self._tip_t = 0.0
                self.ui.log(text)
                return
    # LAN: the host ships the bubbles in its snapshot, the client just draws them
    def _emote_snapshot(self):
        return [[e[0], round(e[1], 2)] if e else None for e in self.emotes]

    def _emote_apply_snapshot(self, data):
        if not isinstance(data, list):
            return
        out = []
        for e in data[:2]:
            if isinstance(e, list) and len(e) == 2 and e[0] in EMOTES:
                out.append([e[0], float(e[1])])
            else:
                out.append(None)
        while len(out) < 2:
            out.append(None)
        self.emotes = out

    def _head_anchor(self, p):
        """Screen point just above a player's head (handles the iso home)."""
        if self.world.current == AREA_HOME:
            try:
                from .. import homeiso
                ox, oy = homeiso.origin(self.world.area)
                fx, fy = homeiso.proj(ox, oy, p.x / TILE, p.y / TILE)
                return fx, fy - 70
            except Exception:
                pass
        return p.x - self.cam.x, p.y - self.cam.y - 40

    def _draw_world_coop_emotes(self):
        self._draw_gift_hint()
        if not any(self.emotes):
            return
        scr = self.screen
        reserve = getattr(self, "hud_reserve", None)   # floating texts keep clear of bubbles
        main = {}                                   # player -> this frame's main bubble rect
        for i, e in enumerate(self.emotes):
            if e is not None:
                fx, tip_y = self._head_anchor(self.players[i])
                main[i] = pygame.Rect(int(fx - 17), int(tip_y - 36), 34, 36)
        for i, e in enumerate(self.emotes):
            if e is None:
                continue
            kind, age = e
            p = self.players[i]
            fx, tip_y = self._head_anchor(p)
            # pop: 0.3 -> 1.25 overshoot -> settle at 1.0; gentle bob; fade out
            if age < 0.16:
                sc = 0.3 + age / 0.16 * 0.95
            elif age < 0.3:
                sc = 1.25 - (age - 0.16) / 0.14 * 0.25
            else:
                sc = 1.0
            spr = _bubble_scaled(kind, sc)
            bob = math.sin(age * 5.0) * 1.5 if age > 0.3 else 0.0
            since = self._coop_clock - self._emote_cycled[i]
            if 0 <= since < 1.1 and kind in EMOTES:
                # while cycling: ghost the neighbours so it reads as a wheel
                k = EMOTES.index(kind)
                fade = int(150 * (1.0 - since / 1.1))
                other = main.get(1 - i)
                for dx, nb in ((-29, EMOTES[k - 1]), (29, EMOTES[(k + 1) % len(EMOTES)])):
                    g = _bubble_scaled(nb, 0.6)
                    gr = g.get_rect(topleft=(int(fx + dx - g.get_width() / 2),
                                             int(tip_y - g.get_height() - 4)))
                    if other is not None and gr.colliderect(other.inflate(4, 4)):
                        continue                    # never ghost over the partner's bubble
                    g.set_alpha(fade)
                    scr.blit(g, gr.topleft)
                    reserve and reserve(gr)
            a = 255 if age < EMOTE_DUR - 0.35 else int(255 * max(0.0, (EMOTE_DUR - age) / 0.35))
            spr.set_alpha(a)
            br = spr.get_rect(topleft=(int(fx - spr.get_width() / 2),
                                       int(tip_y - spr.get_height() + bob)))
            scr.blit(spr, br.topleft)
            reserve and reserve(br)

    # ================================================================ gifting
    def _gift_target(self, idx):
        """(item_id, partner) if player ``idx`` faces the partner within reach
        holding an item, else None."""
        p = self.players[idx]
        entry = p.inv.selected_entry() if p.inv else None
        if not entry or entry[0] != "item" or getattr(p, "sitting", None):
            return None
        other = self.players[1 - idx]
        if other.inv is None:
            return None
        dx, dy = other.x - p.x, other.y - p.y
        along = dx * p.fx + dy * p.fy                 # distance ahead of us
        side = abs(dx * p.fy - dy * p.fx)             # distance off the facing line
        if not (4 < along <= GIFT_REACH and side <= TILE * 0.6):
            return None
        return entry[1], other

    def _draw_gift_hint(self):
        """A small '<key> Give' tag over the partner you could hand an item to --
        only while you stand still facing them (no clutter while walking)."""
        if self.state != "play":
            return
        from ..ui import key_label
        placed = []
        for idx, keys in ((0, P1_KEYS), (1, P2_KEYS)):
            p = self.players[idx]
            if getattr(p, "moving", False) or self.emotes[1 - idx] is not None:
                continue
            tgt = self._gift_target(idx)
            if not tgt:
                continue
            kl = key_label(keys['action'])
            pf = K.font(14, True)
            tw = pf.size(kl)[0] + 12 + pf.size("Give")[0] + 18
            th = max(24, pf.get_height() + 10)
            hx, hy = self._head_anchor(tgt[1])
            bob = math.sin(self.anim_t * 4.0) * 1.5
            gx, gy = int(hx - tw / 2), int(hy - 30 + bob)
            # a held-item tag (UI seltags: 24 px pill ~1.45 tiles above a
            # farmer, pushed sideways when two meet) in the way: sit one row
            # above it so the two pills never overlap. Predicted from this
            # frame's positions -- last frame's rects lag a moving camera.
            r = pygame.Rect(gx, gy, tw, th)
            for ti in list(getattr(self, "_sel_tags", None) or ()):
                if not isinstance(ti, int) or not 0 <= ti < len(self.players):
                    continue
                q = self.players[ti]
                tr = pygame.Rect(int(q.x - self.cam.x - 90), int(q.y - self.cam.y - TILE * 1.45 - 7),
                                 180, 26)
                if r.colliderect(tr):
                    r.bottom = tr.top - 3
            for pr in placed:                    # both offering at once: stack them
                if r.colliderect(pr):
                    r.bottom = pr.top - 2
            placed.append(r)
            pr = K.key_pill(self.screen, kl, "Give", r.center, accent=K.P_COL[idx], fnt=pf)
            # floating texts ("+1 Wood", "Love boost!") step clear of the prompt
            f = getattr(self, "hud_reserve", None)
            f and f(pr)

    def _interact_early_05_coop_gift(self, idx, p):
        """Hand the selected item to the partner you are facing (<= ~1.2 tiles)."""
        tgt = self._gift_target(idx)
        if not tgt:
            return False
        name, other = tgt
        if not p.inv.remove(name, 1):
            return False
        other.inv.add(name, 1)
        if hasattr(other, "hop"):
            other.hop(0.3)
        label = _item_label(name)
        if name.startswith("seed:") and label.endswith(" Seeds"):
            label = label[:-1]                         # always exactly 1: "1 Parsnip Seed"
        mx, my = self._fx((p.x + other.x) / 2, (p.y + other.y) / 2, 26)
        self._raw_fx(self.parts.heart_burst, mx, my, n=8)
        self._popup(*self._fx(other.x, other.y, 58), f"+1 {label}", (255, 190, 210))
        self.audio.play("gift")
        try:
            p.trigger_item_use(name, "place", 0.45)
        except Exception:
            pass
        note = ""
        if idx not in self._pgift_bonus:              # first gift of the day warms both
            self._pgift_bonus.add(idx)
            for q in self.players:
                q.energy = min(MAX_ENERGY, q.energy + 8)
            note = " (+8 energy each)"
        self.ui.log(f"{p.name} gave {other.name} 1 {label} <3{note}")
        self.emit("partner_gift", p=p, to=other, item=name)
        return True

    # ================================================================ stats
    def _pidx(self, p):
        if isinstance(p, int) and p in (0, 1):
            return p
        for i, q in enumerate(self.players):
            if q is p:
                return i
        return 0

    def _on_event_coop_stats(self, event, data):
        if event == "mine_depth":
            try:
                lvl = int(data.get("level") or 0)
            except Exception:
                lvl = 0
            self.stats_today["deepest"] = max(self.stats_today.get("deepest", 0), lvl)
            self.stats_life["deepest"] = max(self.stats_life.get("deepest", 0), lvl)
            return
        if event == "love_boost":
            self.stats_life["love"] = self.stats_life.get("love", 0) + 1
            return
        if event == "mist_run_end":                 # Mist City (lifetime only)
            life = self.stats_life
            life["mist_runs"] = life.get("mist_runs", 0) + 1
            try:
                life["mist_zombies"] = life.get("mist_zombies", 0) + max(0, int(data.get("kills") or 0))
            except Exception:
                pass
            if data.get("boss"):
                life["mist_victories"] = life.get("mist_victories", 0) + 1
            return
        spec = _EVENT_STAT.get(event)
        if spec is None:
            return
        key, amt_field, icon_field = spec
        amt = 1
        if amt_field:
            try:
                amt = int(data.get(amt_field) or 0)
            except Exception:
                amt = 0
        if amt <= 0:
            return
        i = self._pidx(data.get("p"))
        row = self.stats_today["n"].setdefault(key, [0, 0])
        row[i] += amt
        self.stats_life[key] = self.stats_life.get(key, 0) + amt
        if icon_field:
            it = data.get(icon_field)
            if isinstance(it, str) and it:
                self.stats_today["icons"][key] = it
        elif event == "crop_planted" and isinstance(data.get("crop"), str):
            self.stats_today["icons"][key] = "seed:" + data["crop"]

    # runs LAST among the morning hooks ("zz") so overnight shipping income that
    # another domain pays out in its own _on_new_day_ hook is already counted.
    def _on_new_day_zz_coop_report(self):
        self.day_report = self._build_report(at_dawn=True)
        life = self.stats_life
        gd = self.day_report["gold_delta"]
        self.day_report["record"] = (life.get("days", 0) >= 1 and gd > 0
                                     and gd > life.get("best_gold_day", 0))
        life["days"] = life.get("days", 0) + 1
        life["best_gold_day"] = max(life.get("best_gold_day", 0),
                                    self.day_report["gold_delta"])
        self.stats_today = _blank_today()
        self._day_gold0 = self.gold
        t = self.time
        self._stats_date = [t.day, t.season_idx, t.year]
        self._pgift_bonus = set()
        self.emit("day_report", day=self.day_report["day"], stats=self.day_report)

    def _build_report(self, at_dawn=False):
        st = self.stats_today
        day, sidx, year = (list(self._stats_date) + [1, 0, 1])[:3]
        rows = []
        for key in STAT_KEYS:
            v = st["n"].get(key, [0, 0])
            if v[0] or v[1]:
                rows.append((key, int(v[0]), int(v[1]), st["icons"].get(key)))
        # STAT_ROWS order = importance; keep the card tidy (max 8 rows, the
        # chattier stats -- emotes, sales -- are the first to give way)
        if len(rows) > 8:
            keep = sorted(rows, key=lambda r: (r[0] in ("emotes", "gold_sales"),
                                               -(r[1] + r[2])))[:8]
            rows = [r for r in rows if r in keep]
        n = st["n"]

        def tot(k):
            v = n.get(k, [0, 0])
            return v[0] + v[1]
        score = (tot("crops") + tot("fish") * 2 + tot("monsters") + tot("forage")
                 + tot("animal") + tot("cooked") * 2 + tot("crafted") * 2
                 + tot("gifts") * 2 + tot("partner_gifts") * 2 + tot("rocks") // 2
                 + tot("trees") + tot("gold_sales") // 60 + st.get("deepest", 0)
                 + st.get("love", 0) * 3)
        stars = 1 + sum(score >= s for s in (8, 22, 45, 80))
        flavour = {1: "A slow, gentle day. Rest is farming too.",
                   2: "Steady work - the farm is humming.",
                   3: "A lovely, productive day together!",
                   4: "What a team! The valley is impressed.",
                   5: "Legendary teamwork. Stars align for you two!"}[stars]
        if not rows:
            flavour = "A quiet, restful day together."
        pg = n.get("partner_gifts", [0, 0])
        if pg[0] and pg[1]:
            flavour = "You spoiled each other with gifts today. <3"
        passed_out = bool(at_dawn and not getattr(self, "slept_in_bed", True))
        if passed_out:
            flavour = "You passed out! Sleep in bed before 2 AM for full energy."
        # at dawn today's weather was just rolled = the forecast for the new day;
        # a mid-day preview (journal/debug) shows tomorrow's pre-rolled forecast
        tw = (getattr(self, "weather", weather.SUNNY) if at_dawn
              else getattr(self, "weather_tomorrow", weather.SUNNY))
        return {"day": day, "season": SEASONS[sidx % len(SEASONS)], "year": year,
                "rows": rows, "deepest": st.get("deepest", 0), "love": st.get("love", 0),
                "gold_delta": int(self.gold - self._day_gold0), "gold": int(self.gold),
                "sales": tot("gold_sales"), "stars": stars, "flavour": flavour,
                "forecast": tw, "names": [p.name for p in self.players],
                "festival": self._festival_today(),
                "together": int(self.stats_life.get("days", 0)) + 1,
                "passed_out": passed_out}

    def _festival_today(self):
        try:
            from .. import festival
            if festival.is_festival_day(self.time):
                return festival.name(self.time.season)
        except Exception:
            pass
        return None

    def _on_save_coop(self):
        st = self.stats_today
        return {
            "coop_stats_life": {k: int(v) for k, v in sorted(self.stats_life.items())},
            "coop_stats_today": {
                "n": {k: [int(v[0]), int(v[1])] for k, v in sorted(st["n"].items())},
                "deepest": int(st.get("deepest", 0)), "love": int(st.get("love", 0)),
                "icons": {k: v for k, v in sorted(st["icons"].items())}},
            "coop_day_gold0": int(self._day_gold0),
            "coop_tips": sorted(self.coop_tips),
            # who already got today's first-partner-gift glow (no re-grant on reload)
            "coop_pgift_today": sorted(int(i) for i in self._pgift_bonus),
        }

    def _on_load_coop(self, d):
        life = d.get("coop_stats_life", {})
        self.stats_life = {str(k): int(v) for k, v in life.items()
                           if isinstance(v, (int, float))} if isinstance(life, dict) else {}
        td = d.get("coop_stats_today") or {}
        st = _blank_today()
        if isinstance(td, dict):
            for k, v in (td.get("n") or {}).items():
                if isinstance(v, list) and len(v) == 2:
                    st["n"][str(k)] = [int(v[0]), int(v[1])]
            st["deepest"] = int(td.get("deepest", 0) or 0)
            st["love"] = int(td.get("love", 0) or 0)
            st["icons"] = {str(k): str(v) for k, v in (td.get("icons") or {}).items()}
        self.stats_today = st
        self._day_gold0 = int(d.get("coop_day_gold0", self.gold))
        tips = d.get("coop_tips", [])
        self.coop_tips = set(str(x) for x in tips) if isinstance(tips, list) else set()
        pg = d.get("coop_pgift_today", [])
        self._pgift_bonus = set(int(i) for i in pg
                                if isinstance(i, (int, float))) if isinstance(pg, list) else set()
        t = self.time
        self._stats_date = [t.day, t.season_idx, t.year]
        self.day_report = None
        if not getattr(self, "_net_applying_world", False):
            self._dr = None      # (the LAN client's 1 Hz resync keeps the card it shows)

    # ================================================================ day report
    def _open_day_report(self):
        """Called by Game.update_sleep once the 'Sleeping...' banner ends."""
        if self.day_report is None or getattr(self, "net_mode", None) == "client":
            self.day_report = None
            return False
        self._dr = self.day_report
        self.day_report = None
        self._dr["t"] = 0.0
        self._dr["coin_t"] = 0.0
        self._dr["star_shown"] = 0
        self._dr_cache = {}
        self.state = "day_report"
        self.audio.play("bell")
        return True

    def _dr_ensure(self):
        if self._dr is None:                 # opened directly (tests / debug)
            self._dr = self._build_report()
            self._dr.update(t=0.0, coin_t=0.0, star_shown=0)
            self._dr_cache = {}
        return self._dr

    def _dr_done(self):
        return self._dr is not None and self._dr.get("t", 0) >= 2.4

    def _close_day_report(self):
        self.state = "play"
        self._dr = None
        self._dr_cache = {}
        self.audio.play("page")

    def _state_event_day_report(self, e):
        r = self._dr_ensure()
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self._close_day_report()
            elif e.key in (P1_KEYS.get("action"), P2_KEYS.get("action")):
                if self._dr_done():
                    self._close_day_report()
                else:
                    r["t"] = 2.4                 # first press skips the count-up
                    r["star_shown"] = r["stars"]
                    self.audio.play("ui_select")
        elif e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 1) == 1:
            if self._dr_done():
                self._close_day_report()
            else:
                r["t"] = 2.4
                r["star_shown"] = r["stars"]

    def _state_update_day_report(self, dt):
        r = self._dr_ensure()
        r["t"] = r.get("t", 0.0) + dt
        t = r["t"]
        if 0.7 < t < 1.9 and (r.get("sales") or r.get("gold_delta")):
            r["coin_t"] = r.get("coin_t", 0.0) - dt
            if r["coin_t"] <= 0:
                r["coin_t"] = 0.11
                self.audio.play("coin")
        want = min(r["stars"], max(0, int((t - 1.9) / 0.16) + 1)) if t >= 1.9 else 0
        while r.get("star_shown", 0) < want:
            r["star_shown"] = r.get("star_shown", 0) + 1
            self.audio.play("ui_toggle")
        if getattr(self, "net_mode", None) in ("host", "client") and t > 20:
            self._close_day_report()         # don't stall the LAN session forever

    def _dr_text(self, text, size, color, bold=True):
        key = (text, size, color, bold)
        s = self._dr_cache.get(key)
        if s is None:
            s = _font(size, bold).render(text, True, color)
            self._dr_cache[key] = s
        return s

    def _dr_backdrop(self):
        s = _SPR.get("dr_dim")
        if s is None:
            s = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            s.fill((34, 24, 44, 175))
            _SPR["dr_dim"] = s
        return s

    def _dr_card(self, r):
        """Static card body (paper, ribbon, headers) -- built once per report."""
        s = self._dr_cache.get("card")
        if s is not None:
            return s
        W, H, R = _DR_W, _DR_H, _DR_RIB
        # the surface has R px of headroom so the ribbon title can straddle
        # the card's top edge and still fade / slide in with the card
        s = pygame.Surface((W, H + R), pygame.SRCALPHA)
        pygame.draw.rect(s, (40, 20, 30, 90), (6, R + 10, W - 6, H - 10), border_radius=22)
        pygame.draw.rect(s, K.WOOD, (0, R, W - 6, H - 10), border_radius=22)
        pygame.draw.rect(s, K.WOOD_DK, (0, R, W - 6, H - 10), 2, border_radius=22)
        pygame.draw.rect(s, K.CREAM, (5, R + 5, W - 16, H - 20), border_radius=18)
        pygame.draw.rect(s, K.CREAM_HI, (20, R + 9, W - 46, 4), border_radius=2)   # sheen
        # stitched inner border (under the header, above the footer)
        for x in range(26, W - 30, 14):
            pygame.draw.line(s, K.WELL_LINE, (x, R + 62), (x + 6, R + 62), 2)
            pygame.draw.line(s, K.WELL_LINE, (x, R + H - 58), (x + 6, R + H - 58), 2)
        cx = (W - 6) // 2
        # subtitle: season + year in soft ink, flanked by two season-coloured leaves
        rc = _SEASON_COL.get(r["season"], (238, 170, 196))
        sf = _font(16)
        sub = f"{r['season']}  -  Year {r['year']}"
        K.blit_text(s, sf, sub, K.INK_SOFT, (cx, R + 44))
        half = sf.size(sub)[0] // 2 + 16
        for sx in (cx - half, cx + half):
            pygame.draw.circle(s, rc, (sx, R + 44), 5)
            pygame.draw.circle(s, tuple(max(0, c - 60) for c in rc), (sx, R + 44), 5, 1)
        # the shared parchment ribbon title straddling the top edge
        K.ribbon(s, K.font(28, True), f"End of Day {r['day']}", (cx, R + 2))
        # divider between the table and the right column
        pygame.draw.line(s, K.WELL_LINE, (_DR_DIV, R + 80), (_DR_DIV, R + H - 74), 2)
        self._dr_cache["card"] = s
        return s

    def _dr_row(self, i, key, v1, v2, item, w, cx1, cx2):
        """One table row (band, icon badge, label, both values) -- static, so
        it is built once per report and faded / slid in as a whole."""
        ck = ("row", i)
        s = self._dr_cache.get(ck)
        if s is not None:
            return s
        h = 34
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        if i % 2 == 0:
            pygame.draw.rect(s, (*K.WELL, 190), s.get_rect(), border_radius=8)
        cy = h // 2
        try:
            ic = _stat_icon(key, item)
            # tan badge so light items (egg, milk, mayo) stay readable on cream
            cc = (8 + ic.get_width() // 2, cy)
            pygame.draw.circle(s, (226, 210, 186), cc, 15)
            pygame.draw.circle(s, (180, 150, 122), cc, 15, 1)
            s.blit(ic, (8, cy - ic.get_height() // 2))
        except Exception:
            pass
        lf = _font(17)
        K.blit_text(s, lf, K.ellipsize(lf, _ROW[key][0], cx1 - 44 - 30), K.INK, (44, cy), "left")
        fmt = (lambda v: f"{v}g") if key == "gold_sales" else str
        for vx, v, col in ((cx1, v1, K.P_COL[0]), (cx2, v2, K.P_COL[1])):
            K.blit_text(s, _font(18), fmt(v) if v else "-",
                        tuple(max(0, c - 30) for c in col) if v else K.INK_FAINT, (vx, cy))
        self._dr_cache[ck] = s
        return s

    def _state_draw_day_report(self):
        r = self._dr_ensure()
        scr = self.screen
        t = r.get("t", 0.0)
        scr.blit(self._dr_backdrop(), (0, 0))
        card = self._dr_card(r)
        # slide + settle in
        k = min(1.0, t / 0.35)
        ease = 1 - (1 - k) ** 3
        cx0 = SCREEN_W // 2 - (card.get_width() - 6) // 2
        # centred, but never so high that the two hotbar rows peek above it
        top = max(SCREEN_H // 2 - _DR_H // 2, _DR_HUD_CLEAR) + int((1 - ease) * 60)
        card.set_alpha(int(255 * min(1.0, k * 1.4)))
        scr.blit(card, (cx0, top - _DR_RIB))
        cy0 = top - _DR_SHIFT                    # origin of the content offsets below
        if k < 1.0:
            return
        H = _DR_H + _DR_SHIFT                    # footer offsets are from cy0
        # names
        n1, n2 = r["names"][0], r["names"][1]
        a = self._dr_text(n1, 20, K.P_COL[0])
        b = self._dr_text(n2, 20, K.P_COL[1])
        mid = cx0 + 238
        scr.blit(a, (mid - 22 - a.get_width(), cy0 + 100))
        hs = _misc_icon("heart")
        scr.blit(hs, (mid - 14, cy0 + 97))
        scr.blit(b, (mid + 22, cy0 + 100))
        # the two farmers themselves, bobbing happily beside their names
        for i, px in ((0, mid - 22 - a.get_width() - 46), (1, mid + 26 + b.get_width())):
            por = self._dr_cache.get(("portrait", i))
            if por is None:
                try:
                    fr = self.players[i].frames["down"][0]
                    por = pygame.transform.scale(fr, (fr.get_width() * 5 // 6,
                                                      fr.get_height() * 5 // 6))
                except Exception:
                    por = False
                self._dr_cache[("portrait", i)] = por
            if por:
                bob = int(math.sin(t * 3.0 + i * 1.7) * 2)
                scr.blit(por, (px, cy0 + 110 - por.get_height() // 2 + bob))
        # the table (left column: cx0+24 .. divider)
        tx0, tx1 = cx0 + 24, cx0 + _DR_DIV - 12
        vx1, vx2 = cx0 + 342, cx0 + 420              # value column centres
        rows = r["rows"]
        y = cy0 + 152
        if rows:                                     # column headers, centred on their values
            K.blit_text(scr, _font(14), "P1", K.P_COL[0], (vx1, cy0 + 140))
            K.blit_text(scr, _font(14), "P2", K.P_COL[1], (vx2, cy0 + 140))
        else:                                        # a quiet day: one centred note
            ccx = (tx0 + tx1) // 2
            po = r.get("passed_out")
            lines = K.wrap(_font(16, False), "Only 55% energy - sleep in bed before 2 AM."
                           if po else "Just sweet dreams.", tx1 - tx0 - 40)
            z = _bubble_scaled("zzz", 1.3)
            top = y + 60
            scr.blit(z, (ccx - z.get_width() // 2, top))
            K.blit_text(scr, _font(18), "You passed out..." if po else "Nothing to report today",
                        K.INK, (ccx, top + z.get_height() + 22))
            for j, ln in enumerate(lines):
                K.blit_text(scr, _font(16, False), ln, K.INK_SOFT,
                            (ccx, top + z.get_height() + 50 + j * 22))
        for i, (key, v1, v2, item) in enumerate(rows):
            appear = 0.35 + i * 0.08
            if t < appear:
                break
            kk = min(1.0, (t - appear) / 0.18)
            ry = y + i * 36
            row = self._dr_row(i, key, v1, v2, item, tx1 - tx0, vx1 - tx0, vx2 - tx0)
            # fade in with a short slide that stays inside the card's padding
            xo = int((1 - kk) * -10)
            if kk < 1.0:
                row.set_alpha(int(255 * kk))
                scr.blit(row, (tx0 + xo, ry - 3))
                row.set_alpha(255)
            else:
                scr.blit(row, (tx0, ry - 3))
        # ---- right column: gold, team extras, stars, forecast ----
        rx = cx0 + 498
        scr.blit(self._dr_text("GOLD TODAY", 15, K.INK_SOFT), (rx, cy0 + 104))
        prog = max(0.0, min(1.0, (t - 0.7) / 1.1))
        prog = 1 - (1 - prog) ** 2
        delta = r["gold_delta"]
        shown = int(round(delta * prog))
        col = (84, 150, 80) if delta >= 0 else (200, 90, 90)
        scr.blit(_misc_icon("coin"), (rx, cy0 + 128))
        g = _font(30).render(f"{shown:+,}g", True, col)
        pop = 1.0 + (0.12 * math.sin(min(1.0, (t - 1.8) / 0.25) * math.pi) if 1.8 < t < 2.05 else 0)
        if pop != 1.0:
            g = pygame.transform.smoothscale(g, (int(g.get_width() * pop), int(g.get_height() * pop)))
        scr.blit(g, (rx + 34, cy0 + 126))
        if r.get("record") and t >= 1.85:
            tag = _SPR.get("dr_record")
            if tag is None:
                tf = _font(12)
                tag = pygame.Surface((tf.size("NEW BEST!")[0] + 16, 20), pygame.SRCALPHA)
                pygame.draw.rect(tag, (222, 98, 132), tag.get_rect(), border_radius=10)
                K.blit_text(tag, tf, "NEW BEST!", (255, 255, 255), tag.get_rect().center)
                tag = pygame.transform.rotate(tag, 8)
                _SPR["dr_record"] = tag
            k = min(1.0, (t - 1.85) / 0.18)
            sc = 1.6 - 0.6 * k
            tg = pygame.transform.smoothscale(tag, (int(tag.get_width() * sc),
                                                    int(tag.get_height() * sc))) if k < 1 else tag
            scr.blit(tg, (rx + 150 - tg.get_width() // 2, cy0 + 110 - tg.get_height() // 2))
        scr.blit(self._dr_text(f"Purse: {r['gold']:,}g", 15, K.INK_SOFT, False),
                 (rx + 2, cy0 + 164))
        yy = cy0 + 190
        if r.get("together"):
            d = r["together"]
            scr.blit(self._dr_text(f"Together: {d} day{'s' if d != 1 else ''}", 15,
                                   (196, 88, 128), False), (rx + 2, yy))
            yy += 20
        if r.get("deepest"):
            scr.blit(self._dr_text(f"Deepest mine: Lv {r['deepest']}", 15, K.INK, False),
                     (rx + 2, yy))
            yy += 20
        if r.get("love"):
            scr.blit(self._dr_text(f"Love boosts today: {r['love']}", 15, (196, 88, 128),
                                   False), (rx + 2, yy))
            yy += 20
        # stars
        sy = cy0 + 250
        for i in range(5):
            key = ("dr_star", i < r.get("star_shown", 0))
            st = _SPR.get(key)
            if st is None:
                st = pygame.Surface((40, 40), pygame.SRCALPHA)
                if key[1]:
                    _star(st, 20, 21, 18, (214, 150, 40))
                    _star(st, 20, 20, 17, (252, 206, 84))
                    _star(st, 18, 18, 7, (255, 240, 180))
                else:
                    _star(st, 20, 21, 17, (226, 212, 192))
                _SPR[key] = st
            if i < r.get("star_shown", 0):
                since = t - (1.9 + i * 0.16)
                sc = 1.0 + max(0.0, 0.5 * (1 - since / 0.2)) if since < 0.2 else 1.0
                if sc != 1.0:
                    st = pygame.transform.smoothscale(st, (int(40 * sc), int(40 * sc)))
            scr.blit(st, (rx + i * 44 + 20 - st.get_width() // 2, sy + 20 - st.get_height() // 2))
        if t >= 1.9:
            flav = r["flavour"]
            if r.get("passed_out") and not rows:      # the left column already says it
                flav = "Tomorrow is a fresh start."
            lines = K.wrap(_font(15, False), flav, cx0 + _DR_W - 20 - rx)
            for j, ln in enumerate(lines[:3]):
                scr.blit(self._dr_text(ln, 15, K.INK_SOFT, False), (rx + 2, sy + 50 + j * 19))
        # forecast
        fy = cy0 + 364
        box = self._dr_cache.get("fbox")
        if box is None:
            box = pygame.Surface((226, 68), pygame.SRCALPHA)
            pygame.draw.rect(box, (226, 238, 250), box.get_rect(), border_radius=12)
            pygame.draw.rect(box, (170, 196, 226), box.get_rect(), 2, border_radius=12)
            self._dr_cache["fbox"] = box
        scr.blit(box, (rx - 4, fy))
        try:
            from .weather_system import weather_icon
            wi = weather_icon(r["forecast"], 52)
            scr.blit(wi, (rx + 4, fy + 34 - wi.get_height() // 2))
        except Exception:
            pass
        nd, ns = r["day"] + 1, r["season"]
        if nd > DAYS_PER_SEASON:
            nd, ns = 1, SEASONS[(SEASONS.index(ns) + 1) % len(SEASONS)] if ns in SEASONS else ns
        K.blit_text(scr, _font(13), f"Forecast: {ns} {nd}", (84, 104, 136), (rx + 64, fy + 22), "left")
        K.blit_text(scr, _font(20), weather.LABEL.get(r["forecast"], str(r["forecast"]).title()),
                    (60, 86, 130), (rx + 64, fy + 45), "left")
        if r.get("festival"):
            K.blit_text(scr, _font(15), f"Today: {r['festival']}!", (196, 88, 128),
                        (rx + 109, fy + 84))
        # footer
        from ..ui import key_label
        hint = (f"{key_label(P1_KEYS['action'])} / {key_label(P2_KEYS['action'])}"
                f"  -  {'continue' if self._dr_done() else 'skip'}")
        K.continue_hint(scr, (cx0 + (_DR_W - 6) // 2, cy0 + H - 36), t, text=hint)

    # ================================================================ journal
    def _journal_tab_90_coop_stats(self):
        return {"title": "Stats", "draw": self._draw_stats_tab}

    def _draw_stats_tab(self, surf, rect):
        """Cream journal page: lifetime counters in two balanced columns of
        banded rows, a centred title and a 'today so far' strip."""
        rect = pygame.Rect(rect)
        life = self.stats_life
        cx = rect.centerx
        K.blit_text(surf, K.font(20, True), "Lifetime together", K.INK, (cx, rect.y + 12))
        names = " & ".join(p.name for p in self.players)
        K.blit_text(surf, K.font(15), f"{names}  -  {life.get('days', 0)} days on the farm",
                    K.INK_SOFT, (cx, rect.y + 38))
        K.divider(surf, cx, rect.y + 58, min(260, rect.w // 3))
        extra = [("@deepest", "Deepest mine level", life.get("deepest", 0)),
                 ("@love", "Love boosts", life.get("love", 0)),
                 ("@best", "Best day's earnings", f"{life.get('best_gold_day', 0)}g")]
        if life.get("mist_runs"):
            extra += [("@mist", "Mist City runs", life.get("mist_runs", 0)),
                      ("@mistz", "Zombies cleared", life.get("mist_zombies", 0)),
                      ("@mistv", "Mist City victories", life.get("mist_victories", 0))]
        items = [(k, _ROW[k][0], life.get(k, 0)) for k in STAT_KEYS] + extra
        cols = 2 if rect.w >= 560 else 1
        gap = 36
        cw = (rect.w - gap * (cols - 1)) // cols
        top = rect.y + 74
        strip_h = 34
        avail = rect.bottom - strip_h - 12 - top
        want = -(-len(items) // cols)
        rh = max(26, min(36, avail // max(1, want)))
        per_col = max(1, min(avail // rh, want))
        lab_f, val_f = K.font(15), K.font(17, True)
        band = pygame.Surface((cw, rh - 4), pygame.SRCALPHA)
        pygame.draw.rect(band, (*K.WELL, 200), band.get_rect(), border_radius=8)
        for i, (k, label, val) in enumerate(items):
            c, rr = divmod(i, per_col)
            if c >= cols:
                break
            x = rect.x + c * (cw + gap)
            y = top + rr * rh
            cy = y + (rh - 4) // 2
            if rr % 2 == 0:
                surf.blit(band, (x, y))
            if k == "@deepest":
                ic = _stat_icon("rocks", None)
                try:
                    from .. import assets
                    ic = assets.tool_icon("pickaxe")
                except Exception:
                    pass
            elif k == "@love":
                ic = _misc_icon("heart")
            elif k == "@best":
                ic = _misc_icon("coin")
            elif k in ("@mist", "@mistz", "@mistv"):
                ic = _stat_icon("monsters", None)
            else:
                ic = _stat_icon(k, None)
            surf.blit(ic, (x + 8, cy - ic.get_height() // 2))
            K.blit_text(surf, lab_f, label, K.INK, (x + 46, cy), "left")
            if k == "gold_sales":
                val = f"{val:,}g" if isinstance(val, int) else f"{val}g"
            elif isinstance(val, int):
                val = f"{val:,}"
            K.blit_text(surf, val_f, str(val), K.GOLD_TXT, (x + cw - 14, cy), "right")
        # live "today so far" strip along the bottom
        n = self.stats_today.get("n", {})

        def tot(k):
            v = n.get(k, [0, 0])
            return v[0] + v[1]
        today = (f"Today so far:  crops {tot('crops')}  |  fish {tot('fish')}  |  "
                 f"monsters {tot('monsters')}  |  sales {tot('gold_sales')}g  |  "
                 f"gifts {tot('gifts') + tot('partner_gifts')}")
        box = pygame.Rect(rect.x, rect.bottom - strip_h, rect.w, strip_h)
        K.well(surf, box)
        f = K.fit_font(today, box.w - 24, (15, 14, 13, 12))
        K.blit_text(surf, f, today, K.INK, box.center)
