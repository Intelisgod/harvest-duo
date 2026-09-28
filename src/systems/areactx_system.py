"""Per-player areas ("independent maps") for online co-op.

Owner: Core. In LAN host mode each farmer lives in their own area, like any
online game: Player 1 can be down the mine while Player 2 fishes at the beach.
Local co-op (one screen, one keyboard) keeps both farmers in the same area.

HOW IT WORKS
------------
``self.p_area[i]`` is the area player ``i`` stands in. ``self.world.current``
stays "the area being simulated right now": between frames it is the VIEW
area (Player 1's on the host), and ``area_ctx(name)`` temporarily makes another
area current. Each occupied area keeps its own copy of the attributes in
``AREA_LOCAL`` (monsters, villagers, critters, bombs, fish spots ...), swapped
in and out on every switch, so the ~150 places that read ``self.world.area`` /
``self.monsters`` keep working unchanged.

Inside a context, players standing in a DIFFERENT area are "parked" far off
the map (restored on exit), so every proximity / tile check in every domain
naturally ignores them. A non-view context also swaps the screen-only bits
(particles, popups, shake, sounds, camera) for throwaway sinks, and relays
log lines / toasts to the online partner instead of the host's screen.

Rules for domain code:
  * ``_on_update_<x>``      runs ONCE per frame, in the view area (global
                            timers, HUD, weather, achievements).
  * ``_on_area_update_<x>`` runs once per OCCUPIED area, inside its context
                            (monsters, critters, hazards, per-area fx). Loop
                            over ``self.players_here()`` for per-player work.
  * Never call ``_save`` while players are parked -- ``_save`` unparks itself,
    but new save paths should go through it.
"""
from contextlib import contextmanager

from ..settings import TILE, AREA_FARM, AREA_HOME, AREA_MINE

# attributes that belong to ONE area (default factory for a fresh context)
AREA_LOCAL = {
    "monsters": list, "npcs": list, "beach_critters": list,
    "_cb_bombs": list, "_cb_nums": list, "_cb_boss_seen": lambda: None,
    "_cb_area_t": float, "fish_spots": list, "fish_chests": list,
    "forage_pops": list, "_story_spot_cache": dict, "_story_hour": lambda: None,
    "_story_board_hint_t": lambda: None, "_story_flag_t": float,
    "_spot_fx_t": float, "_farm_heart_t": float,
}
# screen-only numbers a non-view context must not disturb on the host screen
_VIEW_NUMBERS = ("shake", "hurt_flash", "fade", "_anniv_hint", "_area_card")
PARK = -100000.0             # far outside every map: tile() is WALL out there


class _Sink:
    """Swallows calls (sounds, particle spawns) but still answers attribute
    reads from the real object, e.g. ``audio.sfx``."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        v = getattr(self._real, name)
        return (lambda *a, **k: None) if callable(v) else v


class _PartSink(_Sink):
    """Particle system stand-in: spawns go nowhere, list reads stay valid."""

    def __init__(self, real):
        super().__init__(real)
        self.items = []


class _UIRelay:
    """ui stand-in for the partner's area: log lines go to the partner."""

    def __init__(self, real, game):
        self._real, self._game = real, game

    def log(self, text, *a, **k):
        self._game._net_toast(str(text))

    def __getattr__(self, name):
        return getattr(self._real, name)


class AreaCtxMixin:
    # ------------------------------------------------------------ state
    def _on_reset_areactx(self):
        cur = self.world.current
        self.p_area = [cur, cur]
        self._ctx_store = {}          # area -> {attr: value} for NON-current areas
        self._ctx_parked = {}         # player index -> (x, y) while parked
        self._ctx_view_saved = None   # screen-only values while a sink is active
        self._ctx_warped = False
        self._ctx_depth = 0           # >0 while inside area_ctx
        self._sleep_pending = False
        self._sleep_ready = None      # index of the farmer waiting in bed
        from ..camera import Camera
        self._cam_p2 = Camera()       # host-side camera that follows Player 2

    def _on_save_areactx(self):
        return {"p_area": list(self.p_area)}

    def _on_load_areactx(self, d):
        cur = self.world.current
        pa = d.get("p_area")
        self._ctx_store = {}
        self._ctx_parked = {}
        self.p_area = [cur, cur]
        if (self.net_mode == "client" and isinstance(pa, list) and len(pa) == 2
                and all(a in self.world.areas for a in pa)):
            self.p_area = list(pa)    # the host's view of who is where
        elif isinstance(pa, list) and len(pa) == 2 and pa[1] != cur:
            self._regroup_p2()        # P2's saved spot was in another area

    # ------------------------------------------------------------ queries
    def independent(self):
        """True when the farmers roam separately (LAN host)."""
        return self.net_mode == "host"

    def view_area(self):
        return self.p_area[0] if self.independent() else self.world.current

    def players_here(self):
        """Players standing in the area being simulated (unparked)."""
        return [p for i, p in enumerate(self.players) if i not in self._ctx_parked]

    def player_here(self, i):
        return i not in self._ctx_parked

    def apart(self):
        return self.p_area[0] != self.p_area[1]

    def partner_online(self):
        """Host: is Player 2's machine connected right now?"""
        net = getattr(self, "net", None)
        return bool(net and getattr(net, "connected", False))

    def together_needed(self, what):
        """Online, a two-player activity asks for both farmers in one place.
        Returns True (and tells both) when the partner is elsewhere; an
        offline partner is simply brought along."""
        if not self.independent() or not self.apart():
            return False
        if not self.partner_online():
            self._regroup_p2()
            return False
        msg = f"{what} needs you both - meet up with your partner first!"
        self._real_ui().log(msg)
        self._net_toast(msg)
        return True

    # ------------------------------------------------------------ switching
    def _ctx_switch(self, name):
        """Make ``name`` the current area: bank the current area's local
        attributes, then load (or freshly spawn) ``name``'s."""
        cur = self.world.current
        if name == cur:
            return
        self._ctx_store[cur] = {a: getattr(self, a) for a in AREA_LOCAL if hasattr(self, a)}
        wl = getattr(self, "wildlife", None)
        if wl is not None:
            self._ctx_store[cur]["wildlife"] = wl
        self._ctx_sink(name != self.view_area())
        self.world.current = name
        saved = self._ctx_store.pop(name, None)
        if saved is not None:
            for a, v in saved.items():
                setattr(self, a, v)
            return
        for a, make in AREA_LOCAL.items():
            setattr(self, a, make())
        if wl is not None:
            self.wildlife = type(wl)()
        self._spawn_area_entities()

    def _ctx_sink(self, on):
        """Swap the screen-only bits for sinks (a partner's area) or back."""
        if on and self._ctx_view_saved is None:
            keep = {k: getattr(self, k, None) for k in _VIEW_NUMBERS}
            keep.update(parts=self.parts, popups=self.popups, audio=self.audio,
                        ui=self.ui, cam=self.cam)
            self._ctx_view_saved = keep
            self.parts = _PartSink(self.parts)
            self.popups = []
            self.audio = _Sink(self.audio)
            self.ui = _UIRelay(self.ui, self)
            self.cam = self._cam_p2
            self.toast = self._ctx_relay_toast
        elif not on and self._ctx_view_saved is not None:
            keep, self._ctx_view_saved = self._ctx_view_saved, None
            for k, v in keep.items():
                setattr(self, k, v)
            self.__dict__.pop("toast", None)

    def _ctx_relay_toast(self, title, subtitle="", *a, **k):
        self._net_toast(f"{title} - {subtitle}" if subtitle else str(title))

    def _ctx_park(self, active):
        for i in range(len(self.players)):
            if i not in active:
                self._ctx_park_one(i)

    def _ctx_park_one(self, i):
        if i not in self._ctx_parked:
            p = self.players[i]
            self._ctx_parked[i] = (p.x, p.y)
            p.x = p.y = PARK

    def _ctx_unpark(self):
        for i, (x, y) in self._ctx_parked.items():
            self.players[i].x, self.players[i].y = x, y
        self._ctx_parked = {}

    @contextmanager
    def area_ctx(self, name, active=None):
        """Simulate ``name`` for the block: its entities are current and the
        players NOT in ``active`` (default: everyone standing elsewhere) are
        parked. Always returns to the view area afterwards."""
        if not self.independent():
            yield
            return
        outer_parked = dict(self._ctx_parked)
        outer_cur = self.world.current
        self._ctx_unpark()
        if name not in self.world.areas:
            name = self.view_area()
        v0 = self.view_area()
        self._ctx_depth += 1
        self._ctx_switch(name)
        if active is None:
            active = [i for i in range(len(self.players)) if self.p_area[i] == name]
        self._ctx_park(active)
        try:
            yield
        finally:
            self._ctx_depth -= 1
            self._ctx_unpark()
            if self._ctx_depth > 0:
                # nested: hand the caller its own area + parking back (parking
                # the farmers where they stand NOW, so a move inside sticks)
                self._ctx_switch(outer_cur if outer_cur in self.p_area else self.view_area())
                for i in outer_parked:
                    if self.p_area[i] != self.world.current:
                        self._ctx_park_one(i)
            else:
                self._ctx_switch(self.view_area())
                self._ctx_gc()
                if self.view_area() != v0:
                    self._view_arrived()

    @contextmanager
    def _unparked(self):
        """Real positions for the block (saving); re-parks afterwards."""
        parked = list(self._ctx_parked)
        self._ctx_unpark()
        try:
            yield
        finally:
            for i in parked:
                self._ctx_park_one(i)

    @contextmanager
    def _draw_parked(self):
        """While drawing, hide farmers who are in another area."""
        cur = self.world.current
        hide = [i for i in range(len(self.players))
                if self.p_area[i] != cur and i not in self._ctx_parked]
        saved = {i: (self.players[i].x, self.players[i].y) for i in hide}
        for i in hide:
            self.players[i].x = self.players[i].y = PARK
        try:
            yield
        finally:
            for i, (x, y) in saved.items():
                self.players[i].x, self.players[i].y = x, y

    def _ctx_gc(self):
        """Forget areas nobody stands in (they respawn fresh on entry)."""
        live = set(self.p_area)
        for a in list(self._ctx_store):
            if a not in live:
                del self._ctx_store[a]

    def _ctx_drop_others(self):
        """New day: every non-view area rebuilds on its next frame."""
        self._ctx_store = {}

    # ------------------------------------------------------------ warps
    def warp_player(self, i, target, spawn, beside=None):
        """Move ONE farmer to ``target`` (independent mode)."""
        p = self.players[i]
        sx, sy = spawn
        off = 1 if beside else 0
        p.x = (sx + off) * TILE + TILE / 2
        p.y = sy * TILE + TILE / 2
        self._ctx_parked.pop(i, None)
        self.p_area[i] = target
        self._ctx_warped = True
        if i == 0:
            self._view_moved(target)
        else:
            sunk = self._ctx_view_saved is not None
            if not sunk:
                self._ctx_sink(True)        # P2's area card / sounds never hit the host screen
            try:
                self.emit("warp", area=target)
            finally:
                if not sunk:
                    self._ctx_sink(False)
        self._ctx_gc()
        if self._ctx_depth == 0 and i == 0:
            self._ctx_switch(self.view_area())      # at rest: follow P1 right away
            self._view_arrived()

    def _view_moved(self, target):
        """Player 1 changed area: the host screen follows (iris, music, card)."""
        if getattr(self, "audio", None):
            real = (self._ctx_view_saved or {}).get("audio", self.audio)
            real.stop_song()
            real.play("warp")
            real.play_area(target)
        keep = self._ctx_view_saved
        parts = keep["parts"] if keep else self.parts
        parts.items.clear()
        (keep["popups"] if keep else self.popups).clear()
        if keep:
            keep["fade"], keep["_anniv_hint"] = 1.0, None
        else:
            self.fade, self._anniv_hint = 1.0, None

    def _view_arrived(self):
        """After a view warp, settle the host screen on the new area."""
        area = self.world.area
        setp = getattr(self.parts, "set_projection", None)
        if setp:
            setp(self._iso_spawn if area.name == AREA_HOME else None)
        self._update_camera(area)
        self.emit("warp", area=self.world.current)

    def _regroup_p2(self):
        """Bring Player 2 next to Player 1 (local co-op / after hosting)."""
        p1, p2 = self.players
        p2.x, p2.y = p1.x + TILE, p1.y
        area = self.world.area
        if area.is_solid(int(p2.x // TILE), int(p2.y // TILE)):
            p2.x = p1.x
        self.p_area = [self.world.current, self.world.current]
        self._ctx_store = {}

    # ------------------------------------------------------------ sleep
    def request_sleep(self, idx):
        """A farmer confirmed the bed. Online, both must be home: the day
        only ends once the partner is in the house too."""
        if not self.independent():
            self.do_sleep()
            return
        other = 1 - idx
        if not self.partner_online() and self.p_area[1] != self.p_area[0]:
            self._regroup_p2()            # Player 2 is offline: they wake up at home too
        if self.p_area[other] != AREA_HOME:
            self._sleep_ready = idx
            me, you = self.players[idx].name, self.players[other].name
            waiting = f"{me} is in bed - waiting for {you} to come home."
            nudge = f"{me} is waiting in bed - come home and sleep to end the day."
            if idx == 0:
                self._real_ui().log(waiting)
                self._net_toast(nudge)
            else:
                self._net_toast(waiting)
                self._real_ui().log(nudge)
            return
        self._sleep_pending = True
        if self.state != "play":
            # Player 1 has a screen open: the day ends as soon as it closes
            self._net_toast("Player 1 is busy - you'll both sleep as soon as they're done.")
            self._real_ui().log(f"{self.players[idx].name} is ready for bed - "
                                "close this screen to end the day.")

    def _real_ui(self):
        return (self._ctx_view_saved or {}).get("ui", self.ui)

    def _ctx_rest_tasks(self):
        """Work that must run with nobody parked (sleep saves the game)."""
        if self._sleep_pending and any(a != AREA_HOME for a in self.p_area) \
                and self.partner_online():
            self._sleep_pending = False   # someone walked out again before it began
            self._net_toast("Sleep cancelled - you both need to be home.")
            self._real_ui().log("Sleep cancelled - you both need to be home.")
        if self._sleep_pending and not self._ctx_parked and self.state == "play":
            self._sleep_pending = False
            self._sleep_ready = None
            self.do_sleep()
            self._net_toast("Sleeping... a new day begins.")
        if self._sleep_ready is not None and self.p_area[self._sleep_ready] != AREA_HOME:
            self._sleep_ready = None   # the sleepy one wandered off again

    # ------------------------------------------------------------ partner HUD
    def area_label(self, name):
        if name == AREA_MINE:
            return f"Mine Lv.{self.world.mine_level}"
        return str(name).replace("_", " ").title()

    def _draw_hud_areactx(self):
        """A small tag over the partner's panel: where they are right now."""
        if self.net_mode not in ("host", "client") or not self.apart():
            return
        if self.state not in ("play", "shop", "dialogue", "journal"):
            return
        import pygame
        from .. import ui_kit as K
        from ..settings import SCREEN_W, SCREEN_H
        me = 0 if self.net_mode == "host" else 1
        other = 1 - me
        txt = f"{self.players[other].name}: {self.area_label(self.p_area[other])}"
        fnt = K.font(14, True)
        w = min(260, fnt.size(txt)[0] + 30)
        r = pygame.Rect(0, 0, w, 26)
        if other == 1:
            r.bottomright = (SCREEN_W - 8, SCREEN_H - 138)
        else:
            r.bottomleft = (8, SCREEN_H - 138)
        K.pill(self.screen, r, (44, 32, 52), K.P_COL[other], alpha=225)
        pygame.draw.circle(self.screen, K.P_COL[other], (r.x + 13, r.centery), 4)
        K.blit_text(self.screen, fnt, K.ellipsize(fnt, txt, w - 30), (250, 238, 212),
                    (r.x + 22, r.centery), align="left")
        f = getattr(self, "hud_reserve", None)
        if f:
            f(r)
